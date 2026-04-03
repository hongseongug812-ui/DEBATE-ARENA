"""
main.py — FastAPI 백엔드: 진짜 대화형 멀티에이전트 토론 엔진
- 에이전트가 이전 에이전트의 실제 발언을 보고 순차 응답
- SSE 실시간 스트리밍 (토큰 단위)
- SQLite 세션 영속화 + IP 일일 사용 제한
"""

import json
import asyncio
import os
import uuid
from datetime import datetime
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIConnectionError
from dotenv import load_dotenv

from agents import AGENTS, JUDGE_PROMPT, CONVERGENCE_CHECK_SYSTEM
from database import init_db, save_session, load_session, log_usage, check_and_increment_limit

load_dotenv()


@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield

app = FastAPI(title="Debate Arena API", version="4.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

DEBATE_AGENTS = ["optimist", "critic", "realist", "businessman", "veteran"]
MAX_ROUNDS = 5
MIN_ROUNDS = 3  # 수렴 체크 시작 라운드

# 라운드별 모델 (비용 최적화)
def get_model(round_num: int) -> tuple[str, int]:
    if round_num <= 1:
        return "gpt-4o-mini", 350
    elif round_num <= 3:
        return "gpt-4o-mini", 400
    else:
        return "gpt-4o", 500


class DebateRequest(BaseModel):
    topic: str
    session_id: str | None = None
    feedback: str | None = None


class ConversationRound:
    """한 라운드 안의 실제 대화 기록"""
    def __init__(self, title: str):
        self.title = title
        self.messages: list[dict] = []  # {"agent_id": str, "name": str, "text": str}

    def add(self, agent_id: str, text: str):
        self.messages.append({
            "agent_id": agent_id,
            "name": AGENTS[agent_id]["name"],
            "text": text,
        })

    def format_for_next(self) -> str:
        """이 라운드에서 지금까지 나온 발언들을 다음 에이전트에게 전달"""
        if not self.messages:
            return ""
        lines = []
        for m in self.messages:
            lines.append(f"{m['name']}: {m['text']}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"title": self.title, "messages": self.messages}


class DebateHistory:
    AGENT_NAMES = {a: AGENTS[a]["name"] for a in DEBATE_AGENTS}

    def __init__(self):
        self.topic: str = ""
        self.rounds: list[ConversationRound] = []

    def add_round(self, round_obj: ConversationRound):
        self.rounds.append(round_obj)

    def format_full_transcript(self) -> str:
        lines = []
        for i, r in enumerate(self.rounds, 1):
            lines.append(f"[Round {i} — {r.title}]")
            for m in r.messages:
                lines.append(f"{m['name']}: {m['text']}")
            lines.append("")
        return "\n".join(lines)

    def to_serializable(self) -> list:
        return [r.to_dict() for r in self.rounds]

    @classmethod
    def from_serializable(cls, data: list) -> "DebateHistory":
        h = cls()
        for d in data:
            r = ConversationRound(d["title"])
            r.messages = d["messages"]
            h.rounds.append(r)
        return h


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def build_agent_prompt(
    topic: str,
    agent_id: str,
    round_num: int,
    round_so_far: str,  # 이번 라운드에서 이전 에이전트들이 한 말
    full_history: str,  # 이전 라운드 전체 기록
    feedback: str | None = None,
) -> str:
    """각 에이전트가 받는 실제 대화형 프롬프트"""
    parts = [f'주제: "{topic}"\n']

    if full_history:
        parts.append("=== 이전 라운드 전체 기록 ===")
        parts.append(full_history)
        parts.append("")

    if feedback:
        parts.append(f"=== 사용자 피드백 ===")
        parts.append(feedback)
        parts.append("")

    if round_so_far:
        parts.append("=== 방금 이 자리에서 나온 발언 ===")
        parts.append(round_so_far)
        parts.append("")
        parts.append("=== 지시 ===")
        if round_num == 1:
            parts.append(
                "위에서 다른 에이전트들이 발언했습니다. "
                "당신도 첫 의견을 밝히되, 방금 나온 발언 중 가장 날카롭다고 생각하는 것에 직접 반응하세요. "
                "동의하면 강화하고, 틀렸다면 에이전트 이름 지목해 반박하세요."
            )
        else:
            parts.append(
                "위 발언들을 읽고, 가장 중요한 쟁점에 반응하세요. "
                "에이전트 이름을 직접 언급하며 반박하거나 보완하고, 새 논거가 있으면 추가하세요."
            )
    else:
        if round_num == 1:
            parts.append("=== 지시 ===")
            if feedback:
                parts.append(
                    "사용자 피드백을 반영해 당신의 관점에서 새로운 의견을 제시하세요. "
                    "이전과 겹치지 않는 방향으로."
                )
            else:
                parts.append(
                    "당신이 이 라운드 첫 발언자입니다. "
                    "주제에 대해 당신의 페르소나 그대로 첫 의견을 밝히세요. "
                    "아이디어 요청이면 구체적 아이디어 1~2개 직접 제시."
                )

    parts.append("\n4문장 이내. 반드시 한국어.")
    return "\n".join(parts)


async def stream_agent(
    agent_id: str,
    prompt: str,
    model: str,
    max_tokens: int,
    retries: int = 2,
) -> AsyncGenerator[str, None]:
    """토큰 단위 실시간 스트리밍"""
    for attempt in range(retries):
        try:
            stream = await client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0.88,
                messages=[
                    {"role": "system", "content": AGENTS[agent_id]["system_prompt"]},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            async for chunk in stream:
                text = chunk.choices[0].delta.content or ""
                if text:
                    yield text
            return

        except (RateLimitError, APITimeoutError, APIConnectionError):
            if attempt == retries - 1:
                yield "[응답 실패 — 잠시 후 다시 시도해주세요]"
            else:
                await asyncio.sleep(2 ** attempt)
        except Exception as e:
            yield f"[오류: {str(e)[:40]}]"
            return


async def check_convergence(topic: str, transcript: str) -> bool:
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=30,
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


async def run_debate_round(
    round_num: int,
    title: str,
    topic: str,
    agent_order: list[str],
    history: DebateHistory,
    session_id: str,
    feedback: str | None = None,
) -> AsyncGenerator[str, None]:
    """한 라운드: 에이전트가 순서대로 앞 발언을 보고 실시간 스트리밍 응답"""
    model, max_tokens = get_model(round_num)
    current_round = ConversationRound(title)
    full_history = history.format_full_transcript()

    for agent_id in agent_order:
        # 이번 라운드에서 지금까지 나온 발언
        round_so_far = current_round.format_for_next()

        prompt = build_agent_prompt(
            topic=topic,
            agent_id=agent_id,
            round_num=round_num,
            round_so_far=round_so_far,
            full_history=full_history,
            feedback=feedback,
        )

        # agent_start
        yield sse_event("agent_start", {
            "agent_id": agent_id,
            "agent_name": AGENTS[agent_id]["name"],
            "round": round_num,
        })

        # 토큰 단위 실시간 스트리밍
        full_text = ""
        async for token in stream_agent(agent_id, prompt, model, max_tokens):
            full_text += token
            yield sse_event("agent_chunk", {
                "agent_id": agent_id,
                "chunk": token,
            })

        # 이번 발언을 라운드 기록에 추가 → 다음 에이전트가 볼 수 있음
        current_round.add(agent_id, full_text)

        yield sse_event("agent_end", {
            "agent_id": agent_id,
            "full_text": full_text,
            "round": round_num,
        })

        # 에이전트 간 자연스러운 간격
        await asyncio.sleep(0.4)

    history.add_round(current_round)
    await log_usage(session_id, round_num, len(agent_order), model, datetime.now().isoformat())


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
        # 피드백: 비판론자 먼저 → 나머지 반응
        title = "피드백 반영 토론"
        yield sse_event("round_start", {"round": round_num, "title": title})
        agent_order = ["critic", "optimist", "veteran", "businessman", "realist"]
        async for event in run_debate_round(
            round_num, title, topic, agent_order, history, session_id, feedback
        ):
            yield event
        yield sse_event("round_end", {"round": round_num})
        round_num += 1

        # 피드백 후 심화 1라운드 추가
        title2 = "심화 논의"
        yield sse_event("round_start", {"round": round_num, "title": title2})
        agent_order2 = ["veteran", "businessman", "critic", "realist", "optimist"]
        async for event in run_debate_round(
            round_num, title2, topic, agent_order2, history, session_id
        ):
            yield event
        yield sse_event("round_end", {"round": round_num})
        round_num += 1

    else:
        # 동적 토론 라운드
        round_count = 1
        while round_count <= MAX_ROUNDS:
            # 수렴 체크
            if round_count > MIN_ROUNDS:
                transcript = history.format_full_transcript()
                if await check_convergence(topic, transcript):
                    yield sse_event("convergence_reached", {"round": round_num})
                    break

            if round_count == 1:
                title = "초기 의견 제시"
                # 첫 라운드: 낙관론자가 첫 발언, 나머지가 반응
                agent_order = ["optimist", "critic", "realist", "businessman", "veteran"]
            elif round_count % 2 == 0:
                title = f"반론 및 심화 {round_count - 1}라운드"
                # 비판론자·개발자 먼저 → 분위기 긴장
                agent_order = ["critic", "veteran", "businessman", "realist", "optimist"]
            else:
                title = f"보완 및 수렴 {round_count - 1}라운드"
                # 현실주의자 먼저 → 중재 역할
                agent_order = ["realist", "optimist", "critic", "veteran", "businessman"]

            yield sse_event("round_start", {"round": round_num, "title": title})
            async for event in run_debate_round(
                round_num, title, topic, agent_order, history, session_id
            ):
                yield event
            yield sse_event("round_end", {"round": round_num})

            round_num += 1
            round_count += 1

    # 최종 심판 — 전체 대화 기록 기반
    judge_round = round_num
    yield sse_event("round_start", {"round": judge_round, "title": "심판 최종 결론"})
    yield sse_event("agent_thinking", {
        "agent_id": "judge",
        "agent_name": AGENTS["judge"]["name"],
        "round": judge_round,
    })

    transcript = history.format_full_transcript()
    judge_prompt = JUDGE_PROMPT.format(topic=topic, transcript=transcript)

    yield sse_event("agent_start", {
        "agent_id": "judge",
        "agent_name": AGENTS["judge"]["name"],
        "round": judge_round,
    })

    judge_text = ""
    async for token in stream_agent("judge", judge_prompt, "gpt-4o", 900):
        judge_text += token
        yield sse_event("agent_chunk", {"agent_id": "judge", "chunk": token})

    yield sse_event("agent_end", {
        "agent_id": "judge",
        "full_text": judge_text,
        "round": judge_round,
    })
    yield sse_event("round_end", {"round": judge_round})

    await log_usage(session_id, judge_round, 1, "gpt-4o", datetime.now().isoformat())
    await save_session(session_id, topic, history.to_serializable(), datetime.now().isoformat())

    yield sse_event("debate_end", {
        "topic": topic,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    })


@app.get("/")
async def root():
    return {"status": "ok", "service": "Debate Arena API v4.0 — Conversational"}


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
