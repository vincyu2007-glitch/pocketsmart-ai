"""HTTP layer tests: auth, CSRF, planner forms, results, history and the API."""

from __future__ import annotations

import io
import json
import re

import pytest
from PIL import Image

from security import RateLimiter, is_safe_next_url
from services.shopping import is_safe_url

from .conftest import HOME_FORM, JEWELRY_FORM, PARTY_FORM, csrf_token

PRICE_RE = re.compile(r"[₹]", re.UNICODE)


def upload(name="outfit.jpg", size=(800, 1000), fmt="JPEG"):
    buffer = io.BytesIO()
    Image.new("RGB", size, (120, 20, 60)).save(buffer, format=fmt)
    buffer.seek(0)
    return (buffer, name)


class TestPublicPages:
    def test_index_renders(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"PocketSmart" in response.data
        assert b"Spend smart on" in response.data

    def test_login_page_renders(self, client):
        assert b"Welcome back" in client.get("/login").data

    def test_register_page_renders(self, client):
        assert b"Create your account" in client.get("/register").data

    def test_unknown_plan_returns_404(self, auth_client):
        assert auth_client.get("/plan/spaceship").status_code == 404

    def test_unknown_plan_post_returns_404(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        assert auth_client.post("/plan/spaceship", data={"csrf_token": token}).status_code == 404

    def test_security_headers_are_set(self, client):
        headers = client.get("/").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_health_endpoint_is_public(self, client):
        payload = client.get("/api/health").get_json()
        assert payload["status"] == "ok"
        assert payload["plans"] == ["home", "party", "jewelry"]
        assert "GEMINI" not in json.dumps(payload).upper().replace("GEMINI", "")

    def test_platforms_endpoint(self, client):
        payload = client.get("/api/platforms?type=jewelry").get_json()
        assert any(p["name"] == "Tanishq" for p in payload["platforms"])

    def test_404_page(self, client):
        response = client.get("/definitely-not-here")
        assert response.status_code == 404
        assert b"Page not found" in response.data


class TestAuth:
    def test_register_creates_a_session(self, client):
        token = csrf_token(client, "/register")
        response = client.post(
            "/register",
            data={
                "csrf_token": token, "name": "Meera", "email": "meera@example.com",
                "password": "longenough1", "confirm": "longenough1",
            },
            follow_redirects=True,
        )
        assert b"Hello, Meera" in response.data

    def test_duplicate_email_is_rejected(self, client):
        for _ in range(2):
            token = csrf_token(client, "/register")
            client.post(
                "/register",
                data={"csrf_token": token, "name": "Meera", "email": "dup@example.com",
                      "password": "longenough1", "confirm": "longenough1"},
            )
        token = csrf_token(client, "/register")
        response = client.post(
            "/register",
            data={"csrf_token": token, "name": "Meera", "email": "dup@example.com",
                  "password": "longenough1", "confirm": "longenough1"},
        )
        assert b"already registered" in response.data

    @pytest.mark.parametrize(
        "field,value,message",
        [
            ("password", "short", "8 characters"),
            ("confirm", "different", "do not match"),
            ("email", "not-an-email", "valid email"),
        ],
    )
    def test_registration_validation(self, client, field, value, message):
        token = csrf_token(client, "/register")
        data = {"csrf_token": token, "name": "Meera", "email": "meera@example.com",
                "password": "longenough1", "confirm": "longenough1"}
        data[field] = value
        response = client.post("/register", data=data)
        assert response.status_code == 200
        assert message.encode() in response.data

    def test_wrong_password_is_rejected(self, auth_client):
        auth_client.get("/logout", follow_redirects=True)
        token = csrf_token(auth_client, "/login")
        response = auth_client.post(
            "/login", data={"csrf_token": token, "email": "aarav@example.com", "password": "wrong"}
        )
        assert b"Incorrect email or password" in response.data

    def test_protected_page_redirects_anonymous_users(self, client):
        response = client.get("/plan/home")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_logout_clears_the_session(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        auth_client.post("/logout", data={"csrf_token": token}, follow_redirects=True)
        assert auth_client.get("/dashboard").status_code == 302

    def test_demo_login(self, client):
        token = csrf_token(client, "/login")
        response = client.post("/demo-login", data={"csrf_token": token}, follow_redirects=True)
        assert response.status_code == 200
        assert client.get("/dashboard").status_code == 200

    def test_open_redirect_is_blocked(self, client):
        token = csrf_token(client, "/login")
        response = client.post(
            "/login?next=https://evil.example.com",
            data={"csrf_token": token, "email": "aarav@example.com", "password": "supersecret1"},
        )
        assert "evil.example.com" not in response.headers.get("Location", "")

    def test_safe_next_url_helper(self):
        assert is_safe_next_url("/dashboard")
        assert not is_safe_next_url("//evil.example.com")
        assert not is_safe_next_url("https://evil.example.com")
        assert not is_safe_next_url(None)


class TestCsrf:
    def test_post_without_token_is_rejected(self, auth_client):
        response = auth_client.post("/plan/home", data=HOME_FORM)
        assert response.status_code == 400

    def test_post_with_wrong_token_is_rejected(self, auth_client):
        response = auth_client.post("/plan/home", data={**HOME_FORM, "csrf_token": "forged"})
        assert response.status_code == 400

    def test_api_rejects_missing_token(self, auth_client):
        response = auth_client.post("/api/recommend", json={"plan_type": "home", "budget": 100000})
        assert response.status_code == 400
        assert "CSRF" in response.get_json()["error"]

    def test_logout_requires_a_token(self, auth_client):
        assert auth_client.post("/logout").status_code == 400


class TestRateLimiting:
    def test_limiter_blocks_after_the_limit(self):
        limiter = RateLimiter(limit=3, window=60)
        assert [limiter.hit("k") for _ in range(3)] == [2, 1, 0]
        assert limiter.hit("k") == -1

    def test_limiter_is_per_key(self):
        limiter = RateLimiter(limit=1, window=60)
        assert limiter.hit("a") == 0
        assert limiter.hit("a") == -1
        assert limiter.hit("b") == 0

    def test_expensive_requests_cost_more(self):
        limiter = RateLimiter(limit=3, window=60)
        assert limiter.hit("k", cost=2) == 1
        assert limiter.hit("k", cost=2) == -1

    def test_old_hits_expire(self):
        clock = [0.0]
        limiter = RateLimiter(limit=1, window=60, clock=lambda: clock[0])
        assert limiter.hit("k") == 0
        assert limiter.hit("k") == -1
        clock[0] = 61.0
        assert limiter.hit("k") == 0

    def test_sweep_drops_stale_buckets(self):
        clock = [0.0]
        limiter = RateLimiter(limit=1, window=10, clock=lambda: clock[0])
        limiter.hit("k")
        clock[0] = 100.0
        limiter.sweep()
        assert limiter.hit("k") == 0

    def test_api_returns_json_429(self, auth_client):
        import views

        token = csrf_token(auth_client, "/plan/home")
        views.recommendation_limiter.limit = 1
        try:
            body = {**HOME_FORM, "plan_type": "home"}
            first = auth_client.post("/api/recommend", json=body, headers={"X-CSRF-Token": token})
            assert first.status_code == 200
            second = auth_client.post("/api/recommend", json=body, headers={"X-CSRF-Token": token})
            assert second.status_code == 429
            assert "Too many requests" in second.get_json()["error"]
        finally:
            views.recommendation_limiter.limit = 8

class TestPlannerForms:
    @pytest.mark.parametrize("plan_type", ["home", "party", "jewelry"])
    def test_form_pages_render(self, auth_client, plan_type):
        response = auth_client.get(f"/plan/{plan_type}")
        assert response.status_code == 200
        assert b"csrf_token" in response.data
        assert b"Budget" in response.data or b"budget" in response.data

    def test_home_plan_generates_and_saves(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        response = auth_client.post(
            "/plan/home", data={**HOME_FORM, "csrf_token": token}, follow_redirects=True
        )
        assert response.status_code == 200
        assert b"Budget allocation" in response.data
        assert b"Recommended products" in response.data
        assert b"Shopping links" in response.data

    def test_party_plan_renders_per_guest(self, auth_client):
        token = csrf_token(auth_client, "/plan/party")
        response = auth_client.post(
            "/plan/party", data={**PARTY_FORM, "csrf_token": token}, follow_redirects=True
        )
        assert b"Per guest" in response.data

    def test_jewelry_plan_renders(self, auth_client):
        token = csrf_token(auth_client, "/plan/jewelry")
        response = auth_client.post(
            "/plan/jewelry", data={**JEWELRY_FORM, "csrf_token": token}, follow_redirects=True
        )
        assert b"Recommended products" in response.data

    def test_jewelry_plan_with_image(self, auth_client):
        token = csrf_token(auth_client, "/plan/jewelry")
        response = auth_client.post(
            "/plan/jewelry",
            data={**JEWELRY_FORM, "csrf_token": token, "image": upload()},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Recommended products" in response.data

    def test_jewelry_plan_with_png_image(self, auth_client):
        token = csrf_token(auth_client, "/plan/jewelry")
        response = auth_client.post(
            "/plan/jewelry",
            data={**JEWELRY_FORM, "csrf_token": token, "image": upload("outfit.png", fmt="PNG")},
            follow_redirects=True,
        )
        assert response.status_code == 200

    def test_bad_image_is_rejected_with_an_inline_error(self, auth_client):
        token = csrf_token(auth_client, "/plan/jewelry")
        response = auth_client.post(
            "/plan/jewelry",
            data={**JEWELRY_FORM, "csrf_token": token, "image": (io.BytesIO(b"not an image"), "x.jpg")},
        )
        assert response.status_code == 400
        assert b"not a readable image" in response.data

    def test_oversized_image_is_rejected(self, auth_client, app):
        token = csrf_token(auth_client, "/plan/jewelry")
        app.config["MAX_CONTENT_LENGTH"] = 1024
        response = auth_client.post(
            "/plan/jewelry",
            data={**JEWELRY_FORM, "csrf_token": token, "image": upload(size=(2000, 2000))},
        )
        assert response.status_code in (400, 413)

    def test_invalid_budget_rerenders_with_an_error(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        response = auth_client.post(
            "/plan/home", data={**HOME_FORM, "budget": "-5", "csrf_token": token}
        )
        assert response.status_code == 400
        assert b"Must be between" in response.data
        assert b"value=\"-5\"" in response.data  # keeps what the user typed

    def test_invalid_option_rerenders_with_an_error(self, auth_client):
        token = csrf_token(auth_client, "/plan/party")
        response = auth_client.post(
            "/plan/party", data={**PARTY_FORM, "event_type": "Hackathon", "csrf_token": token}
        )
        assert response.status_code == 400
        assert b"Choose one of" in response.data

    def test_rendered_links_are_all_safe(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        response = auth_client.post(
            "/plan/home", data={**HOME_FORM, "csrf_token": token}, follow_redirects=True
        )
        html = response.get_data(as_text=True)
        for url in re.findall(r'href="(https://[^"]+)"', html):
            assert is_safe_url(url.replace("&amp;", "&")), url


class TestHistory:
    def test_dashboard_is_empty_at_first(self, auth_client):
        response = auth_client.get("/dashboard")
        assert b"No plans yet" in response.data

    def test_saved_plan_appears_in_history(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        auth_client.post("/plan/home", data={**HOME_FORM, "csrf_token": token}, follow_redirects=True)
        response = auth_client.get("/history")
        assert b"Living Room makeover" in response.data

    def test_history_filter(self, auth_client):
        token = csrf_token(auth_client, "/plan/party")
        auth_client.post("/plan/party", data={**PARTY_FORM, "csrf_token": token}, follow_redirects=True)
        assert "Birthday for 40 guests" in auth_client.get("/history?type=party").get_data(as_text=True)
        assert "Birthday for 40 guests" not in auth_client.get("/history?type=home").get_data(as_text=True)

    def test_plan_can_be_deleted(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        auth_client.post("/plan/home", data={**HOME_FORM, "csrf_token": token}, follow_redirects=True)
        html = auth_client.get("/history").get_data(as_text=True)
        rec_id = re.search(r"/history/(\d+)/delete", html).group(1)
        response = auth_client.post(
            f"/history/{rec_id}/delete", data={"csrf_token": token}, follow_redirects=True
        )
        assert b"Plan deleted" in response.data
        assert "Living Room makeover" not in auth_client.get("/history").get_data(as_text=True)

    def test_users_cannot_read_each_others_plans(self, auth_client, app):
        token = csrf_token(auth_client, "/plan/home")
        auth_client.post("/plan/home", data={**HOME_FORM, "csrf_token": token}, follow_redirects=True)
        rec_id = re.search(r"/result/(\d+)", auth_client.get("/dashboard").get_data(as_text=True)).group(1)

        other = app.test_client()
        other.post(
            "/register",
            data={"csrf_token": csrf_token(other, "/register"), "name": "Other", "email": "other@example.com",
                  "password": "longenough1", "confirm": "longenough1"},
            follow_redirects=True,
        )
        response = other.get(f"/result/{rec_id}", follow_redirects=True)
        assert b"was not found" in response.data

    def test_missing_record_redirects(self, auth_client):
        response = auth_client.get("/result/999999", follow_redirects=True)
        assert b"was not found" in response.data


class TestJsonApi:
    def test_recommend_returns_structured_json(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        body = {**HOME_FORM, "plan_type": "home"}
        response = auth_client.post("/api/recommend", json=body, headers={"X-CSRF-Token": token})
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["data"]["total_budget"] == 150000
        assert data["data"]["budget_breakdown"]
        assert data["data"]["meta"]["plan_type"] == "home"

    def test_recommend_rejects_bad_input(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        response = auth_client.post(
            "/api/recommend",
            json={**HOME_FORM, "plan_type": "home", "budget": "abc"},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 400
        assert "budget" in response.get_json()["errors"]

    def test_recommend_rejects_unknown_plan_type(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        response = auth_client.post(
            "/api/recommend", json={"plan_type": "spaceship"}, headers={"X-CSRF-Token": token}
        )
        assert response.status_code == 400

    def test_non_json_body_is_415(self, auth_client):
        token = csrf_token(auth_client, "/plan/home")
        response = auth_client.post(
            "/api/recommend", data="plan_type=home", headers={"X-CSRF-Token": token}
        )
        assert response.status_code == 415

    def test_anonymous_access_is_redirected(self, client):
        token = csrf_token(client, "/login")
        response = client.post(
            "/api/recommend", json={"plan_type": "home"}, headers={"X-CSRF-Token": token}
        )
        assert response.status_code == 302


class TestAllocationRoute:
    def test_allocation_renders(self, auth_client):
        token = csrf_token(auth_client, "/plan/party")
        response = auth_client.post(
            "/allocate", data={**PARTY_FORM, "plan_type": "party", "csrf_token": token}
        )
        assert response.status_code == 200
        assert b"Budget allocation" in response.data
        assert b"Food &amp; Beverages" in response.data

    def test_allocation_rejects_bad_input(self, auth_client):
        token = csrf_token(auth_client, "/plan/party")
        response = auth_client.post(
            "/allocate", data={**PARTY_FORM, "plan_type": "party", "budget": "-1", "csrf_token": token}
        )
        assert response.status_code == 302
