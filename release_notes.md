# Release Notes

## Build v0

- Added FastAPI agent ingress.
- Added deterministic tenant-aware triage and bounded routing.
- Added PII and injection guardrails.
- Added tenant-scoped Redis cache adapter.
- Added SQLite audit and pending mutation state store.
- Added hash-chained audit payload metadata.
- Added in-memory tenant-scoped BM25 retrieval.
- Added Groq generation configured from `groq_api_key`.
- Added MCP BM25 server and six-tab Streamlit workbench.
- Added guardrail/API tests and progressive k6 script.

### Verified Evidence

- Unit/API tests: 6 passed on 2026-11-18.
- Python compilation: passed.
- Live health endpoint: passed; Groq key configured.
- Live Groq generation: passed with `openai/gpt-oss-20b`.
- Live tenant-scoped retrieval: passed.

### Pending Evidence

- Red-team suite: pending
- RAGAS golden dataset: pending
- 5K load: pending
- 10K load: pending
- 50K load: pending
- Production readiness: not established
