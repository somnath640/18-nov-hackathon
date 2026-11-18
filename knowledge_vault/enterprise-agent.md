---
id: enterprise-agent-core
domain: platform
risk_tier: high
version: 0.1
---

# Enterprise Agent Core

The agent is bounded to five ReAct iterations and a 450 ms loop budget.

- Tier 3 mutations require asynchronous HITL approval.
- Retrieval must remain tenant scoped.
- Raw PII must not persist.
- Reranker confidence below 0.42 requires abstention.

Related: [[architecture]], [[governance]], [[retrieval]].
