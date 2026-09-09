# Screenshot plan

Capture these once the stack is running (`docker compose --profile app up --build`, then sign
in) with a small reference PDF ingested and the seed benchmark imported. Save PNGs beside this
file with the given names and reference them from the main README.

Use a ~1280px-wide window (light theme) for consistency. Redact nothing sensitive appears —
these are dev placeholders only.

| File | Screen | What it should show |
|------|--------|---------------------|
| `01-ask-answer.png` | Ask | A question, the grounded answer, the **Sources** list, and the answer-status badge. |
| `02-retrieval-details.png` | Ask → Retrieval details | The per-stage ranks/scores drawer (lexical/dense/fused/rerank). |
| `03-documents.png` | Documents | The upload form and a document at `indexed` with page/chunk counts. |
| `04-benchmark-cases.png` | Benchmark | A selected version with the case table (category/difficulty/split, judgment status) and the publish/confirmation control. |
| `05-eval-compare.png` | Eval Runs | Two runs selected with the metric-delta table (Hit@5/Recall@5/MRR@10/nDCG@10). |
| `06-eval-detail.png` | Eval Runs → Details | Aggregate metrics, nDCG-by-category, and per-case results. |
| `07-feedback-review.png` | Feedback | The review panel: question/answer, corrected-evidence grading, and the audit history. |

## Capture tips

- Ingest one small PDF first so Ask, Documents, and eval runs have real content.
- For the eval screenshots, publish a benchmark version and queue a run per mode (`lexical`,
  `dense`, `hybrid`) so the compare view has two runs to diff.
- Keep the browser zoom at 100%. Crop to the content area, not the whole desktop.

> Not yet captured. This is the shot list; commit the actual PNGs here when recording the demo.
