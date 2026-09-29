"""Recommendation orchestrator.

Pipeline:

    validate -> build prompt -> Gemini (or offline engine) -> normalise
    -> enforce the budget ceiling -> attach vetted shopping links -> stats
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from . import prompts
from .budget import format_inr, per_head
from .fallback import build_offline_recommendation
from .gemini_client import GeminiClient, GeminiError, build_client, normalise_response
from .shopping import attach_product_links, links_for_products
from .validators import VALIDATORS

log = logging.getLogger(__name__)

PLAN_TYPES = ("home", "party", "jewelry")

# Indicative retail rate used only for the "how many grams" hint in the UI.
GOLD_RATE_22K_PER_GRAM = 7200
KARAT_PURITY = {"14K": 0.585, "18K": 0.75, "22K": 0.916, "24K": 0.995}
SILVER_RATE_PER_GRAM = 95


@dataclass
class RecommendationResult:
    data: dict[str, Any]
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {**self.data, "meta": self.meta}


def build_prompt(plan_type: str, payload: dict[str, Any], image_meta: dict | None = None) -> str:
    """Select and render the right prompt for a plan type."""
    if plan_type == "jewelry" and image_meta:
        return prompts.build_jewelry_image_prompt(payload, image_meta)
    builder = prompts.BUILDERS.get(plan_type)
    if builder is None:
        raise ValueError(f"Unknown plan type: {plan_type!r}")
    return builder(payload)


def generate(
    plan_type: str,
    payload: dict[str, Any],
    *,
    client: GeminiClient | None = None,
    image: bytes | None = None,
    image_meta: dict | None = None,
) -> RecommendationResult:
    """Produce a recommendation document for one plan."""
    if plan_type not in PLAN_TYPES:
        raise ValueError(f"Unknown plan type: {plan_type!r}")
    if plan_type not in VALIDATORS:
        raise ValueError(f"No validator registered for: {plan_type!r}")

    budget = int(float(payload.get("budget", 0)))
    prompt = build_prompt(plan_type, payload, image_meta)
    started = time.perf_counter()
    source = "offline"
    error: str | None = None
    data: dict[str, Any]

    if client is None:
        client = build_client(_current_config())

    if client.available and image_meta:
        payload = {**payload, "has_image": True, "image_meta": image_meta}

    if client.available:
        try:
            raw = client.generate_json(prompt, image=image, mime_type="image/jpeg")
            data = normalise_response(raw, plan_type=plan_type, budget=budget)
            source = "ai"
        except GeminiError as exc:
            log.warning("Falling back to the offline engine: %s", exc)
            error = str(exc)
            data = build_offline_recommendation(payload, plan_type)
    else:
        error = "GEMINI_API_KEY is not configured - showing the built-in sample plan."
        data = build_offline_recommendation(payload, plan_type)

    _enforce_budget(data, budget)
    data["products"] = attach_product_links(plan_type, data.get("products", []))
    data["shopping_links"] = links_for_products(plan_type, data["products"])
    data["stats"] = _stats(plan_type, payload, data)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    meta = {
        "source": source,
        "plan_type": plan_type,
        "model": client.model if source == "ai" else "offline-engine",
        "elapsed_ms": elapsed_ms,
        "prompt_chars": len(prompt),
        "used_image": bool(image),
        "image_meta": image_meta,
        "notice": error,
    }
    return RecommendationResult(data=data, meta=meta)


# --- post-processing -------------------------------------------------------
def _enforce_budget(data: dict[str, Any], budget: int) -> None:
    """Make the numbers add up, whatever the model returned."""
    data["total_budget"] = budget
    breakdown = data.get("budget_breakdown") or []

    if breakdown:
        allocated = sum(int(item.get("amount", 0)) for item in breakdown)
        if allocated != budget and breakdown:
            largest = max(breakdown, key=lambda i: int(i.get("amount", 0)))
            largest["amount"] = max(int(largest["amount"]) + (budget - allocated), 0)
            data.setdefault("warnings", []).append(
                "Allocation figures were reconciled to match the budget exactly."
            )
        for item in breakdown:
            try:
                share = (int(item.get("amount", 0)) / budget) * 100
                item["percentage"] = round(share, 1)
            except ZeroDivisionError:  # pragma: no cover - budget is validated
                item["percentage"] = 0.0
    else:
        contingency = max(int(budget * 0.04), 0)
        core = budget - contingency
        breakdown[:] = [
            {"category": "Core purchases", "amount": core, "percentage": 96.0, "priority": "high", "notes": ""},
            {"category": "Contingency", "amount": contingency, "percentage": 4.0, "priority": "standard", "notes": "Kept aside for overruns"},
        ]
        data["budget_breakdown"] = breakdown

    total_spend = sum(
        int(p.get("price", 0)) * int(p.get("quantity", 1)) for p in data.get("products", [])
    )
    data["total_spend"] = total_spend
    if total_spend > budget:
        data.setdefault("warnings", []).append(
            f"Selected items total {format_inr(total_spend)}, which is above the budget. "
            f"Trim the lowest-priority lines or negotiate to fit {format_inr(budget)}."
        )
    elif total_spend and budget - total_spend > budget * 0.25:
        data.setdefault("suggestions", []).append(
            f"You have {format_inr(budget - total_spend)} unallocated - upgrade the "
            f"highest-priority category rather than leaving it idle."
        )


def _stats(plan_type: str, payload: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    budget = int(data.get("total_budget", 0))
    stats: dict[str, Any] = {
        "product_count": len(data.get("products", [])),
        "category_count": len(data.get("budget_breakdown", [])),
        "link_count": len(data.get("shopping_links", [])),
        "spend": data.get("total_spend", 0),
        "unallocated": budget - int(data.get("total_spend", 0)),
    }
    if plan_type == "party":
        guests = int(payload.get("guest_count") or 1)
        stats["guests"] = guests
        stats["per_guest"] = per_head(budget, guests)
    if plan_type == "jewelry":
        stats.update(_jewelry_stats(payload, budget))
    if plan_type == "home":
        stats["area_sqft"] = payload.get("area_sqft")
        area = float(payload.get("area_sqft") or 0)
        if area > 0:
            stats["cost_per_sqft"] = int(budget / area)
    return stats


def _jewelry_stats(payload: dict[str, Any], budget: int) -> dict[str, Any]:
    metal = str(payload.get("metal", "")).lower()
    karat = str(payload.get("karat", "22K")).upper()
    stats: dict[str, Any] = {"metal": payload.get("metal"), "karat": karat}
    metal_spend = int(budget * 0.7)  # reserve ~30% for making, setting, certs
    if "gold" in metal and karat in KARAT_PURITY:
        rate = GOLD_RATE_22K_PER_GRAM * (KARAT_PURITY[karat] / KARAT_PURITY["22K"])
        stats["grams_estimate"] = round(metal_spend / rate, 1)
        stats["rate_estimate"] = int(rate)
    elif "silver" in metal or "925" in karat:
        stats["grams_estimate"] = round(metal_spend / SILVER_RATE_PER_GRAM, 1)
        stats["rate_estimate"] = SILVER_RATE_PER_GRAM
    elif "diamond" in metal:
        stats["carat_estimate"] = round(metal_spend / 350000, 2)
        stats["lab_grown_saving"] = "40-60% vs natural"
    return stats


def _current_config():
    from config import get_config

    return get_config()


# --- convenience wrappers used by the views --------------------------------
def allocate_only(
    plan_type: str,
    payload: dict[str, Any],
    *,
    client: GeminiClient | None = None,
) -> RecommendationResult:
    """Run only the AI budget-allocation engine (no product catalogue)."""
    if client is None:
        client = build_client(_current_config())
    from .budget import allocate_budget, weights_for

    budget = int(float(payload.get("budget", 0)))
    prompt = prompts.build_allocation_prompt({**payload, "plan_type": plan_type})
    source, error = "ai", None
    try:
        if not client.available:
            raise GeminiError("GEMINI_API_KEY is not configured.")
        raw = client.generate_json(prompt)
        if not isinstance(raw, dict):
            raise GeminiError("Unexpected allocation response.")
        breakdown = []
        for item in raw.get("budget_breakdown", []) or []:
            if isinstance(item, dict) and item.get("category"):
                breakdown.append(
                    {
                        "category": str(item["category"])[:80],
                        "amount": int(float(item.get("amount", 0) or 0)),
                        "percentage": round(float(item.get("percentage", 0) or 0), 1),
                        "priority": "high" if str(item.get("priority", "")).lower() == "high" else "standard",
                        "notes": str(item.get("notes", ""))[:280],
                    }
                )
        if not breakdown:
            raise GeminiError("Allocation response contained no categories.")
        data = {
            "summary": str(raw.get("summary", "")).strip()[:2000],
            "total_budget": budget,
            "currency": "INR",
            "budget_breakdown": breakdown,
            "products": [],
            "cost_breakdown": [],
            "suggestions": [str(s)[:200] for s in (raw.get("suggestions") or []) if str(s).strip()][:8],
            "warnings": [],
            "plan_type": plan_type,
        }
    except (GeminiError, TypeError, ValueError) as exc:
        log.warning("AI allocation unavailable, using the deterministic split: %s", exc)
        error = str(exc)
        source = "offline"
        data = {
            "summary": "Deterministic split based on typical Indian spending patterns.",
            "total_budget": budget,
            "currency": "INR",
            "budget_breakdown": [
                {**e, "notes": e.get("notes") or f"{e['percentage']}% of budget"}
                for e in allocate_budget(budget, weights_for(plan_type))
            ],
            "products": [],
            "cost_breakdown": [],
            "suggestions": [],
            "warnings": [],
            "plan_type": plan_type,
        }

    data["shopping_links"] = []
    data["stats"] = {"category_count": len(data["budget_breakdown"]), "spend": 0, "unallocated": 0}
    return RecommendationResult(
        data=data,
        meta={"source": source, "plan_type": plan_type, "mode": "allocation", "notice": error},
    )
