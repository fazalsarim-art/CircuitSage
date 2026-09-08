# AGENTS.md — Contributor & AI Agent Guide for CircuitSage

CircuitSage is an embedded-systems documentation **RAG** application with a self-built
retrieval benchmark, evaluation harness, and human feedback loop. This file tells any
contributor — human or AI coding agent — how to work in this repository safely.

## Golden rules

1. **Build one phase at a time.** The project is developed in numbered phases (0–14).
   Finish a phase, run its checks, inspect the diff, commit locally, then **STOP**.
   Never attempt to build multiple phases in a single run.
2. **Preserve working behavior.** Do not break or weaken passing tests or features from
   earlier phases. If you must touch shared code, keep its contract intact.
3. **Secrets are always placeholders.** NEVER write a real API key, password, JWT secret,
   cookie, or connection string into any file, commit, prompt, screenshot, or issue.
   Use placeholders (e.g. `sk-placeholder`). Real values live only in local `.env` files
   (git-ignored) or the hosting provider's secret store.
4. **Scope discipline.** Only create/modify the files a phase calls for. Do not add
   services, dependencies, or tools silently. Pin exact dependency versions and commit
   lock files.
5. **Push deliberately.** Commit locally after each verified phase. This project pushes
   to a **private** GitHub repo per phase; never make it public without a security review.

## Environment

- **OS:** Windows 11 + PowerShell (commands below are in PowerShell form).
- **Python 3.13** via the `py -3.13` launcher — the bare `python` is an old 3.8, do not use it.
- **Node.js 24 LTS** (introduced at Phase 7).
- **Docker Desktop** for local PostgreSQL 18 + Qdrant 1.18.

## Local services

```powershell
docker compose config     # validate the compose file
docker compose up -d      # start postgres + qdrant
docker compose ps         # both should report "healthy"
docker compose down       # stop (named volumes keep the data)
```

Health:
- **PostgreSQL** — `pg_isready` inside the container.
- **Qdrant** — HTTP on port 6333. From the host: `Invoke-RestMethod http://localhost:6333/healthz`

## Verification commands (per phase)

Backend (from `backend/`, virtual environment active):

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q
ruff check .
ruff format --check .
```

Frontend (from `frontend/`):

```powershell
npm ci
npm run typecheck
npm run lint
npm run test -- --run
npm run build
```

## Secrets & data

- `.env` files, corpus PDFs, model caches, local databases, and build output are git-ignored.
- Do **not** commit copyrighted PDFs. Record corpus licenses in `docs/corpus.md`.

## Notes / deviations from the build guide

- The guide's shell commands are Linux-style; on Windows we translate them to PowerShell
  (`source .venv/bin/activate` → `.\.venv\Scripts\Activate.ps1`, `cp` → `Copy-Item`, etc.).
- Qdrant's image ships no `curl`/`wget`; its container health check uses a bash TCP probe.
- The spec's chat model name `gpt-5.6-luna` is a placeholder and must be replaced with a
  real, available model before Phase 5/6.
