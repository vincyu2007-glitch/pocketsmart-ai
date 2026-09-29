"""Input validation for the three planners.

Every validator returns a clean, normalised payload dict or raises
:class:`ValidationError` carrying per-field messages so the form can be
re-rendered with inline errors.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from PIL import Image, UnidentifiedImageError

# --- option vocabularies ---------------------------------------------------
ROOM_TYPES = [
    "Living Room",
    "Bedroom",
    "Kitchen",
    "Dining",
    "Kids Room",
    "Study",
    "Office",
    "Bathroom",
    "Balcony",
    "Pooja Room",
]

HOME_STYLES = [
    "Modern",
    "Minimalist",
    "Traditional",
    "Industrial",
    "Scandinavian",
    "Boho",
]

EVENT_TYPES = [
    "Birthday",
    "Wedding",
    "Engagement",
    "Anniversary",
    "Corporate",
    "Baby Shower",
    "Graduation",
    "Festivals",
]

VENUE_TYPES = [
    "At Home",
    "Rented Party Hall",
    "Hotel / Banquet",
    "Outdoor / Farmhouse",
    "Restaurant",
]

ENTERTAINMENT_OPTIONS = [
    "DJ",
    "Live Music",
    "Games & Activities",
    "Photo Booth",
    "None",
]

JEWELRY_OCCASIONS = [
    "Wedding",
    "Engagement",
    "Anniversary",
    "Birthday Gift",
    "Festival / Diwali",
    "Office / Daily Wear",
    "Anniversary Gift",
]

JEWELRY_METALS = ["Gold", "Silver", "Diamond", "Platinum", "Fashion / American Diamond"]

JEWELRY_STYLES = [
    "Traditional",
    "Contemporary",
    "Minimalist",
    "Statement",
    "Elegant",
    "Trendy",
]

KARATS = ["14K", "18K", "22K", "24K", "925 Silver", "Not Applicable"]

TIMELINES = ["Immediately", "Within 1 month", "Within 3 months", "Within 6 months"]

BUDGET_LIMITS = {
    "min": 1000,
    "max": 50_000_000,  # 5 crore
    "soft_min": 5000,
}

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "BMP"}
TEXT_LIMIT = 600
_WHITESPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ValidationError(ValueError):
    """Raised when a planner form fails validation."""

    def __init__(self, errors: dict[str, str], message: str = "Please fix the highlighted fields."):
        super().__init__(message)
        self.errors = {str(k): str(v) for k, v in errors.items()}
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "; ".join(f"{k}: {v}" for k, v in self.errors.items()) or self.message


@dataclass
class ValidatedImage:
    data: bytes
    mime_type: str = "image/jpeg"
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def display_size(self) -> str:
        return f"{self.size_bytes / 1024:.0f} KB"

    def as_dict(self) -> dict[str, Any]:
        return {
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
        }


# --- primitives ------------------------------------------------------------
def clean_text(value: Any, limit: int = TEXT_LIMIT) -> str:
    """Normalise free text: coerce to str, strip control chars, cap length."""
    if value is None:
        return ""
    text = _CONTROL.sub("", str(value))
    text = _WHITESPACE.sub(" ", text).strip()
    return text[:limit]


def clean_multiline(value: Any, limit: int = TEXT_LIMIT * 2) -> str:
    if value is None:
        return ""
    text = _CONTROL.sub("", str(value)).replace("\r\n", "\n").replace("\r", "\n")
    lines = [_WHITESPACE.sub(" ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)[:limit]


def to_number(value: Any, name: str, errors: dict[str, str], *, low: float, high: float) -> float:
    try:
        raw = clean_text(value).replace(",", "").replace("₹", "").strip()
        number = float(raw)
    except (TypeError, ValueError):
        errors[name] = "Enter a valid number."
        return 0.0
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        errors[name] = "Enter a valid number."
        return 0.0
    if number < low or number > high:
        errors[name] = f"Must be between {int(low):,} and {int(high):,}."
        return 0.0
    return number


def to_int(value: Any, name: str, errors: dict[str, str], *, low: int, high: int) -> int:
    number = to_number(value, name, errors, low=low, high=high)
    return int(number)


def to_choice(value: Any, options: Iterable[str], name: str, errors: dict[str, str], label: str) -> str:
    allowed = list(options)
    cleaned = clean_text(value, 60)
    for option in allowed:
        if option.lower() == cleaned.lower():
            return option
    errors[name] = f"Choose one of: {', '.join(allowed)}."
    return cleaned or label


def to_multi_choice(values: Any, options: Iterable[str], name: str, errors: dict[str, str]) -> list[str]:
    allowed = list(options)
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    picked: list[str] = []
    for value in values:
        cleaned = clean_text(value, 60)
        match = next((o for o in allowed if o.lower() == cleaned.lower()), None)
        if match and match not in picked:
            picked.append(match)
    unknown = [
        clean_text(v, 60)
        for v in values
        if clean_text(v, 60)
        and not any(clean_text(v, 60).lower() == o.lower() for o in allowed)
    ]
    if unknown:
        errors[name] = f"Unsupported option(s): {', '.join(unknown[:3])}."
    return picked


def validate_budget(value: Any, name: str = "budget", errors: dict[str, str] | None = None) -> float:
    errors = errors if errors is not None else {}
    return to_number(
        value, name, errors, low=BUDGET_LIMITS["min"], high=BUDGET_LIMITS["max"]
    )


# --- images ----------------------------------------------------------------
def validate_image(
    storage,
    *,
    max_bytes: int = 8 * 1024 * 1024,
    max_dimension: int = 1600,
    field_name: str = "image",
) -> ValidatedImage:
    """Validate and normalise an uploaded outfit/product image.

    Rejects oversized, non-image or corrupt uploads and re-encodes to a bounded
    RGB JPEG, which also strips EXIF/GIF animation payloads.
    """
    if storage is None or not getattr(storage, "filename", ""):
        raise ValidationError({field_name: "Please choose an image file."})

    raw = storage.read()
    if not raw:
        raise ValidationError({field_name: "The uploaded file is empty."})
    if len(raw) > max_bytes:
        raise ValidationError(
            {field_name: f"Image is too large (max {max_bytes // (1024 * 1024)} MB)."}
        )

    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError({field_name: "That file is not a readable image."}) from exc

    if image.format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError(
            {field_name: f"Unsupported format {image.format}. Use JPEG, PNG, WEBP or GIF."}
        )

    warnings: list[str] = []
    if max(image.size) > max_dimension:
        warnings.append(f"Image resized down to {max_dimension}px for faster analysis.")
        image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

    if image.mode in ("RGBA", "LA", "P"):
        warnings.append("Transparency flattened to a white background.")
        image = image.convert("RGBA")
        canvas = Image.new("RGB", image.size, (255, 255, 255))
        canvas.paste(image, mask=image.split()[-1])
        image = canvas
    elif image.mode != "RGB":
        image = image.convert("RGB")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=88, optimize=True)
    data = buffer.getvalue()

    return ValidatedImage(
        data=data,
        mime_type="image/jpeg",
        width=image.width,
        height=image.height,
        size_bytes=len(data),
        warnings=warnings,
    )


# --- planner validators ----------------------------------------------------
def validate_home(form) -> dict[str, Any]:
    errors: dict[str, str] = {}
    payload = {
        "plan_type": "home",
        "budget": validate_budget(form.get("budget"), "budget", errors),
        "area_sqft": to_int(form.get("area_sqft"), "area_sqft", errors, low=50, high=20_000),
        "room_type": to_choice(form.get("room_type"), ROOM_TYPES, "room_type", errors, "Living Room"),
        "style": to_choice(form.get("style"), HOME_STYLES, "style", errors, "Modern"),
        "timeline": to_choice(form.get("timeline"), TIMELINES, "timeline", errors, "Within 1 month"),
        "city": clean_text(form.get("city"), 60),
        "occupants": to_int(form.get("occupants") or 2, "occupants", errors, low=1, high=40),
        "existing_items": clean_multiline(form.get("existing_items")),
        "must_haves": clean_multiline(form.get("must_haves")),
        "color_preference": clean_text(form.get("color_preference"), 120),
    }
    if errors:
        raise ValidationError(errors)
    return payload


def validate_party(form) -> dict[str, Any]:
    errors: dict[str, str] = {}
    payload = {
        "plan_type": "party",
        "budget": validate_budget(form.get("budget"), "budget", errors),
        "event_type": to_choice(form.get("event_type"), EVENT_TYPES, "event_type", errors, "Birthday"),
        "guest_count": to_int(form.get("guest_count"), "guest_count", errors, low=1, high=2000),
        "venue": to_choice(form.get("venue"), VENUE_TYPES, "venue", errors, "At Home"),
        "event_date": clean_text(form.get("event_date"), 40),
        "city": clean_text(form.get("city"), 60),
        "food_preference": clean_text(form.get("food_preference"), 300),
        "decor_theme": clean_text(form.get("decor_theme"), 200),
        "entertainment": to_multi_choice(
            form.getlist("entertainment") if hasattr(form, "getlist") else form.get("entertainment"),
            ENTERTAINMENT_OPTIONS,
            "entertainment",
            errors,
        ),
    }
    if errors:
        raise ValidationError(errors)
    return payload


def validate_jewelry(form) -> dict[str, Any]:
    errors: dict[str, str] = {}
    payload = {
        "plan_type": "jewelry",
        "budget": validate_budget(form.get("budget"), "budget", errors),
        "occasion": to_choice(form.get("occasion"), JEWELRY_OCCASIONS, "occasion", errors, "Wedding"),
        "metal": to_choice(form.get("metal"), JEWELRY_METALS, "metal", errors, "Gold"),
        "karat": to_choice(form.get("karat"), KARATS, "karat", errors, "22K"),
        "style": to_choice(form.get("style"), JEWELRY_STYLES, "style", errors, "Traditional"),
        "gift_for": clean_text(form.get("gift_for"), 80),
        "color_preference": clean_text(form.get("color_preference"), 200),
        "wearing_frequency": clean_text(form.get("wearing_frequency"), 80),
        "has_image": False,
        "image_meta": None,
    }
    if errors:
        raise ValidationError(errors)
    return payload


VALIDATORS = {
    "home": validate_home,
    "party": validate_party,
    "jewelry": validate_jewelry,
}
