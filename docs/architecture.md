# Architecture & decisions

This document records the significant design decisions in CircuitSage and the reasoning behind
them. Everything here reflects code that exists in the repository; no performance numbers are
claimed (see [evaluation-report.md](evaluation-report.md) for how metrics are produced).

## System shape

- **API** (FastAPI) — auth, documents, chat, benchmark authoring, eval runs, feedback.
- **Worker** — a separate process that ingests PDFs (extract → deterministic chunk → embed →
  upsert to Qdrant) and executes queued evaluation runs.
- **PostgreSQL** — source of truth (users, documents, chunks, conversations, messages,
  feedback, benchmarks, eval results) and lexical full-text search.
- **Qdrant** — a derived vector index; each point is a rebuildable copy of one chunk embedding
  that shares the chunk's UUID.
- **SPA** (React) — the operator UI.

## Decisions

### 1. PostgreSQL is the source of truth; Qdrant is a derived index
Chunks, their text, and all relational data live in PostgreSQL. A Qdrant point stores only the
embedding and routing payload (document id, owner, visibility, pages) under the **same UUID** as
the PostgreSQL chunk. Retrieval hydrates results from PostgreSQL, so Qdrant can be rebuilt at any
time from the source of truth without data loss. This keeps a single authority for correctness
and makes the vector store disposable.

### 2. Four retrieval modes behind one pipeline
`run_retrieval(mode, …)` unifies **lexical** (`websearch_to_tsquery` + `ts_rank_cd`), **dense**
(Qdrant cosine), **hybrid** (Reciprocal Rank Fusion, k=60), and **reranked_hybrid**
(cross-encoder). Fusing lexical and dense with RRF is a simple, robust way to combine exact-term
and semantic matches without tuning score scales. The point of supporting all four is not to
pick one by intuition but to **measure** them on the benchmark.

### 3. Grounded answers with fail-closed citation validation
The generator is given evidence labelled `[C1] … [Cn]` and must cite it. `evaluate_answer`
validates that every cited label was actually supplied; an unknown or missing citation makes the
answer fail closed to `INSUFFICIENT_EVIDENCE`. The model cannot invent a source, and answer text
is always rendered escaped in the UI. This trades some answer coverage for trustworthiness — the
right trade for a documentation assistant.

### 4. Deterministic, versioned chunking
Chunking is deterministic (`CHUNKER_VERSION`, heading-window with token targets via tiktoken)
and each chunk carries a content checksum. Determinism makes ingestion reproducible and lets an
eval run record a **corpus fingerprint** (SHA-256 of sorted chunk checksums) so two runs are only
compared when they saw the same corpus.

### 5. A measurable benchmark, immutable on publish
Benchmarks are graded relevance judgments (0–3), versioned per name. A **published** version is
immutable; publication enforces a quality gate (minimum case count, a relevance-2+ judgment per
answerable case, no relevant judgments for `unanswerable` cases). Immutability means a metric is
always attributable to an exact, unchangeable dataset.

### 6. Deterministic metrics as pure functions
Hit@k, Recall@k, MRR@10, and nDCG@10 are pure functions unit-tested with hand calculations.
Aggregates are averaged over *answerable* cases only; nDCG is also broken out by category. Pure
functions make the numbers auditable and the tests trustworthy.

### 7. Human-in-the-loop feedback, never automatic
👍/👎 feedback carries a failure-taxonomy reason and an optional comment. An admin reviews it,
can attach corrected evidence (validated against the feedback author's visibility), and may
**promote** it into a *draft* benchmark case — reusing the same safe authoring path. Nothing a
user submits enters the benchmark automatically, and only an admin can publish. An append-only
`feedback_events` table records the audit trail.

### 8. Injectable clients make AI code testable offline
The embedder, vector store, reranker, and answer client are injected. Tests use a `FakeEmbedder`
(bag-of-words hashing → unit vectors so lexical overlap raises cosine), a `FakeReranker`
(word-overlap), and a `FakeAnswerClient`. Real OpenAI stays behind `RUN_LIVE_AI_TESTS`. This is
why the suite runs deterministically without a network or API key, and why the app degrades
gracefully when a dependency is missing.

### 9. Security as first-class controls
Argon2 password hashing; short-lived in-memory access tokens with rotating, reuse-detecting
refresh tokens; role-based access; per-user daily query quota; login throttling; security
headers; and a safe error envelope that never leaks internals. See
[../SECURITY.md](../SECURITY.md) and [threat-model.md](threat-model.md).

### 10. Reproducible builds and deploys
Dependencies are pinned (`requirements.lock`, `package-lock.json`); images pin their base tags
and run as non-root. CI runs the backend suite against Postgres + Qdrant service containers with
an 85% coverage gate, the frontend checks, and both image builds, with least-privilege
permissions and pinned actions. Production is described as a Render Blueprint with no plaintext
secrets.

## Known limitations

- The optional cross-encoder reranker (`[rerank]` extra) is not installed in the container
  image; `reranked_hybrid` falls back to hybrid ranking there.
- The login rate limiter is in-memory/per-process (needs a shared store for multi-instance).
- No production benchmark run has been recorded yet — judgments must be authored against an
  ingested corpus before real metrics exist (see the evaluation report).
- The refresh cookie is `SameSite=Lax` with no CSRF token; cross-site hosting needs a shared
  registrable domain (see the deployment checklist).
