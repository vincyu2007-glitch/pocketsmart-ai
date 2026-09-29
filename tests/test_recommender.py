"""Offline engine and end-to-end orchestrator tests (with a fake Gemini)."""

from __future__ import annotations

import json

import pytest

from services.fallback import build_offline_recommendation, desired_tags
from services.recommender import allocate_only, build_prompt, generate
from services.shopping import is_safe_url
from services.validators import validate_home, validate_jewelry, validate_party

from .conftest import HOME_FORM, JEWELRY_FORM, PARTY_FORM


class FakeGemini:
    """Stands in for GeminiClient; records calls and returns canned JSON."""

    def __init__(self, payload=None, error=None, model="gemini-2.5-flash"):
        self.payload = payload
        self.error = error
        self.model = model
        self.available = True
        self.calls = []

    def generate_json(self, prompt, image=None, mime_type="image/jpeg"):
        self.calls.append({"prompt": prompt, "image": image, "mime": mime_type})
        if self.error:
            raise self.error
        return self.payload

    @property
    def status(self):
        return {"available": self.available, "model": self.model}


def ai_payload(budget, plan_type="home"):
    return {
        "summary": "A test plan.",
        "total_budget": budget,
        "currency": "INR",
        "budget_breakdown": [
            {"category": "Furniture", "amount": int(budget * 0.8), "percentage": 80, "priority": "high", "notes": "biggest line"},
            {"category": "Contingency", "amount": budget - int(budget * 0.8), "percentage": 20, "priority": "standard", "notes": "buffer"},
        ],
        "products": [
            {
                "name": "3-Seater Sofa",
                "category": "Furniture",
                "price": int(budget * 0.5),
                "quantity": 1,
                "platform": "IKEA",
                "search_terms": "3 seater sofa",
                "why": "Fits the room.",
                "features": ["Wood frame", "Washable"],
                "alternatives": ["Loveseat"],
            },
            {
                "name": "Area Rug",
                "category": "Furniture",
                "price": 5000,
                "quantity": 1,
                "platform": "Amazon",
                "search_terms": "area rug 6x4",
                "why": "Ties the room together.",
                "features": ["Low pile"],
                "alternatives": [],
            },
        ],
        "cost_breakdown": [{"label": "Furniture", "amount": int(budget * 0.8), "note": ""}],
        "suggestions": ["Buy the sofa first."],
        "warnings": ["Sofa lead time is 3 weeks."],
        "shopping_links": [{"platform": "IKEA", "label": "x", "url": "https://evil.example.com/x"}],
    }


class TestOfflineEngine:
    @pytest.mark.parametrize("plan_type,form", [("home", HOME_FORM), ("party", PARTY_FORM), ("jewelry", JEWELRY_FORM)])
    def test_every_plan_produces_a_complete_document(self, plan_type, form):
        payload = {"home": validate_home, "party": validate_party, "jewelry": validate_jewelry}[plan_type](form)
        data = build_offline_recommendation(payload, plan_type)
        assert data["summary"]
        assert data["total_budget"] == payload["budget"]
        assert data["budget_breakdown"]
        assert data["products"]
        assert data["suggestions"]
        assert data["currency"] == "INR"

    def test_allocation_sums_to_budget(self):
        data = build_offline_recommendation(validate_home(HOME_FORM))
        assert sum(r["amount"] for r in data["budget_breakdown"]) == 150000

    def test_products_stay_inside_the_budget(self):
        payload = validate_home(HOME_FORM)
        data = build_offline_recommendation(payload)
        total = sum(p["price"] * p["quantity"] for p in data["products"])
        assert total <= payload["budget"]

    def test_party_quantities_scale_with_guests(self):
        data = build_offline_recommendation(validate_party(PARTY_FORM))
        catering = next(p for p in data["products"] if "Catering" in p["name"])
        assert catering["quantity"] == 40

    def test_tiny_budget_still_returns_something(self):
        form = {**HOME_FORM, "budget": "1000", "area_sqft": "50"}
        data = build_offline_recommendation(validate_home(form))
        assert data["products"]
        assert data["summary"]

    def test_large_budget_scales_up(self):
        form = {**JEWELRY_FORM, "budget": "2500000"}
        data = build_offline_recommendation(validate_jewelry(form))
        assert max(p["price"] for p in data["products"]) > 100000

    def test_desired_tags_map_form_choices(self):
        assert "kids" in desired_tags("home", {"room_type": "Kids Room", "style": "Boho", "area_sqft": 300})
        assert "gold" in desired_tags("jewelry", {"metal": "Gold", "style": "Traditional"})
        assert "wedding" in desired_tags("party", {"event_type": "Wedding", "guest_count": 50})

    def test_deterministic_for_identical_input(self):
        payload = validate_home(HOME_FORM)
        assert build_offline_recommendation(payload) == build_offline_recommendation(payload)


class TestGenerateWithFakeAI:
    def test_ai_output_is_normalised_and_enriched(self):
        client = FakeGemini(ai_payload(150000))
        result = generate("home", validate_home(HOME_FORM), client=client)
        data = result.data
        assert result.meta["source"] == "ai"
        assert sum(r["amount"] for r in data["budget_breakdown"]) == 150000
        assert data["shopping_links"]
        assert all(is_safe_url(link["url"]) for link in data["shopping_links"])
        assert all(is_safe_url(p["search_url"]) for p in data["products"])

    def test_hallucinated_model_urls_are_discarded(self):
        client = FakeGemini(ai_payload(150000))
        data = generate("home", validate_home(HOME_FORM), client=client).data
        assert all("evil.example.com" not in link["url"] for link in data["shopping_links"])

    def test_underspend_is_reported(self):
        client = FakeGemini(ai_payload(150000))
        data = generate("home", validate_home(HOME_FORM), client=client).data
        assert data["stats"]["unallocated"] > 0
        assert any("unallocated" in s for s in data["suggestions"])

    def test_overspend_is_flagged(self):
        payload = ai_payload(150000)
        payload["products"][0]["price"] = 200000
        client = FakeGemini(payload)
        data = generate("home", validate_home(HOME_FORM), client=client).data
        assert any("above the budget" in w for w in data["warnings"])

    def test_breakdown_is_reconciled_to_the_budget(self):
        payload = ai_payload(150000)
        payload["budget_breakdown"] = [{"category": "Furniture", "amount": 1000}]
        client = FakeGemini(payload)
        data = generate("home", validate_home(HOME_FORM), client=client).data
        assert sum(r["amount"] for r in data["budget_breakdown"]) == 150000

    def test_model_budget_is_overwritten_with_the_user_budget(self):
        payload = ai_payload(150000)
        payload["total_budget"] = 999999
        client = FakeGemini(payload)
        data = generate("home", validate_home(HOME_FORM), client=client).data
        assert data["total_budget"] == 150000

    def test_party_stats_include_per_guest(self):
        client = FakeGemini(ai_payload(120000, "party"))
        data = generate("party", validate_party(PARTY_FORM), client=client).data
        assert data["stats"]["per_guest"] == 3000
        assert data["stats"]["guests"] == 40

    def test_jewelry_stats_include_grams_estimate(self):
        client = FakeGemini(ai_payload(250000, "jewelry"))
        data = generate("jewelry", validate_jewelry(JEWELRY_FORM), client=client).data
        assert data["stats"]["grams_estimate"] > 0
        assert data["stats"]["karat"] == "22K"

    def test_home_stats_include_cost_per_sqft(self):
        client = FakeGemini(ai_payload(150000))
        data = generate("home", validate_home(HOME_FORM), client=client).data
        assert data["stats"]["cost_per_sqft"] == round(150000 / 450)

    def test_image_is_forwarded_to_the_client(self):
        client = FakeGemini(ai_payload(250000, "jewelry"))
        meta = {"width": 900, "height": 1200, "mime_type": "image/jpeg", "size_bytes": 90_000}
        result = generate(
            "jewelry", validate_jewelry(JEWELRY_FORM), client=client, image=b"jpegbytes", image_meta=meta
        )
        assert client.calls[0]["image"] == b"jpegbytes"
        assert result.meta["used_image"] is True
        assert "IMAGE ANALYSIS" in client.calls[0]["prompt"]

    def test_jewelry_links_use_jewellery_platforms(self):
        client = FakeGemini(ai_payload(250000, "jewelry"))
        data = generate("jewelry", validate_jewelry(JEWELRY_FORM), client=client).data
        hosts = " ".join(link["url"] for link in data["shopping_links"])
        assert "ikea" not in hosts
        assert all(is_safe_url(p["search_url"]) for p in data["products"])

    def test_falls_back_to_offline_when_the_api_fails(self):
        from services.gemini_client import GeminiError

        client = FakeGemini(error=GeminiError("quota exceeded"))
        result = generate("home", validate_home(HOME_FORM), client=client)
        assert result.meta["source"] == "offline"
        assert result.data["products"]
        assert "quota" in result.meta["notice"]

    def test_falls_back_when_no_key_is_configured(self):
        from services.gemini_client import GeminiClient

        result = generate("home", validate_home(HOME_FORM), client=GeminiClient(api_key=""))
        assert result.meta["source"] == "offline"
        assert result.data["summary"]

    def test_malformed_ai_output_still_renders(self):
        client = FakeGemini({"products": [{"name": "Sofa"}]})
        data = generate("home", validate_home(HOME_FORM), client=client).data
        assert data["products"][0]["search_url"]
        assert data["budget_breakdown"]

    def test_unknown_plan_type_raises(self):
        with pytest.raises(ValueError):
            generate("spaceship", {"budget": 1000})

    def test_meta_records_timing_and_prompt_size(self):
        client = FakeGemini(ai_payload(150000))
        meta = generate("home", validate_home(HOME_FORM), client=client).meta
        assert meta["elapsed_ms"] >= 0
        assert meta["prompt_chars"] > 500
        assert meta["model"] == "gemini-2.5-flash"

    def test_result_is_json_serialisable(self):
        client = FakeGemini(ai_payload(150000))
        result = generate("home", validate_home(HOME_FORM), client=client)
        assert json.loads(json.dumps(result.to_dict()))


class TestAllocationEngine:
    def test_uses_ai_allocation_when_available(self):
        client = FakeGemini(
            {
                "summary": "Split it.",
                "budget_breakdown": [
                    {"category": "Furniture", "amount": 120000, "percentage": 80, "priority": "high", "notes": "n"},
                    {"category": "Contingency", "amount": 30000, "percentage": 20, "priority": "standard", "notes": "n"},
                ],
                "suggestions": ["Measure first."],
            }
        )
        result = allocate_only("home", validate_home(HOME_FORM), client=client)
        assert result.meta["source"] == "ai"
        assert sum(r["amount"] for r in result.data["budget_breakdown"]) == 150000

    def test_falls_back_to_the_deterministic_split(self):
        client = FakeGemini({"budget_breakdown": []})
        result = allocate_only("home", validate_home(HOME_FORM), client=client)
        assert result.meta["source"] == "offline"
        assert sum(r["amount"] for r in result.data["budget_breakdown"]) == 150000

    def test_prompt_requests_only_a_breakdown(self):
        client = FakeGemini({"budget_breakdown": [{"category": "A", "amount": 1}]})
        allocate_only("home", validate_home(HOME_FORM), client=client)
        assert "budget_breakdown" in client.calls[0]["prompt"]
        assert "do not recommend products" in client.calls[0]["prompt"].lower()


def test_build_prompt_is_deterministic_for_the_same_payload():
    payload = validate_home(HOME_FORM)
    assert build_prompt("home", payload) == build_prompt("home", payload)
