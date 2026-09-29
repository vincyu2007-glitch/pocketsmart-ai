# PocketSmart AI

AI budget planner for the Indian market. Enter a budget and a few details about
your home makeover, party or jewellery purchase, and PocketSmart returns a
fully itemised plan with real shopping links on Amazon, Flipkart, IKEA,
Tanishq, CaratLane and more.

All amounts are in **INR** and are formatted the Indian way (`1,23,456`, `1.23 L`).

---

## Features

| Planner | What it produces |
| --- | --- |
| **Home Interior** | Room-by-room budget split, product list with quantities, cost-per-sqft, linked to IKEA / Pepperfry / Amazon / Urban Company |
| **Party** | Per-head cost, venue / F&B / decor split, catering and event-service links (Swiggy, Zomato, PartyKart, BookMyEvents) |
| **Jewellery** | Karat-wise allocation, gram and rate estimates, making-charge reserve, links to Tanishq / Malabar / CaratLane / Bluestone |

Also included:

- **Budget Allocation Engine** - a separate AI mode that only splits the money,
  without a product catalogue.
- **Image-aware jewellery planning** - upload a photo and Gemini factors the
  design into the recommendation.
- **Plan history** - every saved plan is retrievable and deletable per user.
- **Works with no API key** - a curated offline catalogue takes over so the app
  is never dead on screen.
- **Account system** - scrypt-hashed passwords, cookie sessions.

---

## Tech stack

- **Python 3.11+** and **Flask 3**
- **Google Gemini** via `google-genai` (falls back to `google-generativeai`)
- **SQLite** (WAL mode, no ORM, no external database)
- **Jinja2** templates, vanilla CSS/JS - no build step, no bundler
- **gunicorn** in production, **pytest** for tests

---

## Quick start

```bash
git clone https://github.com/vincyu2007-glitch/pocketsmart-ai.git
cd pocketsmart-ai

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

copy .env.example .env      # Windows
# cp .env.example .env      # macOS / Linux

python app.py
```

Open <http://127.0.0.1:5000>.

The app starts and is fully usable **without** a Gemini key. To enable live AI,
put a key in `.env`:

```bash
GEMINI_API_KEY=your-key-here
```

Get one at <https://aistudio.google.com/apikey>.

---

## Configuration

Every variable is optional except `SECRET_KEY` in production (it is generated
automatically if unset, but then sessions die on every restart).

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | random | Flask session signing key. Set this in production. |
| `FLASK_ENV` | `development` | `development`, `testing` or `production`. |
| `FLASK_DEBUG` | `false` | Enables the debugger and reloader. |
| `PORT` | `5000` | Port used by `python app.py`. |
| `ALLOW_GUEST` | `false` | Let visitors plan without signing in. |
| `SESSION_LIFETIME_SECONDS` | `43200` | Session lifetime (12 h). |
| `SESSION_COOKIE_SECURE` | `true` in prod | Only send cookies over HTTPS. |
| `GEMINI_API_KEY` | *(empty)* | Google AI Studio key. Blank = offline engine. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Any multimodal model id. |
| `GEMINI_TEMPERATURE` | `0.4` | Lower = more literal. |
| `GEMINI_MAX_OUTPUT_TOKENS` | `8192` | Response cap. |
| `GEMINI_TIMEOUT` | `60` | Seconds. |
| `GEMINI_MAX_RETRIES` | `3` | Retries on transient API errors. |
| `DATA_DIR` | `data` | Writable directory for the database. |
| `DATABASE_PATH` | `data/pocketsmart.db` | SQLite file location. |
| `MAX_CONTENT_LENGTH_MB` | `8` | Max upload size. |
| `MAX_IMAGE_DIMENSION` | `1600` | Longest image edge in pixels. |

See [`.env.example`](.env.example) for the annotated template.

---

## Project layout

```
app.py                  Flask application factory, error handlers, CLI commands
config.py               Environment-driven configuration
views.py                All HTTP routes (pages + JSON API)
security.py             CSRF tokens, sliding-window rate limiter, open-redirect guard
wsgi.py                 gunicorn entry point -> wsgi:application

services/
  recommender.py        Orchestrator: validate -> prompt -> Gemini -> enforce budget -> links
  prompts.py            Prompt builders and the enforced JSON response schema
  gemini_client.py      Gemini wrapper: JSON extraction, retries, SDK detection
  budget.py             Deterministic allocation (largest-remainder method)
  catalog.py            Curated product catalogue used by the offline engine
  fallback.py           Offline recommendation builder
  shopping.py           Retailer registry and safe search-link generation
  validators.py         Per-planner form validation
  history.py            SQLite persistence

templates/              Jinja2 pages (dashboard, three planners, result, history)
static/                 style.css and app.js
tests/                  202 pytest tests
```

---

## Routes

### Pages

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Landing page |
| `GET`/`POST` | `/register` | Create an account |
| `GET`/`POST` | `/login` | Sign in |
| `POST` | `/logout` | Sign out |
| `POST` | `/demo-login` | One-click demo account |
| `GET` | `/dashboard` | Recent plans |
| `GET`/`POST` | `/plan/<home\|party\|jewelry>` | Planner form and submit |
| `GET` | `/result/<id>` | A saved plan |
| `GET` | `/history` | All saved plans, filterable by type |
| `POST` | `/history/<id>/delete` | Delete a plan |
| `POST` | `/allocate` | Budget-allocation-only mode |

### JSON API

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/health` | no | Liveness probe and AI status |
| `GET` | `/api/platforms?type=home` | no | Retailer list for a plan type |
| `POST` | `/api/recommend` | yes | Full recommendation as JSON |

Example:

```bash
curl -X POST http://127.0.0.1:5000/api/recommend \
  -H 'Content-Type: application/json' \
  -H "X-CSRF-Token: $TOKEN" \
  -b cookies.txt \
  -d '{"plan_type":"home","budget":250000,"area_sqft":600,
       "room_type":"Living Room","style":"Modern","timeline":"Within 1 month"}'
```

`/api/recommend` requires a session cookie and a CSRF token, so use the HTML
forms unless you are scripting a logged-in session.

---

## Architecture notes

### The recommendation pipeline

```
validate form  ->  build prompt  ->  Gemini (or offline engine)  ->  normalise
                ->  enforce budget ceiling  ->  attach vetted links  ->  stats
```

Two things are worth knowing:

1. **The budget ceiling is enforced in code, not trusted to the model.**
   `_enforce_budget` reconciles the category split so the parts always sum to
   the budget, and flags when the selected products cost more than the budget.

2. **The render path is total.** `normalise_response` coerces whatever the model
   returns into the exact shape the templates expect and never raises on a
   missing key. A malformed model response degrades, it does not 500.

### Graceful degradation

If the Gemini key is missing, the SDK is absent, or the API is rate-limited,
`build_offline_recommendation` builds a plan from the curated catalogue in
`services/catalog.py`. The result page shows a notice explaining the fallback.
The app is never blank.

### Security

- Passwords hashed with **scrypt** via `werkzeug.security`.
- **CSRF** tokens on every unsafe method, compared with `hmac.compare_digest`.
- **Rate limiting** on login, registration and AI endpoints (sliding window).
  Note this is in-process, so with multiple gunicorn workers each worker keeps
  its own counter - put a real limiter at the proxy if that matters.
- **Open-redirect protection** via `is_safe_next_url` on all `?next=` targets.
- **Shopping links** are rendered from a template registry and validated to be
  HTTPS on a known marketplace host, so the model cannot inject a link.
- **Uploads** are size-checked, format-checked and re-encoded through Pillow.
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, and HSTS when `SESSION_COOKIE_SECURE` is on.

---

## Testing

```bash
python -m pytest
```

202 tests covering budget allocation, the offline engine, the Gemini JSON
extractor and response normaliser, prompt construction, shopping-link safety,
SQLite persistence, form validation and the HTTP routes. No network access and
no API key required.

Verified on Python 3.11, 3.12 and 3.13.

---

## Deployment

See **[DEPLOY.md](DEPLOY.md)** for step-by-step deployment to Render (a
`render.yaml` blueprint is included), Docker, and other hosts.

---

## Licence

No licence granted. All rights reserved.
