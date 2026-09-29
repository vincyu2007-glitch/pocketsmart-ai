"""Lightweight security helpers: CSRF tokens and a sliding-window rate limiter."""

from __future__ import annotations

import hmac
import secrets
import time
from collections import defaultdict, deque
from functools import wraps
from typing import Callable

from flask import abort, request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_FIELD = "csrf_token"
CSRF_SESSION_KEY = "_csrf_token"


# --- CSRF ------------------------------------------------------------------
def get_csrf_token() -> str:
    """Return (creating if needed) the token bound to this session."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
        token = session[CSRF_SESSION_KEY]
    return token


def validate_csrf() -> bool:
    sent = (
        request.form.get(CSRF_FIELD)
        or request.headers.get("X-CSRF-Token")
        or (request.is_json and (request.json or {}).get(CSRF_FIELD))
    )
    if not sent:
        return False
    return hmac.compare_digest(str(sent), str(session.get(CSRF_SESSION_KEY, "")))


def csrf_protect(view):
    """Reject unsafe requests without a valid CSRF token."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method not in SAFE_METHODS and not validate_csrf():
            if request.path.startswith("/api/") or request.is_json:
                return {"error": "Invalid or missing CSRF token."}, 400
            abort(400, description="Invalid or missing CSRF token. Please reload the page.")
        return view(*args, **kwargs)

    return wrapper


# --- rate limiting ---------------------------------------------------------
class RateLimiter:
    """In-process sliding window limiter.

    Adequate for a single-process deployment; put a real limiter at the proxy
    (nginx/Cloudflare) when running multiple workers.
    """

    def __init__(self, limit: int = 10, window: int = 60, clock: Callable[[], float] = time.time) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._last_sweep = clock()

    def hit(self, key: str, *, cost: int = 1) -> int:
        """Record a hit. Returns remaining allowance, or -1 if it was blocked."""
        now = self._clock()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) + cost > self.limit:
            return -1
        for _ in range(max(cost, 0)):
            bucket.append(now)
        if now - self._last_sweep > self.window:
            self.sweep(now)
        return max(self.limit - len(bucket), 0)

    def sweep(self, now: float | None = None) -> None:
        now = now if now is not None else self._clock()
        for key in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
            self._hits.pop(key, None)
        self._last_sweep = now

    def reset(self) -> None:
        self._hits.clear()


limiter = RateLimiter(limit=int(10), window=60)
recommendation_limiter = RateLimiter(limit=8, window=60)


def client_key(prefix: str = "") -> str:
    """Identify the caller: user id when signed in, else the remote address."""
    identity = session.get("user_id") or request.remote_addr or "unknown"
    return f"{prefix}{identity}"


def rate_limited(bucket: RateLimiter = limiter, cost: int = 1):
    """Return a decorator that 429s once the window is exhausted."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            remaining = bucket.hit(client_key(), cost=cost)
            if remaining < 0:
                if request.path.startswith("/api/"):
                    return {"error": "Too many requests. Please wait a minute."}, 429
                abort(429, description="Too many requests. Please wait a minute and try again.")
            return view(*args, **kwargs)

        return wrapper

    return decorator


# --- input sanitising for templates ----------------------------------------
def is_safe_next_url(target: str | None) -> bool:
    """Only allow same-site relative redirects (blocks open-redirect)."""
    if not target:
        return False
    return target.startswith("/") and not target.startswith("//") and "\\" not in target
