# The Unreliable Assistant — Build v0

Enterprise MCP agent implementation with bounded routing, tenant-isolated cache/state, hybrid retrieval groundwork, Groq generation, observability hooks, and a six-tab Streamlit workbench.

## Source Documents

- `Unreliable_Assistant_MidCheck_Enterprise_Blueprint_v2.docx`
- `Post_Hardening_Engineering_Audit_Report.docx`
- `SLM_Comprehensive_Guide.docx`

## Start

```bash
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
.venv/bin/streamlit run app.py --server.port 8501
```

Groq configuration is read from `.env` using `groq_api_key`.

## Test

```bash
.venv/bin/python -m pytest -q
```

## Load

Install k6 separately, then run:

```bash
k6 run -e TIER=5k load_tests/k6_progressive.js
k6 run -e TIER=10k load_tests/k6_progressive.js
k6 run -e TIER=50k load_tests/k6_progressive.js
```

No 5K, 10K, 50K, RAGAS, or red-team result makes the system production-ready until recorded evidence passes the gates in `design.md`.
