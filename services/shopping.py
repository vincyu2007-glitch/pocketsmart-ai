"""Platform registry + shopping search-link generation.

Every retailer below is expressed as a URL *template* so that the patterns can
be corrected in one place if a marketplace changes its search route. Supported
placeholders: ``{q}`` (url-encoded query) and ``{slug}`` (lower-case, hyphen
separated).
"""

from __future__ import annotations

from urllib.parse import quote_plus, urlparse

# --- plan type -> ordered list of platform keys -----------------------------
PLAN_PLATFORMS: dict[str, list[str]] = {
    "home": [
        "amazon",
        "flipkart",
        "ikea",
        "pepperfry",
        "firstcry",
        "homecentre",
        "urbancompany",
    ],
    "party": [
        "amazon",
        "flipkart",
        "swiggy",
        "zomato",
        "oyo",
        "partykart",
        "bookmyevents",
    ],
    "jewelry": [
        "myntra",
        "amazon",
        "flipkart",
        "tanishq",
        "reliancejewels",
        "malabargold",
        "caratlane",
        "bluestone",
    ],
}

PLATFORMS: dict[str, dict[str, str]] = {
    # ---- Home interiors ----------------------------------------------------
    "amazon": {
        "name": "Amazon",
        "url": "https://www.amazon.in/s?k={q}",
        "category": "Marketplace",
        "note": "Widest catalogue and fastest delivery; check for Prime deals.",
    },
    "flipkart": {
        "name": "Flipkart",
        "url": "https://www.flipkart.com/search?q={q}",
        "category": "Marketplace",
        "note": "Strong on furniture, appliances and bundle value.",
    },
    "ikea": {
        "name": "IKEA",
        "url": "https://www.ikea.com/in/en/search/?q={q}",
        "category": "Furniture",
        "note": "Best for modular storage, lighting and small-space solutions.",
    },
    "pepperfry": {
        "name": "Pepperfry",
        "url": "https://www.pepperfry.com/search?q={q}",
        "category": "Furniture",
        "note": "Curated sofas, beds and dining; frequent sale events.",
    },
    "firstcry": {
        "name": "FirstCry",
        "url": "https://www.firstcry.com/search?q={q}",
        "category": "Kids & Nursery",
        "note": "Kids rooms, nursery gear and toys.",
    },
    "homecentre": {
        "name": "Home Centre",
        "url": "https://www.homecentre.com/search?q={q}",
        "category": "Homeware",
        "note": "Bedding, bathware and decor accessories.",
    },
    "urbancompany": {
        "name": "Urban Company",
        "url": "https://www.urbancompany.com/search?q={q}",
        "category": "Services",
        "note": "Carpenters, electricians, painters and deep cleaning.",
    },
    # ---- Party / events ----------------------------------------------------
    "swiggy": {
        "name": "Swiggy",
        "url": "https://www.swiggy.com/search?query={q}",
        "category": "Food & Catering",
        "note": "Snacks, desserts and party platters for same-day delivery.",
    },
    "zomato": {
        "name": "Zomato",
        "url": "https://www.zomato.com/search?q={q}",
        "category": "Food & Catering",
        "note": "Compare restaurant bulk orders and dessert vendors.",
    },
    "oyo": {
        "name": "OYO",
        "url": "https://www.oyosrooms.com/hotels-in-{slug}",
        "category": "Venue",
        "note": "Budget party halls and rooms for out-of-town guests.",
    },
    "partykart": {
        "name": "PartyKart",
        "url": "https://www.partykart.com/search?q={q}",
        "category": "Party Supplies",
        "note": "Decorations, cutlery, balloons and themed props.",
    },
    "bookmyevents": {
        "name": "BookMyEvents",
        "url": "https://bookmyevents.com/search?q={q}",
        "category": "Services",
        "note": "Decorators, sound/light, hosts and event planners.",
    },
    # ---- Jewellery ---------------------------------------------------------
    "myntra": {
        "name": "Myntra",
        "url": "https://www.myntra.com/{slug}",
        "category": "Fashion Jewellery",
        "note": "Largest range of costume and silver fashion jewellery.",
    },
    "tanishq": {
        "name": "Tanishq",
        "url": "https://www.tanishq.co.in/search?q={q}",
        "category": "Fine Jewellery",
        "note": "Trusted hallmarking and easy exchange on gold/diamond.",
    },
    "reliancejewels": {
        "name": "Reliance Jewels",
        "url": "https://www.reliancejewels.com/search?q={q}",
        "category": "Fine Jewellery",
        "note": "Large-format store with good wedding collections.",
    },
    "malabargold": {
        "name": "Malabar Gold & Diamonds",
        "url": "https://www.malabargoldandsilver.com/search?q={q}",
        "category": "Fine Jewellery",
        "note": "Value-for-money gold and silver across budgets.",
    },
    "caratlane": {
        "name": "CaratLane",
        "url": "https://www.caratlane.com/search?q={q}",
        "category": "Diamond Jewellery",
        "note": "Best for engagement rings and lab-grown diamonds.",
    },
    "bluestone": {
        "name": "Bluestone",
        "url": "https://www.bluestone.com/search?q={q}",
        "category": "Diamond Jewellery",
        "note": "Engagement rings with transparent certification.",
    },
}

# Fallback chain used when a plan type has no curated platform list.
DEFAULT_PLATFORM_KEYS = ["amazon", "flipkart"]


def platform_name(key: str) -> str:
    entry = PLATFORMS.get(key)
    return entry["name"] if entry else key.title()


def platforms_for(plan_type: str) -> list[dict[str, str]]:
    """Return platform metadata (safe to render) for a plan type."""
    keys = PLAN_PLATFORMS.get(plan_type, DEFAULT_PLATFORM_KEYS)
    return [
        {
            "key": key,
            "name": PLATFORMS[key]["name"],
            "category": PLATFORMS[key]["category"],
            "note": PLATFORMS[key]["note"],
        }
        for key in keys
    ]


def _slugify(text: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in text.lower())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "products"


def build_search_url(platform_key: str, query: str) -> str:
    """Render the search URL for ``platform_key`` for ``query``.

    Unknown platforms fall back to an Amazon search so the UI never renders a
    dead link.
    """
    entry = PLATFORMS.get(platform_key)
    if entry is None:
        entry = PLATFORMS["amazon"]
    query = " ".join(str(query).split())[:120]
    slug = _slugify(query)[:80]
    return entry["url"].format(q=quote_plus(query), slug=slug)


def is_safe_url(url: str, allowed_hosts: tuple[str, ...] | None = None) -> bool:
    """True when ``url`` is an https URL on a known marketplace host."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    hosts = allowed_hosts or tuple(
        urlparse(entry["url"]).netloc for entry in PLATFORMS.values()
    )
    return any(parsed.netloc == host or parsed.netloc.endswith("." + host) for host in hosts)


def platform_key_for(plan_type: str, platform_name_value: str) -> str:
    """Resolve a display name (e.g. "IKEA") to a platform key, scoped to a plan."""
    allowed = PLAN_PLATFORMS.get(plan_type, DEFAULT_PLATFORM_KEYS)
    name = str(platform_name_value or "").strip().lower()
    for key in allowed:
        if PLATFORMS[key]["name"].lower() == name:
            return key
    return "amazon"


def attach_product_links(plan_type: str, products: list[dict]) -> list[dict]:
    """Add a validated ``search_url`` to every product in place."""
    for product in products:
        key = platform_key_for(plan_type, product.get("platform", ""))
        query = str(product.get("search_terms") or product.get("name") or "").strip()
        url = build_search_url(key, query)
        product["search_platform"] = PLATFORMS[key]["name"]
        product["search_url"] = url if is_safe_url(url) else build_search_url("amazon", query)
    return products


def links_for_products(plan_type: str, products: list[dict], limit: int = 12) -> list[dict]:
    """Build deduplicated, validated shopping links for a recommendation set."""
    allowed = set(PLAN_PLATFORMS.get(plan_type, DEFAULT_PLATFORM_KEYS))
    seen: set[tuple[str, str]] = set()
    links: list[dict] = []

    for product in products:
        if len(links) >= limit:
            break
        key = platform_key_for(plan_type, product.get("platform", ""))
        if key not in allowed:
            key = "amazon"
        query = str(
            product.get("search_terms") or product.get("name") or ""
        ).strip()
        if not query:
            continue
        signature = (key, query.lower())
        if signature in seen:
            continue
        seen.add(signature)
        url = build_search_url(key, query)
        if not is_safe_url(url):
            continue
        links.append(
            {
                "platform": PLATFORMS[key]["name"],
                "category": PLATFORMS[key]["category"],
                "label": f"Buy {product.get('name', query)} on {PLATFORMS[key]['name']}",
                "url": url,
            }
        )
    return links
