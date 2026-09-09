# CircuitSage threat model

A lightweight STRIDE-style threat model for a single-tenant RAG service with member and admin
roles. Scope: the FastAPI backend, the React SPA, PostgreSQL (source of truth), Qdrant (derived
vector index), and the OpenAI API (embeddings + generation). This is a portfolio project; the
model is honest about what is and is not mitigated.

## Assets

| Asset | Why it matters |
|-------|----------------|
| User credentials & sessions | Account takeover |
| Private documents & their chunks | Confidential source material |
| Benchmark & eval data | Integrity of the measurement story |
| OpenAI / Qdrant keys | Cost and data exfiltration if leaked |
| Answer integrity | A fabricated but confident answer is the core product risk |

## Trust boundaries

1. Browser ↔ API (authenticated JSON over HTTPS in production).
2. API ↔ PostgreSQL / Qdrant (trusted network; credentials in env).
3. API ↔ OpenAI (outbound; provider is trusted but rate-limited and fallible).
4. Member ↔ Admin (privilege boundary inside the app).

## STRIDE analysis

### Spoofing
- **Threat:** credential stuffing / brute force on `/auth/login`.
  **Mitigation:** Argon2 hashing; per-IP+email login throttling (`429 too_many_attempts`).
  **Residual:** in-memory limiter is per-process (see limitations); no MFA.
- **Threat:** forged session.
  **Mitigation:** signed JWT access tokens; rotating hashed refresh tokens with family
  reuse-detection.

### Tampering
- **Threat:** a member edits another user's documents, conversations, or feedback.
  **Mitigation:** owner-only access checks; admin-only mutations for corpus/benchmark/eval.
- **Threat:** benchmark judgments altered after publication.
  **Mitigation:** published benchmark versions are immutable; corpus fingerprint recorded per
  eval run.
- **Threat:** poisoned feedback silently enters the benchmark.
  **Mitigation:** feedback never becomes a case automatically; only an admin can promote a
  reviewed item into a *draft* version, and only an admin can publish.

### Repudiation
- **Threat:** no record of who changed a review decision.
  **Mitigation:** append-only `feedback_events` audit trail; every request carries a correlation
  `X-Request-ID` that appears in logs and error envelopes.

### Information disclosure
- **Threat:** leaking `password_hash` or internal errors.
  **Mitigation:** hash never serialized; unhandled exceptions return a generic `500` with the
  detail logged server-side only.
- **Threat:** cross-user document access via retrieval.
  **Mitigation:** visibility filter applied to lexical, dense, hybrid, and rerank paths, and to
  feedback corrected-evidence.
- **Threat:** secrets committed to git.
  **Mitigation:** placeholder-only policy; `.env` gitignored; secret-pattern scan in the smoke
  test.

### Denial of service
- **Threat:** a single user exhausts OpenAI budget or CPU.
  **Mitigation:** per-user daily query quota; login throttling; upload size/page caps; bounded
  `top_k`/`candidate_k`.
  **Residual:** no global request-rate ceiling or per-org budget; a determined authenticated
  user can still spend up to their quota.

### Elevation of privilege
- **Threat:** a member reaches admin endpoints.
  **Mitigation:** `require_admin` dependency on all admin routes; role encoded in the signed
  token and re-checked against the DB user.

## Prompt-injection & answer-integrity risks

- Retrieved chunks are untrusted text. They are placed in the prompt as evidence, and the
  answer is **citation-validated**: an answer citing a label that was not supplied fails closed
  to `INSUFFICIENT_EVIDENCE`. The UI renders answer text escaped, never as HTML.
- The same model is not used to generate a question, assign final relevance, and judge its own
  answer without human verification — relevance judgments and draft-case promotion are human/
  admin actions.

## Dependency findings

Run `npm --prefix frontend audit` and review Python dependencies before release. Record any
finding here with **severity** and **mitigation** rather than silently upgrading across a phase
boundary:

| Date | Component | Advisory | Severity | Mitigation / status |
|------|-----------|----------|----------|---------------------|
| 2026-09-09 | (none recorded) | — | — | Baseline: `npm audit` clean at phase 11; Python deps pinned in `requirements.lock`. |

## Known limitations

- Login rate limiter is per-process/in-memory — needs a shared store for multi-instance.
- No CSRF token on the refresh cookie (mitigated by `SameSite=Lax` + scoped path).
- No MFA, account lockout, or CAPTCHA.
- No field-level encryption at rest beyond what PostgreSQL/host provide.
