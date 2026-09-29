# Deploying PocketSmart AI

Three options are covered: **Render** (recommended, a `render.yaml` blueprint is
included), **Docker**, and **any other WSGI host**.

Read [Before you deploy](#before-you-deploy) first - there are two things in
this app that behave differently in production than they do locally.

---

## Before you deploy

### 1. The SQLite database is ephemeral on most platforms

The app stores users and saved plans in a single SQLite file. On Render, Railway,
Fly.io and most container hosts, **the local filesystem is wiped on every
redeploy and on every instance restart**. Your users' accounts and plan history
will disappear.

`render.yaml` therefore points the database at `/tmp/pocketsmart.db`. That is
fine for a demo, but it means:

- Plans saved today may be gone after tomorrow's deploy.
- Running more than one instance gives each one its **own separate database**,
  so a user can register on instance A and fail to log in on instance B.

**For anything beyond a demo, move to a persistent store.** The smallest change
is a mounted disk (Render Persistent Disk), pointing `DATABASE_PATH` at it:

```yaml
disk:
  name: pocketsmart-data
  mountPath: /var/data
  sizeGB: 1
envVars:
  - key: DATABASE_PATH
    value: /var/data/pocketsmart.db
  - key: DATA_DIR
    value: /var/data
```

Note that a single SQLite file is still a single-writer store. It handles one
app instance comfortably; it will not survive horizontal scaling without
changing `services/history.py` to point at Postgres.

### 2. The demo account is a shared, publicly known login

`views.py` defines:

```python
DEMO_EMAIL = "demo@pocketsmart.ai"
DEMO_PASSWORD = "demo1234"
```

The `/demo-login` button signs any visitor into that **one shared account**, and
every plan they save is stored against it - so any visitor can read plans other
visitors saved. The password is in the public source.

This is fine for a demo you are actively driving. It is **not** fine on a public
site. Pick one:

| Option | Effect |
| --- | --- |
| Remove `/demo-login` and the template button | No shared account at all |
| Keep the route but gate it behind a config flag | Off in production unless explicitly enabled |
| Leave as is | Anyone can read anything saved to the demo account |

---

## Option A: Render (recommended)

`render.yaml` in the repo root is a Render Blueprint, so the whole service is
described already.

### Deploy from the dashboard

1. Go to <https://dashboard.render.com> and sign in.
2. **New → Blueprint**, then connect the repository
   `vincyu2007-glitch/pocketsmart-ai`.
3. Render reads `render.yaml` and shows the `pocketsmart-ai` web service.
   Click **Apply**.
4. Render provisions the service and starts the build. Watch the log for
   `pip install -r requirements.txt` followed by gunicorn starting.

### Set the Gemini key

The blueprint declares `GEMINI_API_KEY` with `sync: false`, meaning Render will
**prompt** for it rather than generating a value. If you skipped that step:

- **Dashboard** → your service → **Environment** → **Add Environment Variable**
- Key: `GEMINI_API_KEY`
- Value: your key from <https://aistudio.google.com/apikey>
- Save, then **Restart Instance**.

Until this is set the app still works - it serves plans from the offline
catalogue and shows a notice on each result page.

### Confirm it is healthy

```bash
curl https://<your-service>.onrender.com/api/health
```

Expected:

```json
{
  "status": "ok",
  "ai": { "configured": true, "sdk": "genai", "model": "gemini-2.5-flash", "available": true },
  "plans": ["home", "party", "jewelry"]
}
```

`"configured": false` means the environment variable never made it into the
service. The health check Render polls is this same endpoint, via
`healthCheckPath: /api/health`.

### Custom domain

**Dashboard → your service → Settings → Custom Domains → Add Custom Domain**,
then add the CNAME Render shows at your DNS provider. Once the host is verified
and Render has issued a certificate, leave `SESSION_COOKIE_SECURE=true` in place
so sessions stay HTTPS-only.

### Cost and cold starts

`render.yaml` specifies `plan: starter`, which is **$7/month**. On the free
plan, change `plan: free` - but expect the service to sleep during inactivity
and take roughly 30-60 seconds to wake on the first request. Free instances
also spin down after 15 minutes idle, which will feel broken during a demo.

---

## Option B: Docker

The `Dockerfile` builds a production image running as a non-root user on port
8080 with a built-in health check.

```bash
docker build -t pocketsmart-ai .
docker run --rm -p 8080:8080 --env-file .env pocketsmart-ai
```

Then verify:

```bash
curl http://localhost:8080/api/health
```

For a real deployment pass the database and secrets through:

```bash
docker run -d --name pocketsmart-ai \
  -p 8080:8080 \
  -v pocketsmart-data:/app/data \
  -e SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')" \
  -e GEMINI_API_KEY="your-key" \
  -e FLASK_ENV=production \
  pocketsmart-ai
```

The named volume keeps the database across restarts and redeploys. A platform
that ignores volumes (Heroku-style, Render's default `/tmp`) will lose data -
see [the note above](#1-the-sqlite-database-is-ephemeral-on-most-platforms).

---

## Option C: Any other WSGI host

The app exposes a standard WSGI callable at `wsgi:application`, so it runs on
gunicorn, uWSGI, waitress or mod_wsgi.

### gunicorn (Linux)

```bash
pip install -r requirements.txt
export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
export GEMINI_API_KEY="your-key"
export FLASK_ENV=production
export DATABASE_PATH=/var/lib/pocketsmart/pocketsmart.db

gunicorn "wsgi:application" \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --threads 4 \
  --timeout 120 \
  --access-logfile -
```

`Procfile` already contains this command, so platforms that read a `Procfile`
(Render, Railway, Fly.io, Heroku) need no extra configuration.

### waitress (Windows)

```bash
waitress-serve --port=8080 wsgi:application
```

### nginx in front

```nginx
server {
    listen 80;
    server_name pocketsmart.example.com;

    client_max_body_size 8M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`X-Forwarded-Proto` matters - without it Flask cannot tell the request arrived
over HTTPS, and secure session cookies will not be set.

---

## Environment variables for production

At minimum set these:

| Variable | Notes |
| --- | --- |
| `SECRET_KEY` | **Required.** Without it a random key is generated at every boot and all users are logged out on each restart. Generate with `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `GEMINI_API_KEY` | Enables live AI. Omit it and the offline catalogue is used. |
| `FLASK_ENV` | `production` - switches off debug output. |
| `DATABASE_PATH` | Point at a persistent location, not the app directory. |
| `ALLOW_GUEST` | `true` to let visitors plan without an account. |

Everything else is listed in [`.env.example`](.env.example) and the README.

**Never commit `.env`.** It is already in `.gitignore`; confirm it has not been
committed before making a repository public:

```bash
git log --all --full-history -- .env
```

No output means you are clean.

---

## Post-deploy checklist

```bash
BASE=https://<your-service>.onrender.com

curl -fsS $BASE/api/health                                    # status ok
curl -fsS "$BASE/api/platforms?type=jewelry"                  # retailer list
curl -fsS $BASE/ | head -5                                    # landing page renders
```

- [ ] `/api/health` returns `"status": "ok"`
- [ ] `ai.configured` is `true` (if you set a key)
- [ ] Landing page renders with styling
- [ ] Register, then build a plan in all three planners
- [ ] Result page shows products **and** working shopping links
- [ ] Save a plan, reload history, delete it
- [ ] Session survives a page refresh
- [ ] Confirm the persistence story for the database matches your intent

---

## Troubleshooting

**App boots but plans say "offline engine"**
`GEMINI_API_KEY` is not set on the service. Check Environment in the dashboard
and restart. Confirm with `curl $BASE/api/health` and look at `ai.configured`.

**`502` or `503` from the platform, app is fine locally**
The service is asleep (free plan cold start) or crashed at boot. Read the
service logs. A missing `SECRET_KEY` warning is harmless; a `RuntimeError` is not.

**Users logged out constantly**
`SECRET_KEY` is unset, so a new random key is generated on every restart and
all sessions are invalidated. Set a fixed one.

**Plans disappeared after a deploy**
Expected on ephemeral storage. See
[note 1](#1-the-sqlite-database-is-ephemeral-on-most-platforms) and move the
database to a persistent disk.

**Slow first request, fast afterwards**
Gemini latency. `GEMINI_MAX_RETRIES=3` retries transient failures with
exponential backoff, so a struggling API call can take a while. Lower
`GEMINI_MAX_RETRIES` or `GEMINI_TIMEOUT` if requests are timing out at the proxy.

**`429 Too many requests` on the planner**
The in-process limiter allows 8 recommendation calls per minute per identity.
With `--workers 2` each worker keeps its own counter, so the real ceiling is
higher and inconsistent. Move the limit to the proxy or cache aggressively.

**`Render` deploy fails at the build step**
`pip install -r requirements.txt` failing is almost always Python version. The
blueprint does not pin one; the app needs **3.11 or newer**. Add
`PYTHON_VERSION` to the environment, or rely on the CI matrix in
`.github/workflows/ci.yml` to confirm which versions work.

**ModuleNotFoundError on a fresh clone**
`google-genai` failed to install, so `GeminiClient._detect_sdk` returns `None`
and AI is unavailable. This degrades gracefully - install the package:
`pip install -r requirements.txt`.

---

## Rollback

Render keeps the previous build. **Dashboard → your service → Events**, pick the
earlier successful deploy and choose **Rollback**.

For GitHub Actions, revert the commit on `main`:

```bash
git revert <sha>
git push origin main
```

That triggers a fresh deploy of the reverted code.
