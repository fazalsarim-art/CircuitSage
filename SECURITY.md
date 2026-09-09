# Security

CircuitSage is a portfolio project, not a hosted service with real users. This document
records the security controls that are implemented, how to report an issue, and the known
limitations that a production deployment would need to close.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository, or email the maintainer. Please do
not file public issues for suspected vulnerabilities. Include reproduction steps and the commit
hash. There is no bug-bounty program.

## Secrets policy

- No real secret (API key, password, token, cookie, or private connection string) is ever
  committed. Every value in a tracked file is a placeholder.
- Runtime configuration comes from environment variables / a local `.env` (gitignored) via
  `app/core/config.py`. `JWT_SECRET` must be ≥32 chars or the app refuses to start.
- `VITE_*` variables are bundled into the browser build and are therefore public by design —
  never place a secret in one.
- `scripts/smoke_test.sh` runs a secret-pattern scan over tracked files as a guard.

## Implemented controls

### Authentication & sessions
- Passwords hashed with Argon2 (`pwdlib`). `password_hash` is never returned by the API.
- Short-lived JWT access tokens (15 min) kept in browser memory only — never `localStorage`.
- Rotating refresh tokens (random, SHA-256 hashed at rest) in an HttpOnly, `SameSite=Lax`
  cookie scoped to `/api/v1/auth`; reuse of a rotated token revokes the whole family.
- **Login throttling**: a per-instance fixed-window limiter caps attempts per client IP + email
  (`LOGIN_RATE_LIMIT` per `LOGIN_RATE_WINDOW_SECONDS`), returning `429 too_many_attempts`.

### Authorization
- Role-based access (`member` / `admin`). Admin-only: document ingest, benchmark authoring &
  publish, eval runs, and the feedback review queue.
- Document visibility (`private` / `shared`) is enforced on every retrieval and on feedback
  corrected-evidence: a chunk can only be graded if it is visible to the feedback author.
- Conversations and their messages are owner-only.

### Input handling & abuse limits
- **Per-user daily query quota** (`users.daily_query_limit`, 1–10,000): enforced before
  retrieval on the chat endpoint, returning `429 daily_limit_exceeded`.
- Chat questions are length-bounded by schema (3–1000 chars); uploads are size- and
  page-bounded (`MAX_UPLOAD_BYTES`, `MAX_PDF_PAGES`) and validated as real PDFs.
- Model output is rendered as escaped text in the UI, never as HTML.
- Answers are citation-validated and fail closed to `INSUFFICIENT_EVIDENCE` on unknown or
  missing `[Cn]` labels — the model cannot fabricate a source.

### Transport & browser hardening
- Security headers on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options:
  DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin`, a strict
  `Content-Security-Policy` (`default-src 'none'`), and `Strict-Transport-Security` in
  production.
- CORS is restricted to the configured `FRONTEND_ORIGIN` with credentials.
- Interactive API docs (`/docs`, `/redoc`) are disabled when `APP_ENV=production`.

### Error handling & observability
- A single error envelope `{error:{code,message,request_id,details}}`. Unhandled exceptions
  return `500 internal_error` with **no** stack trace or internal detail; the full error is
  logged server-side against the request id.
- Every request carries an `X-Request-ID` (propagated or generated) for correlation.

### Dependency degradation
- Qdrant unavailable → dense/hybrid retrieval returns `503`; lexical search still works.
- No/invalid OpenAI key → generation returns `generation_failed` and embeddings degrade to
  `503` for dense — the app stays up and lexical retrieval is unaffected.

## Known limitations (would need work before real production use)

- The login limiter is in-memory and per-process; a multi-instance deployment needs a shared
  store (e.g. Redis). Tracked in `docs/threat-model.md`.
- No CSRF token on the refresh cookie; mitigated by `SameSite=Lax` and a scoped path, but a
  token would be stronger.
- No account lockout or CAPTCHA beyond rate limiting; no MFA.
- Daily quota resets at 00:00 UTC and is not configurable per role beyond the column value.
- Dependency CVE findings are recorded (with severity and mitigation) in the threat model
  rather than auto-remediated.
