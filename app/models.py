from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Route(str, Enum):
    DIRECT = "DIRECT_ANSWER"
    RAG = "HYBRID_RAG"
    EXECUTION = "TRANSACTION_EXEC"
    REJECT = "REJECT_OOS"


class PermissionTier(str, Enum):
    READ = "TIER_1_READ"
    COMPUTE = "TIER_2_COMPUTE"
    MUTATE = "TIER_3_MUTATE"


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    user_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    session_id: str | None = Field(default=None, max_length=128)
    query: str = Field(min_length=1, max_length=4096)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_name: str
    canonical_args: dict[str, Any]
    permission_tier: PermissionTier
    idempotency_key: str


class AgentResponse(BaseModel):
    request_id: str
    tenant_id: str
    route: Route
    answer: str
    citations: list[str] = Field(default_factory=list)
    status: str
    traceparent: str
