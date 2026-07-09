# TalentIQ — Engineering Guide

> **Purpose:** This document is the single source of truth for anyone building, debugging, or extending TalentIQ. Read this before touching any code.

---

## Table of Contents

1. [What TalentIQ Is](#1-what-talentiq-is)
2. [Overall Architecture](#2-overall-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Module Breakdown](#4-module-breakdown)
5. [Database Schema](#5-database-schema)
6. [AI / LLM Engine](#6-ai--llm-engine)
7. [Environment Variables](#7-environment-variables)
8. [Local Development Setup](#8-local-development-setup)
9. [Deployment (Railway)](#9-deployment-railway)
10. [Authentication System](#10-authentication-system)
11. [Coding Standards](#11-coding-standards)
12. [Common Errors and Fixes](#12-common-errors-and-fixes)
13. [Recovery Procedures](#13-recovery-procedures)
14. [Release Checklist](#14-release-checklist)

---

## 1. What TalentIQ Is

TalentIQ is a multi-tenant SaaS ATS (Applicant Tracking System) built for healthcare recruitment in Mozambique and the wider Lusophone Africa market.

**Core value proposition:**
- Upload CVs (PDF/DOCX) → AI extracts structured candidate profiles
- Upload Terms of Reference (ToR) → AI extracts structured job vacancy data
- AI scores each candidate against each vacancy (0–100 fit score)
- Manage candidates through a recruitment pipeline
- Export ranked shortlists to Excel and Word reports

**Tech stack:**
- Backend: Django 6.0.7 (Python 3.14)
- Frontend: Tailwind CSS (CDN) + HTMX 1.9 + Font Awesome 6
- Database: PostgreSQL (Railway) / SQLite (local dev)
- AI: Grok-3 (xAI) via OpenAI-compatible API — with deterministic fallback
- Deployment: Railway (nixpacks + gunicorn)
- File exports: openpyxl (Excel), python-docx (Word)

---

## 2. Overall Architecture

```
Browser
  |
  | HTTPS
  v
Railway (gunicorn — 2 workers)
  |
  |-- Django Middleware Stack
  |     AutoLoginMiddleware / LoginRequiredMiddleware (auth gate)
  |     HtmxMiddleware (detects HTMX requests)
  |     WhiteNoiseMiddleware (serves static files)
  |
  |-- URL Router (talentiq/urls.py)
  |     /              → dashboard
  |     /vagas/        → job vacancies CRUD
  |     /candidatos/   → candidates CRUD + CV upload
  |     /scoring/      → fit scoring + exports
  |     /pipeline/     → recruitment pipeline board
  |     /gestao/       → user management (built-in)
  |     /ajuda/        → help page
  |     /admin/        → Django admin
  |     /setup/        → one-time admin setup (remove after use)
  |
  |-- Django Apps
  |     accounts       → Organisation + User models + auth
  |     vagas          → Vaga (job vacancy) model + views
  |     candidatos     → Candidato model + views + CV upload
  |     scoring        → fit score calculation + Excel/Word export
  |     pipeline       → recruitment pipeline board
  |     ajuda          → help/onboarding page
  |
  |-- Core Engine (core/)
  |     parser.py      → CV and ToR text extraction + parsing
  |     scorer.py      → fit score calculation (LLM + deterministic)
  |     llm.py         → pluggable LLM client (Grok / OpenAI / deterministic)
  |
  v
Railway PostgreSQL Database
```

**Request flow for CV upload:**
```
User uploads PDF → candidatos/views.py → core/parser.py
  → extract_text_from_file() [pdfplumber]
  → parse_cv() → _parse_with_llm() [Grok API]
  → fallback: _parse_deterministic() [regex + keyword matching]
  → Candidato saved to PostgreSQL
```

**Request flow for scoring:**
```
User clicks "Calcular" → scoring/views.py → core/scorer.py
  → calcular_fit() → _score_with_llm() [Grok API]
  → fallback: _score_deterministic() [competencia matching + exp + education]
  → score_fit + perfil_completo saved to Candidato
  → HTMX re-renders candidate table
```

---

## 3. Repository Structure

```
TalentIQ_Web/
├── manage.py
├── config.py               # Compatibility shim: bridges desktop config to Django
├── requirements.txt        # Production dependencies
├── nixpacks.toml           # Railway build config
├── railway.json            # Railway start command (OVERRIDES nixpacks.toml start)
├── Procfile                # Fallback start config
├── .gitignore
├── ENGINEERING.md          # This file
│
├── talentiq/               # Django project package
│   ├── settings.py         # All settings — reads from env vars
│   ├── urls.py             # Root URL configuration
│   ├── middleware.py       # Auth middleware (AutoLogin or LoginRequired)
│   ├── dashboard.py        # Dashboard view
│   ├── gestao_views.py     # Built-in user management views
│   ├── setup_view.py       # One-time admin setup URL (REMOVE AFTER USE)
│   ├── wsgi.py
│   └── asgi.py
│
├── accounts/               # Authentication and multi-tenancy
│   ├── models.py           # Organisation + User
│   ├── views.py            # login, logout, register
│   ├── forms.py            # LoginForm (email-based) + RegisterForm
│   ├── backends.py         # EmailBackend (case-insensitive email auth)
│   ├── admin.py            # Django admin registration
│   ├── urls.py
│   └── management/
│       └── commands/
│           └── seed_admin.py  # Auto-creates admin user on deploy
│
├── vagas/                  # Job vacancies
│   ├── models.py           # Vaga model
│   ├── views.py            # CRUD + ToR upload
│   └── urls.py
│
├── candidatos/             # Candidates
│   ├── models.py           # Candidato model
│   ├── views.py            # CRUD + CV upload
│   └── urls.py
│
├── scoring/                # Fit scoring + exports
│   ├── views.py            # score_calculate, exportar_excel, exportar_word
│   └── urls.py
│
├── pipeline/               # Recruitment pipeline board
│   ├── views.py
│   └── urls.py
│
├── ajuda/                  # Help page
│   └── views.py
│
├── core/                   # AI engine (shared, framework-agnostic)
│   ├── parser.py           # CV + ToR parsing (LLM + deterministic)
│   ├── scorer.py           # Fit scoring (LLM + deterministic)
│   └── llm.py              # LLM client abstraction
│
├── templates/              # All HTML templates
│   ├── base.html           # Master layout with sidebar
│   ├── dashboard.html
│   ├── accounts/
│   ├── vagas/
│   ├── candidatos/
│   ├── scoring/
│   ├── pipeline/
│   ├── gestao/
│   └── ajuda/
│
└── static/                 # Static assets
    └── .gitkeep
```

---

## 4. Module Breakdown

### talentiq/settings.py
Reads all configuration from environment variables. Key logic:
- `DATABASE_URL` present → use PostgreSQL via `dj_database_url`
- `DATABASE_URL` absent → use SQLite (local dev)
- `RAILWAY_PUBLIC_DOMAIN` → auto-appended to `ALLOWED_HOSTS`
- `DEBUG=True` in dev, `DEBUG=False` in production (set in Railway Variables)

### talentiq/middleware.py
Two modes — swap by changing the class name in `settings.py MIDDLEWARE`:

| Class | Behaviour |
|---|---|
| `AutoLoginMiddleware` | Logs in first active user automatically — no login required (demo mode) |
| `LoginRequiredMiddleware` | Redirects unauthenticated users to `/accounts/login/` (production mode) |

**IMPORTANT:** `railway.json` `startCommand` overrides `nixpacks.toml` start. Always update `railway.json` when changing the startup sequence.

### accounts/backends.py — EmailBackend
Django's default `ModelBackend` authenticates by `username` field (exact match). Our `EmailBackend` authenticates by `email` field (case-insensitive). This is critical because the register form stores `username = email.lower()` but users may type their email in any case at login.

Both backends are active in `AUTHENTICATION_BACKENDS` — EmailBackend is tried first.

### core/llm.py — LLM Client
Pluggable client controlled by `LLM_ENGINE` env var:
- `grok` → calls xAI Grok API at `https://api.x.ai/v1` using model `grok-3`
- `openai` → calls OpenAI API using model `gpt-4o`
- `deterministic` → skips LLM entirely

All LLM calls return `None` on failure — callers always fall back to deterministic logic.

### core/parser.py — CV and ToR Parser
Two public functions:
- `parse_cv(text)` → returns structured candidate dict
- `parse_tor(text)` → returns structured vacancy dict

Both follow the same pattern: try LLM → parse JSON response → on failure, run deterministic hybrid parser (regex + keyword matching from `config.py` keyword lists).

### core/scorer.py — Fit Scorer
Public function: `calcular_fit(candidato_dict, vaga_dict)` → returns score dict.

**Scoring dimensions (deterministic):**

| Dimension | Weight | Logic |
|---|---|---|
| Competencias | 50 pts | Synonym-aware matching of candidate skills vs vacancy requirements |
| Experiencia | 30 pts | Graduated: meets min=25pts, exceeds 1.5x=30pts, below=proportional |
| Formacao | 20 pts | Education hierarchy: licenciatura=2, mestrado=3, doutoramento=4 |

**Output format:**
```json
{
  "score_total": 78,
  "pontuacao_detalhada": {"competencias": 40, "experiencia": 25, "formacao": 13},
  "nivel_alinhamento": "Alto Alinhamento",
  "cor": "green",
  "explicacao": ["list of explanation strings"],
  "metodo": "LLM (grok) | Determinístico"
}
```

### accounts/management/commands/seed_admin.py
Runs on every Railway deploy (called in `railway.json` startCommand).
- Creates organisation "TalentIQ Demo" if none exists
- Creates/updates `ngaspar10@gmail.com` as superuser with password from `ADMIN_PASSWORD` env var (default: `TalentIQ2024!`)
- Idempotent — safe to run multiple times

---

## 5. Database Schema

### Organisation
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | auto-generated |
| name | CharField(255) | e.g. "Clínica Esperança" |
| slug | SlugField(100) | unique, URL-safe |
| is_active | Boolean | default True |
| created_at | DateTime | auto |

### User (extends AbstractUser)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | overrides int PK |
| username | CharField | set to email address |
| email | EmailField | used for login |
| organisation | FK → Organisation | nullable |
| role | CharField | admin / recruiter / viewer |
| is_superuser | Boolean | required for /admin/ access |
| is_staff | Boolean | required for /admin/ access |

### Vaga (Job Vacancy)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| organisation | FK → Organisation | multi-tenant isolation |
| titulo | CharField(255) | job title |
| organizacao | CharField(255) | hiring organisation name |
| departamento | CharField | choices field |
| local | CharField | location |
| modalidade | CharField | Presencial/Remoto/Híbrido |
| nivel_formacao | CharField | education requirement |
| anos_experiencia_min | PositiveInt | minimum years |
| tipo_contrato | CharField | contract type |
| competencias_requeridas | JSONField | list of required skills |
| responsabilidades | JSONField | list of responsibilities |
| descricao | TextField | full description |
| estado | CharField | Aberta/Fechada/Suspensa |
| tor_file_path | CharField | path to uploaded ToR file (temporary) |

### Candidato (Candidate)
| Field | Type | Notes |
|---|---|---|
| id | UUID PK | |
| organisation | FK → Organisation | multi-tenant isolation |
| vaga | FK → Vaga | nullable — candidate may not be linked to a vacancy |
| nome | CharField(255) | full name |
| email | EmailField | |
| telefone | CharField | |
| experiencia_anos | PositiveInt | years of experience |
| competencias | JSONField | list of skills |
| formacao | JSONField | list of education entries |
| idiomas | JSONField | list of languages |
| resumo | TextField | professional summary |
| etapa | CharField | pipeline stage |
| score_fit | PositiveInt | 0–100 fit score (null = not scored) |
| notas | TextField | recruiter notes |
| cv_file_path | CharField | path to uploaded CV (temporary — not persisted across redeploys) |
| perfil_completo | JSONField | full AI scoring output including explanation |

**⚠️ Important:** `cv_file_path` stores a filesystem path inside the Railway container. This path is **wiped on every redeploy**. The actual CV content is extracted and stored in `perfil_completo` (JSONField in PostgreSQL), which persists. Only the raw file is lost.

---

## 6. AI / LLM Engine

### Configuration
```
LLM_ENGINE=grok          # grok | openai | deterministic
GROK_API_KEY=xai-...     # from console.x.ai
GROK_BASE_URL=https://api.x.ai/v1   # hardcoded in config.py
GROK_MODEL=grok-3                   # hardcoded in config.py
```

### Fallback Chain
Every AI operation has a deterministic fallback:
```
LLM call → success → use LLM result
         → failure (any exception, timeout, bad JSON) → use deterministic result
```

The deterministic engine always produces a result. The app never shows an error to the user because of an AI failure.

### config.py — Compatibility Shim
`core/` was originally written for a desktop app and imports `config` as a top-level module. In Django (Railway), the project root may not be on `sys.path`. Both `core/scorer.py` and `core/llm.py` handle this with a try/except that falls back to reading from Django settings directly.

---

## 7. Environment Variables

Set in Railway → web service → Variables tab.

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Django secret key — generate with `python -c "import secrets; print(secrets.token_hex(50))"` |
| `DEBUG` | Yes | `False` in production, `True` in dev |
| `ALLOWED_HOSTS` | Yes | comma-separated, e.g. `localhost,127.0.0.1,web-production-d01715.up.railway.app` |
| `DATABASE_URL` | Auto | injected by Railway PostgreSQL service — do NOT set manually |
| `GROK_API_KEY` | Yes | API key from console.x.ai — must start with `xai-` |
| `LLM_ENGINE` | Yes | `grok` for production |
| `ADMIN_PASSWORD` | No | password for seed_admin user (default: `TalentIQ2024!`) |
| `SUPABASE_URL` | Future | for permanent CV file storage |
| `SUPABASE_KEY` | Future | for permanent CV file storage |
| `RAILWAY_PUBLIC_DOMAIN` | Auto | injected by Railway — used for ALLOWED_HOSTS |

**⚠️ Critical:** Never manually set `DATABASE_URL` in Railway Variables. The Railway PostgreSQL service injects the correct value automatically as one of the "8 variables added by Railway". A manually set `DATABASE_URL` overrides the correct one and breaks the database connection.

---

## 8. Local Development Setup

```powershell
# 1. Clone
git clone https://github.com/Ngaspar20/TalentIQ-web.git
cd TalentIQ-web

# 2. Create .env file
echo SECRET_KEY=django-insecure-local-dev-key > .env
echo DEBUG=True >> .env
echo GROK_API_KEY=xai-your-key-here >> .env
echo LLM_ENGINE=grok >> .env

# 3. Install dependencies (use Python 3.12+ recommended)
pip install -r requirements.txt

# 4. Run migrations
python manage.py migrate

# 5. Create local admin user
python manage.py seed_admin

# 6. Run dev server
python manage.py runserver

# App available at http://127.0.0.1:8000
```

Local dev uses SQLite (`db.sqlite3`) — no PostgreSQL needed.

---

## 9. Deployment (Railway)

### First-time setup
1. Push repo to GitHub
2. Railway → New Project → GitHub Repository → select repo
3. Add PostgreSQL service: Railway project → New → Database → PostgreSQL
4. Set environment variables (see section 7)
5. Railway auto-deploys on every push to `main`

### Startup sequence (railway.json)
```json
{
  "startCommand": "python manage.py migrate --noinput && python manage.py seed_admin && gunicorn talentiq.wsgi --bind 0.0.0.0:$PORT --workers 2"
}
```

**Order matters:**
1. `migrate` — applies any new DB migrations
2. `seed_admin` — ensures admin user exists
3. `gunicorn` — starts the web server

### Build sequence (nixpacks.toml)
```toml
[phases.build]
cmds = [
  "pip install -r requirements.txt",
  "python manage.py collectstatic --noinput"
]
```

**⚠️ `railway.json` takes priority over `nixpacks.toml` for the start command.** Always update `railway.json` when changing startup logic.

### Static files
WhiteNoise serves static files directly from gunicorn — no nginx or CDN needed. `STATICFILES_STORAGE = CompressedManifestStaticFilesStorage` (auto-versioned).

---

## 10. Authentication System

### Two modes (swap in settings.py MIDDLEWARE list)

**Demo mode (AutoLoginMiddleware):**
- Any visitor is automatically logged in as the first active user
- No login page shown
- Use for client demos where frictionless access is needed

**Production mode (LoginRequiredMiddleware):**
- All routes require authentication except `/accounts/login/`, `/accounts/register/`, `/admin/`, `/setup/`
- Unauthenticated requests → redirect to `/accounts/login/?next=<original_url>`

### Login form
Uses `email` as the username field. The `EmailBackend` authenticates by looking up `User.objects.get(email__iexact=username)` — case-insensitive.

### Registration
`/accounts/register/` → `RegisterForm.save()`:
- Creates `Organisation` with unique slug
- Creates `User` with `username = email.lower()` (so both backends can find them)
- Role: `ROLE_ADMIN` (organisation owner)

### Multi-tenancy
Every model has a `organisation` FK. Views filter all querysets by `request.user.organisation`. Users from different organisations never see each other's data.

### /setup/promote/ (emergency admin reset)
A one-time URL that deletes and recreates the admin user with a known password. **Remove this URL in production** by deleting `talentiq/setup_view.py` and its URL entry.

---

## 11. Coding Standards

- **No `@login_required` decorators** — authentication is handled globally by middleware
- **No nested `<form>` elements** — browsers silently ignore inner forms; use separate `<form>` elements or `<a>` links for each action
- **HTMX targets** — all HTMX responses must render partial templates (prefix with `_`), not full pages
- **CSRF for HTMX** — handled globally in `base.html` via `htmx:configRequest` event listener; do not add `X-CSRFToken` headers manually
- **No `split` template filter** — Django has no built-in `split` filter; use hardcoded `<option>` elements
- **Portuguese** — all UI text, template labels, and user-facing strings in Portuguese (pt-BR/pt-MZ)
- **No emojis** — use Font Awesome icons only (`<i class="fa-solid fa-...">`)
- **UUIDs as PKs** — all models use `UUIDField(primary_key=True)`
- **File editing** — always use Python scripts (not PowerShell `Set-Content`) for files with Portuguese characters to avoid UTF-8 corruption

---

## 12. Common Errors and Fixes

### "Application failed to respond" on Railway
**Cause:** App crashes at startup before gunicorn can bind to port.
**Fix:** Check Railway deployment logs → View logs. Common sub-causes:
- Import error in any module (check `from X import Y` statements)
- Missing migration (run `python manage.py migrate`)
- `DATABASE_URL` pointing to wrong host

### "could not translate host name 'host' to address"
**Cause:** `DATABASE_URL` was manually set in Railway Variables with a placeholder value, overriding the real PostgreSQL URL injected by Railway.
**Fix:** Delete the manually set `DATABASE_URL` variable in Railway → Variables tab. Railway will use its own injected value.

### "Invalid filter: 'split'"
**Cause:** Django templates do not have a built-in `split` filter.
**Fix:** Replace `"a,b,c"|split:","` loops with hardcoded `<option>` elements in the template.

### Login not working after logout
**Cause 1:** User record has `username != email` (e.g., username is "admin" but login form submits email).
**Fix:** Ensure `EmailBackend` is in `AUTHENTICATION_BACKENDS` and `username` field equals the email address.
**Cause 2:** `seed_admin` creates user with wrong username on each deploy.
**Fix:** `seed_admin` now uses `email` as both `username` and `email` fields.

### Scoring shows "Sem score" (no scores calculated)
**Cause 1:** `import config` fails in `core/scorer.py` because project root is not on `sys.path` in Railway.
**Fix:** Both `core/scorer.py` and `core/llm.py` have try/except that falls back to Django settings.
**Cause 2:** HTMX recalculate buttons were nested inside a GET `<form>` — inner forms are ignored by browsers.
**Fix:** Each action must be a separate, non-nested `<form>` element.
**Cause 3:** Grok API key invalid or model name wrong.
**Fix:** Deterministic fallback always runs if LLM fails. Check `GROK_API_KEY` starts with `xai-`. Model is `grok-3`.

### Candidate missing from scoring page
**Cause:** Candidate has no `vaga` linked (FK is nullable).
**Fix:** Edit the candidate and assign them to a vacancy. The scoring page shows a warning banner for candidates without a vacancy.

### Django admin at /admin/ shows TalentIQ login page instead
**Cause:** `LoginRequiredMiddleware` intercepts `/admin/` before Django admin can handle its own auth.
**Fix:** Add `/admin/` to `PUBLIC_URLS` in `middleware.py`.

### PowerShell corrupts Portuguese characters in files
**Cause:** PowerShell `Set-Content` defaults to UTF-16 LE encoding.
**Fix:** Always use `Set-Content ... -Encoding utf8` or write files with Python scripts using `encoding='utf-8'`.

### Railway deployment fails at build — migrate error
**Cause:** `migrate` was in the build phase (`nixpacks.toml`) before the database is available.
**Fix:** `migrate` must be in the start command (`railway.json`), not the build phase.

### `railway.json` startCommand ignored
**Cause:** `nixpacks.toml` `[start]` cmd conflicts with `railway.json`.
**Fix:** `railway.json` takes priority. Keep start logic only in `railway.json`. Use `nixpacks.toml` only for build steps.

---

## 13. Recovery Procedures

### App is down (Railway shows failed deployment)
1. Go to Railway → Deployments → find last ACTIVE deployment
2. Click the three dots → Redeploy (rolls back to last working version)
3. Investigate the failed deployment logs before pushing a new fix

### Lost access to admin account
1. Temporarily add `/setup/promote/` URL (see `talentiq/setup_view.py`)
2. Visit the URL — it deletes and recreates `ngaspar10@gmail.com` with password `TalentIQ2024!`
3. Log in and change password via `/gestao/utilizadores/` or Django admin
4. Remove `/setup/promote/` from `urls.py` and push

### Database is empty after redeploy
**This should not happen** — Railway PostgreSQL persists across redeploys.
**If it does:** `seed_admin` runs on every deploy and recreates the admin user automatically. Other data (vagas, candidatos) cannot be automatically restored without a backup.

### Scoring stops working after code change
1. Check Railway logs for Python tracebacks
2. Most likely: import error in `core/scorer.py` or `core/llm.py`
3. The deterministic fallback is independent of LLM — if both fail, check `config.py` compatibility shim
4. Test locally: `python manage.py shell` → `from core.scorer import calcular_fit`

### CV upload stops working
1. `pdfplumber` handles PDFs — check it is in `requirements.txt`
2. `python-docx` handles DOCX — check it is in `requirements.txt`
3. File size limit is 10MB (`FILE_UPLOAD_MAX_MEMORY_SIZE` in settings)
4. Raw CV files are stored in Railway's temporary filesystem — they are wiped on redeploy. The extracted text in `perfil_completo` (PostgreSQL) persists.

---

## 14. Release Checklist

Before every production push:

**Code**
- [ ] No hardcoded credentials or API keys in code
- [ ] No `print()` debug statements left
- [ ] Portuguese spelling checked on all new UI text
- [ ] No nested `<form>` elements in new templates
- [ ] HTMX partial templates prefixed with `_`
- [ ] `/setup/promote/` URL removed from `urls.py`

**Database**
- [ ] New model fields have `null=True, blank=True` or a `default` value (so migrations don't break existing data)
- [ ] Migration file created and committed (`python manage.py makemigrations`)

**Deployment**
- [ ] `railway.json` startCommand includes `migrate` and `seed_admin`
- [ ] `requirements.txt` updated for any new packages
- [ ] `DEBUG=False` in Railway Variables
- [ ] `SECRET_KEY` is set and not the insecure dev key
- [ ] `DATABASE_URL` is NOT manually set (let Railway inject it)
- [ ] `GROK_API_KEY` starts with `xai-`

**After deploy**
- [ ] Railway deployment shows ACTIVE (green)
- [ ] App loads at production URL
- [ ] Login works with admin credentials
- [ ] CV upload works (upload a test PDF)
- [ ] Scoring calculates (at least deterministic fallback)
- [ ] Excel and Word exports download correctly

---

*Last updated: July 2026*
*Stack: Django 6.0.7 · Python 3.14 · PostgreSQL · Grok-3 · Railway*
*Repository: https://github.com/Ngaspar20/TalentIQ-web*
