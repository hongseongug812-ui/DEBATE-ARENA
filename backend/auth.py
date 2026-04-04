"""
auth.py — API 키 기반 인증 + 사용량 제한
"""
import os
import uuid
import hashlib
import aiosqlite
from datetime import datetime
from database import DB_PATH

MASTER_KEY = os.getenv("MASTER_KEY", "debate-arena-admin")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "10"))


async def init_auth_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_hash TEXT PRIMARY KEY,
                label TEXT,
                daily_limit INTEGER DEFAULT 10,
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS key_usage (
                key_hash TEXT NOT NULL,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (key_hash, date)
            )
        """)
        await db.commit()


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def create_api_key(label: str = "", limit: int = DAILY_LIMIT) -> str:
    raw = f"da-{uuid.uuid4().hex}"
    key_hash = _hash(raw)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO api_keys (key_hash, label, daily_limit, created_at) VALUES (?,?,?,?)",
            (key_hash, label, limit, datetime.now().isoformat()),
        )
        await db.commit()
    return raw


async def verify_and_consume(api_key: str) -> tuple[bool, str]:
    """
    (허용 여부, 에러 메시지)
    """
    key_hash = _hash(api_key)
    today = datetime.now().strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT daily_limit, is_active FROM api_keys WHERE key_hash=?", (key_hash,)
        ) as cur:
            row = await cur.fetchone()

        if not row:
            return False, "유효하지 않은 API 키입니다."
        if not row[1]:
            return False, "비활성화된 API 키입니다."

        daily_limit = row[0]

        async with db.execute(
            "SELECT count FROM key_usage WHERE key_hash=? AND date=?", (key_hash, today)
        ) as cur:
            usage = await cur.fetchone()

        count = usage[0] if usage else 0
        if count >= daily_limit:
            return False, f"일일 한도({daily_limit}회)를 초과했습니다."

        if usage:
            await db.execute(
                "UPDATE key_usage SET count=count+1 WHERE key_hash=? AND date=?",
                (key_hash, today),
            )
        else:
            await db.execute(
                "INSERT INTO key_usage (key_hash, date, count) VALUES (?,?,1)",
                (key_hash, today),
            )
        await db.commit()

    return True, ""
