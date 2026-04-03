"""
main.py — FastAPI 백엔드: 멀티에이전트 동적 토론 엔진 + SSE 스트리밍
세션 기반 피드백 재토론 지원
"""

import json
import asyncio
import os
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv

from agents import (
    AGENTS,
    INITIAL_PROMPT,
    DEBATE_PROMPT,
    JUDGE_PROMPT,
    FEEDBACK_PROMPT,
    CONVERGENCE_CHECK_SYSTEM,
)

load_dotenv()

app = FastAPI(title="Debate Arena API", version="3.0.0")

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

# 세션 저장소 (메모리)
sessions: dict[str, dict] = {}


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
        self.rounds: list[dict[str, str]] = []
        self.round_titles: list[str] = []

    def add_round(self, responses: dict[str, str], title: str):
        self.rounds.append(responses)
        self.round_titles.append(title)

    def format_transcript(self, from_round: int = 0) -> str:
        lines = []
        for i, (round_data, title) in enumerate(
            zip(self.rounds[from_round:], self.round_titles[from_round:]), from_round + 1
        ):
            lines.append(f"[Round {i} — {title}]")
            for agent_id in DEBATE_AGENTS:
                name = self.AGENT_NAMES[agent_id]
                text = round_data.get(agent_id, "")
                if text:
                    lines.append(f"{name}: {text}")
            lines.append("")
        return "\n".join(lines)


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def collect_agent_response(
    agent_id: str, system_prompt: str, user_prompt: str, max_tokens: int = 500
) -> tuple[str, str]:
    full_text = ""
    stream = await client.chat.completions.create(
        model="gpt-4o",
        max_tokens=max_tokens,
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


async def emit_agents(
    round_num: int,
    agent_order: list[str],
    prompt: str,
    history: DebateHistory,
    round_title: str,
) -> AsyncGenerator[str, None]:
    """에이전트 thinking → 병렬 호출 → 순서대로 SSE 출력"""
    for agent_id in agent_order:
        yield sse_event("agent_thinking", {
            "agent_id": agent_id,
            "agent_name": AGENTS[agent_id]["name"],
            "round": round_num,
        })

    tasks = [
        collect_agent_response(agent_id, AGENTS[agent_id]["system_prompt"], prompt)
        for agent_id in agent_order
    ]
    results = await asyncio.gather(*tasks)

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
        # ── 피드백 기반 재토론 ──
        transcript = history.format_transcript()
        feedback_prompt = FEEDBACK_PROMPT.format(
            topic=topic,
            transcript=transcript,
            feedback=feedback,
        )

        title = f"피드백 반영 토론"
        yield sse_event("round_start", {"round": round_num, "title": title})
        async for event in emit_agents(round_num, DEBATE_AGENTS, feedback_prompt, history, title):
            yield event
        yield sse_event("round_end", {"round": round_num})
        round_num += 1

        # 피드백 후 추가 1라운드 더
        transcript = history.format_transcript()
        debate_prompt = DEBATE_PROMPT.format(topic=topic, transcript=transcript)
        title2 = "심화 논의"
        yield sse_event("round_start", {"round": round_num, "title": title2})
        agent_order = ["critic", "veteran", "optimist", "businessman", "realist"]
        async for event in emit_agents(round_num, agent_order, debate_prompt, history, title2):
            yield event
        yield sse_event("round_end", {"round": round_num})
        round_num += 1

    else:
        # ── Round 1: 초기 의견 ──
        title = "초기 의견 제시"
        yield sse_event("round_start", {"round": round_num, "title": title})
        initial_prompt = INITIAL_PROMPT.format(topic=topic)
        async for event in emit_agents(round_num, DEBATE_AGENTS, initial_prompt, history, title):
            yield event
        yield sse_event("round_end", {"round": round_num})
        round_num += 1

        # ── 동적 토론 라운드 ──
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

            debate_prompt = DEBATE_PROMPT.format(topic=topic, transcript=transcript)
            async for event in emit_agents(round_num, agent_order, debate_prompt, history, round_title):
                yield event
            yield sse_event("round_end", {"round": round_num})

            round_num += 1
            debate_round += 1

    # ── 최종 심판 ──
    judge_round = round_num
    yield sse_event("round_start", {"round": judge_round, "title": "심판 최종 결론"})

    yield sse_event("agent_thinking", {
        "agent_id": "judge",
        "agent_name": AGENTS["judge"]["name"],
        "round": judge_round,
    })

    transcript = history.format_transcript()
    judge_prompt = JUDGE_PROMPT.format(topic=topic, transcript=transcript)
    _, judge_response = await collect_agent_response(
        "judge", AGENTS["judge"]["system_prompt"], judge_prompt, max_tokens=900
    )

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

    # 세션 저장
    sessions[session_id] = {
        "topic": topic,
        "history": history,
        "updated_at": datetime.now().isoformat(),
    }

    yield sse_event("debate_end", {
        "topic": topic,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    })


@app.get("/")
async def root():
    return {"status": "ok", "service": "Debate Arena API v3"}


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


@app.post("/api/debate")
async def start_debate(request: DebateRequest):
    if not request.topic.strip():
        raise HTTPException(status_code=400, detail="토론 주제를 입력해주세요.")

    if request.session_id and request.feedback:
        # 기존 세션 이어서
        session = sessions.get(request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
        history = session["history"]
        session_id = request.session_id
    else:
        # 새 세션
        history = DebateHistory()
        session_id = str(uuid.uuid4())

    return StreamingResponse(
        run_debate(request.topic.strip(), session_id, history, request.feedback),
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
