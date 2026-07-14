# Security Policy

## Data handling

- Resumes are processed **in memory only**. Raw resume text and job
  descriptions are **never written to disk or database**.
- Only a SHA-256 hash of the request (for caching) and the resulting
  numeric match score are persisted — no personally identifiable
  information is stored.
- Uploaded files are validated by **magic bytes**, not file extension, to
  prevent disguised/malicious files from being processed.
- File size is capped (default 2MB, configurable via `MAX_UPLOAD_SIZE_MB`)
  to prevent resource-exhaustion attacks.
- Extracted text is sanitized (control characters and script tags
  stripped, length capped) before being passed to any downstream service.

## API security

- Rate limiting is enforced per-IP on the `/analyze` endpoint
  (`RATE_LIMIT_PER_MINUTE`, default 10/min) to protect the free LLM quota
  from abuse.
- CORS is restricted to an explicit allow-list (`ALLOWED_ORIGINS`) —
  wildcard origins are never used.
- All unhandled exceptions are caught by a global handler that logs the
  full error server-side but returns a generic message to the client,
  so internal stack traces are never leaked.
- API docs (`/docs`) are disabled automatically when `ENVIRONMENT=production`.

## Secrets

- All API keys and credentials are loaded from environment variables via
  `pydantic-settings`. Nothing is hardcoded in source.
- `.env` is git-ignored; only `.env.example` (with placeholder values) is
  committed.

## Reporting a vulnerability

This is a personal/portfolio project. If you find a security issue,
please open a GitHub issue or reach out directly rather than exploiting it.
