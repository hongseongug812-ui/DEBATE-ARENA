"""
test_api.py — FastAPI 엔드포인트 테스트 (OpenAI 호출 없이)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
import database

# 테스트용 임시 DB 경로
TEST_DB = os.path.join(os.path.dirname(__file__), "test_debate.db")


@pytest.fixture(autouse=True)
def use_test_db(tmp_path):
    """각 테스트마다 임시 DB 사용"""
    test_db = str(tmp_path / "test.db")
    original = database.DB_PATH
    database.DB_PATH = test_db
    yield
    database.DB_PATH = original
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest.fixture
async def client():
    with patch("main.check_and_increment_limit", new_callable=AsyncMock, return_value=True):
        from main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # DB 초기화
            await database.init_db()
            yield c


@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Debate Arena" in resp.json()["service"]


@pytest.mark.asyncio
async def test_get_agents(client):
    resp = await client.get("/api/agents")
    assert resp.status_code == 200
    data = resp.json()
    for agent_id in ["optimist", "critic", "realist", "businessman", "veteran", "judge"]:
        assert agent_id in data
        assert "name" in data[agent_id]
        assert "color" in data[agent_id]


@pytest.mark.asyncio
async def test_debate_empty_topic(client):
    resp = await client.post("/api/debate", json={"topic": ""})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_debate_topic_too_long(client):
    resp = await client.post("/api/debate", json={"topic": "x" * 501})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_debate_whitespace_topic(client):
    resp = await client.post("/api/debate", json={"topic": "   "})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_session_not_found(client):
    resp = await client.get("/api/session/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_feedback_without_valid_session(client):
    resp = await client.post("/api/debate", json={
        "topic": "테스트",
        "session_id": "fake-session-id",
        "feedback": "다른 아이디어 줘",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_daily_limit_exceeded(client):
    with patch("main.check_and_increment_limit", new_callable=AsyncMock, return_value=False):
        resp = await client.post("/api/debate", json={"topic": "테스트"})
        assert resp.status_code == 429
