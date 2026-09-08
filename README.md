# CircuitSage

> An embedded-systems documentation assistant (RAG) with a self-built retrieval
> benchmark, evaluation harness, and human feedback loop.

**Status:** 🚧 Under construction — **Phase 0** (repository & local services).

CircuitSage answers practical embedded-systems debugging questions (e.g. *"why does the
SPI status register stay busy?"*) by retrieving passages from a controlled document
collection and generating an answer that **cites its evidence** — or honestly reports
insufficient evidence. Unlike a basic PDF chatbot, its focus is **measurement**: a graded
benchmark and repeatable metrics comparing lexical, dense, hybrid, and reranked retrieval.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, TypeScript, Vite |
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic |
| Relational DB | PostgreSQL 18 (source of truth + lexical full-text search) |
| Vector DB | Qdrant 1.18 (derived index, 1536-dim) |
| AI | OpenAI embeddings + generation; local cross-encoder reranker |
| Infra | Docker Compose (local); Render + Qdrant Cloud (production) |

## Prerequisites

- Docker Desktop
- Python 3.13 (`py -3.13` on Windows)
- Node.js 24 LTS (from Phase 7)
- Git

## Quick start (local services)

```powershell
# 1. Copy environment templates
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env

# 2. Start PostgreSQL + Qdrant
docker compose up -d

# 3. Confirm both are healthy
docker compose ps
Invoke-RestMethod http://localhost:6333/healthz
```

Application code (API, worker, frontend) arrives in later phases.

## Project structure

```
backend/       FastAPI service, worker, retrieval, evals   (later phases)
frontend/      React application                            (later phases)
data/eval/     canonical benchmark export                  (later phases)
data/sample_docs/  local corpus (git-ignored contents)
docs/          architecture, corpus, threat model, evaluation report
scripts/       utility scripts
compose.yaml   local PostgreSQL + Qdrant
AGENTS.md      contributor & workflow guide
```

## Development

See **[AGENTS.md](AGENTS.md)** for the phased workflow, verification commands, and
security rules.
