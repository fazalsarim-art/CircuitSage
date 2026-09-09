# Demo script

A rehearsed ~2-minute walkthrough plus the clean-install steps behind it. Everything here maps
to commands and screens that exist in the repository.

## Clean install (rehearsal)

From a fresh clone, the fastest path is the full stack in containers:

```bash
export JWT_SECRET="a-strong-random-secret-at-least-32-chars"
export OPENAI_API_KEY="sk-..."          # optional; lexical works without it
docker compose --profile app up --build
# Web UI: http://localhost:8080   API: http://localhost:8000
```

Create the first admin (once the API is up):

```bash
docker compose exec api python -m app.cli create-admin --email admin@example.com
```

The local dev path (hot reload) is in the [README](../README.md#quick-start).

## Two-minute demo (spoken track)

**0:00 — The pitch (15s).**
"CircuitSage answers embedded-systems documentation questions with cited evidence. The point
isn't the chatbot — it's that retrieval quality is *measured* with a self-built benchmark."

**0:15 — Ask a grounded question (30s).**
Sign in → **Ask**. Upload a small reference PDF on the **Documents** page; watch it move to
`indexed` (the worker chunks and embeds it). Back on **Ask**, ask *"Which register selects the
SPI clock polarity?"* Show the answer, its **sources**, and the **Retrieval details** drawer
(per-stage ranks/scores). Point out that if the model can't ground an answer it says
`INSUFFICIENT_EVIDENCE` instead of guessing.

**0:45 — The benchmark (30s).**
Open **Benchmark**. Import the seed question bank
(`data/eval/circuitsage_benchmark_v1.jsonl`), open a draft version, and show cases labelled by
category/difficulty/split with a judgment status. Explain the immutability + quality gate on
publish. "Judgments point at real chunk IDs, so labelling happens against the ingested corpus —
that's the human part of a self-built benchmark."

**1:15 — Evaluation & comparison (30s).**
Open **Eval Runs**. Queue a run per mode over a published version, then select two runs to show
the **metric-delta** table (Hit@5 / Recall@5 / MRR@10 / nDCG@10) and the run detail with
per-case results and nDCG-by-category. "Each run records a corpus fingerprint so comparisons are
apples-to-apples."

**1:45 — The feedback loop (15s).**
On an answer, give 👎 with a reason. As admin, open **Feedback**: review it, grade the retrieved
chunks as corrected evidence, and **promote** it into a draft benchmark case. "Nothing a user
submits enters the benchmark automatically — an admin reviews and promotes, and there's an audit
trail."

## What to show if offline / no OpenAI key

Lexical retrieval works fully without a key. Dense/hybrid return `503` and generation returns
`generation_failed` — a good moment to point out the deliberate graceful degradation.

## Honest caveats to mention

- No production benchmark run is recorded yet, so there are no headline scores to quote — the
  demo shows the *machinery* that produces them.
- The cross-encoder reranker isn't installed in the container image (`reranked_hybrid` falls
  back to hybrid there).
