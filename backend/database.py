"""
database.py — SQLite 세션 영속화
"""
import json
import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "debate_sessions.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                transcript TEXT NOT NULL,
                round_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                round_num INTEGER,
                agent_count INTEGER,
                model TEXT,
                created_at TEXT
            )
        """)
        await db.commit()


async def save_session(session_id: str, topic: str, rounds: list, updated_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        transcript = json.dumps(rounds, ensure_ascii=False)
        await db.execute("""
            INSERT INTO sessions (session_id, topic, transcript, round_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                transcript = excluded.transcript,
                round_count = excluded.round_count,
                updated_at = excluded.updated_at
        """, (session_id, topic, transcript, len(rounds), updated_at, updated_at))
        await db.commit()


async def load_session(session_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT topic, transcript, round_count FROM sessions WHERE session_id = ?",
            (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "topic": row[0],
                "rounds": json.loads(row[1]),
                "round_count": row[2],
            }


async def log_usage(session_id: str, round_num: int, agent_count: int, model: str, created_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO usage_log (session_id, round_num, agent_count, model, created_at) VALUES (?,?,?,?,?)",
            (session_id, round_num, agent_count, model, created_at)
        )
        await db.commit()
