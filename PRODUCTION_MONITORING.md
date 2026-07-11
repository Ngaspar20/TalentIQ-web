# TalentIQ — Production Monitoring Guide

## Architecture

```
Browser → Railway (Gunicorn + Django) → PostgreSQL (Railway)
                 ↓
           Sentry (errors)
                 ↓
        UptimeRobot (uptime)
```

---

## Phase 1 — Railway Dashboard

### Where to look
Go to https://railway.app → your project → **TalentIQ service**

| Tab | What it shows | Normal | Worry when |
|-----|--------------|--------|-----------|
| **Deployments** | Build history | Green ticks | Red X appears |
| **Logs** | Live app output | INFO/WARNING lines | ERROR or CRASH lines |
| **Metrics** | CPU + Memory graphs | CPU < 40%, RAM < 400MB | CPU > 80% or RAM > 700MB |
| **Variables** | Environment config | All keys present | Any key missing |

### Daily checklist (5 min)
- [ ] Open Railway → Deployments tab — last deploy is green
- [ ] Open Logs tab — no ERROR lines in last 24h
- [ ] Open Metrics — CPU and Memory look normal
- [ ] Visit https://web-production-d01715.up.railway.app/health/ — returns `{"status":"ok","db":true}`

---

## Phase 2 — Uptime Monitoring (UptimeRobot)

**Recommended: UptimeRobot** (free plan, checks every 5 minutes, email alerts)

### Setup steps
1. Go to https://uptimerobot.com and create a free account
2. Click **Add New Monitor**
3. Settings:
   - Monitor Type: **HTTPS**
   - Friendly Name: `TalentIQ Production`
   - URL: `https://web-production-d01715.up.railway.app/health/`
   - Monitoring Interval: **5 minutes**
4. Under **Alert Contacts** → add your email
5. Click **Create Monitor**

### What happens
- UptimeRobot pings `/health/` every 5 minutes
- If it gets anything other than 200 OK, it emails you within 5 minutes
- The `/health/` endpoint checks the database too — so you get alerted if the DB goes down

---

## Phase 3 — Sentry Error Tracking

### Setup steps
1. Go to https://sentry.io and create a free account
2. Create a new project → Platform: **Django**
3. Copy the **DSN** (looks like `https://abc123@o123.ingest.sentry.io/456`)
4. In Railway → your service → **Variables** → add:
   ```
   SENTRY_DSN = <paste your DSN here>
   ```
5. Redeploy

### Verify it works
Visit this URL (causes a test error):
```
https://web-production-d01715.up.railway.app/accounts/debug-login/
```
Then check Sentry dashboard — you should see the event within 30 seconds.

### Reading Sentry reports
- **Issues** tab → list of all errors, grouped by type
- Click an issue → see **Stack Trace** (which line of code caused it)
- **Breadcrumbs** → what happened before the error
- **Tags** → which URL, which user, which environment
- **Performance** tab → slow pages (anything > 2s is worth investigating)

---

## Phase 4 — Logging

Logs are visible in Railway → **Logs** tab (live) or **Deployments → view logs**.

### Log format
```
[ERROR] 2025-01-15 14:32:01 django.request POST /scoring/calcular/ 500
[WARNING] 2025-01-15 14:30:00 talentiq.scoring Score calculation took 8.2s
[INFO] 2025-01-15 14:28:00 talentiq App started
```

### How to investigate a problem
1. Railway → Logs tab
2. Filter by `ERROR` (type in search box)
3. Note the timestamp and URL
4. Cross-reference with Sentry for full stack trace

### What NOT to log (security)
- Passwords
- API keys
- Full user data
- Database connection strings

---

## Phase 5 — Key Metrics to Watch

| Metric | Where to check | Target |
|--------|---------------|--------|
| Uptime | UptimeRobot dashboard | > 99.5% |
| Response time | UptimeRobot | < 2 seconds |
| Error rate | Sentry → Issues | 0 new issues/day |
| Memory | Railway Metrics | < 400 MB |
| CPU | Railway Metrics | < 40% average |
| DB connections | Railway Metrics | < 10 active |
| Failed logins | Railway Logs (grep ERROR) | < 5/hour |

---

## Phase 6 — Alerts Configuration

| Alert | Tool | Trigger | Action |
|-------|------|---------|--------|
| App down | UptimeRobot | /health/ returns non-200 | Check Railway logs, restart service |
| 500 errors | Sentry | Any unhandled exception | Check stack trace, deploy fix |
| High memory | Railway | > 700 MB | Check for memory leaks, restart |
| Deploy failed | Railway email | Build failure | Read build logs, fix error |
| DB down | UptimeRobot (/health/) | db: false | Check Railway PostgreSQL service |

### Enable Railway deploy notifications
Railway → Settings → Notifications → enable **Deploy Success** and **Deploy Failure** emails.

---

## Phase 7 — Security Configuration

### Current status
- [x] `DEBUG = False` in production (env var not set = False)
- [x] HTTPS enforced via `SECURE_SSL_REDIRECT`
- [x] HSTS enabled (browsers remember HTTPS for 1 year)
- [x] Session cookies marked Secure (HTTPS only)
- [x] CSRF cookies marked Secure
- [x] XSS filter enabled
- [x] Content-type sniffing blocked
- [x] Clickjacking blocked (X-Frame-Options: DENY)
- [ ] `SECRET_KEY` — must be set in Railway Variables (not the default)
- [ ] `ALLOWED_HOSTS` — should be set explicitly in Railway Variables

### Required Railway Variables
```
SECRET_KEY        = <generate with: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG             = False
ALLOWED_HOSTS     = web-production-d01715.up.railway.app
SENTRY_DSN        = <from Sentry project>
ADMIN_PASSWORD    = Med!c!na25
DATABASE_URL      = <auto-set by Railway PostgreSQL>
```

### Generate a secure SECRET_KEY
Run this in your terminal:
```
python -c "import secrets; print(secrets.token_urlsafe(50))"
```
Copy the output and set it as `SECRET_KEY` in Railway.

---

## Phase 8 — Maintenance Schedule

### Daily (5 minutes)
- [ ] Check UptimeRobot dashboard — uptime 100%
- [ ] Check Railway Logs — no ERROR lines
- [ ] Check Sentry — no new issues

### Weekly (30 minutes)
- [ ] Review Sentry issues from the week — any patterns?
- [ ] Check Railway Metrics — memory trending up?
- [ ] Review UptimeRobot response time graph — getting slower?
- [ ] Check if Railway has any maintenance announcements

### Monthly (1 hour)
- [ ] Review and resolve all Sentry issues
- [ ] Check Railway PostgreSQL storage usage
- [ ] Test the full flow: login → add candidate → score → export report
- [ ] Test email alerts are working (pause UptimeRobot monitor, confirm email arrives)
- [ ] Rotate `ADMIN_PASSWORD` if needed

### Quarterly
- [ ] Update `requirements.txt` packages (check for security patches)
- [ ] Review Railway plan usage and costs
- [ ] Review Sentry plan usage
- [ ] Full backup of PostgreSQL data (Railway → PostgreSQL → Backups)

---

## Troubleshooting Guide

### App won't start
1. Railway → Deployments → click failed deploy → read build log
2. Common causes: syntax error in Python, missing package in requirements.txt

### Login not working
1. Visit `/accounts/debug-login/` — confirms if user exists and password matches
2. Visit `/accounts/debug-auth/` — confirms if Django authenticate() works
3. Check Railway Variables — `ADMIN_PASSWORD` set correctly?

### Scoring gives no results
1. Check Railway Logs for errors during POST to `/scoring/calcular/`
2. Check if candidates have a vaga (job) associated

### Database errors
1. Visit `/health/` — if `db: false`, database is down
2. Railway → PostgreSQL service → check if running
3. Railway → your app Variables → `DATABASE_URL` still set?

### Memory keeps growing
1. Railway Metrics → Memory graph trending up over days = memory leak
2. Railway → your service → Restart (buys time)
3. Check for large files being loaded into memory (Excel uploads, etc.)

---

## Recovery Procedures

### Emergency: app is down
1. Railway → your service → **Restart** button
2. If still down: Railway → Deployments → **Rollback** to last good deploy
3. Notify users if downtime > 10 minutes

### Emergency: database corrupted
1. Railway → PostgreSQL → **Backups** tab
2. Restore from most recent backup
3. Re-run `python manage.py migrate`

### Emergency: wrong password set
1. Visit `/accounts/reset-admin/` — resets to current `ADMIN_PASSWORD` env var
2. Or change `ADMIN_PASSWORD` in Railway Variables and restart

---

## Production Readiness Score

| Area | Score | Notes |
|------|-------|-------|
| Error tracking (Sentry) | ⚠ Pending | Add SENTRY_DSN to Railway |
| Uptime monitoring | ⚠ Pending | Set up UptimeRobot |
| Security headers | ✅ Done | HSTS, HTTPS, XSS, CSRF |
| Health endpoint | ✅ Done | /health/ checks DB |
| Logging | ✅ Done | Structured production logs |
| Secret key | ⚠ Action needed | Generate and set in Railway |
| Database backups | ✅ Done | Railway auto-backups daily |
| DEBUG=False | ✅ Done | Default is now False |

**Current score: 6/10**

To reach 10/10:
1. Set `SENTRY_DSN` in Railway → +2 points
2. Set up UptimeRobot → +1 point
3. Generate and set a real `SECRET_KEY` → +1 point

**Target: 10/10** ✅
