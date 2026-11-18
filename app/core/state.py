import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import text

from app.config import settings


class StateStore:
    def __init__(self) -> None:
        db_url = settings.database_url
        Path("data").mkdir(parents=True, exist_ok=True)
        self.engine = create_async_engine(db_url, future=True)

    async def initialize(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    redacted_payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS session_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    provenance_hash TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS pending_mutations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    canonical_args TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tenant_id, idempotency_key)
                )
            """))

    async def write_audit(self, tenant_id: str, request_id: str, event: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        async with self.engine.begin() as conn:
            row = await conn.execute(text("""
                SELECT hash FROM audit_events WHERE tenant_id=:tenant
                ORDER BY id DESC LIMIT 1
            """), {"tenant": tenant_id})
            previous = row.scalar() or "0" * 64
            digest = hashlib.sha256((previous + canonical).encode("utf-8")).hexdigest()
            await conn.execute(text("""
                INSERT INTO audit_events
                    (tenant_id, request_id, event, redacted_payload, previous_hash, hash)
                VALUES
                    (:tenant, :request, :event, :payload, :previous, :hash)
            """), {
                "tenant": tenant_id,
                "request": request_id,
                "event": event,
                "payload": canonical,
                "previous": previous,
                "hash": digest,
            })
            return digest

    async def save_fact(self, tenant_id: str, session_id: str, fact: str, provenance: str) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO session_facts (tenant_id, session_id, fact, provenance_hash)
                VALUES (:tenant, :session, :fact, :provenance)
            """), {"tenant": tenant_id, "session": session_id, "fact": fact, "provenance": provenance})

    async def get_facts(self, tenant_id: str, session_id: str) -> list[str]:
        async with self.engine.connect() as conn:
            rows = await conn.execute(text("""
                SELECT fact FROM session_facts
                WHERE tenant_id=:tenant AND session_id=:session
                ORDER BY id DESC LIMIT 3
            """), {"tenant": tenant_id, "session": session_id})
            return [row[0] for row in rows.fetchall()][::-1]

    async def create_pending_mutation(
        self, tenant_id: str, user_id: str, request_id: str,
        action: str, canonical_args: dict[str, Any], idempotency_key: str,
    ) -> int:
        async with self.engine.begin() as conn:
            await conn.execute(text("""
                INSERT OR IGNORE INTO pending_mutations
                    (tenant_id, user_id, request_id, action, canonical_args, idempotency_key, status)
                VALUES (:tenant, :user, :request, :action, :args, :key, 'PENDING_APPROVAL')
            """), {
                "tenant": tenant_id,
                "user": user_id,
                "request": request_id,
                "action": action,
                "args": json.dumps(canonical_args, sort_keys=True),
                "key": idempotency_key,
            })
            row = await conn.execute(text("""
                SELECT id FROM pending_mutations
                WHERE tenant_id=:tenant AND idempotency_key=:key
            """), {"tenant": tenant_id, "key": idempotency_key})
            return int(row.scalar_one())
