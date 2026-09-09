# Interview Q&A

Questions a reviewer might ask about CircuitSage, answered from the actual implementation. No
performance numbers are claimed — where a question asks "how well", the honest answer is "run
the benchmark; no production run is recorded yet."

## Project & scope

**Q. What is CircuitSage in one sentence?**
A retrieval-augmented assistant for embedded-systems documentation whose focus is *measurement*:
it answers with cited evidence and ships a self-built graded benchmark plus an evaluation harness
to compare retrieval strategies.

**Q. What makes it more than a PDF chatbot?**
Three things: answers are citation-validated and fail closed to `INSUFFICIENT_EVIDENCE`; there's
a versioned, immutable benchmark with deterministic metrics; and there's a human feedback loop
that turns reviewed feedback into draft benchmark cases.

## Retrieval & RAG

**Q. Why support lexical, dense, hybrid, and reranked retrieval instead of just one?**
So the choice is measured, not assumed. Lexical nails exact register/flag names; dense catches
paraphrases; hybrid (RRF) combines them; reranking can sharpen the top results. The benchmark
exists to decide which is worth its cost on this corpus.

**Q. How does hybrid fusion work?**
Reciprocal Rank Fusion with k=60: each candidate's score is the sum of `1/(k+rank)` across the
lexical and dense rankings, with a deterministic tie-break on the chunk UUID. RRF avoids having
to normalize incompatible score scales.

**Q. How do you stop the model from hallucinating a citation?**
The generator only sees evidence labelled `[C1]…[Cn]`. After generation, `evaluate_answer`
checks that every cited label was actually supplied; any unknown or missing label forces
`INSUFFICIENT_EVIDENCE`. It's fail-closed by design.

**Q. Why PostgreSQL *and* Qdrant?**
PostgreSQL is the source of truth and does lexical FTS; Qdrant is a derived index holding only
embeddings under the same chunk UUID. Qdrant is disposable — it can be rebuilt from PostgreSQL —
which keeps one authority for correctness.

## Evaluation

**Q. How is the benchmark built and why is it immutable?**
It's a set of graded relevance judgments (0–3) per question, versioned per name. Publishing
freezes a version and enforces a quality gate (minimum cases, a relevance-2+ judgment per
answerable case, zero relevant judgments for `unanswerable` cases). Immutability means every
metric is attributable to an exact dataset.

**Q. Which metrics, and how do you trust them?**
Hit@5, Recall@5, MRR@10, nDCG@10 — pure functions unit-tested with hand calculations. Aggregates
average over answerable cases only, and nDCG is broken out by category. Each run stores per-case
results and a corpus fingerprint so an aggregate is traceable and comparable.

**Q. What are the actual scores?**
None are published. The seed ships questions and expected answers, but relevance judgments
reference database-generated chunk IDs, so they must be authored against an ingested corpus
first. The harness produces the numbers via `eval-run`/the Eval Runs page; I have not recorded a
production run, so I don't quote figures I can't back with an exported run.

**Q. Why can't the seed just include the judgments?**
Because a judgment points at a specific chunk UUID that only exists after ingestion. Shipping
fabricated IDs would be dishonest and wouldn't resolve. The labelling step is the human part of
"self-built benchmark."

## Testing & reliability

**Q. How do you test AI code without a live model?**
Every AI dependency is injected. Tests use a `FakeEmbedder` (bag-of-words hashing to unit vectors
so lexical overlap raises cosine), a `FakeReranker`, and a `FakeAnswerClient`. Real OpenAI is
gated behind `RUN_LIVE_AI_TESTS`. The suite is deterministic and needs no network.

**Q. What happens when a dependency is down?**
Graceful degradation: no Qdrant → dense/hybrid return 503 while lexical still works; no OpenAI
key → generation returns `generation_failed` and embeddings degrade to 503. The app stays up.

**Q. What's your coverage and how is it enforced?**
The backend suite runs with an 85% coverage gate in CI (currently ~88%). Metrics have hand-calc
unit tests; the API has integration tests against real Postgres + Qdrant.

## Security

**Q. How are sessions handled?**
Argon2 password hashing; short-lived JWT access tokens kept only in browser memory; rotating
refresh tokens (hashed at rest) in an HttpOnly cookie with family reuse-detection. Plus per-user
query quotas, login throttling, security headers, and a safe error envelope.

**Q. Biggest security caveat you'd flag?**
The refresh cookie is `SameSite=Lax` with no CSRF token, and the rate limiter is in-memory. For
a real deployment I'd add a CSRF token, a shared rate-limit store, and host the SPA and API on a
shared registrable domain so the cookie is same-site.

## Deployment & ops

**Q. How does it deploy?**
A Render Blueprint (`render.yaml`): managed Postgres, the API (Docker) with an Alembic pre-deploy
migration, the worker, and the SPA as a static site; Qdrant Cloud for vectors. No plaintext
secrets — Render generates `JWT_SECRET`, and OpenAI/Qdrant creds are dashboard-entered. A
container entrypoint normalizes the managed `DATABASE_URL` to the `+psycopg` dialect.

## Résumé bullets (truthful — describe what was built, not fabricated impact)

- Built **CircuitSage**, a retrieval-augmented documentation assistant (FastAPI, PostgreSQL,
  Qdrant, React) that returns answers with validated citations and fails closed to
  `INSUFFICIENT_EVIDENCE` rather than hallucinating sources.
- Implemented four retrieval modes (lexical FTS, dense vector, RRF hybrid, cross-encoder rerank)
  behind one pipeline, plus a **self-built graded relevance benchmark** and a deterministic
  evaluation harness (Hit@k, Recall@k, MRR@10, nDCG@10) to compare them.
- Designed a human-in-the-loop feedback loop with a failure taxonomy, admin review with corrected
  evidence, an append-only audit trail, and safe promotion of reviewed feedback into draft
  benchmark cases (nothing enters the benchmark automatically).
- Made AI code deterministically testable with injectable embedder/reranker/answer clients and
  graceful dependency degradation; backend suite runs with an 85% coverage gate in CI.
- Containerized the stack and authored a least-privilege GitHub Actions pipeline (Postgres +
  Qdrant service containers, pinned actions) and a secret-free Render Blueprint for deployment.
