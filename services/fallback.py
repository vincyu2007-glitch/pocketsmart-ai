"""Deterministic offline recommendation engine.

Used when no Gemini API key is configured, when the key is invalid, or when
the API call fails. It produces exactly the same document shape as the AI path
so templates, tests and the JSON API behave identically - only the ``source``
field changes. This is also what makes the project demo-able out of the box.
"""

from __future__ import annotations

from typing import Any

from .budget import allocate_budget, format_inr, per_head, plan_summary, weights_for
from .catalog import (
    HOME_ROOM_ROOM_TAGS,
    HOME_STYLE_TAGS,
    JEWELRY_METAL_TAGS,
    PARTY_EVENT_TAGS,
    catalog_for,
    filter_items,
)

PLAN_LABELS = {"home": "Home Interior", "party": "Party", "jewelry": "Jewelry"}

# How many line items each category gets, and how much of a category's
# allocation is deliberately left unspent so the split never looks oversold.
MAX_ITEMS_PER_CATEGORY = 3
CATEGORY_RESERVE = 0.12
MIN_ITEM_VALUE = 200


def desired_tags(plan_type: str, payload: dict[str, Any]) -> list[str]:
    """Translate the user's form selections into catalog tags."""
    tags: list[str] = ["all"]
    if plan_type == "home":
        room = str(payload.get("room_type", "")).lower()
        style = str(payload.get("style", "")).lower()
        tags.append(HOME_ROOM_ROOM_TAGS.get(room, "all"))
        tags.append(HOME_STYLE_TAGS.get(style, "all"))
        area = float(payload.get("area_sqft") or 500)
        if area <= 400:
            tags.append("small")
    elif plan_type == "party":
        event = str(payload.get("event_type", "")).lower()
        tags.append(PARTY_EVENT_TAGS.get(event, "all"))
        tags.append("all")
    elif plan_type == "jewelry":
        metal = str(payload.get("metal", "")).lower()
        tags.append(JEWELRY_METAL_TAGS.get(metal, "all"))
        style = str(payload.get("style", "")).lower()
        tags.append(style)
    return [t for t in tags if t]


def _unit_for(plan_type: str, item: dict[str, Any], payload: dict[str, Any]) -> tuple[int, str]:
    """Return (quantity, note) for a catalog item."""
    unit = item.get("unit")
    guests = int(payload.get("guest_count") or 0)
    if plan_type == "party" and unit == "per_guest" and guests:
        return guests, f"per guest x {guests}"
    if plan_type == "party" and unit == "per_person" and guests:
        return guests, f"per person x {guests}"
    if unit == "block":
        return 1, "one block for up to 100 sq ft"
    return 1, ""


def _scale_to_budget(price: float, quantity: int, available: float) -> tuple[int, int, bool]:
    """Clamp (price, quantity) so ``price * quantity`` fits inside ``available``.

    Returns ``(unit_price, quantity, was_reduced)``.
    """
    price, quantity = float(price), max(int(quantity), 1)
    available = max(float(available), 0)
    if available <= 0 or price * quantity <= available:
        return int(price), quantity, False

    unit_price = int(available // quantity)
    if unit_price < 50 and quantity > 1:  # not viable per unit -> sell a single unit
        quantity, unit_price = 1, int(available)
    return unit_price, quantity, True


def build_offline_recommendation(
    payload: dict[str, Any], plan_type: str | None = None
) -> dict[str, Any]:
    """Build a full recommendation document without calling any model."""
    plan_type = plan_type or payload.get("plan_type", "home")
    budget = int(float(payload.get("budget", 0)))
    tags = desired_tags(plan_type, payload)

    allocation = allocate_budget(budget, weights_for(plan_type))
    products: list[dict[str, Any]] = []
    warnings: list[str] = []
    shortfall: list[str] = []

    for entry in allocation:
        category = entry["category"]
        available = entry["amount"]
        if category.lower().startswith("contingen"):
            continue

        items = filter_items(plan_type, category, tags, max_price=available)
        if not items:
            continue

        # Fill the category greedily, holding back a reserve so the plan never
        # promises to spend the last rupee of a category.
        remaining = int(available * (1 - CATEGORY_RESERVE))
        added = 0
        for item in items:
            if added >= MAX_ITEMS_PER_CATEGORY or remaining < MIN_ITEM_VALUE:
                break
            quantity, unit_note = _unit_for(plan_type, item, payload)
            unit_price, quantity, reduced = _scale_to_budget(
                item["price"], quantity, remaining
            )
            if reduced:
                warnings.append(
                    f"{item['name']} was trimmed to "
                    f"{format_inr(unit_price * quantity)} to stay inside the {category} allocation."
                )
            line_total = unit_price * quantity
            if line_total <= 0:
                if not added:
                    shortfall.append(category)
                break

            products.append(
                {
                    "name": item["name"],
                    "category": category,
                    "price": unit_price,
                    "quantity": quantity,
                    "platform": item["platform"],
                    "search_terms": item["search_terms"],
                    "why": _why(plan_type, item, payload, category),
                    "features": list(item["features"]),
                    "alternatives": [
                        f"{item['name']} - entry variant",
                        f"{item['name']} - premium variant",
                    ],
                    "unit_note": unit_note,
                }
            )
            remaining -= line_total
            added += 1

        if added == 0:
            shortfall.append(category)

    if shortfall:
        warnings.append(
            "No realistic option fits: " + ", ".join(shortfall) + ". Increase the budget or "
            "downgrade the requirement."
        )

    summary = _summary(plan_type, payload, allocation, products)
    cost_breakdown = [
        {
            "label": entry["category"],
            "amount": entry["amount"],
            "note": entry["notes"] or f"{entry['percentage']}% of budget",
        }
        for entry in allocation
    ]

    return {
        "summary": summary,
        "total_budget": budget,
        "currency": "INR",
        "budget_breakdown": [
            {**entry, "notes": entry["notes"] or f"{entry['percentage']}% of budget"}
            for entry in allocation
        ],
        "products": products,
        "cost_breakdown": cost_breakdown,
        "suggestions": _suggestions(plan_type, payload),
        "warnings": warnings,
        "plan_type": plan_type,
    }


# --- narrative helpers -----------------------------------------------------
def _why(plan_type: str, item: dict[str, Any], payload: dict[str, Any], category: str) -> str:
    if plan_type == "home":
        return (
            f"Matches the {payload.get('style', 'modern')} look for a "
            f"{payload.get('area_sqft')} sq ft {str(payload.get('room_type', 'room')).lower()} "
            f"and fits the {category} allocation."
        )
    if plan_type == "party":
        guests = int(payload.get("guest_count") or 0)
        return (
            f"Works for a {str(payload.get('event_type', 'event')).lower()} with {guests} "
            f"guests and holds inside the {category} budget."
        )
    return (
        f"Fits a {str(payload.get('occasion', 'special-occasion')).lower()} purchase in "
        f"{str(payload.get('metal', 'gold')).lower()} within the {category} budget."
    )


def _summary(
    plan_type: str, payload: dict[str, Any], allocation: list[dict], products: list[dict]
) -> str:
    label = PLAN_LABELS.get(plan_type, "Plan")
    budget = int(float(payload.get("budget", 0)))
    top = allocation[0] if allocation else {"category": "Core items", "amount": 0}
    line = (
        f"{label} plan built around a {format_inr(budget)} ceiling. "
        f"{top['category']} takes the largest share at {format_inr(top['amount'])}, and the "
        f"remaining {len(products)} line items are sized to leave the rest of the budget "
        f"for installation, delivery and a contingency."
    )
    if plan_type == "party":
        guests = int(payload.get("guest_count") or 1)
        line += f" That is {format_inr(per_head(budget, guests))} per guest."
    elif plan_type == "jewelry":
        metal = payload.get("metal", "gold")
        karat = payload.get("karat", "22K")
        line += f" Purity held at {karat} {metal} with making charges shown separately."
    else:
        line += f" Styled for {payload.get('style', 'modern')} with a {payload.get('room_type', 'room')} layout."
    return line


def _suggestions(plan_type: str, payload: dict[str, Any]) -> list[str]:
    if plan_type == "home":
        return [
            "Measure each wall and note door/window positions before ordering - returns cost more than the discount saves.",
            "Buy the biggest-ticket item (sofa, bed, wardrobe) first, then style the room around it.",
            "Do walls and flooring before furniture so a scratch or a paint drop does not ruin a new sofa.",
            "Use the Urban Company service allocation for assembly; unassembled furniture often costs 10-15% more than assembled delivery.",
            "Keep the contingency untouched - one wall socket, bracket or delivery fee usually eats into it.",
        ]
    if plan_type == "party":
        guests = int(payload.get("guest_count") or 1)
        return [
            f"Plan for {int(guests * 1.1)} covers - a 10% buffer prevents a shortage at peak hour.",
            "Book caterers and decorators with a written quote; per-head rates change on weekends and last-minute orders.",
            "Order cake and perishables 24 hours ahead, but book the venue and DJ at least 7 days out.",
            "Do a 30-minute run-through of the venue layout a day before, including power points and washroom access.",
            "Keep the last 3% of the budget for taxis, ice, and the inevitable extra guest.",
        ]
    return [
        "Always check the BIS hallmark on gold and an IGI/AGS certificate on diamonds before paying.",
        "Ask for making charges in writing - it is 10-25% of the bill and is the easiest place to overshoot.",
        "Ask about exchange/buy-back policy at purchase; it materially affects the resale value.",
        "Lab-grown diamonds give the same look at 40-60% less, which buys a larger stone for the same budget.",
        "Insure anything above roughly one month of salary - premium is 1-2% of the metal value.",
    ]
