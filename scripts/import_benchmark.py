#!/usr/bin/env python
"""Import a benchmark JSONL question bank into a new draft benchmark version.

Thin wrapper around ``app.cli.import_benchmark`` so the seed benchmark can be loaded
without remembering the module path. Requires the backend environment and a running
database (see docs/evaluation-report.md).

    python scripts/import_benchmark.py --file data/eval/circuitsage_benchmark_v1.jsonl \
        --name circuitsage
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cli import import_benchmark  # noqa: E402
from app.core.errors import APIError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="Path to the JSONL question bank")
    parser.add_argument("--name", default="circuitsage", help="Benchmark name")
    parser.add_argument("--description", default=None)
    parser.add_argument("--replace", action="store_true", help="Replace existing cases")
    parser.add_argument("--email", default=None, help="Admin to attribute (default: first admin)")
    args = parser.parse_args()
    try:
        import_benchmark(args.file, args.name, args.description, args.replace, args.email)
    except APIError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
