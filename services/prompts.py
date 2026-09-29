"""Prompt engineering for PocketSmart AI.

Design rules applied to every prompt in this module:

* **Role first** - the model is positioned as a cost-conscious interior /
  event / jewellery planner working in the Indian market.
* **Hard constraints** - the budget is a ceiling, every rupee is accounted
  for, and parts must sum to the total.
* **Structured output** - a single JSON object matching :data:`RESPONSE_SCHEMA`
  so the UI can render cards without scraping prose.
* **Anti-hallucination guardrails** - the model is explicitly told *not* to
  invent URLs, brand mandates or live prices; links are generated server-side
  from the platform registry.
* **Image awareness** - when an image is attached, the model is told to reason
  about colour and style grounding in it.
"""

from __future__ import annotations

import json
from typing import Any

MODEL_NAME_LABEL = "Gemini"

# --- shared building blocks ------------------------------------------------
GUARDRAILS = """STRICT RULES (never break these):
1. Every price is in Indian Rupees (INR) and is a realistic current market
   price for the mid-tier Indian market. Never quote USD, EUR or "approx".
2. The sum of all `budget_breakdown` amounts MUST equal `total_budget`, and
   `total_budget` MUST equal the user's budget exactly. Never exceed it.
3. Product prices within a category must fit inside that category's allocated
   amount. If a category cannot be filled, redistribute the leftover to other
   categories and say so in `notes`.
4. NEVER output URLs, links, or full store names. Use only the `platform`
   values listed in the PLATFORMS section and put a short keyword string in
   `search_terms`. The app builds the links.
5. `products` must contain 8-14 items. `features` must be 3-5 short,
   concrete bullet points each (no marketing adjectives like "amazing").
6. `why` explains the fit for THIS user's budget and preferences in one
   sentence. No generic filler.
7. Respond with a single raw JSON object. No markdown, no ``` fences, no
   commentary before or after.
8. Be decisive. Never reply "it depends" or "consult a professional" as the
   main advice. Numbers, names, and choices only.
"""

RESPONSE_SCHEMA = """{
  "summary": "string - 2-3 sentence overall plan, mentions the budget and the biggest money-saving decision",
  "total_budget": "number - integer INR, equals the user budget",
  "currency": "string - always INR",
  "budget_breakdown": [
    {"category": "string", "amount": "number - integer INR", "percentage": "number 0-100",
     "priority": "high|standard", "notes": "string - one short sentence"}
  ],
  "products": [
    {"name": "string - specific product type, not a brand",
     "category": "string - must match one budget_breakdown category",
     "price": "number - integer INR unit or bundle price",
     "quantity": "number - integer, default 1",
     "platform": "string - one of the allowed platform names",
     "search_terms": "string - 3-6 keyword search string",
     "why": "string - why this fits this user",
     "features": ["string - 3-5 concrete features"],
     "alternatives": ["string - 1-2 cheaper or pricier substitute names"]}
  ],
  "cost_breakdown": [
    {"label": "string", "amount": "number - integer INR", "note": "string - short"}
  ],
  "shopping_links": [
    {"platform": "string", "label": "string", "url": "string - always return an empty string; the app generates real links"}
  ],
  "suggestions": ["string - 4-6 actionable planning tips, budget specific"],
  "warnings": ["string - 0-3 real risks: gold rate movement, monsoon, rental clashes, guest count buffer"]
}"""

PLATFORM_INSTRUCTIONS = {
    "home": """PLATFORMS - use these exact names in `platform`:
Amazon (marketplace, fast delivery, best for appliances/small decor),
Flipkart (marketplace, bundles and value),
IKEA (modular furniture, storage, lighting),
Pepperfry (sofas, beds, dining),
FirstCry (kids rooms, nursery),
Home Centre (bedding, bathware, decor accessories),
Urban Company (carpenters, electricians, painters, deep cleaning - service
bookings, no product images).""",
    "party": """PLATFORMS - use these exact names in `platform`:
Amazon (party props, fairy lights, cutlery, ice),
Flipkart (appliances for a home party, bulk packs),
Swiggy (catering, cakes, desserts, same-day snacks),
Zomato (restaurant catering comparison),
OYO (budget party halls and rooms for out-of-town guests),
PartyKart (decorations, balloons, themed props),
BookMyEvents (decorators, DJ, sound & lights, photographers, venues).""",
    "jewelry": """PLATFORMS - use these exact names in `platform`:
Myntra (fashion jewellery, costume and 925 silver),
Amazon (wide range, budget options),
Flipkart (marketplace jewellery, often better pricing),
Tanishq (hallmarked gold and diamond, trusted exchange),
Reliance Jewels (wedding collections, large store network),
Malabar Gold & Diamonds (value-for-money gold and silver),
CaratLane (engagement rings, lab-grown and certified diamonds),
Bluestone (engagement rings, transparent certification).""",
}

COMMON_RULES = """RULES:
- The user's budget is a hard ceiling. Always leave a 3-5% contingency inside
  the plan and label it "Contingency".
- If the budget is unrealistic for the request, still produce the best plan and
  explain in `warnings` what must be cut or downgraded to fit.
- Prefer durable, high-resale items over disposable decor.
- Keep `quantity` accurate: for per-item costs, use the per-unit price in
  `price` and set `quantity` to the number of units needed."""

CURRENCY_NOTE = "All amounts are INR (₹)."


def _json_block(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def build_home_prompt(payload: dict[str, Any]) -> str:
    """Prompt for the Home Interior Budget Planner."""
    facts = {
        "budget_inr": int(payload["budget"]),
        "room_type": payload["room_type"],
        "area_sqft": payload["area_sqft"],
        "occupants": payload["occupants"],
        "style": payload["style"],
        "timeline": payload["timeline"],
        "city": payload.get("city") or "unspecified",
        "existing_items_to_keep": payload.get("existing_items") or "none specified",
        "must_have_items": payload.get("must_haves") or "none specified",
        "color_preference": payload.get("color_preference") or "no preference",
    }
    return f"""You are a senior Indian residential interior designer AND a ruthless
cost planner. You plan complete {payload['room_type']} makeovers so that a real
family gets a beautiful, functional room without ever exceeding the budget.

USER INPUT:
{_json_block(facts)}

{PLATFORM_INSTRUCTIONS['home']}

{COMMON_RULES}

HOW TO ALLOCATE (adapt, do not copy blindly):
Furniture 30-40%, Lighting 10-12%, Storage 10-14%, Decor & Accents 8-12%,
Bedding & Textiles 8-12%, Appliances 5-10%, Paint & Walls 3-6%,
Services & Installation 3-6%, Contingency 3-5%.
For a {payload['area_sqft']} sq ft {payload['room_type'].lower()}, scale product
quantities realistically (e.g. a 3-seater sofa + coffee table + TV unit for a
living room; a queen bed + wardrobe + side tables for a bedroom).
Respect these constraints:
- Keep these items: {facts['existing_items_to_keep']}
- Must include: {facts['must_have_items']}
- Style: {facts['style']}
- Colour direction: {facts['color_preference']}
- Timeline: {facts['timeline']} - flag in `warnings` anything with a longer lead time.

{GUARDRAILS}

OUTPUT - a single JSON object with this exact shape:
{RESPONSE_SCHEMA}"""


def build_party_prompt(payload: dict[str, Any]) -> str:
    """Prompt for the Party / Event Budget Planner."""
    guests = int(payload["guest_count"])
    per_guest = int(round(float(payload["budget"]) / max(guests, 1)))
    facts = {
        "budget_inr": int(payload["budget"]),
        "event_type": payload["event_type"],
        "guest_count": guests,
        "venue": payload["venue"],
        "event_date": payload.get("event_date") or "not specified",
        "city": payload.get("city") or "unspecified",
        "food_preference": payload.get("food_preference") or "no preference",
        "decor_theme": payload.get("decor_theme") or "no theme given",
        "entertainment": payload.get("entertainment") or ["None"],
        "derived_per_guest_budget_inr": per_guest,
    }
    return f"""You are an experienced Indian event planner who has run 500+ weddings,
birthdays and corporate events. You build complete party plans inside a strict
budget and you think in per-guest costs.

USER INPUT:
{_json_block(facts)}

{PLATFORM_INSTRUCTIONS['party']}

{COMMON_RULES}

HOW TO ALLOCATE (adapt to venue and guest count):
Food & Beverages 28-34% (this is the number that must not be cut - guests
remember food), Venue & Rentals 15-22%, Decor & Theme 14-20%,
Entertainment & Sound 7-11%, Gifts & Favours 6-10%,
Photography & Content 4-6%, Cake & Desserts 4-7%, Miscellaneous 1-3%,
Contingency 2-3%.
Venue rules:
- "At Home": venue allocation becomes rentals + electricity/cleaning backup.
- "Rented Party Hall" / "Hotel / Banquet": venue allocation covers slot booking
  (assume ₹{max(400, int(per_guest * 1.5)):,} per guest as a band for a mid-tier hall).
- "Outdoor / Farmhouse": add weather backup, power backup and lighting in `warnings`.
Food rules: cost = per-guest rate x {guests} guests. If the per-guest budget of
₹{per_guest:,} is too low for a full service meal, put snacks + a dessert table
in `warnings` as the realistic alternative. Always add a 5-10% guest-count
buffer in `warnings`.

{GUARDRAILS}

OUTPUT - a single JSON object with this exact shape:
{RESPONSE_SCHEMA}"""


def build_jewelry_prompt(payload: dict[str, Any], image_meta: dict | None = None) -> str:
    """Prompt for the Jewellery Budget Planner (text-only variant)."""
    facts = {
        "budget_inr": int(payload["budget"]),
        "occasion": payload["occasion"],
        "metal_preference": payload["metal"],
        "purity": payload["karat"],
        "style": payload["style"],
        "bought_for": payload.get("gift_for") or "self",
        "colour_preference": payload.get("color_preference") or "no preference",
        "wearing_frequency": payload.get("wearing_frequency") or "not specified",
    }
    return f"""You are a certified Indian gemologist and jewellery advisor working inside
a fixed budget. You are known for being honest about karat, making charges and
resale value - you never upsell.

USER INPUT:
{_json_block(facts)}

{PLATFORM_INSTRUCTIONS['jewelry']}

{COMMON_RULES}

MONEY RULES (critical for jewellery):
- Gold: budget = grams x rate x karat factor. 22K = 91.6% purity, 24K = 99.5%,
  18K = 75%, 14K = 58.5%. Typical retail rate today is roughly ₹6,500-7,500 per
  gram for 22K (rate-check in `warnings`). State the making charges separately
  (10-25% of metal value) under "Certification & Making Charges".
- Diamond: budget = carat x rate + making. ₹2.5L-₹5L per carat is typical for
  good natural certified stones; lab-grown is 40-60% cheaper - suggest it in
  `alternatives` when the budget is tight.
- Silver / fashion: 925 sterling roughly ₹70-₹120 per gram.
- Always include at least one complete, wearable "main piece" and matching
  earrings, plus a cheaper everyday option in `alternatives`.
- Insurance (1-2% of metal value) and a 3-5% "gold rate movement" contingency
  are mandatory line items.

{GUARDRAILS}

OUTPUT - a single JSON object with this exact shape:
{RESPONSE_SCHEMA}"""


IMAGE_ANALYSIS_BLOCK = """
IMAGE ANALYSIS (do this FIRST, before the money rules):
- Describe the visible outfit/product: base colour, secondary colours, fabric or
  finish, pattern, and overall formality in one short phrase per attribute.
- Extract the dominant colour in plain English (for example "deep maroon with
  gold zari work") and derive the complementary metal and stone that flatters
  it (silver/oxidised for cool pastels and white, gold for warm and jewel
  tones, diamond for black/white and formal).
- Note neckline, sleeve or setting constraints: a high neck rules out long
  pendants, an open neckline suits a choker or statement necklace, heavy
  embroidery suits small studs over a large necklace.
- Name up to 3 accessories the image already shows so you do not recommend
  duplicates, and put them in `warnings` only if they conflict with the plan.
- If the image is too blurry, too dark, or shows no person/product at all, say
  so in `warnings` and fall back to the text preferences instead of guessing.
- Put the colour analysis in `summary` (first sentence) and in the `features`
  of the main piece, for example "Picks up the gold zari in the image".
"""


def build_jewelry_image_prompt(
    payload: dict[str, Any], image_meta: dict | None = None
) -> str:
    """Prompt for the image-aware Jewellery planner.

    The image is attached as a second part of the user turn, so the text refers
    to it explicitly and asks for colour-matching reasoning.
    """
    base = build_jewelry_prompt(payload, image_meta)
    if image_meta:
        image_notes = (
            f"\nATTACHED IMAGE: {image_meta.get('width')}x{image_meta.get('height')} "
            f"{image_meta.get('mime_type', 'image')} "
            f"({int(image_meta.get('size_bytes', 0) / 1024)} KB).\n"
        )
    else:
        image_notes = ""
    return (
        f"{base}\n\n{image_notes}{IMAGE_ANALYSIS_BLOCK}\n"
        f"{GUARDRAILS}\n\n"
        "OUTPUT - a single JSON object with this exact shape:\n"
        f"{RESPONSE_SCHEMA}"
    )


def build_allocation_prompt(payload: dict[str, Any]) -> str:
    """Standalone AI budget-allocation engine (no product catalogue)."""
    plan_type = payload.get("plan_type", "home")
    plan_label = {
        "home": "home interior makeover",
        "party": "party / event",
        "jewelry": "jewellery purchase",
    }.get(plan_type, plan_type)
    facts = {k: v for k, v in payload.items() if k not in ("image_meta", "has_image")}
    return f"""You are a budgeting analyst. Split an Indian customer's total budget
for a {plan_label} into categories. You do not recommend products here.

USER INPUT:
{_json_block(facts)}

Return ONLY a JSON object:
{{
  "summary": "string - 1-2 sentences",
  "total_budget": "number - integer INR",
  "currency": "INR",
  "budget_breakdown": [
    {{"category": "string", "amount": "number - integer INR",
      "percentage": "number 0-100", "priority": "high|standard", "notes": "string"}}
  ],
  "suggestions": ["string - 3-5 tips to save money in this plan"]
}}

RULES:
- The `amount` values MUST sum to `total_budget` to the rupee.
- Always include a "Contingency" line of 3-5%.
- Percentages must sum to 100 (rounding aside).
- Be realistic for India: food dominates party budgets, furniture dominates
  interior budgets, metal value dominates jewellery budgets.
- Raw JSON only, no markdown."""


BUILDERS = {
    "home": build_home_prompt,
    "party": build_party_prompt,
    "jewelry": build_jewelry_prompt,
}
