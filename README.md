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
| OCR fallback | Tesseract (via pytesseract) + PyMuPDF for scanned PDFs |
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
- **OCR fallback with graceful degradation** — scanned/image-based PDFs
  are handled via Tesseract OCR, but if the Tesseract binary isn't
  installed (e.g. a fresh dev machine, or a hosting environment that
  doesn't have it), the app doesn't crash — it falls back to a clear
  "couldn't extract text" error instead. OCR accuracy is inherently
  imperfect (misreads on stylized fonts, tables, etc.), so this is a
  best-effort fallback, not a guarantee — and it costs meaningfully more
  CPU/memory per request than the normal text-layer path, since it
  rasterizes each page to an image before running recognition on it.

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

### 2. Install Tesseract OCR (optional but recommended)

Scanned/image-based PDF resumes are handled via OCR, which needs the
**Tesseract** system binary (separate from the `pytesseract` Python
package already in `requirements.txt`). The app works fine without it —
scanned PDFs will just get a clear "couldn't extract text" error instead
of being OCR'd.

- **Windows**: download and run the installer from the
  [UB-Mannheim Tesseract build](https://github.com/UB-Mannheim/tesseract/wiki),
  keeping the default install path. If `pytesseract` can't find it automatically,
  set the path explicitly near the top of `app/services/parser.py`:
  ```python
  import pytesseract
  pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
  ```
- **Mac**: `brew install tesseract`
- **Linux**: `sudo apt-get install tesseract-ocr`

The Docker image and CI pipeline already install this for you — this step
is only needed if you're running `uvicorn` directly on your own machine.

### 3. Configure environment

```bash
cp .env.example .env
```

Get a **free** Groq API key at https://console.groq.com/keys and add it to `.env`.

### 4. Run the backend

```bash
uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs`.

### 5. Run the frontend (separate terminal)

```bash
streamlit run frontend/streamlit_app.py
```

Visit `http://localhost:8501`.

### 6. Run with Docker instead

```bash
docker-compose up --build
```

### 7. Run tests

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
- Add a proper Redis-backed cache layer in front of the DB cache.
- Expand the skill vocabulary using a maintained taxonomy (e.g. ESCO or
  O*NET) instead of hardcoded per-field lists — the current lists are a
  solid starting point covering tech, healthcare, finance, marketing,
  education, legal, operations/HR, design, and hospitality/retail, but a
  real taxonomy would generalize further.

## License

MIT — see [LICENSE](LICENSE).
