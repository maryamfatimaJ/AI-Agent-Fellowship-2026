# Productivity Agent

A tool-using AI agent that helps organize work: creating tasks, analyzing meeting notes, and preparing daily/weekly plans — built for the AI Agent Fellowship Week 3 project.

## Tech stack

- Python 3.11+
- Flask (UI)
- LangGraph (agent controller)
- Google Gemini API (LLM)
- Pydantic (schemas)
- SQLite + SQLAlchemy (storage)

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# then edit .env and paste in your real GEMINI_API_KEY and a SECRET_KEY
python app.py
```

Open **http://127.0.0.1:5000**

## Build status — all phases complete

- [x] Phase 0 — UI direction and color system
- [x] Phase 1 — Project scaffolding, config, Flask + HTML/CSS/JS shell
- [x] Phase 2 — Task and Notes data models (SQLAlchemy + Pydantic, persisted)
- [x] Phase 3 — Tools (8 required + 2 bonus: Detect Overdue Tasks, Estimate Task Effort)
- [x] Phase 4 — Agent decision logic, prompts, and the real agent controller
- [x] Phase 5 — Approval flow and execution limits (landed inside Phase 4's controller)
- [x] Phase 6 — Execution logging, with a real reviewable history page
- [x] Phase 7 — Session memory (recent messages, last shown tasks, preferences)
- [x] Phase 8 — All 3 required multi-step workflows, tested end-to-end
- [x] Phase 9 — Resilience fixes, execution-limits documentation, final polish

45 automated tests, all passing (`pytest tests/ -v`). Every phase above
was verified by actually running the code — the full server, real
requests, and mocked-LLM-decision test sequences — not just written
and assumed to work.

## Requirements coverage

| Requirement | Where it's implemented |
|---|---|
| 1. Professional UI | `templates/index.html`, `static/css/style.css`, `static/js/app.js` |
| 2. Task data model | `database/models.py` (`Task`), `schemas.py` |
| 3. Notes data model | `database/models.py` (`Note`), `schemas.py` |
| 4. Minimum tool set (8 + 2 bonus) | `tools/task_tools.py`, `tools/note_tools.py`, `tools/planning_tools.py`, `tools/registry.py` |
| 5. Agent decision logic | `agent/nodes.py` (`decide_next_action`), `agent/graph.py` |
| 6. Multi-step workflows | `agent/graph.py`'s loop; proven in `tests/test_workflows.py` |
| 7. Human approval | `tools/registry.py` (`requires_approval`), `agent/graph.py`'s approval gate, `app.py`'s `/approve` and `/reject` routes |
| 8. Error handling | `agent/nodes.py`, `services/llm_service.py`, `app.py`'s top-level safety nets |
| 9. Execution limits | `config.py`, `agent/graph.py`; documented in `docs/execution_limits.md` |
| 10. Execution logging | `database/models.py` (`ExecutionLog`), `logging_/run_logger.py`, `app.py`'s `/logs` route |
| 11. Session memory | `agent/memory.py`, wired into `agent/graph.py` and `agent/prompts.py` |
| 12. Prompt design | `agent/prompts.py` (documented inline, section by section) |

## Project structure

```
productivity-agent/
├── app.py              # Flask routes only — no agent logic here
├── config.py            # Environment-based settings, no hard-coded secrets
├── templates/
│   └── index.html       # Chat, status indicator, approval card, panels
├── static/
│   ├── css/style.css
│   └── js/app.js
├── agent/               # Controller, state, prompts, decision nodes
├── tools/                # Task, note, and planning tools
├── database/             # SQLAlchemy models + repository functions
├── services/              # LLM client wrapper
├── logging_/               # Execution run logger (named logging_ to avoid
│                            shadowing Python's built-in logging module)
├── tests/
├── docs/
├── screenshots/
├── .env.example
├── requirements.txt
└── Dockerfile
```

## Note on live status updates

Flask handles one request at a time and returns once — it doesn't naturally
"stream" the agent's state live the way a tool like Streamlit does. This
project instead has each agent run record its full step-by-step history
(intent analysis, tool selection, execution, validation) and shows that
history in the Execution History panel after the run finishes, plus the
final state clearly in the status bar. True live mid-run updates would
need polling or websockets, which isn't required by the assignment.
