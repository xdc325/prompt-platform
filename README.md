# Prompt Platform

A full-stack platform for managing LLM prompts as engineering assets: version control, regression testing, A/B experiments, multi-model playground, and review/publish workflow.

---

## Features

- **Version Control** — Create, diff, rollback, and delete prompt versions. Diff visualization highlighting additions, deletions, and changes word-by-word.
- **Regression Testing** — Define test suites with input/expected pairs. Run against any version + model combination via background worker. Poll results with pass rate and per-case output.
- **Playground & Compare** — Execute a single version or compare two versions side-by-side against the same input, with latency and word-level diff.
- **A/B Experiments** — Create and manage experiments between two versions with traffic split configuration.
- **Multi-Provider** — Factory pattern routes model selection to OpenAI, DeepSeek, or Claude providers automatically.
- **JWT Auth** — Register/login with dual-token (access + httpOnly refresh), route guards on frontend.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI 0.138 + Uvicorn (async) |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| Database | PostgreSQL 16 |
| Queue | Redis 7 + ARQ (background task worker) |
| Frontend | Vue 3 (Composition API) + Vite |
| Proxy | Nginx (static serve + API reverse proxy) |
| DevOps | Docker Compose (6 services) |

---

## Architecture

```
nginx (:80)
  ├── /           → Vue 3 SPA
  └── /api/v1/*   → FastAPI (:8000)
                       ├── api/          — 7 route modules
                       ├── services/     — 7 business services
                       ├── repositories/  — 9 data-access layers
                       ├── models/        — 9 ORM models
                       ├── schemas/       — Pydantic request/response validation
                       ├── providers/     — OpenAI / DeepSeek / Claude (factory)
                       └── worker/        — ARQ background regression tests

Router → Service → Repository → Model
              ↘ Provider (LLM calls)
```

All responses follow a unified envelope: `{ success: bool, data: ..., error: string | null }`.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/xdc325/prompt-platform.git
cd prompt-platform

# 2. Configure environment
cp .env.example .env
# Edit .env — add at least one API key (DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)

# 3. Start all services
docker compose up -d

# 4. Open in browser
# http://localhost
```

Services: `postgres`, `redis`, `backend` (:8000), `frontend` (Vite dev), `worker` (ARQ), `nginx` (:80).

---

## Project Scale

- **61** Python source files, **~3,400** lines (backend)
- **9** Vue/JS source files, **~1,100** lines (frontend)
- **35** REST API endpoints
- **9** database tables
- **47** end-to-end test cases
- **6** Docker Compose services

---

## Real Problems Solved

### 1. Foreign Key Cascade Deletion (3 locations)

**Problem**: Deleting a row referenced by foreign keys caused PostgreSQL constraint violations.

**Root Cause**: `prompt_versions` had `current_version_id` FK to `prompts`, `parent_version_id` self-referential FK, `test_runs` FK to `test_suites`, and `experiments` FK to `versions`. Naive `DELETE` violated all of them.

**Fix**: Implemented explicit cascade chains in service layer —
- Version delete: clear `current_version_id` on prompt + `parent_version_id` on child versions before DELETE
- Project delete: full cascade order — prompts → versions → test_runs / experiments / experiment_results → suites → members
- Test suite delete: DELETE test_runs before suite

### 2. Background Job Queue Never Firing (2 bugs)

**Problem**: Test suite "Run" created a `test_run` with status "running", but it stayed "running" forever. No results were ever produced.

**Root Cause**:
- `TestService.__init__` accepted an `arq` parameter but the API layer never injected it — `self.arq` was always `None`, so `if self.arq:` silently skipped the `enqueue_job` call
- The worker's `async with async_session_factory() as session:` context manager does NOT auto-commit (unlike `get_db` which calls `session.commit()` in finally). After updating `test_run.results`, `test_run.status`, `test_run.finished_at`, none of it was persisted

**Fix**:
- Added `get_arq()` async dependency in `deps.py` that creates an `ArqRedis` connection pool
- Injected it into the `run_test` API route and passed through to `TestService`
- Added `await session.commit()` in the worker after updating the test run

### 3. Worker Hardcoded Model

**Problem**: The ARQ worker called `get_provider("gpt-3.5-turbo")` and `provider.chat(model="gpt-3.5-turbo")`. Users with only a DeepSeek API key could never run regression tests.

**Fix**: Added `model` field to `TestRunRequest` schema (default: `deepseek-chat`), passed it through the API → service → ARQ job args → worker function. Updated frontend with a model selector dropdown.

### 4. API Key Validation Hang (60s Timeout)

**Problem**: Without a valid API key, the playground/compare features sent HTTP requests with `Authorization: Bearer None` to the LLM provider, then waited 60 seconds for httpx timeout before returning an error. The user perceived this as the app "freezing."

**Fix**: Added explicit API key presence checks in `experiment_service.py` before creating the provider. For each model prefix (`deepseek`, `claude`, `openai`), validate the corresponding config key exists. If not, raise `ConflictError` immediately — no HTTP call is made.

### 5. Worker Input Rendering Bug

**Problem**: The worker rendered test case input by iterating `.items()` on `case.get("input", {})`. But the `input` field is a string (e.g., `"我要退货"`), not a dict. `.items()` on a string yields character pairs (`('我','我')`, `('要','要')`, ...), resulting in garbled character-level template replacement.

**Fix**: Changed to `version.content.replace("{input}", str(case_input))` — direct placeholder substitution matching the schema definition.

### 6. Frontend UX Issues (3 fixes)

- **Expand/Collapse threshold**: Long prompt content was cut off at 120px / 8 lines. Increased to 200px / 12 lines.
- **Close-diff button overlap**: `float` layout caused the button to overlay diff content. Migrated to flexbox header layout.
- **Missing delete buttons**: No delete action existed for projects and versions. Added red delete buttons with confirmation dialogs.

### 7. Multi-Provider Routing

**Problem**: Different LLM providers have different API endpoints and auth schemes. Hardcoding one provider limits usability.

**Fix**: Designed a provider factory pattern:
- `BaseProvider` abstract class with `chat()` and `chat_stream()` interface
- `OpenAIProvider`, `DeepSeekProvider`, `ClaudeProvider` — each with own base URL and API key
- `get_provider(model)` factory function routes by model name prefix (`deepseek-*`, `claude-*`, others → OpenAI)
- `DeepSeekProvider` inherits from `OpenAIProvider` (DeepSeek API is OpenAI-compatible), only overrides `__init__` with different API key and base URL

---

## Key Design Decisions

- **Repository pattern**: All data access through repositories inheriting `BaseRepository`. Service layer never writes raw SQL except for cascade deletes.
- **PromptAccessMixin**: Permission check reused across 5 services. Verifies the user is a project member via one method call.
- **Immutable operations**: Services always return new objects; never mutate input parameters in place.
- **Unified response envelope**: `{ success, data, error }` on every endpoint. Frontend error handling is a single branch.

---

## License

MIT
