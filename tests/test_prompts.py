"""Prompt engineering, JSON extraction and response-normalisation tests."""

from __future__ import annotations

import json

import pytest

from services import prompts
from services.gemini_client import (
    GeminiClient,
    GeminiError,
    GeminiNotConfigured,
    coerce_int,
    coerce_str_list,
    extract_json,
    normalise_response,
)
from services.recommender import build_prompt
from services.validators import validate_home, validate_jewelry, validate_party

from .conftest import HOME_FORM, JEWELRY_FORM, PARTY_FORM


@pytest.fixture(scope="module")
def home_payload():
    return validate_home(HOME_FORM)


@pytest.fixture(scope="module")
def party_payload():
    return validate_party(PARTY_FORM)


@pytest.fixture(scope="module")
def jewelry_payload():
    return validate_jewelry(JEWELRY_FORM)


class TestPromptContent:
    def test_home_prompt_contains_user_facts(self, home_payload):
        text = prompts.build_home_prompt(home_payload)
        assert "150000" in text
        assert "Living Room" in text
        assert "Modern" in text
        assert "Pune" in text

    def test_home_prompt_lists_allowed_platforms(self, home_payload):
        text = prompts.build_home_prompt(home_payload)
        for platform in ("Amazon", "IKEA", "Urban Company", "Pepperfry"):
            assert platform in text

    def test_party_prompt_derives_per_guest_rate(self, party_payload):
        text = prompts.build_party_prompt(party_payload)
        assert "3000" in text  # 120000 / 40 guests
        assert "Swiggy" in text and "OYO" in text

    def test_jewelry_prompt_has_money_rules(self, jewelry_payload):
        text = prompts.build_jewelry_prompt(jewelry_payload)
        assert "22K" in text
        assert "making charges" in text.lower()
        assert "lab-grown" in text.lower()

    def test_image_prompt_adds_image_instructions(self, jewelry_payload):
        meta = {"width": 900, "height": 1200, "mime_type": "image/jpeg", "size_bytes": 120_000}
        text = prompts.build_jewelry_image_prompt(jewelry_payload, meta)
        assert "IMAGE ANALYSIS" in text
        assert "900x1200" in text
        assert "dominant colour" in text

    def test_guardrails_appear_in_every_prompt(self, home_payload, party_payload, jewelry_payload):
        for text in (
            prompts.build_home_prompt(home_payload),
            prompts.build_party_prompt(party_payload),
            prompts.build_jewelry_prompt(jewelry_payload),
        ):
            assert "STRICT RULES" in text
            assert "INR" in text
            assert "single raw JSON object" in text
            assert "NEVER output URLs" in text

    def test_allocation_prompt_returns_only_a_split(self, home_payload):
        text = prompts.build_allocation_prompt({**home_payload, "plan_type": "home"})
        assert "Contingency" in text
        assert "sum" in text.lower()

    def test_build_prompt_dispatches_to_the_image_variant(self, jewelry_payload):
        meta = {"width": 10, "height": 10, "mime_type": "image/jpeg", "size_bytes": 100}
        assert "IMAGE ANALYSIS" in build_prompt("jewelry", jewelry_payload, meta)
        assert "IMAGE ANALYSIS" not in build_prompt("jewelry", jewelry_payload, None)

    def test_build_prompt_rejects_unknown_plan(self, home_payload):
        with pytest.raises(ValueError):
            build_prompt("nope", home_payload)

    def test_prompts_have_no_unrendered_placeholders(self, home_payload, party_payload, jewelry_payload):
        texts = [
            prompts.build_home_prompt(home_payload),
            prompts.build_party_prompt(party_payload),
            prompts.build_jewelry_prompt(jewelry_payload),
            prompts.build_jewelry_image_prompt(
                jewelry_payload, {"width": 1, "height": 1, "size_bytes": 1}
            ),
        ]
        for text in texts:
            for placeholder in ("{budget}", "{q}", "{slug}", "{platform}", "{city}"):
                assert placeholder not in text

    def test_user_facts_block_never_leaks_python_none(self, home_payload, party_payload, jewelry_payload):
        for text in (
            prompts.build_home_prompt(home_payload),
            prompts.build_party_prompt(party_payload),
            prompts.build_jewelry_prompt(jewelry_payload),
        ):
            facts_block = text.split("USER INPUT:")[1].split("PLATFORMS")[0]
            assert "None" not in facts_block


class TestExtractJson:
    def test_plain_object(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_markdown_fenced(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_bare_fence_without_language(self):
        assert extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_prose_around_object(self):
        assert extract_json('Sure! Here you go:\n{"a": 1}\nHope that helps.') == {"a": 1}

    def test_nested_objects(self):
        payload = {"a": {"b": [1, 2, {"c": 3}]}}
        assert extract_json(f"prefix {json.dumps(payload)} suffix") == payload

    def test_braces_inside_strings(self):
        assert extract_json('{"a": "} not the end {"}') == {"a": "} not the end {"}

    def test_escaped_quotes(self):
        assert extract_json('{"a": "he said \\"hi\\""}') == {"a": 'he said "hi"'}

    def test_trailing_commas_repaired(self):
        assert extract_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}

    def test_empty_response_raises(self):
        with pytest.raises(GeminiError):
            extract_json("")

    def test_garbage_raises(self):
        with pytest.raises(GeminiError):
            extract_json("I cannot help with that.")


class TestCoercion:
    @pytest.mark.parametrize(
        "value,expected",
        [(5, 5), ("5", 5), ("₹1,200", 1200), (5.6, 6), (None, 0), ("abc", 0), (True, 0), (float("nan"), 0)],
    )
    def test_coerce_int(self, value, expected):
        assert coerce_int(value) == expected

    def test_coerce_str_list_handles_junk(self):
        assert coerce_str_list("one") == ["one"]
        assert coerce_str_list(["a", "", None, 5]) == ["a", "5"]
        assert coerce_str_list({"a": 1}) == []
        assert len(coerce_str_list([f"i{i}" for i in range(50)], limit=3)) == 3


class TestNormaliseResponse:
    def test_missing_keys_get_safe_defaults(self):
        data = normalise_response({}, plan_type="home", budget=100000)
        assert data["total_budget"] == 100000
        assert data["products"] == []
        assert data["currency"] == "INR"
        assert data["summary"]

    def test_string_numbers_are_converted(self):
        raw = {
            "total_budget": "150000",
            "budget_breakdown": [{"category": "Furniture", "amount": "100000", "percentage": "66.6"}],
            "products": [{"name": "Sofa", "price": "30000", "quantity": "1"}],
        }
        data = normalise_response(raw, plan_type="home", budget=150000)
        assert data["total_budget"] == 150000
        assert data["budget_breakdown"][0]["amount"] == 100000
        assert data["products"][0]["price"] == 30000

    def test_negative_amounts_are_clamped(self):
        raw = {"budget_breakdown": [{"category": "X", "amount": -5000}]}
        data = normalise_response(raw, plan_type="home", budget=1000)
        assert data["budget_breakdown"][0]["amount"] == 0

    def test_products_without_a_name_are_dropped(self):
        raw = {"products": [{"price": 100}, {"name": "Sofa", "price": 100}]}
        data = normalise_response(raw, plan_type="home", budget=1000)
        assert len(data["products"]) == 1

    def test_junk_entries_are_ignored(self):
        raw = {"products": ["not a dict", {"name": "Sofa"}], "budget_breakdown": ["junk"]}
        data = normalise_response(raw, plan_type="home", budget=1000)
        assert len(data["products"]) == 1
        assert data["budget_breakdown"] == []

    def test_quantity_defaults_to_one(self):
        raw = {"products": [{"name": "Sofa", "quantity": 0}]}
        data = normalise_response(raw, plan_type="home", budget=1000)
        assert data["products"][0]["quantity"] == 1

    def test_nested_data_key_is_unwrapped(self):
        data = normalise_response({"data": {"summary": "hi"}}, plan_type="home", budget=100)
        assert data["summary"] == "hi"

    def test_non_dict_raises(self):
        with pytest.raises(GeminiError):
            normalise_response(["a list"], plan_type="home", budget=100)


class TestClientConfig:
    def test_reports_unavailable_without_key(self):
        client = GeminiClient(api_key="", model="gemini-2.5-flash")
        assert client.available is False
        assert client.status["configured"] is False

    def test_raises_when_called_without_key(self):
        client = GeminiClient(api_key="")
        with pytest.raises(GeminiNotConfigured):
            client.generate_json("hi")

    def test_raises_when_called_without_sdk(self, monkeypatch):
        client = GeminiClient(api_key="k")
        client._sdk = None
        with pytest.raises(GeminiNotConfigured):
            client.generate_json("hi")

    def test_detects_an_installed_sdk(self):
        client = GeminiClient(api_key="k")
        assert client._sdk in {"genai", "legacy"}

    def test_retries_then_raises_on_persistent_failure(self, monkeypatch):
        client = GeminiClient(api_key="k", max_retries=2)
        calls = {"n": 0}

        def boom(*args, **kwargs):
            calls["n"] += 1
            raise RuntimeError("503 Service Unavailable")

        monkeypatch.setattr(client, "_call", boom)
        monkeypatch.setattr("services.gemini_client.time.sleep", lambda *_: None)
        with pytest.raises(GeminiError):
            client.generate_text("hi")
        assert calls["n"] == 2

    def test_does_not_retry_permanent_errors(self, monkeypatch):
        client = GeminiClient(api_key="k", max_retries=3)
        calls = {"n": 0}

        def boom(*args, **kwargs):
            calls["n"] += 1
            raise ValueError("Invalid API key provided")

        monkeypatch.setattr(client, "_call", boom)
        with pytest.raises(GeminiError):
            client.generate_text("hi")
        assert calls["n"] == 1

    def test_returns_text_on_success(self, monkeypatch):
        client = GeminiClient(api_key="k")
        monkeypatch.setattr(client, "_call", lambda *a, **k: '{"ok": true}')
        assert client.generate_json("hi") == {"ok": True}
