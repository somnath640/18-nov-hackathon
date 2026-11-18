import hashlib
import time
import uuid
from typing import Any

from groq import Groq

from app.config import settings
from app.models import AgentRequest, AgentResponse, Route
from app.plugins.guardrails import injection_detected, normalize_unicode, redact_pii


class BoundedAgent:
    def __init__(self, rag: Any, state: Any, cache: Any) -> None:
        self.rag = rag
        self.state = state
        self.cache = cache
        self.client = Groq(api_key=settings.groq_api_key) if settings.groq_api_key else None

    async def handle(self, request: AgentRequest) -> AgentResponse:
        request_id = str(uuid.uuid4())
        traceparent = f"00-{uuid.uuid4().hex}-{uuid.uuid4().hex[:16]}-01"
        query = normalize_unicode(request.query)

        redacted, pii_found = redact_pii(query)
        if pii_found:
            await self.state.write_audit(request.tenant_id, request_id, "pii.redacted", {"pii_detected": True})
        if injection_detected(redacted):
            await self.state.write_audit(request.tenant_id, request_id, "injection.blocked", {"blocked": True})
            return AgentResponse(
                request_id=request_id, tenant_id=request.tenant_id,
                route=Route.REJECT, answer="Request rejected by the injection shield.",
                status="HALTED_SECURITY", traceparent=traceparent,
            )

        cached = await self.cache.get(request.tenant_id, request.user_id, redacted)
        if cached:
            cached["request_id"] = request_id
            cached["traceparent"] = traceparent
            return AgentResponse(**cached)

        route = self.triage(redacted)
        citations: list[str] = []
        started = time.perf_counter()

        if route == Route.RAG:
            hits = self.rag.retrieve(request.tenant_id, redacted)
            if not hits:
                answer = "I cannot find tenant-scoped evidence for that request."
                status = "ABSTAINED"
            else:
                top_chunk, top_score = hits[0]
                confidence = min(1.0, max(0.0, top_score))
                citations = [chunk.chunk_id for chunk, _ in hits]
                if top_score < settings.rerank_threshold:
                    answer = "I cannot establish sufficient retrieval confidence to answer safely."
                    status = "ABSTAINED"
                else:
                    context = "\n".join(chunk.text for chunk, _ in hits)
                    answer = await self.generate(redacted, context)
                    status = "DONE"
        elif route == Route.EXECUTION:
            if any(word in redacted.lower() for word in ("approve", "reject", "release", "submit", "mutate")):
                canonical = {"action": "domain_mutation", "query_hash": hashlib.sha256(redacted.encode()).hexdigest()}
                key = str(uuid.uuid4())
                mutation_id = await self.state.create_pending_mutation(
                    request.tenant_id, request.user_id, request_id,
                    "domain_mutation", canonical, key,
                )
                answer = f"Mutation paused for asynchronous approval. Pending review ID: {mutation_id}."
                status = "PENDING_APPROVAL"
            else:
                answer = await self.generate(redacted, "No mutation is authorized from this request.")
                status = "DONE"
        elif route == Route.REJECT:
            answer = "This request is outside the supported assistant scope."
            status = "HALTED_OOS"
        else:
            answer = await self.generate(redacted, "Answer only from the request and verified platform constraints.")
            status = "DONE"

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        await self.state.write_audit(request.tenant_id, request_id, "agent.completed", {
            "route": route.value,
            "status": status,
            "elapsed_ms": elapsed_ms,
            "citations": citations,
        })

        response = AgentResponse(
            request_id=request_id,
            tenant_id=request.tenant_id,
            route=route,
            answer=answer,
            citations=citations,
            status=status,
            traceparent=traceparent,
        )
        await self.cache.set(request.tenant_id, request.user_id, redacted, response.model_dump(mode="json"))
        return response

    @staticmethod
    def triage(query: str) -> Route:
        lowered = query.lower()
        if any(word in lowered for word in ("unknown", "capsule", "outside scope")):
            return Route.REJECT
        if any(word in lowered for word in ("approve", "reject", "submit", "release", "mutation", "delete", "update")):
            return Route.EXECUTION
        if any(word in lowered for word in ("batch", "policy", "protocol", "lot", "50k", "rag", "latency", "pii")):
            return Route.RAG
        return Route.DIRECT

    async def generate(self, query: str, context: str) -> str:
        if not self.client:
            return "Build v0 grounded fallback: " + context
        try:
            completion = self.client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": "Answer concisely only from the supplied evidence. Never invent facts. If evidence is insufficient, abstain."},
                    {"role": "user", "content": f"Evidence:\n{context}\n\nQuestion:\n{query}"},
                ],
                temperature=0.0,
                max_tokens=300,
            )
            return completion.choices[0].message.content or "I cannot provide a grounded answer."
        except Exception:
            await self.state.write_audit("system", str(uuid.uuid4()), "llm.fallback", {"fallback": "deterministic"})
            return "Build v0 deterministic fallback: " + context
