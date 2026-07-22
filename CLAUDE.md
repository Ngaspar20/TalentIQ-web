# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

TalentIQ Web is a multi-tenant SaaS Applicant Tracking System (ATS) for healthcare recruitment in Mozambique and Lusophone Africa. Recruiters upload CVs and Terms of Reference (ToR) documents; an LLM (with a deterministic fallback) extracts structured data and scores candidate-vacancy fit.

A full architecture/ops reference already exists at `ENGINEERING.md` — read it before making non-trivial changes. It covers the database schema, LLM fallback chain, deployment startup sequence, coding standards, and a "Common Errors and Fixes" section. This file only summarizes what's needed to be immediately productive.

## Commands

```powershell
# Local dev (SQLite, no PostgreSQL needed)
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Seed/reset the admin user (idempotent; also runs on every Railway deploy)
python manage.py seed_admin

# Tests (per-app test.py files exist but are currently empty stubs)
python manage.py test
python manage.py test accounts        # single app
python manage.py test vagas.tests.SomeTestCase.test_method   # single test, once written
```

There is no lint/format tooling configured in this repo (no `.flake8`, `pyproject.toml`, `black` config, etc.) — don't assume one.

## Architecture

**Django apps, each owning one pipeline stage:**
- `accounts` — Organisation + User models, auth (email-based login via custom `EmailBackend`), multi-tenancy
- `vagas` — job vacancies (Vaga model), ToR upload
- `candidatos` — candidates (Candidato model), CV upload
- `scoring` — fit-score calculation, Excel/Word export
- `pipeline` — Kanban-style recruitment pipeline board
- `ajuda` — static help page
- `talentiq/` — project settings, root URLs, middleware, dashboard, built-in user management (`gestao_views.py`)

**`core/` is the framework-agnostic AI engine**, shared by the Django apps (originally written for a desktop prototype):
- `core/llm.py` — pluggable LLM client, selected via `LLM_ENGINE` env var (`grok` | `openai` | `deterministic`). Every call returns `None` on failure rather than raising.
- `core/parser.py` — `parse_cv(text)` / `parse_tor(text)`: try LLM first, fall back to deterministic regex/keyword parsing (keyword lists live in `config.py`) if the LLM fails or returns bad JSON.
- `core/scorer.py` — `calcular_fit(candidato_dict, vaga_dict)`: same LLM-then-deterministic pattern. Deterministic scoring weights: competências 50pts, experiência 30pts, formação 20pts.
- `config.py` — compatibility shim bridging the desktop app's flat-module imports (`import config`) into Django; `core/scorer.py` and `core/llm.py` both handle `sys.path` issues with try/except fallback to Django settings.

**The LLM fallback chain is the central design invariant of this codebase**: every AI-backed operation (CV parsing, ToR parsing, fit scoring) must succeed with a deterministic result even if the LLM call fails, times out, or returns malformed JSON. Never let an AI failure surface as a user-facing error.

**Multi-tenancy** is row-based: every data model (`Vaga`, `Candidato`, etc.) has an `organisation` FK, and all UUIDs are primary keys. Views must filter querysets by `request.user.organisation` — there is no shared/global data across organisations.

**Auth is middleware-driven, not decorator-driven** — do not add `@login_required` to views. `talentiq/middleware.py` swaps between `AutoLoginMiddleware` (demo mode: auto-logs in the first active user) and `LoginRequiredMiddleware` (production mode) via the `MIDDLEWARE` list in `talentiq/settings.py`. `/admin/` and a few other paths are listed in `PUBLIC_URLS` and bypass the gate.

**Deployment startup order is defined in `railway.json`, not `nixpacks.toml`** — `railway.json`'s `startCommand` takes priority over `nixpacks.toml`'s `[start]`. It runs `migrate` → `seed_admin` → `gunicorn`, in that order; keep future startup logic changes there. `nixpacks.toml` is build-phase only (`pip install`, `collectstatic`).

## Project-Specific Conventions

- All UI text is Portuguese (pt-MZ/pt-BR) — templates, labels, model verbose names, everything user-facing.
- No emojis in UI — use Font Awesome icons (`<i class="fa-solid fa-...">`) only.
- No nested `<form>` elements in templates — browsers silently drop inner forms; give each action its own top-level `<form>` or use a link.
- HTMX partial templates are prefixed with `_` (e.g. `_candidato_row.html`) and must render partials, not full pages. CSRF for HTMX is handled globally in `base.html`'s `htmx:configRequest` listener — don't add `X-CSRFToken` headers manually.
- Django templates have no built-in `split` filter — use hardcoded `<option>` elements instead of trying to split a comma string in a template.
- When editing files containing Portuguese characters (á, ã, ç, etc.), don't use PowerShell `Set-Content` without `-Encoding utf8` — it defaults to UTF-16 LE and corrupts them. Prefer writing via Python/UTF-8-aware tooling.
- `DATABASE_URL` must never be manually set in Railway env vars — Railway's PostgreSQL add-on injects it, and a manual value silently overrides it and breaks the DB connection.
- `cv_file_path` / `tor_file_path` point into the Railway container's ephemeral filesystem and are wiped on every redeploy. The data that matters (parsed candidate/vacancy fields) is persisted separately in PostgreSQL (`Candidato.perfil_completo`, etc.) — don't rely on the raw file surviving a deploy.
- `talentiq/setup_view.py` exposes a one-time `/setup/promote/` admin-recovery URL. It should not exist in a production deploy — remove it (and its `urls.py` entry) once no longer needed for recovery.
