"""Deterministic budget allocation engine.

Used for two things:

1. Pre-flight: show the user how their budget will be split *before* spending
   tokens on a Gemini call (and to sanity-check the model afterwards).
2. Offline/demo mode: drive the curated catalog when no API key is configured.
"""

from __future__ import annotations

from math import floor

# Relative weights per category. Weights are normalised internally, so any
# positive numbers work - these express the "expected" split for Indian urban
# households and mid-tier events.
CATEGORY_WEIGHTS: dict[str, dict[str, float]] = {
    "home": {
        "Furniture": 34.0,
        "Lighting": 12.0,
        "Storage": 12.0,
        "Decor & Accents": 11.0,
        "Bedding & Textiles": 10.0,
        "Appliances": 8.0,
        "Paint & Walls": 5.0,
        "Services & Installation": 5.0,
        "Contingency": 3.0,
    },
    "party": {
        "Venue & Rentals": 20.0,
        "Food & Beverages": 30.0,
        "Decor & Theme": 18.0,
        "Cake & Desserts": 6.0,
        "Entertainment & Sound": 9.0,
        "Gifts & Favours": 8.0,
        "Photography & Content": 5.0,
        "Miscellaneous": 2.0,
        "Contingency": 2.0,
    },
    "jewelry": {
        "Main Piece": 52.0,
        "Matching Earrings": 14.0,
        "Pendant or Mangalsutra": 10.0,
        "Bangles or Bracelet": 8.0,
        "Nose Ring or Ear Studs": 3.0,
        "Certification & Making Charges": 8.0,
        "Insurance & Resale": 3.0,
        "Contingency": 2.0,
    },
}

# Multipliers used to turn a total budget into an indicative item budget.
SHOPPING_EXPANSION: dict[str, int] = {"home": 3, "party": 4, "jewelry": 2}


def normalise_weights(weights: dict[str, float]) -> dict[str, float]:
    clean = {
        str(name).strip(): float(value)
        for name, value in weights.items()
        if str(name).strip() and float(value) > 0
    }
    total = sum(clean.values())
    if total <= 0:
        raise ValueError("At least one category weight must be positive")
    return {name: value / total for name, value in clean.items()}


def allocate_budget(
    budget: float,
    weights: dict[str, float],
    *,
    round_to: int = 100,
) -> list[dict]:
    """Split ``budget`` across ``weights`` using the largest-remainder method.

    Guarantees ``sum(amount) == budget`` (after rounding) so the UI never shows
    a plan whose parts do not add up.
    """
    budget = float(budget)
    if budget <= 0:
        raise ValueError("budget must be greater than zero")

    shares = normalise_weights(weights)
    step = max(int(round_to), 1)

    quotas = {name: budget * share for name, share in shares.items()}
    amounts = {name: floor(value / step) * step for name, value in quotas.items()}
    # Integer steps were removed by the floor, so the remainder is bounded.
    remainder_total = int(round((budget - sum(amounts.values())) / step))
    remainders = sorted(quotas, key=lambda n: quotas[n] - amounts[n], reverse=True)

    for index in range(max(remainder_total, 0)):
        amounts[remainders[index % len(remainders)]] += step

    # Rounding the budget itself can leave a small residue; park it on the
    # largest category so the total always matches what the user typed.
    residue = int(round(budget)) - sum(amounts.values())
    if residue:
        amounts[remainders[0]] += residue

    return [
        {
            "category": name,
            "amount": int(amount),
            "percentage": round(shares[name] * 100, 1),
            "priority": "high" if shares[name] >= 0.2 else "standard",
            "notes": "",
        }
        for name, amount in sorted(amounts.items(), key=lambda kv: kv[1], reverse=True)
    ]


def weights_for(plan_type: str, overrides: dict[str, float] | None = None) -> dict[str, float]:
    """Category weights for a plan type, with optional user overrides applied."""
    weights = dict(CATEGORY_WEIGHTS.get(plan_type, CATEGORY_WEIGHTS["home"]))
    for name, value in (overrides or {}).items():
        if name in weights and float(value) > 0:
            weights[name] = float(value)
    return weights


def plan_summary(budget: float, breakdown: list[dict]) -> dict:
    total = sum(int(item["amount"]) for item in breakdown)
    return {
        "total_budget": int(budget),
        "allocated": total,
        "remaining": int(budget) - total,
        "categories": len(breakdown),
        "contingency": next(
            (int(i["amount"]) for i in breakdown if "contingen" in i["category"].lower()),
            0,
        ),
    }


def per_head(cost: float, guests: int) -> int:
    guests = max(int(guests), 1)
    return int(round(float(cost) / guests))


def format_inr(amount: float) -> str:
    """Format a number the way prices are shown in India (1,23,456)."""
    amount = int(round(float(amount)))
    if amount >= 100000:
        return f"{amount / 100000:.2f} L".replace(".00 L", " L")
    if amount >= 1000:
        return f"{amount:,}"
    return str(amount)
