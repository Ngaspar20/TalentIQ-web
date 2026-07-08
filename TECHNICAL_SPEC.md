# TalentIQ Web — Technical Specification
**Version:** 1.0  
**Date:** 2026-07-08  
**Author:** TalentIQ Health Partners  

---

## 1. Project Overview

TalentIQ Web is a multi-tenant SaaS Applicant Tracking System (ATS) designed for healthcare recruitment in Mozambique. It replaces the desktop Streamlit prototype with a production-grade web application accessible via browser, requiring no local installation.

### 1.1 Business Context
- Current state: Streamlit desktop app, single-user, local data storage
- Target state: Multi-tenant web app, multiple organisations, cloud data storage
- Primary market: Healthcare organisations in Mozambique (NGOs, government health institutions, private clinics)
- Deployment model: SaaS — one platform, multiple client organisations

### 1.2 Core Features
1. **Criar Vaga** — Upload Terms of Reference (ToR), AI extracts job requirements automatically
2. **Carregar CV** — Upload candidate CVs, AI parses skills, experience and education
3. **Pontuação Fit** — Calculate candidate-job fit score using AI scoring engine
4. **Pipeline** — Kanban board tracking candidates through recruitment stages
5. **Scoring Geral** — Rankings and analytics across all candidates per job

---

## 2. Technology Stack

| Layer | Technology | Justification |
|---|---|---|
| Backend framework | Django 5.x | Python-native, built-in auth, admin, ORM — maintainable by solo developer |
| Dynamic UI | HTMX 1.9 | Dynamic interactions without JavaScript framework — Python developer friendly |
| CSS framework | Tailwind CSS 3.x | Utility-first, professional UI, no custom CSS required |
| Database | PostgreSQL 15 (Supabase) | Robust relational DB, managed hosting, free tier available |
| File storage | Supabase Storage | S3-compatible, handles CV/ToR uploads, per-organisation isolation |
| Task queue | None (v1) | AI calls handled synchronously; async queue added in v2 if needed |
| AI engine | Grok API (xAI) | Existing integration, OpenAI-compatible API, held server-side |
| Hosting | Railway | Simple deployment, GitHub auto-deploy, PostgreSQL add-on |
| Version control | Git | Local repository |

### 2.1 Python Dependencies
```
django>=5.0
django-htmx
whitenoise          # static file serving
psycopg2-binary     # PostgreSQL adapter
django-storages     # Supabase/S3 file storage
boto3               # S3-compatible storage client
openai              # Grok API (OpenAI-compatible)
python-docx         # DOCX parsing
pdfplumber          # PDF parsing
pandas              # data processing
openpyxl            # Excel export
python-dotenv       # environment variables
gunicorn            # production WSGI server
```

---

## 3. Architecture

### 3.1 High-Level Architecture

```
Browser (Client)
      │
      │ HTTPS
      ▼
Railway (Django App)
      │
      ├── PostgreSQL (Supabase) ── stores all structured data
      ├── Supabase Storage ──────── stores CV/ToR files
      └── Grok API (xAI) ─────────── AI parsing and scoring
```

### 3.2 Multi-Tenancy Model

Row-based isolation. Every table that contains client data includes an `organisation` foreign key. All Django views and querysets filter by `request.user.organisation` automatically via a base queryset mixin.

No data from Organisation A is ever accessible to Organisation B.

### 3.3 Request Flow

```
User request
    → Django middleware (authentication check)
    → View (filters queryset by organisation)
    → Template (renders HTML)
    → HTMX (partial page updates where needed)
    → Response
```

---

## 4. Project Structure

```
talentiq_web/
├── manage.py
├── requirements.txt
├── .env                        # environment variables (never committed)
├── .env.example                # template for .env
│
├── talentiq/                   # Django project settings
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/               # authentication, organisations, users
│   ├── vagas/                  # job postings (Criar Vaga)
│   ├── candidatos/             # CV upload and parsing (Carregar CV)
│   ├── scoring/                # fit scoring (Pontuação Fit + Scoring Geral)
│   └── pipeline/               # recruitment pipeline (Pipeline)
│
├── core/                       # business logic (moved from desktop app)
│   ├── __init__.py
│   ├── llm.py                  # Grok API integration
│   ├── parser.py               # CV and ToR text extraction
│   └── scorer.py               # fit scoring engine
│
├── templates/                  # Django HTML templates
│   ├── base.html               # base layout (navbar, sidebar, footer)
│   ├── accounts/
│   ├── vagas/
│   ├── candidatos/
│   ├── scoring/
│   └── pipeline/
│
└── static/                     # CSS, JS, images
    ├── css/
    ├── js/
    └── images/
```

---

## 5. Database Schema

### 5.1 Organisation
```
Organisation
├── id (UUID, PK)
├── name (varchar 255)
├── slug (varchar 100, unique)    # used in URLs
├── created_at (datetime)
└── is_active (boolean)
```

### 5.2 User
```
User (extends Django AbstractUser)
├── id (UUID, PK)
├── organisation (FK → Organisation)
├── email (unique)
├── first_name (varchar)
├── last_name (varchar)
├── role (varchar) — admin | recruiter | viewer
├── is_active (boolean)
└── created_at (datetime)
```

### 5.3 Vaga (Job Posting)
```
Vaga
├── id (UUID, PK)
├── organisation (FK → Organisation)
├── titulo (varchar 255)
├── organizacao (varchar 255)
├── departamento (varchar 100)
├── local (varchar 255)
├── modalidade (varchar 50)       — Presencial | Remoto | Híbrido
├── nivel_formacao (varchar 100)
├── anos_experiencia_min (integer)
├── tipo_contrato (varchar 100)
├── salario (varchar 100)
├── prazo_candidatura (varchar 100)
├── competencias_requeridas (JSONField)   — list of strings
├── responsabilidades (JSONField)          — list of strings
├── descricao (TextField)
├── estado (varchar 50)           — Aberta | Fechada | Suspensa
├── tor_file_path (varchar)       — Supabase Storage path
├── origem (varchar 100)
├── created_by (FK → User)
├── created_at (datetime)
└── updated_at (datetime)
```

### 5.4 Candidato (Candidate)
```
Candidato
├── id (UUID, PK)
├── organisation (FK → Organisation)
├── vaga (FK → Vaga)
├── nome (varchar 255)
├── email (varchar 255)
├── telefone (varchar 50)
├── experiencia_anos (integer)
├── competencias (JSONField)       — list of strings
├── formacao (JSONField)           — list of strings
├── idiomas (JSONField)            — list of strings
├── resumo (TextField)
├── etapa (varchar 100)            — pipeline stage
├── score_fit (integer, nullable)  — 0-100
├── notas (TextField)
├── cv_file_path (varchar)         — Supabase Storage path
├── perfil_completo (JSONField)    — full parsed profile
├── created_by (FK → User)
├── created_at (datetime)
└── updated_at (datetime)
```

### 5.5 Pipeline Stage Reference
```
Etapas (fixed values, not a table):
- Candidatura Recebida
- Em Triagem
- Entrevista
- Proposta
- Contratado
- Rejeitado
```

---

## 6. Django Apps — Detailed Specification

### 6.1 accounts

**Models:** Organisation, User (extended)

**Views:**
- `LoginView` — email + password login
- `LogoutView`
- `RegisterView` — create organisation + admin user
- `ProfileView` — edit name, password
- `OrganisationSettingsView` — organisation name, manage users
- `InviteUserView` — invite colleague by email

**URLs:**
```
/login/
/logout/
/register/
/profile/
/settings/
/settings/invite/
```

### 6.2 vagas

**Models:** Vaga

**Views:**
- `VagaListView` — list all job postings for the organisation
- `VagaCreateView` — upload ToR, AI extraction, form review, save
- `VagaDetailView` — view job details
- `VagaEditView` — edit existing job
- `VagaDeleteView` — delete job (with confirmation)
- `TorParseView` (HTMX) — async ToR parsing, returns pre-filled form fields

**URLs:**
```
/vagas/
/vagas/criar/
/vagas/<id>/
/vagas/<id>/editar/
/vagas/<id>/eliminar/
/vagas/parse-tor/          # HTMX endpoint
```

### 6.3 candidatos

**Models:** Candidato

**Views:**
- `CandidatoListView` — list all candidates
- `CandidatoCreateView` — upload CV, AI parsing, form review, save
- `CandidatoDetailView` — candidate profile
- `CandidatoEditView` — edit candidate
- `CandidatoDeleteView` — delete candidate
- `CvParseView` (HTMX) — async CV parsing, returns pre-filled form fields

**URLs:**
```
/candidatos/
/candidatos/carregar/
/candidatos/<id>/
/candidatos/<id>/editar/
/candidatos/<id>/eliminar/
/candidatos/parse-cv/      # HTMX endpoint
```

### 6.4 scoring

**Views:**
- `ScoringView` — select job, calculate scores for all candidates, display results
- `ScoreCalculateView` (HTMX) — calculate score for one candidate, return result
- `ScoringGeralView` — global rankings across all jobs

**URLs:**
```
/scoring/
/scoring/<vaga_id>/
/scoring/calcular/         # HTMX endpoint
/scoring/geral/
```

### 6.5 pipeline

**Views:**
- `PipelineView` — kanban board + funnel chart + full table
- `MoverEtapaView` (HTMX) — move candidate to new stage
- `PipelineExportView` — export to Excel

**URLs:**
```
/pipeline/
/pipeline/<vaga_id>/
/pipeline/mover/           # HTMX endpoint
/pipeline/exportar/
```

---

## 7. Authentication and Authorisation

### 7.1 Authentication
- Django session-based authentication
- Login required on all views (LoginRequiredMixin)
- No public pages except /login/ and /register/

### 7.2 Authorisation (Roles)
| Role | Permissions |
|---|---|
| admin | Full access — create/edit/delete everything, manage users, organisation settings |
| recruiter | Create/edit/delete vagas and candidatos, run scoring, manage pipeline |
| viewer | Read-only access to all data |

### 7.3 Organisation Isolation
All views inherit from `OrganisationQuerysetMixin` which automatically filters every queryset by `request.user.organisation`. Direct URL access to another organisation's data returns 404.

---

## 8. AI Integration

### 8.1 Configuration
- Grok API key stored as environment variable `GROK_API_KEY` on the server (Railway)
- Never exposed to clients
- Single key shared across all organisations (Model A)
- Fallback: `LLM_ENGINE = "deterministic"` for offline/testing mode

### 8.2 ToR Parsing Flow
1. User uploads ToR file (PDF or DOCX)
2. File saved to Supabase Storage
3. HTMX request triggers `TorParseView`
4. `core/parser.py` extracts text from file
5. `core/llm.py` sends text to Grok API
6. Extracted fields returned as JSON
7. HTMX swaps form fields with extracted data
8. User reviews, edits if needed, saves

### 8.3 CV Parsing Flow
Same as ToR parsing but calls `parse_cv()` instead of `parse_tor()`.

### 8.4 Scoring Flow
1. User selects a job posting
2. All candidates for that job are listed
3. HTMX triggers score calculation per candidate
4. `core/scorer.py` computes fit score (0-100)
5. Score saved to `Candidato.score_fit`
6. Results rendered with colour-coded badges

---

## 9. File Storage

### 9.1 Supabase Storage Structure
```
talentiq/
├── {organisation_id}/
│   ├── tors/
│   │   └── {vaga_id}/{filename}
│   └── cvs/
│       └── {candidato_id}/{filename}
```

### 9.2 File Validation
- Allowed types: PDF, DOCX only
- Maximum size: 10MB
- Virus scanning: not in v1, added in v2

### 9.3 Access Control
- Files stored with private access (not publicly accessible)
- Signed URLs generated on demand for download/preview (expire in 1 hour)

---

## 10. User Interface

### 10.1 Design Principles
- Language: Portuguese (Mozambique)
- Colour palette: Blue (#1d4ed8 primary), white backgrounds, clean typography
- Responsive: works on desktop and tablet (primary use case is desktop)
- No mobile optimisation in v1

### 10.2 Layout
```
┌─────────────────────────────────────────────┐
│ Navbar: Logo | Organisation name | User menu │
├──────────┬──────────────────────────────────┤
│          │                                  │
│ Sidebar  │  Main content area               │
│          │                                  │
│ - Vagas  │                                  │
│ - CVs    │                                  │
│ - Score  │                                  │
│ - Pipe   │                                  │
│ - Geral  │                                  │
│          │                                  │
├──────────┴──────────────────────────────────┤
│ Footer: version | feedback link             │
└─────────────────────────────────────────────┘
```

### 10.3 HTMX Usage
HTMX is used for partial page updates to avoid full page reloads:
- ToR/CV file upload → triggers AI parsing → swaps form fields
- Score calculation → updates score badge inline
- Move candidate stage → updates kanban card inline
- Delete confirmations → inline confirmation without navigation

---

## 11. Environment Variables

```env
# Django
SECRET_KEY=
DEBUG=False
ALLOWED_HOSTS=

# Database (Supabase PostgreSQL)
DATABASE_URL=

# Supabase Storage
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_BUCKET=talentiq

# AI
GROK_API_KEY=
LLM_ENGINE=grok

# Email (for user invitations)
EMAIL_HOST=
EMAIL_PORT=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

---

## 12. Deployment

### 12.1 Railway Setup
1. Connect GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Railway auto-deploys on every push to `main` branch
4. Run `python manage.py migrate` on first deploy

### 12.2 Supabase Setup
1. Create Supabase project
2. Copy PostgreSQL connection string → `DATABASE_URL`
3. Create storage bucket `talentiq` (private)
4. Copy API URL and key → `SUPABASE_URL`, `SUPABASE_KEY`

### 12.3 Domain
- Railway provides a default domain: `talentiq.up.railway.app`
- Custom domain can be added in Railway settings (e.g. `app.talentiq.health`)

---

## 13. Migration from Desktop App

### 13.1 Data Migration
- Existing `jobs.json` data can be imported via a one-time management command
- Command: `python manage.py import_legacy_data jobs.json --organisation="Client Name"`

### 13.2 Core Logic Migration
The following files move over unchanged:
- `core/parser.py` → `core/parser.py`
- `core/scorer.py` → `core/scorer.py`
- `core/llm.py` → `core/llm.py`

Only import paths and file handling (local file vs Supabase Storage) need updating.

---

## 14. Development Phases

### Phase 1 — Foundation (Week 1)
- Django project setup with settings, URLs, base template
- accounts app: login, registration, organisation model
- Database schema and migrations
- Supabase connection (database + storage)
- Base layout (navbar, sidebar, Tailwind CSS)

### Phase 2 — Core Features (Week 2-3)
- vagas app: ToR upload, AI parsing, CRUD
- candidatos app: CV upload, AI parsing, CRUD
- scoring app: fit score calculation and display
- pipeline app: kanban board, stage management

### Phase 3 — Polish and Deploy (Week 4)
- Scoring Geral page
- Excel export
- User invitation flow
- Railway deployment
- Data migration command for existing client
- End-to-end testing

---

## 15. Out of Scope (v1)

The following are explicitly excluded from v1 and will be considered for v2:
- Mobile responsive design
- Email notifications (candidate stage changes)
- Calendar integration
- Job posting publication to external boards
- Bulk CV upload
- Custom scoring weights per organisation
- Analytics dashboard beyond current Pipeline page
- API for third-party integrations
- Virus scanning on file uploads
- Two-factor authentication

---

*Document prepared for TalentIQ Health Partners — Confidential*
