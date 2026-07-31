# TalentIQ — Technical Reference & Debug Guide

> **Audience:** Developers debugging, extending, or operating TalentIQ.
> **Scope:** This document captures what the app actually does, the precise data flow, known issues, and how to diagnose failures. Architecture is in `ENGINEERING.md`; this document is for runtime debugging.

---

## Table of Contents

1. [What the App Does](#1-what-the-app-does)
2. [Feature Inventory](#2-feature-inventory)
3. [Data Flow Diagrams](#3-data-flow-diagrams)
4. [Known Issues & Bugs](#4-known-issues--bugs)
5. [Debugging Runbook](#5-debugging-runbook)
6. [Industry-Readiness Assessment](#6-industry-readiness-assessment)
7. [Security Checklist](#7-security-checklist)
8. [Performance Notes](#8-performance-notes)
9. [Dependency Map](#9-dependency-map)

---

## 1. What the App Does

TalentIQ is a multi-tenant Applicant Tracking System (ATS) for healthcare and general recruitment in Mozambique and Lusophone Africa. It covers the full recruitment lifecycle:

| Stage | What happens |
|---|---|
| **1. Vaga criada** | HR uploads a ToR (PDF/DOCX) or fills a form. AI extracts structured vacancy data. HR reviews + approves the ToR before candidates can be added. |
| **2. Candidatos carregados** | HR uploads CVs (PDF/DOCX). AI extracts structured profiles per candidate. Candidates are linked to the vacancy. |
| **3. Scoring** | Each candidate is scored 0–100 against the vacancy across 3 dimensions (skills 50%, experience 30%, education 20%). LLM-enhanced if Grok API key is set. |
| **4. Triagem** | HR reviews the ranked shortlist, moves candidates from "Em Triagem" to "Entrevista". |
| **5. Guião de entrevista** | AI generates a structured interview guide. HR sends it via tokenized link to a committee chair (public, no login required). Chair edits/approves questions and submits. HR approves and downloads a formatted Word scoring table. |
| **6. Avaliação do júri** | HR sends tokenized evaluation links to committee members (or a single group link). Each member fills a structured evaluation per candidate. HR confirms the results, which auto-updates candidate pipeline stages. |
| **7. Relatório de seleção** | AI generates a selection narrative comparing candidates. Downloadable as Word. |
| **8. Cartas** | AI generates formal letters (exclusão de triagem, pré-seleção, rejeição pós-entrevista, oferta) for each candidate. Downloadable as Word. |
| **Export** | Excel ranking (formatted with scores) and Word selection report for each vacancy. |

---

## 2. Feature Inventory

### Vagas (`/vagas/`)

| Route | View | Description |
|---|---|---|
| `GET /vagas/` | `vaga_list` | Lists all organisation vacancies |
| `GET/POST /vagas/criar/` | `vaga_create` | Manual creation or ToR upload |
| `GET /vagas/<uuid>/` | `vaga_detail` | Full pipeline view: triagem / entrevista / decisão tabs |
| `GET/POST /vagas/<uuid>/editar/` | `vaga_edit` | Edit vacancy fields |
| `POST /vagas/<uuid>/delete/` | `vaga_delete` | Delete vacancy |
| `POST /vagas/<uuid>/confirmar-analise/` | `vaga_confirmar_analise` | Mark ToR as AI-analysed |
| `POST /vagas/<uuid>/aprovar-tor/` | `vaga_aprovar_tor` | Approve ToR (unlocks CV uploads) |
| `POST /vagas/parse-tor/` | `parse_tor_view` | HTMX: extract ToR text, return preview |
| `POST /vagas/analyse-tor/` | `analyse_tor_view` | HTMX: send ToR text to AI, return pre-filled form |
| `GET /vagas/<uuid>/perguntas/` | `gerar_perguntas_entrevista` | Generate structured interview guide via AI |
| `GET/POST /vagas/<uuid>/shortlist/` | `shortlist` | Shortlist view with "Mover para Entrevista" action |
| `POST /vagas/<uuid>/mover-entrevista/<uuid>/` | `mover_para_entrevista` | Move candidate to Entrevista stage |
| `POST /vagas/<uuid>/enviar-juri/` | `enviar_guiao_juri` | Create interview guide session + tokenized link for chair |
| `GET/POST /vagas/juri/<token>/` | `guiao_juri_view` | **PUBLIC** — chair reviews and edits questions |
| `GET/POST /vagas/<uuid>/guiao/<uuid>/aprovar/` | `guiao_aprovar` | HR approves chair's submitted guide |
| `GET /vagas/<uuid>/guiao/<uuid>/download/` | `guiao_download` | Download approved guide as Word |
| `POST /vagas/<uuid>/download-perguntas/` | `download_perguntas` | Download preview questions as Word |
| `POST /vagas/<uuid>/comite/adicionar/` | `comite_adicionar_avaliador` | Add committee member |
| `POST /vagas/<uuid>/comite/<uuid>/remover/` | `comite_remover_avaliador` | Remove committee member |
| `GET/POST /vagas/comite/<token>/` | `comite_avaliacao_view` | **PUBLIC** — committee member fills evaluation table |
| `GET /vagas/<uuid>/comite/resultados/` | `comite_resultados` | HR views consolidated committee results |
| `POST /vagas/<uuid>/comite/confirmar/` | `comite_confirmar_decisoes` | HR consolidates committee decisions → NotaEntrevista |
| `POST /vagas/<uuid>/candidato/<uuid>/decisao/` | `candidato_decisao_final` | Final hire/reject/hold decision per candidate |
| `POST /vagas/<uuid>/enviar-avaliacao-grupo/` | `enviar_avaliacao_grupo` | Generate group evaluation token + AvaliacaoSession for all interview candidates |
| `GET/POST /vagas/avaliacao-grupo/<token>/` | `avaliacao_grupo_juri` | **PUBLIC** — juror evaluates all interview candidates at once |
| `POST /vagas/<uuid>/confirmar-avaliacoes-grupo/` | `confirmar_avaliacoes_grupo` | Confirm all submitted group evaluations |
| `GET /vagas/<uuid>/relatorio/` | `relatorio_selecao` | AI-generated selection report (web view) |
| `GET /vagas/<uuid>/relatorio/download/` | `relatorio_selecao_download` | Download selection report as Word |

### Candidatos (`/candidatos/`)

| Route | View | Description |
|---|---|---|
| `GET /candidatos/` | `candidato_list` | List all organisation candidates |
| `GET/POST /candidatos/criar/` | `candidato_create` | Create candidate manually |
| `GET /candidatos/<uuid>/` | `candidato_detail` | Candidate profile with scores, interview notes |
| `GET/POST /candidatos/<uuid>/editar/` | `candidato_edit` | Edit candidate |
| `POST /candidatos/<uuid>/delete/` | `candidato_delete` | Delete candidate |
| `POST /candidatos/parse-cv/` | `parse_cv_view` | HTMX: extract CV text, return preview |
| `POST /candidatos/analyse-cv/` | `analyse_cv_view` | HTMX: send CV to AI, return pre-filled form |
| `GET /candidatos/<uuid>/carta/` | `gerar_carta` | Generate letter via AI |
| `POST /candidatos/<uuid>/carta/download/` | `download_carta` | Download letter as Word |
| `POST /candidatos/<uuid>/enviar-avaliacao/` | `enviar_avaliacao_juri` | Create AvaliacaoSession + tokenized link |
| `GET/POST /candidatos/avaliacao/<token>/` | `avaliacao_juri_view` | **PUBLIC** — juror evaluates one candidate |
| `POST /candidatos/<uuid>/avaliacao/<uuid>/confirmar/` | `avaliacao_confirmar` | HR confirms single evaluation |
| `POST /candidatos/<uuid>/guardar-nota/` | `guardar_nota_entrevista` | Manually save interview notes |

### Scoring (`/scoring/`)

| Route | View | Description |
|---|---|---|
| `GET /scoring/` | `scoring_view` | Score dashboard — select vaga to view candidates |
| `POST /scoring/calcular/` | `score_calculate` | Calculate score for one or all candidates |
| `GET /scoring/exportar-excel/` | `exportar_excel` | Download Excel ranking |
| `GET /scoring/exportar-word/` | `exportar_word` | Download Word selection report |
| `GET /scoring/geral/` | `scoring_geral` | All candidates across all vacancies, ranked |

### Other

| Route | View | Description |
|---|---|---|
| `GET /` | `dashboard` | KPI summary (vacancies, candidates, scores) |
| `GET /health/` | `health_check` | Database connectivity check (used by Railway) |
| `GET /sistema/` | `sistema_view` | System info panel |
| `GET /gestao/utilizadores/` | `utilizadores_list` | User management (admin only in practice) |
| `GET /ajuda/` | `ajuda_view` | Help page |

---

## 3. Data Flow Diagrams

### CV Upload → Candidate Created

```
POST /candidatos/parse-cv/
  ↓ extract_text_from_file(uploaded_file)
    ↓ if .pdf  → pdfplumber.open() → extract_text()
    ↓ if .docx → python-docx Document → paragraphs + table cells
    ↓ else     → raw UTF-8 decode
  ↓ Returns text preview (first 4000 chars shown)

POST /candidatos/analyse-cv/
  ↓ os.environ["GROK_API_KEY"] = settings.GROK_API_KEY  [sets env for config shim]
  ↓ parse_cv(texto)
    ↓ if LLM_ENGINE != "deterministic":
        _parse_with_llm(text)
          ↓ get_llm_response(prompt, system) → Grok API
          ↓ json.loads(response) → structured dict
          ↓ on failure → returns {}
    ↓ if LLM failed or deterministic mode:
        _parse_deterministic(text)
          ↓ keyword match → competencias, formacao, cargos
          ↓ regex → email, phone, years of experience
          ↓ date range analysis → experiencia_anos
  ↓ HTMX returns _cv_form_fields.html (pre-filled form)

POST /candidatos/criar/
  ↓ vaga.tor_aprovado must be True (otherwise redirects to vaga_detail)
  ↓ Candidato.objects.create(...)
  ↓ redirect("candidato_list")
```

### Scoring

```
POST /scoring/calcular/
  ↓ os.environ set for config shim
  ↓ _score_deterministic(cand_dict, vaga_dict)   [NOTE: bypasses LLM regardless of LLM_ENGINE]
    ↓ Competências (0-50pts):
        vaga_reqs = deduplicated synonym keys from competencias_requeridas
        cand_keys = expanded synonym keys from candidato.competencias
        score = (matched / total) * 50
    ↓ Experiência (0-30pts):
        if cand_years >= req * 1.5  → 30
        if cand_years >= req        → 25
        else                        → proportional
    ↓ Formação (0-20pts):
        education level hierarchy → graduated 0-20
    ↓ total = competencias + experiencia + formacao
    ↓ nivel: Alto (>=75) / Médio (>=50) / Baixo (<50)
  ↓ candidato.score_fit = total
  ↓ candidato.perfil_completo = resultado dict
  ↓ candidato.save(update_fields=["score_fit","perfil_completo"])
  ↓ redirect to scoring page
```

### Interview Guide Workflow

```
HR: GET /vagas/<pk>/perguntas/
  ↓ get_llm_response(prompt) → structured guide text
  ↓ session["perguntas_<pk>"] = texto
  ↓ _parse_perguntas(texto) → list of (categoria, [(question, what_to_assess)])
  ↓ render perguntas_preview.html

HR: POST /vagas/<pk>/enviar-juri/
  ↓ get_llm_response(prompt) OR _fallback_texto(vaga)
  ↓ InterviewGuideSession.objects.create(vaga, texto_gerado, chair_email)
  ↓ token = session.token (UUID, public)
  ↓ link = /vagas/juri/<token>/
  ↓ render guiao_link.html (HR copies link manually)

Chair: GET/POST /vagas/juri/<token>/    [PUBLIC — no login]
  ↓ GET: render guiao_juri.html with parsed questions
  ↓ POST: _reconstruct_texto(form_data)
         session.texto_editado = texto_novo
         session.estado = ESTADO_SUBMETIDO
  ↓ render guiao_juri_obrigado.html

HR: GET/POST /vagas/<pk>/guiao/<session_pk>/aprovar/
  ↓ action=="aprovar": session.estado = ESTADO_APROVADO → redirect guiao_download
  ↓ action=="devolver": session.estado = ESTADO_PENDENTE → back for chair to redo

HR: GET /vagas/<pk>/guiao/<session_pk>/download/
  ↓ session.estado must be ESTADO_APROVADO
  ↓ _build_word_doc(vaga, categorias) → Word table with scoring columns
```

### Committee Evaluation Workflow

```
HR: POST /vagas/<pk>/comite/adicionar/
  ↓ ComiteSession.objects.create(vaga, avaliador_nome, avaliador_email)
  ↓ token = session.token (UUID, public)
  ↓ link = /vagas/comite/<token>/

Member: GET/POST /vagas/comite/<token>/    [PUBLIC — no login]
  ↓ GET: loads approved InterviewGuideSession questions
         loads Candidato.objects.filter(vaga=vaga, etapa="Entrevista")
  ↓ POST: ComiteAvaliacao.objects.update_or_create per candidate
         session.estado = ESTADO_SUBMETIDO

HR: POST /vagas/<pk>/comite/confirmar/
  ↓ averages pontuacoes across all submitted sessions
  ↓ takes most-common recomendacao by majority vote
  ↓ NotaEntrevista.update_or_create per candidate
  ↓ HR then manually confirms final decision per candidate
```

---

## 4. Known Issues & Bugs

### Critical

**BUG-01: `pdfplumber` not in requirements.txt**
- File: `requirements.txt`
- `core/parser.py:34` imports `pdfplumber` inside `_extract_pdf()`
- If Railway installs from `requirements.txt` only, PDF upload will fail with `ModuleNotFoundError`
- **Fix:** Add `pdfplumber==0.11.4` (or latest stable) to `requirements.txt`

**BUG-02: `setup_view.py` file still in repo (not wired, but present)**
- File: `talentiq/setup_view.py` (exists on disk, NOT registered in `urls.py`)
- The URL `/setup/promote/` is not currently active — the URL entry was already removed
- However, the file is still in the repo and could accidentally be re-added in a future edit
- **Fix:** Delete `talentiq/setup_view.py` to eliminate the risk permanently

**BUG-03: Portuguese string corruption in view files**
- Files: `candidatos/views.py:24,89`, `vagas/views.py:29,137`, and several HTMX error strings
- Strings like `"O nome do candidato Ã© obrigatÃ³rio."` are UTF-8 sequences incorrectly decoded as Latin-1 during file editing
- These display as garbage characters to end users
- **Fix:** Open each view file in a UTF-8 editor and retype the corrupted strings, OR run: `python -c "print('O nome do candidato Ã\xa9 obrigatÃ³rio.'.encode('latin-1').decode('utf-8'))"`

### Significant

**BUG-04: `score_calculate` bypasses LLM entirely**
- File: `scoring/views.py:85`
- The view calls `_score_deterministic()` directly instead of `calcular_fit()`
- `LLM_ENGINE=grok` in production has no effect on the scoring endpoint
- **Fix:** Replace `_score_deterministic(cand_dict, vaga_dict)` with `calcular_fit(cand_dict, vaga_dict)` if LLM scoring is desired

**BUG-05: `set_password` logs full call stack on every password change**
- File: `accounts/models.py:49-55`
- `User.set_password()` is overridden to log a WARNING with full Python stack trace
- This pollutes production logs (Sentry, Railway logs) on every login/registration/password reset
- **Fix:** Remove the `set_password` override entirely, or reduce to DEBUG level

**BUG-06: `@login_required` decorator on `comite_resultados`**
- File: `vagas/views.py:872`
- Inconsistent with the project convention (middleware-based auth); this decorator adds a second auth gate that redirects to the default Django login path, not the customised `/accounts/login/`
- **Fix:** Remove `@login_required` from `comite_resultados`

**BUG-07: `core/parser.py` unconditional `sys.path.append`**
- File: `core/parser.py:10-11`
- Unlike `core/llm.py` and `core/scorer.py` which wrap the import in try/except, `parser.py` adds to `sys.path` unconditionally and calls `import config` at module level
- If `config.py` is not found, the entire module fails to import and CV/ToR upload breaks silently
- **Fix:** Wrap in try/except like the other core modules, or confirm `config.py` is always at repo root

### Minor

**BUG-08: No role-based access control enforcement**
- All authenticated users within an organisation can create, edit, and delete vacancies and candidates regardless of their `role` field
- The `User.ROLE_VIEWER` role does nothing — viewers can still mutate data
- **Fix:** Add role checks in views, or create a permission decorator that checks `request.user.role`

**BUG-09: No rate limiting on LLM-backed endpoints**
- `POST /vagas/analyse-tor/`, `POST /candidatos/analyse-cv/`, `GET /vagas/<pk>/perguntas/`, `POST /vagas/<pk>/enviar-juri/` all make Grok API calls
- A single user can trigger many API calls rapidly
- **Fix:** Add Django's built-in `cache.set()`-based rate limiting, or use `django-ratelimit`

**BUG-10: File type validation is extension-only**
- `core/parser.py:18-26` checks `filename.endswith(".pdf")` and `.endswith(".docx")`
- A malicious file renamed to `.pdf` would be passed to `pdfplumber` (which would fail gracefully, but the file is still read)
- **Fix:** Add MIME type validation using `python-magic` after reading file bytes

**BUG-11: `gerar_perguntas_entrevista` is a GET that triggers an LLM call**
- File: `vagas/views.py:229`
- Reloading the page or navigating back/forward makes another Grok API call
- **Fix:** Change to POST, or cache the result with `session["perguntas_<pk>"]` and return cached on GET

**BUG-12: Group evaluation token has no expiry**
- `Vaga.avaliacao_group_token` (UUID) is persistent once set
- Anyone who had the link previously can still submit new evaluations even after the process is closed
- **Fix:** Add a `ComiteSession.estado` check or a separate `avaliacao_group_active` flag to close the link

**BUG-13: No tests**
- All `tests.py` files across all apps are empty stubs
- No unit tests for `core/scorer.py` scoring logic, `core/parser.py` parsing, or any views
- **Fix:** At minimum, add unit tests for `calcular_fit()` and `_parse_deterministic()` since these are the deterministic fallback layer

---

## 5. Debugging Runbook

### App won't start on Railway

```bash
# Check deployment logs in Railway dashboard → Deployments → View Logs
# Common causes (in order of frequency):

# 1. Import error — look for "ModuleNotFoundError" or "ImportError"
python manage.py check  # run locally to catch import errors before pushing

# 2. Missing migration
python manage.py showmigrations  # shows unapplied migrations

# 3. DATABASE_URL wrong
# Check Railway → web service → Variables tab
# DATABASE_URL must NOT be manually set — Railway PostgreSQL injects it
```

### PDF upload fails silently

```bash
# Symptom: "Não foi possível extrair texto" message, even for valid PDFs

# Check 1: Is pdfplumber installed?
pip show pdfplumber
# If not: pdfplumber is missing from requirements.txt (BUG-01)

# Check 2: Is the PDF image-based (scanned)?
# pdfplumber cannot extract text from image-only PDFs
# Workaround: use OCR tools (e.g. tesseract) before uploading

# Check 3: Railway logs
# Look for "Erro ao extrair PDF:" followed by an exception
```

### Scoring shows 0 or doesn't update

```bash
# Check 1: Is candidato linked to a vaga?
python manage.py shell
from candidatos.models import Candidato
c = Candidato.objects.get(pk="<uuid>")
print(c.vaga)  # None means no vaga linked

# Check 2: Does the vaga have competencias_requeridas?
from vagas.models import Vaga
v = Vaga.objects.get(pk="<uuid>")
print(v.competencias_requeridas)  # Empty list → score defaults to 25/50

# Check 3: Test scorer directly
from core.scorer import _score_deterministic
result = _score_deterministic(
    {"competencias": ["python", "sql"], "experiencia_anos": 5, "formacao": ["licenciatura"]},
    {"competencias_requeridas": ["python"], "anos_experiencia_min": 3, "nivel_formacao": "licenciatura"}
)
print(result)

# Check 4: score_calculate view always uses deterministic (BUG-04)
# LLM scoring is not called from the /scoring/calcular/ endpoint
```

### LLM / Grok API not working

```bash
# Check 1: Is GROK_API_KEY set and starts with "xai-"?
python manage.py shell
from django.conf import settings
print(settings.GROK_API_KEY[:8])  # Should be "xai-XXXX"
print(settings.LLM_ENGINE)        # Should be "grok"

# Check 2: Test LLM call directly
from core.llm import get_llm_response
result = get_llm_response("Respond with: {\"test\": true}", "You are a test.")
print(result)  # None means LLM failed, will use deterministic fallback

# Check 3: Check core/llm.py logs for "Erro ao chamar Grok:"
# The error is logged at ERROR level → visible in Railway logs
```

### Portuguese characters showing as garbage (Ã©, Ã£, etc.)

```bash
# These are UTF-8 bytes decoded as Latin-1 during file editing
# To see the correct string:
python -c "print('Ã©'.encode('latin-1').decode('utf-8'))"

# To fix, open the file in a UTF-8 aware editor and retype affected strings
# Or use Python to rewrite the file:
# See BUG-03 above for affected files
```

### Login not working

```bash
# Check 1: EmailBackend configured?
python manage.py shell
from django.conf import settings
print(settings.AUTHENTICATION_BACKENDS)
# Should include "accounts.backends.EmailBackend"

# Check 2: User's username field == email field?
from accounts.models import User
u = User.objects.get(email="user@example.com")
print(u.username)  # Must equal u.email (lowercase)
# Fix: u.username = u.email.lower(); u.save()

# Check 3: seed_admin ran on deploy?
# seed_admin sets username=email for the admin user
python manage.py seed_admin  # safe to run multiple times
```

### Template / HTMX response renders full page instead of partial

```bash
# Symptom: HTMX swap replaces the whole page with a full HTML document
# Cause: The view returned a full-page template instead of a partial

# Check: Does the view call render() with a _prefixed template?
# HTMX partials must be in templates named with _prefix (e.g., _cv_form_fields.html)

# Check: Is hx-target set to the correct element?
# Inspect the HTMX response in browser DevTools → Network → check response body
```

### /admin/ shows TalentIQ login instead of Django admin

```bash
# Cause: LoginRequiredMiddleware intercepts /admin/ before Django admin auth
# Fix: /admin/ is already in PUBLIC_URLS in talentiq/middleware.py
# If still broken, check that "/admin/" is in PUBLIC_URLS:
grep -n "PUBLIC_URLS" talentiq/middleware.py
```

### Database empty after redeploy

```bash
# Railway PostgreSQL persists across redeploys — this should not happen
# If it does, confirm you're connected to the correct database:
python manage.py dbshell
\dt  # lists tables

# seed_admin recreates the admin user on every deploy
# Other data cannot be automatically restored without a backup
```

### Session / CSRF issues in HTMX

```bash
# CSRF for HTMX is handled in base.html's htmx:configRequest listener
# Do NOT add X-CSRFToken headers manually to HTMX attributes

# Check base.html contains:
# document.addEventListener('htmx:configRequest', (event) => {
#   event.detail.headers['X-CSRFToken'] = csrfToken;
# });
```

---

## 6. Industry-Readiness Assessment

### What's Well Done

| Area | Status | Notes |
|---|---|---|
| LLM fallback chain | ✅ Solid | Every AI operation has a deterministic fallback — app never errors on LLM failure |
| Multi-tenancy isolation | ✅ Correct | Every queryset filtered by `request.user.organisation`; UUID PKs prevent enumeration |
| Security headers (prod) | ✅ Configured | HSTS, CSRF_COOKIE_SECURE, SESSION_COOKIE_SECURE, X_FRAME_OPTIONS when DEBUG=False |
| HTMX integration | ✅ Correct | Global CSRF handler in base.html; partials prefixed with `_` |
| Error monitoring | ✅ Sentry | `SENTRY_DSN` env var triggers Sentry SDK with release tracking |
| Health check | ✅ Present | `/health/` verifies DB connection, returns 503 on failure |
| Deployment startup order | ✅ Correct | `migrate` → `seed_admin` → `gunicorn` in `railway.json` |
| Session management | ✅ Configured | 30-day sessions, DB-backed, secure cookies in production |
| Auth backend | ✅ Robust | Email-based auth, case-insensitive, dual backends |
| Structured logging | ✅ Present | Production format: `[LEVEL] timestamp module message` |

### What Needs Work Before General SaaS Launch

| Gap | Severity | Fix Effort |
|---|---|---|
| `pdfplumber` missing from requirements.txt (PDF upload broken in prod) | 🔴 Critical | 5 min — add one line |
| `setup_view.py` in repo (not wired, but risky) | 🟡 Medium | 5 min — delete the file |
| Corrupted Portuguese strings in views | 🟠 High | 30 min — retype affected strings |
| No role-based access control (viewers can delete) | 🟠 High | 4–8 hrs — add permission decorators |
| No test coverage | 🟠 High | Ongoing — start with `core/scorer.py` unit tests |
| `set_password` stack trace in production logs | 🟡 Medium | 5 min — remove override |
| LLM not called from scoring endpoint (BUG-04) | 🟡 Medium | 10 min — swap function call |
| No rate limiting on LLM endpoints | 🟡 Medium | 2 hrs — add `django-ratelimit` |
| File type validated by extension only | 🟡 Medium | 1 hr — add `python-magic` check |
| Group evaluation token has no expiry | 🟡 Medium | 2 hrs — add active flag or expiry |
| `@login_required` on `comite_resultados` (inconsistent) | 🟢 Low | 2 min — remove decorator |
| `gerar_perguntas_entrevista` is GET + LLM call (reloads waste API) | 🟢 Low | 1 hr — change to POST |
| RBAC not enforced on user management routes | 🟠 High | Only admins should access `/gestao/` — add role check |

### Honest Summary

**The core is production-grade for a V1 internal product.** The architecture decisions are sound: deterministic fallback, row-level multi-tenancy, middleware-based auth, health check, Sentry, and Railway deployment are all configured correctly. The app is deployable and functional today.

**It is NOT ready for general public SaaS** without addressing the critical bugs (pdfplumber, setup_view) and the role-enforcement gap. A recruiter with "viewer" role can currently delete all vacancies.

**Confidence level by feature:**
- Multi-tenancy isolation: **High** — thoroughly implemented
- LLM scoring accuracy: **Medium** — synonym matching is good but limited to defined keyword groups
- CV parsing accuracy: **Medium** — LLM is good, deterministic fallback is basic
- Committee evaluation workflow: **Medium** — functional but tokenized URLs never expire
- Data durability: **Medium** — raw CV files are lost on redeploy (documented, but surprising for users)

---

## 7. Security Checklist

| Check | Status | Notes |
|---|---|---|
| No hardcoded credentials in code | ✅ | All secrets via env vars |
| `SECRET_KEY` not default in production | ⚠️ Check | Default value in settings.py is `django-insecure-dev-key-change-in-production` — verify Railway has a real key |
| `DEBUG=False` in production | ✅ (if set) | Controlled by `DEBUG` env var — verify in Railway |
| CSRF protection | ✅ | Django CSRF middleware + secure cookies in prod |
| SQL injection | ✅ | Django ORM throughout — no raw SQL |
| XSS | ✅ | Django template auto-escaping; no `mark_safe` usage found |
| `setup_view.py` removed | ❌ | **MUST remove before any external access** |
| File upload limited to 10MB | ✅ | `FILE_UPLOAD_MAX_MEMORY_SIZE = 10MB` |
| Public token views (committee, jury) | ⚠️ | No expiry, no rate limiting on token routes |
| `DATABASE_URL` not manually set | ✅ (if correct) | Must verify in Railway Variables tab |
| HTTPS enforced | ✅ | `SECURE_PROXY_SSL_HEADER` + `SECURE_HSTS_SECONDS=31536000` in prod |

---

## 8. Performance Notes

- **Gunicorn workers: 2** — adequate for low/medium concurrent users. Increase to `(2 × CPU_cores) + 1` if Railway plan allows more CPUs.
- **No database indexes beyond PKs and FKs** — for organisations with >1000 candidates, add indexes on `Candidato.vaga`, `Candidato.organisation`, `Candidato.etapa`.
- **Scoring is synchronous** — calculating scores for all candidates in a vacancy blocks the request. For >50 candidates, consider Celery + Redis for async scoring.
- **Excel/Word export is in-memory** — for very large exports (>500 candidates), buffer to a temp file.
- **LLM calls are synchronous** — CV analysis and ToR parsing block for 2–10 seconds. No timeout is set on the Grok API call. Consider adding `timeout=30` to the `client.chat.completions.create()` call.

---

## 9. Dependency Map

```
requirements.txt (production)
  ├── Django==6.0.7           — web framework
  ├── django-htmx==1.27.0     — HTMX middleware + HtmxMiddleware
  ├── openai==2.36.0          — Grok API client (OpenAI-compatible)
  ├── openpyxl==3.1.5         — Excel export
  ├── pillow==12.1.0          — image processing (indirect dep of openpyxl)
  ├── psycopg2-binary==2.9.12 — PostgreSQL adapter
  ├── python-docx==1.2.0      — Word export (interview guides, letters, reports)
  ├── python-dotenv==1.2.2    — .env file loader (local dev)
  ├── whitenoise==6.12.0      — static file serving
  ├── gunicorn==26.0.0        — WSGI server
  ├── dj-database-url==3.1.2  — DATABASE_URL → DATABASES dict parser
  └── sentry-sdk[django]==2.19.2 — error monitoring

MISSING from requirements.txt:
  └── pdfplumber              — PDF text extraction (CRITICAL — BUG-01)

Runtime-only (CDN, not installed):
  ├── Tailwind CSS (CDN)      — utility-first CSS framework
  ├── HTMX 1.9 (CDN)         — AJAX interactions without JS
  └── Font Awesome 6 (CDN)   — icons

External services:
  ├── xAI Grok API            — LLM for CV/ToR parsing and scoring
  ├── Railway PostgreSQL      — production database
  ├── Sentry                  — error tracking (optional, env-var gated)
  └── Railway                 — hosting, static IPs, managed deploys
```

---

*Last updated: July 2026*
*Stack: Django 6.0.7 · Python 3.14 · Grok-3 (xAI) · Railway · PostgreSQL*
