"""
main.py — FastAPI 백엔드: 멀티에이전트 동적 토론 엔진 + SSE 스트리밍
- SQLite 세션 영속화
- 스마트 비용 최적화 (라운드별 모델 선택)
- 에러 핸들링 + retry
- 사용량 로깅
"""

import json
import asyncio
import os
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIConnectionError
from dotenv import load_dotenv

from agents import (
    AGENTS,
    INITIAL_PROMPT,
    DEBATE_PROMPT,
    JUDGE_PROMPT,
    FEEDBACK_PROMPT,
    CONVERGENCE_CHECK_SYSTEM,
)
from database import init_db, save_session, load_session, log_usage, check_and_increment_limit

load_dotenv()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield

app = FastAPI(title="Debate Arena API", version="3.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DEBATE_AGENTS = ["optimist", "critic", "realist", "businessman", "veteran"]
MAX_DEBATE_ROUNDS = 6
MIN_DEBATE_ROUNDS = 4

# 비용 최적화: 초기·중간 라운드는 mini, 심화·심판은 4o
MODEL_BY_ROUND = {
    "initial": ("gpt-4o-mini", 350),
    "debate_early": ("gpt-4o-mini", 400),
    "debate_deep": ("gpt-4o", 500),
    "judge": ("gpt-4o", 900),
    "convergence": ("gpt-4o-mini", 30),
}



class DebateRequest(BaseModel):
    topic: str
    session_id: str | None = None
    feedback: str | None = None


class DebateHistory:
    AGENT_NAMES = {
        "optimist": "낙관론자",
        "critic": "비판론자",
        "realist": "현실주의자",
        "businessman": "사업가",
        "veteran": "개발 20년차",
    }

    def __init__(self):
        self.topic: str = ""
        self.rounds: list[dict] = []  # {"title": str, "responses": {agent_id: text}}

    def add_round(self, responses: dict[str, str], title: str):
        self.rounds.append({"title": title, "responses": responses})

    def format_transcript(self) -> str:
        lines = []
        for i, round_data in enumerate(self.rounds, 1):
            lines.append(f"[Round {i} — {round_data['title']}]")
            for agent_id in DEBATE_AGENTS:
                name = self.AGENT_NAMES[agent_id]
                text = round_data["responses"].get(agent_id, "")
                if text:
                    lines.append(f"{name}: {text}")
            lines.append("")
        return "\n".join(lines)

    def to_serializable(self) -> list:
        return self.rounds

    @classmethod
    def from_serializable(cls, rounds: list) -> "DebateHistory":
        h = cls()
        h.rounds = rounds
        return h


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def call_api(
    agent_id: str,
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_tokens: int,
    retries: int = 3,
) -> tuple[str, str]:
    """API 호출 with exponential backoff retry"""
    for attempt in range(retries):
        try:
            full_text = ""
            stream = await client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.85,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
            )
            async for chunk in stream:
                text = chunk.choices[0].delta.content or ""
                full_text += text
            return agent_id, full_text

        except (RateLimitError, APITimeoutError, APIConnectionError) as e:
            if attempt == retries - 1:
                return agent_id, f"[응답 실패: {type(e).__name__}]"
            wait = 2 ** attempt
            await asyncio.sleep(wait)

        except Exception as e:
            return agent_id, f"[오류: {str(e)[:50]}]"

    return agent_id, "[응답 실패]"


async def check_convergence(topic: str, transcript: str) -> bool:
    try:
        model, _ = MODEL_BY_ROUND["convergence"][0], MODEL_BY_ROUND["convergence"][1]
        response = await client.chat.completions.create(
            model=MODEL_BY_ROUND["convergence"][0],
            max_tokens=MODEL_BY_ROUND["convergence"][1],
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": CONVERGENCE_CHECK_SYSTEM},
                {"role": "user", "content": f"주제: {topic}\n\n{transcript}"},
            ],
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("converged", False)
    except Exception:
        return False


async def emit_agents(
    round_num: int,
    agent_order: list[str],
    prompt: str,
    history: DebateHistory,
    round_title: str,
    model_key: str,
    session_id: str,
) -> AsyncGenerator[str, None]:
    model, max_tokens = MODEL_BY_ROUND[model_key]

    for agent_id in agent_order:
        yield sse_event("agent_thinking", {
            "agent_id": agent_id,
            "agent_name": AGENTS[agent_id]["name"],
            "round": round_num,
        })

    tasks = [
        call_api(agent_id, AGENTS[agent_id]["system_prompt"], prompt, model, max_tokens)
        for agent_id in agent_order
    ]
    results = await asyncio.gather(*tasks)

    # 사용량 로깅
    await log_usage(session_id, round_num, len(agent_order), model, datetime.now().isoformat())

    round_responses = {agent_id: text for agent_id, text in results}

    for agent_id in agent_order:
        full_response = round_responses[agent_id]
        yield sse_event("agent_start", {
            "agent_id": agent_id,
            "agent_name": AGENTS[agent_id]["name"],
            "round": round_num,
        })
        await asyncio.sleep(0.05)
        yield sse_event("agent_chunk", {"agent_id": agent_id, "chunk": full_response})
        await asyncio.sleep(0.05)
        yield sse_event("agent_end", {
            "agent_id": agent_id,
            "full_text": full_response,
            "round": round_num,
        })
        await asyncio.sleep(0.3)

    history.add_round(round_responses, round_title)


async def run_debate(
    topic: str,
    session_id: str,
    history: DebateHistory,
    feedback: str | None = None,
) -> AsyncGenerator[str, None]:

    history.topic = topic
    is_feedback = feedback is not None

    yield sse_event("debate_start", {
        "topic": topic,
        "session_id": session_id,
        "is_feedback": is_feedback,
        "timestamp": datetime.now().isoformat(),
    })

    round_num = len(history.rounds) + 1

    if is_feedback:
        transcript = history.format_transcript()
        feedback_prompt = FEEDBACK_PROMPT.format(
            topic=topic, transcript=transcript, feedback=feedback
        )
        title = "피드백 반영 토론"
        yield sse_event("round_start", {"round": round_num, "title": title})
        async for event in emit_agents(
            round_num, DEBATE_AGENTS, feedback_prompt, history, title, "debate_deep", session_id
        ):
            yield event
        yield sse_event("round_end", {"round": round_num})
        round_num += 1

        transcript = history.format_transcript()
        debate_prompt = DEBATE_PROMPT.format(topic=topic, transcript=transcript)
        title2 = "심화 논의"
        yield sse_event("round_start", {"round": round_num, "title": title2})
        agent_order = ["critic", "veteran", "optimist", "businessman", "realist"]
        async for event in emit_agents(
            round_num, agent_order, debate_prompt, history, title2, "debate_deep", session_id
        ):
            yield event
        yield sse_event("round_end", {"round": round_num})
        round_num += 1

    else:
        # Round 1: 초기 의견 (mini로 비용 절감)
        title = "초기 의견 제시"
        yield sse_event("round_start", {"round": round_num, "title": title})
        initial_prompt = INITIAL_PROMPT.format(topic=topic)
        async for event in emit_agents(
            round_num, DEBATE_AGENTS, initial_prompt, history, title, "initial", session_id
        ):
            yield event
        yield sse_event("round_end", {"round": round_num})
        round_num += 1

        # 동적 토론 라운드
        debate_round = 2
        while debate_round <= MAX_DEBATE_ROUNDS:
            transcript = history.format_transcript()

            if debate_round >= MIN_DEBATE_ROUNDS:
                converged = await check_convergence(topic, transcript)
                if converged:
                    yield sse_event("convergence_reached", {"round": round_num})
                    break

            round_title = f"심화 토론 {debate_round - 1}라운드"
            yield sse_event("round_start", {"round": round_num, "title": round_title})

            if debate_round % 2 == 0:
                agent_order = list(reversed(DEBATE_AGENTS))
            else:
                agent_order = ["critic", "veteran", "optimist", "businessman", "realist"]

            # 초반은 mini, 3라운드 이후는 4o
            model_key = "debate_early" if debate_round <= 3 else "debate_deep"

            debate_prompt = DEBATE_PROMPT.format(topic=topic, transcript=transcript)
            async for event in emit_agents(
                round_num, agent_order, debate_prompt, history, round_title, model_key, session_id
            ):
                yield event
            yield sse_event("round_end", {"round": round_num})

            round_num += 1
            debate_round += 1

    # 최종 심판
    judge_round = round_num
    yield sse_event("round_start", {"round": judge_round, "title": "심판 최종 결론"})
    yield sse_event("agent_thinking", {
        "agent_id": "judge",
        "agent_name": AGENTS["judge"]["name"],
        "round": judge_round,
    })

    transcript = history.format_transcript()
    judge_prompt = JUDGE_PROMPT.format(topic=topic, transcript=transcript)
    model, max_tokens = MODEL_BY_ROUND["judge"]
    _, judge_response = await call_api(
        "judge", AGENTS["judge"]["system_prompt"], judge_prompt, model, max_tokens
    )
    await log_usage(session_id, judge_round, 1, model, datetime.now().isoformat())

    yield sse_event("agent_start", {
        "agent_id": "judge",
        "agent_name": AGENTS["judge"]["name"],
        "round": judge_round,
    })
    await asyncio.sleep(0.05)
    yield sse_event("agent_chunk", {"agent_id": "judge", "chunk": judge_response})
    await asyncio.sleep(0.05)
    yield sse_event("agent_end", {
        "agent_id": "judge",
        "full_text": judge_response,
        "round": judge_round,
    })
    yield sse_event("round_end", {"round": judge_round})

    # DB 저장
    await save_session(session_id, topic, history.to_serializable(), datetime.now().isoformat())

    yield sse_event("debate_end", {
        "topic": topic,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    })


@app.get("/")
async def root():
    return {"status": "ok", "service": "Debate Arena API v3.1"}


@app.get("/api/agents")
async def get_agents():
    return {
        agent_id: {
            "name": agent["name"],
            "name_en": agent["name_en"],
            "color": agent["color"],
        }
        for agent_id, agent in AGENTS.items()
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = await load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return session


@app.post("/api/debate")
async def start_debate(http_request: Request, body: DebateRequest):
    ip = http_request.client.host if http_request.client else "unknown"
    allowed = await check_and_increment_limit(ip, max_per_day=10)
    if not allowed:
        raise HTTPException(status_code=429, detail="일일 사용 한도(10회)를 초과했습니다. 내일 다시 시도해주세요.")

    if not body.topic or not body.topic.strip():
        raise HTTPException(status_code=400, detail="토론 주제를 입력해주세요.")

    topic = body.topic.strip()
    if len(topic) > 500:
        raise HTTPException(status_code=400, detail="주제는 500자 이내로 입력해주세요.")

    if body.session_id and body.feedback:
        session_data = await load_session(body.session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        history = DebateHistory.from_serializable(session_data["rounds"])
        history.topic = session_data["topic"]
        session_id = body.session_id
    else:
        history = DebateHistory()
        session_id = str(uuid.uuid4())

    return StreamingResponse(
        run_debate(topic, session_id, history, body.feedback),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
