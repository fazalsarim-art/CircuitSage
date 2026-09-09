#!/usr/bin/env bash
# CircuitSage smoke test (§7.12): a secret-pattern scan (always), plus an optional API health
# check and a lightweight performance sample when the API is reachable.
#
# Usage:
#   scripts/smoke_test.sh                 # secret scan; health+perf if localhost:8000 is up
#   API_BASE_URL=http://host:8000 scripts/smoke_test.sh
#   PERF_SAMPLES=50 PERF_P95_BUDGET_MS=500 scripts/smoke_test.sh
set -uo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
PERF_SAMPLES="${PERF_SAMPLES:-20}"
PERF_P95_BUDGET_MS="${PERF_P95_BUDGET_MS:-750}"
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

fail=0
section() { printf '\n=== %s ===\n' "$1"; }

# ---------------------------------------------------------------------------
# 1. Secret-pattern scan over tracked files. High-signal patterns only, so a
#    placeholder like sk-placeholder or change_me does not trip it.
# ---------------------------------------------------------------------------
section "Secret-pattern scan"
# High-signal patterns only; matched lines that look like placeholders/examples are ignored.
pattern='(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{40,}|ghp_[A-Za-z0-9]{36}|xox[baprs]-[A-Za-z0-9-]{10,}|postgres(ql)?://[^:@/ ]+:[^@/ ]{6,}@)'
placeholder='change_me|placeholder|example|EXAMPLE|your-|xxxx|<[a-z-]+>|dummy|redacted'
found=0
tracked="$(git ls-files ':!:*.lock' ':!:scripts/smoke_test.sh' ':!:package-lock.json' 2>/dev/null)"
while IFS= read -r file; do
  [ -z "$file" ] && continue
  hits="$(grep -Ean "$pattern" "$file" 2>/dev/null | grep -Ev "$placeholder" || true)"
  if [ -n "$hits" ]; then
    echo "POTENTIAL SECRET in $file:"
    echo "$hits"
    found=1
  fi
done <<< "$tracked"
if [ "$found" -eq 0 ]; then
  echo "OK: no secret patterns found in tracked files."
else
  echo "FAIL: possible secrets detected — review before committing."
  fail=1
fi

# ---------------------------------------------------------------------------
# 2. API health + performance sample (skipped if the API is not reachable).
# ---------------------------------------------------------------------------
section "API health"
if ! curl -fsS -m 3 "$API_BASE_URL/health/live" >/dev/null 2>&1; then
  echo "SKIP: API not reachable at $API_BASE_URL (start uvicorn to include health + perf)."
else
  echo "OK: $API_BASE_URL/health/live responded."

  section "Performance sample (/health/live x $PERF_SAMPLES)"
  times_ms=()
  for _ in $(seq 1 "$PERF_SAMPLES"); do
    t="$(curl -fsS -o /dev/null -w '%{time_total}' -m 5 "$API_BASE_URL/health/live" 2>/dev/null || echo 0)"
    ms="$(awk "BEGIN{printf \"%d\", $t*1000}")"
    times_ms+=("$ms")
  done
  sorted="$(printf '%s\n' "${times_ms[@]}" | sort -n)"
  count="$(printf '%s\n' "$sorted" | grep -c .)"
  p95_index="$(awk "BEGIN{i=int(0.95*($count-1)+1); print i}")"
  p95="$(printf '%s\n' "$sorted" | sed -n "${p95_index}p")"
  max="$(printf '%s\n' "$sorted" | tail -1)"
  avg="$(printf '%s\n' "${times_ms[@]}" | awk '{s+=$1} END{printf "%d", s/NR}')"
  echo "avg=${avg}ms p95=${p95}ms max=${max}ms budget(p95)=${PERF_P95_BUDGET_MS}ms"
  if [ "${p95:-0}" -gt "$PERF_P95_BUDGET_MS" ]; then
    echo "WARN: p95 exceeds budget."
  else
    echo "OK: p95 within budget."
  fi
fi

section "Result"
if [ "$fail" -eq 0 ]; then
  echo "SMOKE TEST PASSED"
  exit 0
fi
echo "SMOKE TEST FAILED"
exit 1
