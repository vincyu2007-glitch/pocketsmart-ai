"""Shared pytest fixtures."""

from __future__ import annotations

import re

import pytest

from app import create_app
from security import recommendation_limiter, limiter
from services.history import init_db

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture
def app(tmp_path):
    application = create_app("testing")
    application.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        DATABASE_PATH=tmp_path / "test.db",
        DATA_DIR=tmp_path,
        ALLOW_GUEST=False,
        GEMINI_API_KEY="",
        WTF_CSRF_ENABLED=False,
    )
    init_db(application.config["DATABASE_PATH"])
    limiter.reset()
    recommendation_limiter.reset()
    yield application
    limiter.reset()
    recommendation_limiter.reset()


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_token(client, path: str = "/login") -> str:
    """Pull a CSRF token out of a rendered form."""
    html = client.get(path).get_data(as_text=True)
    match = CSRF_RE.search(html)
    assert match, f"no csrf token found on {path}"
    return match.group(1)


@pytest.fixture
def auth_client(client):
    """A client with a registered, signed-in user."""
    token = csrf_token(client, "/register")
    response = client.post(
        "/register",
        data={
            "csrf_token": token,
            "name": "Aarav Sharma",
            "email": "aarav@example.com",
            "password": "supersecret1",
            "confirm": "supersecret1",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Hello, Aarav" in response.data
    return client


HOME_FORM = {
    "budget": "150000",
    "room_type": "Living Room",
    "area_sqft": "450",
    "occupants": "3",
    "style": "Modern",
    "color_preference": "warm neutrals",
    "city": "Pune",
    "existing_items": "one old armchair",
    "must_haves": "sofa, coffee table",
    "timeline": "Within 1 month",
}

PARTY_FORM = {
    "budget": "120000",
    "event_type": "Birthday",
    "guest_count": "40",
    "venue": "Rented Party Hall",
    "event_date": "14 Feb 2027",
    "city": "Pune",
    "food_preference": "North Indian",
    "decor_theme": "pastel garden",
    "entertainment": ["DJ", "Photo Booth"],
}

JEWELRY_FORM = {
    "budget": "250000",
    "occasion": "Engagement",
    "metal": "Gold",
    "karat": "22K",
    "style": "Traditional",
    "gift_for": "self",
    "color_preference": "matches a maroon and gold outfit",
    "wearing_frequency": "on ceremonies",
}
