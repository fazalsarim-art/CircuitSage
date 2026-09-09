#!/usr/bin/env python
"""Export a benchmark version (cases + relevance judgments) to JSONL.

Thin wrapper around ``app.cli.export_benchmark``. Writes to a file or stdout, producing
the same schema-v1 JSONL that import_benchmark consumes (round-trippable).

    python scripts/export_benchmark.py --version-id <uuid> --out data/eval/export.jsonl
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cli import export_benchmark  # noqa: E402
from app.core.errors import APIError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version-id", required=True, help="Benchmark version UUID")
    parser.add_argument("--out", default=None, help="Output file (default: stdout)")
    args = parser.parse_args()
    try:
        export_benchmark(args.version_id, args.out)
    except APIError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
