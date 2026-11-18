import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from app.config import settings


class SemanticCache:
    def __init__(self) -> None:
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        self.available = True

    @staticmethod
    def key(tenant_id: str, user_id: str, normalized_query: str) -> str:
        digest = hashlib.sha256(
            f"{tenant_id}:{user_id}:{normalized_query}".encode("utf-8")
        ).hexdigest()
        return f"agent:v1:{digest}"

    async def get(self, tenant_id: str, user_id: str, query: str) -> dict[str, Any] | None:
        if not self.available:
            return None
        try:
            raw = await self.redis.get(self.key(tenant_id, user_id, query))
            if not raw:
                return None
            value = json.loads(raw)
            if value.get("tenant_id") != tenant_id:
                return None
            return value
        except Exception:
            self.available = False
            return None

    async def set(self, tenant_id: str, user_id: str, query: str, value: dict[str, Any]) -> None:
        if not self.available:
            return
        try:
            await self.redis.setex(
                self.key(tenant_id, user_id, query), 300, json.dumps(value)
            )
        except Exception:
            self.available = False
