# Design — The Unreliable Assistant Enterprise Build

**Status:** Pre-build design locked for Build v0  
**Source specification:** `Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2.docx`  
**Implementation start:** prohibited until this document and `docs/workflow_orchestration.png` are reviewed and locked

## 1.1 System Charter and Hard Boundaries

### Mission

Transform the unreliable prototype into a tenant-isolated, MCP-enabled, observable agent platform that performs grounded retrieval, bounded tool execution, verification, and progressive-load validation.

### Supported Personas

- **Operator:** monitors traces, KPIs, incidents, releases, and red-team findings.
- **Reviewer:** approves or rejects Tier 3 mutations.
- **Developer:** uses the Streamlit workbench to inspect routing, RAG stages, MCP traffic, memory, and gates.
- **Enterprise user:** submits read or transaction requests within assigned tenant and permission scope.

### In Scope for Build v0

- FastAPI ingress and streamed responses.
- Deterministic intent triage and bounded ReAct state machine.
- Three-stage hybrid retrieval and reranking.
- MCP servers for retrieval, state, and knowledge graph access.
- PII, injection, argument, permission, and loop guardrails.
- Redis scoped cache and PostgreSQL durable state/audit.
- RAGAS, OTel, Prometheus, k6, JMeter, and Streamlit verification.
- Progressive 5K, 10K, and 50K test tiers.

### Non-goals

- Autonomous clinical diagnosis or treatment.
- Autonomous financial or legal authorization.
- Unreviewed high-impact mutation.
- Cross-tenant retrieval or mutation.
- Raw PII persistence.
- Open-ended agent recursion or unbounded tool loops.

### Failure Philosophy

A security or tenant-isolation failure fails closed. Latency or availability failures activate deterministic degraded modes. Correctness failures abstain or route to HITL rather than fabricate an answer.

## 1.2 MCP Tool and Data Contracts

### API Contract

`POST /api/v1/agent/query`

```json
{
  "tenant_id": "tenant_123",
  "user_id": "user_456",
  "session_id": "optional UUID",
  "query": "string, 1-4096 characters",
  "metadata": {}
}
```

Required response fields:

```json
{
  "request_id": "UUID",
  "tenant_id": "tenant_123",
  "route": "DIRECT_ANSWER | HYBRID_RAG | TRANSACTION_EXEC | REJECT_OOS",
  "answer": "string",
  "citations": [],
  "status": "DONE | PENDING_APPROVAL | HALTED_BREAKER | ABSTAINED",
  "traceparent": "W3C traceparent"
}
```

### MCP Configuration

```json
{
  "mcpServers": {
    "hybrid-rag": {"command": "uv", "args": ["run", "mcp_servers/rag_server.py"], "transport": "stdio", "timeout_ms": 150},
    "state-store": {"url": "http://localhost:8081/mcp", "transport": "streamable-http", "pool_size": 200},
    "graphify-vault": {"command": "uv", "args": ["run", "mcp_servers/graphify_server.py"], "transport": "stdio"}
  }
}
```

### MCP Tools

- `hybrid_retrieve(tenant_id, normalized_query, top_k, rerank_threshold)` → ranked chunks and span citations.
- `graphify_subgraph(tenant_id, anchor, depth<=2)` → minimal tenant-scoped knowledge subgraph.
- `get_session_facts(session_id, tenant_id)` → verified durable facts.
- `save_session_fact(session_id, tenant_id, fact, provenance_hash)` → redacted verified fact.
- `create_pending_mutation(tenant_id, user_id, action, canonical_args, idempotency_key)` → pending approval record.
- `approve_mutation(review_id, reviewer_id, decision)` → approved or rejected result.
- `write_audit_event(tenant_id, request_id, event, payload)` → hash-chained audit record.

### Validation Rules

- Pydantic v2 strict models reject unknown fields for mutation payloads.
- Query length: 1–4096 characters; normalize Unicode and whitespace.
- Entity repair examples: `SKU99` → `SKU-099`; `lot 44` → `LOT-00044`.
- Tenant and user values match the authenticated principal. Header-only identity is not accepted.
- Mutation arguments require canonical hash and UUIDv4 idempotency key.
- Tool timeout is 150 ms by default; per-step timeout is 120 ms.

### Error Codes

- `AUTH_TENANT_MISMATCH`
- `INVALID_TOOL_ARGUMENT`
- `PERMISSION_DENIED`
- `MCP_TIMEOUT`
- `MCP_UNAVAILABLE`
- `CIRCUIT_BREAKER_OPEN`
- `LOOP_LIMIT_REACHED`
- `HITL_PENDING_APPROVAL`
- `LOW_RETRIEVAL_CONFIDENCE`
- `INJECTION_BLOCKED`
- `PII_BLOCKED_OR_REDACTED`

### Lifecycle Plugins

| Plugin | Stage | Priority | Failure Policy |
|---|---|---:|---|
| `pii_redactor` | PRE_EXECUTION | 10 | fail closed |
| `injection_shield` | PRE_EXECUTION | 20 | fail closed |
| `circuit_breaker` | TOOL_DISPATCH | 10 | halt repeated calls |
| `ragas_auditor` | POST_EXECUTION | 10 | flag or abstain |
| `otel_exporter` | ALL_SPANS | 10 | best effort telemetry |

## 1.3 Distributed Topology and Data Flow

```text
Users / k6 / JMeter
        |
  NGINX / Envoy
        |
 FastAPI API + Auth + Tenant Context
        |
 Pre-Hooks: PII -> Injection -> Cache Lookup
        |
 Triage Agent (temp=0.0)
        +-> Direct Answer
        +-> Retrieval Subagent -> hybrid-rag MCP
        |                         -> BM25 -> Dense/FAISS -> RRF -> ONNX reranker
        |                         -> graphify-vault MCP
        +-> Execution Subagent -> state-store MCP -> HITL gate
        +-> Audit/Reject
        |
 Bounded ReAct (<=5 steps)
        |
 Tool Harness -> Permission -> Idempotency -> Circuit Breaker
        |
 Verification Subagent -> RAGAS/NLI
        |
 Egress + OTel -> Collector -> Prometheus/Tempo/Grafana

Redis Cluster: tenant-scoped cache/session state
PostgreSQL/pgvector: tenant-scoped facts, HITL, audit
```

### Storage Rules

- Redis cache key includes tenant, user, normalized query, and version.
- PostgreSQL row-level access and SQL predicates include tenant IDs.
- Session hot window: last 3 turns.
- Verified facts persist in `session_facts`; tool noise is not persisted.
- Audit payload omits raw PII and includes a redacted event plus payload hash.

## 1.4 End-to-End Latency Budget

Target: p95 <= 450 ms and p99 <= 590 ms at 50K VUs.

| Hop | Budget |
|---|---:|
| Hook pre-processing | <=15 ms |
| Cache lookup | <=10 ms |
| Triage | <=25 ms |
| MCP serialization | <=4 ms |
| BM25 | <=12 ms |
| Dense/FAISS | <=25 ms |
| RRF | <=3 ms |
| Cross-encoder rerank | <=45 ms |
| Generation TTFT | <=180 ms |
| Verification | <=60 ms |
| Remaining network and export overhead | <=71 ms |
| **End-to-end p95 target** | **<=450 ms** |

The 450 ms p95 budget and 590 ms p99 budget are hard release thresholds. The aggregate budgets contain a complete request envelope but are not expected to be additive for every cache-hit request. Cache hits and direct answers must be tested separately.

### Progressive Capacity Plan

| Tier | Virtual Users | Ramp | Minimum Evidence |
|---|---:|---|---|
| Build v0 baseline | 1–500 | 5 min | functional, trace, and cache checks |
| Tier 1 | 5K | 5 min ramp | p95/p99, 5xx, isolation, RSS, CPU |
| Tier 2 | 10K | 8 min ramp | saturation, pool contention, cache hit ratio |
| Tier 3 | 50K | 12 min ramp | all 36 gates and 60-minute soak |

## 1.5 KPI and SLA Gate Matrix

The release is blocked if any mandatory KPI fails.

| Stage | KPI | Threshold | Evidence |
|---|---|---:|---|
| Ingress | Pre-hook p95 | <=15 ms | OTel hook.pre |
| Ingress | PII recall | >=99.8% | Presidio/regex audit |
| Ingress | Injection block | >=99.5% | Red-team benchmark |
| Ingress | Triage accuracy | >=97% | labeled intent set |
| Ingress | Triage p95 | <=25 ms | triage span |
| Ingress | Benign false refusal | <=1% | benign control set |
| Retrieval | BM25 p95 | <=12 ms | rag.bm25 span |
| Retrieval | Dense/FAISS p95 | <=25 ms | rag.dense span |
| Retrieval | Rerank p95 | <=45 ms | rag.rerank span |
| Retrieval | Context Recall@50 | >=0.92 | IR/RAGAS |
| Retrieval | Precision@4 | >=0.88 | RAGAS |
| Retrieval | MRR@4 | >=0.85 | IR benchmark |
| Retrieval | nDCG@4 | >=0.86 | IR benchmark |
| Agent | Schema first pass | >=96% | Pydantic telemetry |
| Agent | Repair success | >=90% | harness metrics |
| Agent | Loop escape | 100% | chaos suite |
| Agent | Mean ReAct steps | <=2.2 | trace count |
| Agent | Context drift | <=0.15 / >=0.85 alignment | embedding audit |
| Agent | HITL gate enforcement | 100% | audit log |
| Generation | Faithfulness | >=0.92 | RAGAS |
| Generation | Answer relevancy | >=0.90 | RAGAS |
| Generation | Entity recall | >=0.85 | RAGAS |
| Generation | Negative abstention | >=98% | negative set |
| Generation | Unsupported claim rate | <=0.5% | NLI verifier |
| Generation | TTFT p95 | <=180 ms | streaming metric |
| Token | Prompt reduction | >=45% | token counter |
| Token | Cache hit ratio | >=35% | Redis metrics |
| Token | Cross-tenant leak count | 0 | concurrency probe |
| Token | Cost per 1K queries | <=$0.45 | OTel cost calculation |
| Token | MCP serialization p95 | <=4 ms | MCP timer |
| Scale | p50 at 50K | <=240 ms | k6/JMeter |
| Scale | p95 at 50K | <=450 ms | k6/JMeter |
| Scale | p99 at 50K | <=590 ms | k6/JMeter |
| Scale | HTTP 5xx | <=0.05% | load runners |
| Scale | Sustained throughput | >=8500 RPS | load counter |
| Scale | RSS growth over 1 hour | <=3% | Prometheus |

## 1.6 Failure Mode and Effects Analysis

| FMEA ID | Failure | Detection | Deterministic Fallback | Recovery |
|---|---|---|---|---|
| F01 | Redis unavailable | timeout/error counter | bypass cache, continue with primary store | reconnect/restart |
| F02 | Tenant cache key collision | probe/metric | reject request; trip key-validation test | rotate keys/repair logic |
| F03 | Reranker timeout | span >45 ms | abstain or sparse+dense result at reduced rank | restart/scale worker |
| F04 | MCP hybrid-rag crash | timeout/health check | stop retrieval; return abstention | bulkhead trip and restart |
| F05 | MCP state-store unavailable | timeout/write error | reject mutation; read-only mode | restore Postgres/replica |
| F06 | Graphify unavailable | MCP timeout | skip subgraph; use verified retrieved chunks | restart worker |
| F07 | Postgres unavailable | ACID/write alert | fail mutation/session persistence; direct cache-only reads if allowed | restore primary/replica |
| F08 | LLM 429/timeout | provider status | backoff, fallback SLM, or abstain | quota/retry policy |
| F09 | PII detector failure | hook health/error | fail closed/no egress | restore plugin |
| F10 | Injection classifier failure | hook health/error | reject/hold for manual review | restore plugin |
| F11 | Repeated identical tool call | canonical args hash | `HALTED_BREAKER` after 2 failures | reset after review |
| F12 | Verification disagreement | RAGAS/NLI score | abstain or cite unavailable evidence | tune models/dataset |

Alerting:

- p95 >550 ms for 30 seconds: switch to aggressive cache and reduce top_k 50→25.
- Faithfulness <0.90 for 5 minutes: raise rerank cutoff 0.42→0.55 and require extractive mode.
- MCP timeout >150 ms above 1%: trip MCP bulkhead and fail over to cached read replica.
- Redis CPU >85% or stampede: use jittered 300-second TTL ±45 seconds.

## 1.7 Architecture Decision Records

### ADR-001: Hybrid Retrieval

Use sparse BM25 and dense embeddings fused through RRF, then rerank with a cross-encoder. BM25 protects exact identifiers and policy clauses; dense retrieval protects semantic variants; reranking improves final precision.

Hyperparameters: BM25 k1=1.25, b=0.75; 512-token chunks with 64-token overlap; dense top_k=50; RRF k=60; rerank top=4; cutoff=0.42.

### ADR-002: ONNX Quantization

Use FP16 or INT8 ONNX where accuracy and hardware validation pass. Dynamic micro-batches permit 32 items with 8 ms maximum wait. The source document's baseline report showed 35 ms or lower reranking is achievable; every release must prove this against the actual environment.

### ADR-003: Tenant-Isolated Cache

Redis keys use `SHA256(tenant_id:user_id:normalized_query:cache_schema_version)`. The key hashes an identity boundary but must never replace authorization checks. Cache entries carry tenant metadata and response validation.

### ADR-004: Bounded ReAct

Use a deterministic state machine with five maximum iterations. This prevents recursive tool loops and permits traceable verification. The 450 ms loop budget is secondary to the 120 ms per-step limit.

### ADR-005: Verification Before Generation

Cross-encoder confidence below 0.42 produces a deterministic abstention instead of invoking generation. A low-confidence response is safer and cheaper than a hallucinated answer.

### ADR-006: Tiered Deployment

Build v0 starts local or single-host, but service boundaries remain MCP separable. Scale increments proceed 5K→10K→50K with evidence and rollback gates rather than assuming one-host performance scales linearly.

## Release and Rollback Policy

- One immutable artifact per version, tagged in Git and recorded in `release_manifest.json`.
- Store image digest, MCP manifest hash, model versions, index digest, configuration, and test report hashes.
- A failed gate does not modify the next tier baseline until the root-cause fix is verified.
- Rollback restores previous application image, configuration, model, index, and cache schema together.
- Database migrations require forward-compatible writes or explicit rollback migrations.
- A 50K campaign result is advisory only for a new model or index unless the same artifact is deployed.

## Required Evidence Artifacts

- `FAILURE_NOTES.md`
- `release_notes.md`
- `reports/5k/`
- `reports/10k/`
- `reports/50k/`
- `reports/redteam/`
- `reports/ragas/`
- `reports/soak/`
- `release_manifest.json`
