# Claude Code Instructions — The Unreliable Assistant

## Mission

Build and iteratively harden an enterprise-grade MCP agent for progressive load targets: 5K, 10K, then 50K virtual users. The first objective is a safe, measurable Build v0; later iterations must reduce end-to-end latency and improve accuracy without weakening isolation or governance.

## Hard Gate Rules

1. Do not begin application implementation until `design.md` and `docs/workflow_orchestration.png` exist and are consistent.
2. Treat `design.md` as the source of truth for scope, contracts, thresholds, architecture decisions, and failure handling.
3. Never weaken a security, isolation, HITL, audit, or release threshold to obtain green test results.
4. Never claim production readiness from unit tests alone. Production claims require load, red-team, RAGAS, and soak evidence.
5. Use tenant-scoped keys and database filters everywhere. Cross-tenant access is a release-blocking defect.
6. Never persist raw PII. Emit redacted data and hash-chained audit events only.
7. No autonomous clinical, financial, legal, or other high-impact mutations without asynchronous HITL approval.

## Development Sequence

- Build v0: minimal API, deterministic triage, bounded ReAct state machine, MCP harness, cache, retrieval, observability, and workbench.
- Version after 5K test: fix only reproducible failure categories and save a rollback tag.
- Version after 10K test: tune bottlenecks exposed by trace evidence.
- Final 50K campaign: meet all latency and governance thresholds.
- Post any audit report: create `FAILURE_NOTES.md`, verify findings, remediate, add regression tests, and rerun affected gates before the next load tier.

## Architecture Constraints

- Runtime: Python 3.11+, FastAPI, Uvicorn, async I/O.
- MCP transport: stdio for local workers and Streamable HTTP/SSE for distributed services.
- MCP servers: `hybrid-rag`, `state-store`, `graphify-vault`.
- Retrieval: BM25, dense embedding/FAISS/HNSW, RRF, ONNX cross-encoder reranking.
- Plugins: Pluggy lifecycle interceptors for PII, injection detection, circuit breaking, RAGAS, and OTel.
- State: PostgreSQL/pgvector for durable facts and audit; Redis for scoped hot state and semantic cache.
- Loop: `INIT -> TRIAGE -> REASONING -> TOOL_CALL -> OBSERVATION -> VERIFY -> DONE/HALTED`.
- Loop limits: 5 iterations, 120 ms per step, 450 ms total loop budget.

## Implementation Priorities

1. Contracts and configuration before implementation.
2. Authentication, tenant isolation, and audit hooks before feature logic.
3. Pydantic v2 validation and deterministic argument repair before tool execution.
4. Bounded state machine before subagents or recursive behavior.
5. Observability spans attached to every external and internal hop.
6. Fallback behavior must be deterministic and tested.
7. RAG abstention must occur before expensive generation when reranker confidence is below threshold.

## Tool and MCP Rules

- Every tool call requires a Pydantic input model, permission tier, canonical arguments, and UUIDv4 idempotency key.
- Permission tiers: `TIER_1_READ`, `TIER_2_COMPUTE`, `TIER_3_MUTATE`.
- MCP calls require explicit timeout and circuit-breaker behavior.
- Never accept raw SQL, arbitrary shell, or unvalidated tool arguments.
- Tier 3 mutations return `PENDING_APPROVAL` and pause until a reviewer authorizes execution.

## Security and Audit

- Cache keys: `SHA256(tenant_id:user_id:normalized_query)`.
- Every PostgreSQL/SQLite query includes `tenant_id` unless explicitly documented as system-only.
- Hash-chain audit records using `SHA256(previous_hash + canonical_event_payload)`.
- Reject obfuscated PII and direct/indirect prompt injection according to fail-closed plugin policy.
- Signed MCP manifests are required before distributed MCP registration.

## Iterative Failure Workflow

For every test failure:

1. Record the exact test, load tier, configuration, commit, and trace IDs in `FAILURE_NOTES.md`.
2. Classify: security, correctness, latency, throughput, stability, or observability.
3. Define the smallest evidence-based hypothesis and reproducible regression test.
4. Apply a revertible change behind a feature flag or versioned configuration.
5. Save a rollback checkpoint/tag before deployment.
6. Re-run unit, contract, red-team, correctness, and affected load gates.
7. Mark the finding resolved only with traceable evidence and a passing rerun.

## Progressive Load Plan

- 5K: establish baselines, validate correctness, cache isolation, and 5xx behavior.
- 10K: measure capacity saturation and concurrency contention.
- 50K: enforce p50 <= 240 ms, p95 <= 450 ms, p99 <= 590 ms, 5xx <= 0.05%, throughput >= 8,500 RPS.
- No tier may be bypassed after a blocker is found.

## Testing Expectations

- Unit tests for parsers, repair, permissions, circuit breakers, loops, and cache isolation.
- Golden RAG dataset stratified: 25% factoid, 25% reasoning, 20% multi-hop, 15% summary, 15% negative/unanswerable.
- 100-prompt red-team suite covering jailbreaks, indirect injection, social engineering, PII smuggling, and fuzzing.
- k6 for distributed load and JMeter for independent controller/worker validation.
- RAGAS release gates: faithfulness >= 0.92, relevancy >= 0.90, context precision >= 0.88, recall >= 0.85, entity recall >= 0.85.

## Streamlit Workbench

Build six tabs:

1. Architecture and workflow.
2. Hybrid RAG laboratory.
3. MCP/plugin inspector.
4. Memory, Graphify, and token analysis.
5. Red-team and circuit-breaker controls.
6. KPI and progressive load scorecard.

## Documentation Rules

- Update `design.md` when contracts, topology, thresholds, or fallback behavior change.
- Generate `docs/workflow_orchestration.png` from `docs/workflow_orchestration.dot`.
- Keep `FAILURE_NOTES.md`, `release_notes.md`, and evidence paths for every tested version.
- Do not overwrite prior load reports or audit results. Preserve them as append-only evidence.
