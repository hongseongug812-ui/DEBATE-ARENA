"""
test_auth.py — API 키 생성 / 검증 / 한도 초과 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import database
from auth import init_auth_db, create_api_key, verify_and_consume


@pytest.fixture(autouse=True)
def use_test_db(tmp_path):
    test_db = str(tmp_path / "auth_test.db")
    original = database.DB_PATH
    database.DB_PATH = test_db
    yield
    database.DB_PATH = original
    if os.path.exists(test_db):
        os.remove(test_db)


@pytest.mark.asyncio
async def test_create_and_verify():
    await init_auth_db()
    key = await create_api_key(label="test", limit=5)
    assert key.startswith("da-")

    ok, msg = await verify_and_consume(key)
    assert ok is True
    assert msg == ""


@pytest.mark.asyncio
async def test_invalid_key():
    await init_auth_db()
    ok, msg = await verify_and_consume("da-invalid-key")
    assert ok is False
    assert "유효하지 않은" in msg


@pytest.mark.asyncio
async def test_daily_limit_enforced():
    await init_auth_db()
    key = await create_api_key(label="limited", limit=3)

    for _ in range(3):
        ok, _ = await verify_and_consume(key)
        assert ok is True

    ok, msg = await verify_and_consume(key)
    assert ok is False
    assert "한도" in msg


@pytest.mark.asyncio
async def test_keys_endpoint_requires_master_key():
    import database as db_module
    from unittest.mock import AsyncMock, patch
    from httpx import AsyncClient, ASGITransport

    with patch("main.check_and_increment_limit", new_callable=AsyncMock, return_value=True):
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await db_module.init_db()
            await init_auth_db()

            # 마스터 키 없이 → 403
            resp = await c.post("/api/keys", json={"label": "x"})
            assert resp.status_code == 403

            # 틀린 마스터 키 → 403
            resp = await c.post("/api/keys", json={"label": "x"}, headers={"x-master-key": "wrong"})
            assert resp.status_code == 403

            # 올바른 마스터 키 → 200
            resp = await c.post(
                "/api/keys",
                json={"label": "mykey", "daily_limit": 5},
                headers={"x-master-key": "debate-arena-admin"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["api_key"].startswith("da-")
            assert data["daily_limit"] == 5


@pytest.mark.asyncio
async def test_debate_with_valid_api_key():
    import database as db_module
    from unittest.mock import AsyncMock, patch
    from httpx import AsyncClient, ASGITransport

    with patch("main.check_and_increment_limit", new_callable=AsyncMock, return_value=True):
        from main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await db_module.init_db()
            await init_auth_db()
            key = await create_api_key(label="debate-test", limit=10)

            # 유효한 API 키로 요청 → limit 체크 통과 (SSE 시작)
            with patch("main.run_debate") as mock_run:
                async def fake_gen(*a, **kw):
                    yield "event: debate_end\ndata: {}\n\n"
                mock_run.return_value = fake_gen()

                resp = await c.post(
                    "/api/debate",
                    json={"topic": "테스트"},
                    headers={"x-api-key": key},
                )
                # 응답이 시작됐으면 성공 (200)
                assert resp.status_code == 200
