# CircuitSage evaluation harness

CircuitSage is built to be **measured**, not just demoed. This document describes the
retrieval benchmark, the metrics, and how to run an evaluation comparing retrieval modes.

## Why a benchmark

A RAG system has two failure surfaces: *retrieval* (did we find the right passage?) and
*generation* (did we answer faithfully and cite it?). Anecdotes hide regressions. The
benchmark turns "it feels better" into repeatable numbers so a change to chunking, the
embedding model, or the reranker can be accepted or rejected on evidence.

## The dataset

The benchmark is a set of **graded relevance judgments**: for each question, one or more
corpus chunks are labelled with a relevance grade.

| Grade | Meaning |
|-------|---------|
| 0 | Not relevant |
| 1 | Marginally related, does not answer |
| 2 | Relevant, partially answers |
| 3 | Directly and fully answers |

Each case also carries a `category` (e.g. `register_lookup`, `troubleshooting`,
`configuration`, `concept`, `unanswerable`), a `difficulty` (`easy`/`medium`/`hard`), and a
dataset `split` (`train`/`validation`/`test`). Cases in the `unanswerable` category must have
**no** relevant judgments — they verify the system reports *insufficient evidence* rather than
hallucinating.

### Seed question bank

`data/eval/circuitsage_benchmark_v1.jsonl` is the versioned seed: a curated bank of
embedded-systems questions (SPI, UART, I2C, GPIO, ADC, DMA, timers, interrupts, clocks,
low-power modes, CAN, watchdog) spanning every category, difficulty, and split. Because a
relevance judgment references a **database-generated chunk id**, the seed ships the questions
and expected answers only; judgments are authored against the *ingested corpus* (they cannot
be hard-coded in a portable file). This is the honest "self-built benchmark" workflow:

1. Ingest the reference documents (Phase 4 upload / worker).
2. Import the question bank into a **draft** version.
3. In the Benchmark UI (or API), label the relevant chunk(s) for each question.
4. Publish the version once it meets the quality bar.

### JSONL schema (version 1)

One JSON object per line:

```json
{
  "external_id": "spi-cpol-cpha",
  "question": "Which register bits select the SPI clock polarity and clock phase?",
  "category": "register_lookup",
  "difficulty": "easy",
  "split": "test",
  "expected_answer": "The CPOL and CPHA bits in SPI_CR1 ...",
  "notes": "Core SPI mode configuration lookup.",
  "judgments": [{ "chunk_id": "<uuid>", "relevance": 3, "rationale": "..." }]
}
```

Import and export are round-trippable through the same schema.

## Publication quality gate

A version is **immutable once published**. Publication is refused unless:

- the version has at least `MIN_CASES_FOR_PUBLISH` cases (100 by default);
- every **answerable** case has at least one relevance-2-or-3 judgment;
- every `unanswerable` case has zero relevant judgments.

This prevents evaluating against a half-labelled or contradictory dataset.

## Metrics

All metrics are pure functions (`app/evals/metrics.py`) unit-tested with hand calculations.
A chunk counts as "relevant" when its graded relevance is ≥ 1.

| Metric | What it measures |
|--------|------------------|
| **Hit@5** | Did any relevant chunk appear in the top 5? (0/1, averaged) |
| **Recall@5** | Fraction of a case's relevant chunks found in the top 5 |
| **MRR@10** | Reciprocal rank of the first relevant chunk (rewards ranking it first) |
| **nDCG@10** | Graded ranking quality; gain `2^rel − 1`, discount `log2(rank+1)`, normalized to the ideal ordering |
| **p95 latency** | 95th-percentile per-case retrieval latency (ms) |

Aggregate ranking metrics are averaged over **answerable cases only** (cases with at least one
relevant judgment); `unanswerable` cases would otherwise force the average toward zero.
nDCG is additionally broken out **by category** so, e.g., `register_lookup` regressions are
visible even when the overall number holds.

## Retrieval modes compared

| Mode | Pipeline |
|------|----------|
| `lexical` | PostgreSQL `websearch_to_tsquery` + `ts_rank_cd` |
| `dense` | Qdrant cosine similarity over OpenAI embeddings |
| `hybrid` | Reciprocal Rank Fusion (RRF, k=60) of lexical + dense |
| `reranked_hybrid` | Hybrid candidates re-scored by a cross-encoder |

## Running an evaluation

Each run records the retrieval config, embedding model, reranker model, and a
**corpus fingerprint** (SHA-256 of the sorted chunk checksums). Two runs are only directly
comparable when their benchmark version and corpus fingerprint match — the comparison endpoint
flags this as `equivalent`.

### 1. Import the seed question bank

```bash
python scripts/import_benchmark.py --file data/eval/circuitsage_benchmark_v1.jsonl --name circuitsage
```

or via the CLI:

```bash
python -m app.cli import-benchmark --file data/eval/circuitsage_benchmark_v1.jsonl --name circuitsage
```

### 2. Label judgments and publish

Use the Benchmark UI to attach relevant chunks to each question, then publish the version
(the confirmation must equal the benchmark name).

### 3. Run and compare

```bash
python -m app.cli eval-run --benchmark-version-id <uuid> --mode lexical
python -m app.cli eval-run --benchmark-version-id <uuid> --mode dense
python -m app.cli eval-run --benchmark-version-id <uuid> --mode hybrid
```

Runs are also queued through `POST /api/v1/evals/runs` and executed by the background worker.
Compare two completed runs at `GET /api/v1/evals/runs/compare?left_id=…&right_id=…`, and export
a run's per-case results at `GET /api/v1/evals/runs/{id}/export`.

### 4. Export a labelled benchmark

```bash
python scripts/export_benchmark.py --version-id <uuid> --out data/eval/labelled.jsonl
```

## Reproducibility notes

- Metrics are deterministic given the same corpus fingerprint and retrieval config.
- Per-case results (ranked chunk ids + graded relevances + latency) are stored so an aggregate
  number can always be traced back to the cases that produced it.
- Without an OpenAI key, `lexical` still runs; `dense`/`hybrid` degrade to a 503 for the dense
  leg — evaluate `lexical` offline, the full matrix with a key.

## Operational safety (does not affect metrics)

Evaluation is deterministic and independent of the runtime security controls added in phase 11.
The per-user daily query quota and login throttling apply to the interactive `/conversations`
and `/auth` endpoints only; eval runs are executed by an admin over the whole corpus and are not
rate-limited, so metrics are unchanged. Security headers, the safe error envelope, and
dependency-degradation behavior are documented in [`SECURITY.md`](../SECURITY.md) and
[`docs/threat-model.md`](threat-model.md). `scripts/smoke_test.sh` runs a secret-pattern scan
plus an optional API health and latency sample.
