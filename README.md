# 📄 AI Resume Analyzer

An end-to-end, production-style application that analyzes a resume against
a job description and returns a match score, skill gap analysis, and
AI-generated improvement suggestions — built entirely with **free tools**.

Works across professions, not just tech: the skill matcher and LLM prompt
cover healthcare, finance/accounting, marketing/sales, education, legal,
operations/HR, design, and hospitality/retail in addition to software roles.

> Built to demonstrate: API design, local + LLM-based NLP, input validation
> and security hardening, testing, containerization, and CI/CD — not just
> "call an AI API and print the result."

## Live demo

- Frontend: https://resume-analyser-c7gcwwntw3lad9j3lxtkc3.streamlit.app/
- Backend API docs: https://ai-resume-analyzer-api.onrender.com/docs

## Architecture

```
┌──────────────┐        HTTP        ┌──────────────────┐
│  Streamlit    │ ─────────────────▶ │   FastAPI backend │
│  frontend     │ ◀───────────────── │                    │
└──────────────┘        JSON        └─────────┬──────────┘
                                               │
                     ┌─────────────────────────┼─────────────────────────┐
                     │                         │                         │
              ┌──────▼──────┐          ┌───────▼────────┐        ┌───────▼───────┐
              │ pdfplumber/  │          │ spaCy (local,   │        │ Groq API      │
              │ python-docx  │          │ free) + TF-IDF   │        │ (free tier    │
              │ (parsing)    │          │ (scikit-learn)   │        │ LLM reasoning)│
              └──────────────┘          └─────────────────┘        └───────────────┘
                                               │
                                        ┌───────▼────────┐
                                        │ PostgreSQL/     │
                                        │ SQLite (metrics │
                                        │ only, no PII)   │
                                        └────────────────┘
```

## Tech stack

| Layer | Tool |
|---|---|
| Backend API | FastAPI (async, auto-documented) |
| Resume parsing | pdfplumber, python-docx |
| Local NLP | spaCy, scikit-learn (TF-IDF similarity) |
| LLM reasoning | Groq API (Llama 3.3 70B, free tier) |
| Database | PostgreSQL (prod) / SQLite (dev) via SQLAlchemy |
| Rate limiting | slowapi |
| Auth | JWT (python-jose) + bcrypt password hashing |
| Frontend | Streamlit |
| Containerization | Docker + docker-compose |
| CI | GitHub Actions (lint + test on every push) |

## Key engineering decisions

- **No PII persistence** — only a SHA-256 request hash and the numeric
  score are stored, so the database never holds raw resume content.
- **Defense in depth on uploads** — file type is verified via magic
  bytes (not extension), size is capped, and extracted text is
  sanitized before it reaches the LLM.
- **Graceful degradation** — corrupt files, LLM timeouts, and malformed
  LLM responses all return clean HTTP errors instead of crashing the
  worker or leaking stack traces.
- **Cost control** — a local TF-IDF similarity score plus a
  keyword-based skill matcher run before/alongside the LLM call, and a
  DB-backed cache means repeated identical requests don't burn free-tier
  LLM quota.
- **Stateless backend** — no in-memory session state, so it can be
  horizontally scaled behind a load balancer.
- **Optional authentication** — JWT-based auth (bcrypt-hashed passwords,
  stateless tokens) lets users optionally create an account to save their
  analysis history; `/analyze` works fully anonymously too, so auth never
  gates the core feature. Only match scores and timestamps are saved to
  history — never resume text or job descriptions.

## Authentication

- `POST /api/v1/auth/register` — create an account (email + password, bcrypt-hashed)
- `POST /api/v1/auth/login` — OAuth2-compatible login, returns a JWT access token
- `GET /api/v1/auth/me` — returns the current authenticated user
- `GET /api/v1/history` — returns the logged-in user's past match scores (requires a valid token)
- `POST /api/v1/analyze` accepts an optional `Authorization: Bearer <token>` header — if present, the result is linked to that user's history; if absent, the analysis still runs normally for anonymous use

## Project structure

```
ai-resume-analyzer/
├── app/
│   ├── main.py              # FastAPI app, middleware, startup
│   ├── api/routes.py         # /analyze, /health endpoints
│   ├── core/                 # config, security, logging
│   ├── services/              # parser, nlp_engine, llm_client, scorer
│   ├── models/schemas.py       # Pydantic request/response models
│   └── db/                     # SQLAlchemy engine + models
├── frontend/streamlit_app.py
├── tests/                        # pytest suite
├── .github/workflows/ci.yml
├── Dockerfile / docker-compose.yml
├── requirements.txt
└── .env.example
```

## Setup (local development)

### 1. Clone and install

```bash
git clone https://github.com/<your-username>/ai-resume-analyzer.git
cd ai-resume-analyzer
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure environment

```bash
cp .env.example .env
```

Get a **free** Groq API key at https://console.groq.com/keys and add it to `.env`.

### 3. Run the backend

```bash
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`.

### 4. Run the frontend (separate terminal)

```bash
streamlit run frontend/streamlit_app.py
```

Visit `http://localhost:8501`.

### 5. Run with Docker instead

```bash
docker-compose up --build
```

### 6. Run tests

```bash
pytest tests/ -v
ruff check app tests
```

## Deployment (all free tiers)

1. **Backend** → push to GitHub, connect the repo on [Render](https://render.com)
   or [Railway](https://railway.app), set environment variables from `.env.example`
   in the dashboard, deploy as a Docker service using the included `Dockerfile`.
2. **Database** → free Postgres instance on [Neon](https://neon.tech) or
   [Supabase](https://supabase.com); paste the connection string into `DATABASE_URL`.
3. **Frontend** → deploy `frontend/streamlit_app.py` on
   [Streamlit Community Cloud](https://streamlit.io/cloud), set `BACKEND_URL`
   to your deployed backend's public URL.
4. **CI** → GitHub Actions (`.github/workflows/ci.yml`) runs lint + tests
   automatically on every push/PR.

## What I'd improve with more time


- Move the LLM call to a background task queue (Celery/RQ) so the
  request thread never blocks on external API latency.
- Add OCR fallback (e.g. `pytesseract`) for scanned/image-based PDFs.
- Add a proper Redis-backed cache layer in front of the DB cache.
- Expand the skill vocabulary using a maintained taxonomy (e.g. ESCO or
  O*NET) instead of hardcoded per-field lists — the current lists are a
  solid starting point covering tech, healthcare, finance, marketing,
  education, legal, operations/HR, design, and hospitality/retail, but a
  real taxonomy would generalize further.

## License

MIT — see [LICENSE](LICENSE).
