from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.core.agent import BoundedAgent
from app.core.cache import SemanticCache
from app.core.rag import HybridRAG
from app.core.state import StateStore
from app.models import AgentRequest, AgentResponse


state = StateStore()
cache = SemanticCache()
rag = HybridRAG()
agent = BoundedAgent(rag, state, cache)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await state.initialize()
    yield


app = FastAPI(title="The Unreliable Assistant", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "groq_configured": bool(agent.client), "cache_available": cache.available}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/agent/query", response_model=AgentResponse)
async def query(request: AgentRequest) -> AgentResponse:
    try:
        return await agent.handle(request)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Agent request failed closed") from exc


@app.post("/api/v1/agent/stream")
async def stream(request: AgentRequest) -> StreamingResponse:
    response = await query(request)

    async def iterator():
        words = response.answer.split()
        for index in range(0, len(words), 8):
            yield " ".join(words[index:index + 8]) + " "

    return StreamingResponse(iterator(), media_type="text/plain")
