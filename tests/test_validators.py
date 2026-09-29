"""Validator tests: budgets, enums, free text and image uploads."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from services.validators import (
    ValidationError,
    clean_multiline,
    clean_text,
    validate_home,
    validate_image,
    validate_jewelry,
    validate_party,
)

from .conftest import HOME_FORM, JEWELRY_FORM, PARTY_FORM


class TestCleanText:
    def test_strips_control_characters_and_collapses_space(self):
        assert clean_text("  Sofa\x00 \n\t  bed  ") == "Sofa bed"

    def test_truncates_at_limit(self):
        assert len(clean_text("x" * 900, limit=100)) == 100

    def test_handles_none(self):
        assert clean_text(None) == ""

    def test_multiline_keeps_line_breaks(self):
        assert clean_multiline("a\r\n b \n\n c ") == "a\nb\nc"


class TestHomeValidator:
    def test_accepts_a_valid_form(self):
        payload = validate_home(HOME_FORM)
        assert payload["budget"] == 150000.0
        assert payload["room_type"] == "Living Room"
        assert payload["area_sqft"] == 450
        assert payload["plan_type"] == "home"

    def test_rejects_budget_below_the_floor(self):
        with pytest.raises(ValidationError) as exc:
            validate_home({**HOME_FORM, "budget": "10"})
        assert "budget" in exc.value.errors

    def test_rejects_budget_above_the_ceiling(self):
        with pytest.raises(ValidationError) as exc:
            validate_home({**HOME_FORM, "budget": "990000000"})
        assert "budget" in exc.value.errors

    def test_rejects_unknown_room_type(self):
        with pytest.raises(ValidationError) as exc:
            validate_home({**HOME_FORM, "room_type": "Cockpit"})
        assert "room_type" in exc.value.errors

    def test_is_case_insensitive_on_options(self):
        assert validate_home({**HOME_FORM, "style": "modern"})["style"] == "Modern"

    def test_rejects_non_numeric_area(self):
        with pytest.raises(ValidationError) as exc:
            validate_home({**HOME_FORM, "area_sqft": "big"})
        assert "area_sqft" in exc.value.errors

    def test_defaults_occupants_when_blank(self):
        assert validate_home({**HOME_FORM, "occupants": ""})["occupants"] == 2

    def test_reports_every_bad_field_at_once(self):
        with pytest.raises(ValidationError) as exc:
            validate_home({**HOME_FORM, "budget": "x", "area_sqft": "-5", "style": "nope"})
        assert set(exc.value.errors) == {"budget", "area_sqft", "style"}


class TestPartyValidator:
    def test_accepts_a_valid_form(self):
        payload = validate_party(PARTY_FORM)
        assert payload["guest_count"] == 40
        assert payload["entertainment"] == ["DJ", "Photo Booth"]

    def test_rejects_zero_guests(self):
        with pytest.raises(ValidationError) as exc:
            validate_party({**PARTY_FORM, "guest_count": "0"})
        assert "guest_count" in exc.value.errors

    def test_rejects_unknown_entertainment_option(self):
        with pytest.raises(ValidationError) as exc:
            validate_party({**PARTY_FORM, "entertainment": ["Disco"]})
        assert "entertainment" in exc.value.errors

    def test_deduplicates_entertainment(self):
        payload = validate_party({**PARTY_FORM, "entertainment": ["DJ", "DJ", "dj"]})
        assert payload["entertainment"] == ["DJ"]


class TestJewelryValidator:
    def test_accepts_a_valid_form(self):
        payload = validate_jewelry(JEWELRY_FORM)
        assert payload["metal"] == "Gold"
        assert payload["karat"] == "22K"
        assert payload["has_image"] is False

    def test_rejects_unknown_metal(self):
        with pytest.raises(ValidationError) as exc:
            validate_jewelry({**JEWELRY_FORM, "metal": "Plutonium"})
        assert "metal" in exc.value.errors


class _Upload:
    def __init__(self, data: bytes, filename: str = "outfit.jpg"):
        self.filename = filename
        self._data = data

    def read(self):
        return self._data


def _image_bytes(fmt: str = "JPEG", size=(900, 1200), mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, (200, 30, 60)).save(buffer, format=fmt)
    return buffer.getvalue()


class TestImageValidation:
    def test_accepts_and_normalises_a_jpeg(self):
        result = validate_image(_Upload(_image_bytes()))
        assert result.mime_type == "image/jpeg"
        assert result.data[:2] == b"\xff\xd8"
        assert result.size_bytes > 0

    def test_flattens_transparency_to_jpeg(self):
        result = validate_image(_Upload(_image_bytes("PNG", mode="RGBA")))
        assert result.mime_type == "image/jpeg"
        assert any("transparency" in w.lower() for w in result.warnings)

    def test_downscales_large_images(self):
        result = validate_image(_Upload(_image_bytes(size=(3000, 4000))), max_dimension=800)
        assert max(result.width, result.height) <= 800

    def test_rejects_non_image_bytes(self):
        with pytest.raises(ValidationError) as exc:
            validate_image(_Upload(b"this is definitely not an image"))
        assert "image" in exc.value.errors

    def test_rejects_empty_upload(self):
        with pytest.raises(ValidationError):
            validate_image(_Upload(b""))

    def test_rejects_missing_file(self):
        with pytest.raises(ValidationError):
            validate_image(None)

    def test_rejects_oversized_file(self):
        with pytest.raises(ValidationError) as exc:
            validate_image(_Upload(_image_bytes()), max_bytes=64)
        assert "too large" in exc.value.errors["image"].lower()
