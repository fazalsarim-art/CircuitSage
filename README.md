# CircuitSage

> An embedded-systems documentation assistant (RAG) with a **self-built retrieval
> benchmark**, an **evaluation harness**, and a **human feedback loop**.

CircuitSage answers practical embedded-systems debugging questions (e.g. *"which register
selects the SPI clock polarity?"*) by retrieving passages from a controlled document
collection and generating an answer that **cites its evidence** — or honestly reports
`INSUFFICIENT_EVIDENCE`. Unlike a basic PDF chatbot, its focus is **measurement**: a graded
benchmark and repeatable metrics comparing lexical, dense, hybrid, and reranked retrieval.

## Highlights

- **Grounded answers with citation validation.** Answers must cite supplied evidence `[Cn]`;
  unknown or missing citations fail closed to `INSUFFICIENT_EVIDENCE` — the model cannot
  invent a source. Answer text is always rendered escaped, never as HTML.
- **Four retrieval modes.** Lexical (PostgreSQL full-text), dense (Qdrant cosine), hybrid
  (Reciprocal Rank Fusion), and reranked-hybrid (cross-encoder).
- **A real benchmark, not vibes.** Versioned, immutable-on-publish benchmark of graded
  relevance judgments; deterministic Hit@5 / Recall@5 / MRR@10 / nDCG@10 (hand-calc tested).
- **Evaluation runs & comparisons.** Queue a run per mode, compare two runs, break nDCG out by
  category, and record a corpus fingerprint for reproducibility.
- **Human feedback loop.** 👍/👎 with a failure taxonomy → an admin review queue with corrected
  evidence and an audit trail → optional promotion into a *draft* benchmark case (never
  automatic).
- **Security-minded.** Argon2 + rotating refresh tokens, role-based access, per-user query
  quotas, login throttling, security headers, and a safe error envelope. See
  [`SECURITY.md`](SECURITY.md) and [`docs/threat-model.md`](docs/threat-model.md).

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite, React Router |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic |
| Relational DB | PostgreSQL 18 (source of truth + lexical full-text search) |
| Vector DB | Qdrant 1.18 (derived index, 1536-dim) |
| AI | OpenAI embeddings + generation; optional local cross-encoder reranker |
| Infra | Docker + Compose (local & full stack); GitHub Actions CI |

## Architecture

```
                 ┌──────────────┐        ┌──────────────────────────┐
Browser ──HTTP──▶│  web (nginx) │──/api─▶│  api (FastAPI)           │
                 │  React SPA   │        │  auth · docs · chat ·    │
                 └──────────────┘        │  benchmark · evals ·     │
                                         │  feedback                │
                                         └───────┬───────────┬──────┘
                                                 │           │
                                   source of truth│           │derived vectors
                                                 ▼           ▼
                                         ┌────────────┐  ┌──────────┐
                                         │ PostgreSQL │  │  Qdrant  │
                                         │  + FTS     │  │  cosine  │
                                         └────────────┘  └──────────┘
                                                 ▲
                              ingestion / eval    │
                                         ┌────────┴────────┐
                                         │  worker         │
                                         │  (PDF→chunks→   │
                                         │   embeddings;   │
                                         │   eval runs)    │
                                         └─────────────────┘
```

PostgreSQL is the source of truth; a Qdrant point is a rebuildable copy of one chunk embedding
that shares the chunk's UUID. The worker performs ingestion (PDF → deterministic chunks →
embeddings → Qdrant) and executes queued evaluation runs.

## Prerequisites

- Docker Desktop
- Python 3.13 (`py -3.13` on Windows)
- Node.js 22 LTS or newer
- Git

## Quick start

### Option A — full stack in containers

```bash
# Real secrets come from your environment; sane dev placeholders are built in.
export JWT_SECRET="a-strong-random-secret-at-least-32-chars"
export OPENAI_API_KEY="sk-..."   # optional; lexical retrieval works without it

docker compose --profile app up --build
```

- Web UI: <http://localhost:8080>
- API (direct): <http://localhost:8000> — docs at `/docs` (dev only)

The `migrate` service runs Alembic before the API starts; `worker` handles ingestion and eval
runs; `web` (nginx) serves the SPA and reverse-proxies `/api` to the API.

### Option B — local dev (hot reload)

```powershell
# 1. Env templates
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env

# 2. Infra only
docker compose up -d

# 3. Backend (from backend/)
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock
pip install -e .
alembic -c alembic.ini upgrade head
python -m app.cli create-admin --email admin@example.com
uvicorn app.main:app --reload           # http://localhost:8000

# 4. Worker (separate shell, from backend/)
python -m app.worker

# 5. Frontend (from frontend/)
npm ci
npm run dev                              # http://localhost:5173 (proxies /api to :8000)
```

Without an OpenAI key the app still runs: lexical retrieval works fully; dense/hybrid return
`503` and generation returns `generation_failed` — by design.

## Testing & verification

```bash
# Backend (from backend/)
python -m ruff check app tests
python -m pytest -c pyproject.toml --cov=app --cov-fail-under=85

# Frontend (from frontend/)
npm run lint && npm run typecheck && npm run test -- --run && npm run build
npm audit --audit-level=high

# End-to-end browser flows (needs the app running + an admin user)
npx playwright test -c playwright.config.ts

# Repo smoke test: secret-pattern scan + optional API health/latency sample
bash scripts/smoke_test.sh
```

CI (`.github/workflows/ci.yml`) runs the backend suite (with Postgres + Qdrant service
containers and an 85% coverage gate), the frontend checks, and both container builds, with
least-privilege permissions and pinned action versions.

## The evaluation harness

The differentiator is measurement. See **[docs/evaluation-report.md](docs/evaluation-report.md)**
for the full method. In short:

1. Ingest reference PDFs (Documents page / worker).
2. Import the seed question bank: `python -m app.cli import-benchmark --file
   data/eval/circuitsage_benchmark_v1.jsonl --name circuitsage`.
3. Label the relevant chunk(s) per question and publish an immutable version.
4. Run and compare modes: `python -m app.cli eval-run --benchmark-version-id <id> --mode hybrid`
   (or queue via the Eval Runs page).

Relevance judgments reference database-generated chunk IDs, so the seed ships the questions and
expected answers; judgments are authored against the ingested corpus — the honest "self-built
benchmark" workflow.

## Deployment (Render + Qdrant Cloud)

Production is defined as a Render Blueprint in [`render.yaml`](render.yaml): a managed
PostgreSQL, the API (Docker, with an Alembic pre-deploy migration), the ingestion/eval worker,
and the SPA as a static site. Vectors live on Qdrant Cloud.

- **No plaintext secrets** in `render.yaml` — `JWT_SECRET` is generated by Render, OpenAI/Qdrant
  credentials are `sync: false` (entered in the dashboard), and the database URL is injected
  from the managed database. CORS uses an **exact** origin.
- The image entrypoint normalizes a managed-host `DATABASE_URL` (`postgres://` /
  `postgresql://`) to the `+psycopg` dialect the app expects.
- Post-deploy: `PROD=1 API_BASE_URL=https://<api-host> bash scripts/smoke_test.sh` checks
  `/health/ready` (dependency readiness) and `/version`.

Follow **[docs/deployment-checklist.md](docs/deployment-checklist.md)** for the full step list,
the environment-variable reference, and known considerations (notably the `*.onrender.com`
cross-site refresh-cookie caveat and how to resolve it with a shared custom domain).

## Project structure

```
backend/       FastAPI service, worker, retrieval, evals, feedback + tests
  app/         api routes · services · retrieval · evals · db models · core
  alembic/     migrations
  Dockerfile   production API/worker image
frontend/      React app (features: auth, chat, documents, benchmark, evals, feedback)
  Dockerfile   production static image (nginx)
data/eval/     seed benchmark JSONL (v1)
docs/          evaluation-report, threat-model, deployment-checklist (+ screenshots)
scripts/       import/export benchmark, smoke_test.sh
compose.yaml   infra (default) + full stack (--profile app)
render.yaml    Render Blueprint (API + worker + static web + managed Postgres)
.github/workflows/ci.yml
AGENTS.md      contributor & workflow guide
SECURITY.md    security controls & reporting
```

## Security

Secrets are never committed — every value in a tracked file is a placeholder, and runtime
configuration comes from environment variables. See [`SECURITY.md`](SECURITY.md) for the full
control list and [`docs/threat-model.md`](docs/threat-model.md) for the threat analysis.

## License

Portfolio project; no license granted for reuse at this time.
