"""Curated offline catalog.

These entries drive the deterministic (no-API-key) engine and also act as a
sanity reference for the AI prompt. Prices are indicative Indian-market
mid-tier figures in INR and are used as *base prices*, not guarantees.
"""

from __future__ import annotations

from typing import Any

# Each item: name, base price, search terms, preferred platform, features, tags.
HOME_CATALOG: dict[str, list[dict[str, Any]]] = {
    "Furniture": [
        {
            "name": "3-Seater Fabric Sofa",
            "price": 28000,
            "search_terms": "3 seater fabric sofa wooden frame",
            "platform": "Amazon",
            "features": ["Solid wood frame", "Removable washable covers", "High-density foam"],
            "tags": ["living", "modern", "small", "medium"],
        },
        {
            "name": "Recliner / Accent Chair",
            "price": 12000,
            "search_terms": "recliner armchair accent chair",
            "platform": "Pepperfry",
            "features": ["Manual recline", "Stain-resistant fabric"],
            "tags": ["living", "modern", "small"],
        },
        {
            "name": "Coffee Table (Sheesham Wood)",
            "price": 7500,
            "search_terms": "coffee table sheesham wood glass top",
            "platform": "IKEA",
            "features": ["Two drawers", "Scratch-resistant finish"],
            "tags": ["living", "modern", "traditional", "medium"],
        },
        {
            "name": "Dining Table with 4 Chairs",
            "price": 22000,
            "search_terms": "4 seater dining table with chairs set",
            "platform": "IKEA",
            "features": ["Engineered wood top", "Chair cushions included"],
            "tags": ["dining", "modern", "minimalist", "medium"],
        },
        {
            "name": "Queen Bed with Hydraulic Storage",
            "price": 26000,
            "search_terms": "queen bed hydraulic storage solid wood",
            "platform": "Pepperfry",
            "features": ["Hydraulic lift", "Anti-termite treatment"],
            "tags": ["bedroom", "small", "modern"],
        },
        {
            "name": "Study Desk + Chair Combo",
            "price": 11000,
            "search_terms": "study table chair combo wfh desk",
            "platform": "Amazon",
            "features": ["Cable management", "Adjustable chair"],
            "tags": ["study", "office", "small", "kids"],
        },
        {
            "name": "3-Door Wardrobe",
            "price": 19000,
            "search_terms": "3 door wardrobe with mirror and internal storage",
            "platform": "IKEA",
            "features": ["Hanging + shelf space", "Anti-fungal laminate"],
            "tags": ["bedroom", "small", "modern"],
        },
        {
            "name": "TV Unit / Media Console",
            "price": 9500,
            "search_terms": "TV unit cabinet for wall mounted television",
            "platform": "IKEA",
            "features": ["Cable routing", "Soft-close doors"],
            "tags": ["living", "modern", "minimalist"],
        },
    ],
    "Lighting": [
        {
            "name": "LED Floor Lamp",
            "price": 4500,
            "search_terms": "led floor lamp tripod bedroom living room",
            "platform": "Amazon",
            "features": ["3-step dimming", "Foot switch"],
            "tags": ["living", "bedroom", "modern", "reading"],
        },
        {
            "name": "Pendant Hanging Light",
            "price": 3200,
            "search_terms": "brass pendant hanging light ceiling",
            "platform": "IKEA",
            "features": ["Warm white bulb included", "Adjustable cord"],
            "tags": ["dining", "modern", "industrial"],
        },
        {
            "name": "Smart LED Bulb Pack (4)",
            "price": 1800,
            "search_terms": "smart led bulb wifi app control pack of 4",
            "platform": "Amazon",
            "features": ["16M colours", "Schedules", "Works offline"],
            "tags": ["smart", "modern", "all"],
        },
        {
            "name": "Table Lamp (Ceramic Base)",
            "price": 1600,
            "search_terms": "ceramic table lamp bedside lamp",
            "platform": "Home Centre",
            "features": ["E27 holder", "Neutral shade"],
            "tags": ["bedroom", "traditional", "boho", "reading"],
        },
    ],
    "Storage": [
        {
            "name": "Modular Wall Shelving Unit",
            "price": 6500,
            "search_terms": "modular wall shelves floating wooden",
            "platform": "IKEA",
            "features": ["5 shelves", "Holds 15 kg/shelf"],
            "tags": ["living", "study", "small", "modern", "minimalist"],
        },
        {
            "name": "Chest of Drawers (4 Drawer)",
            "price": 8900,
            "search_terms": "4 drawer chest of drawers bedroom",
            "platform": "Amazon",
            "features": ["Soft-close runners", "Anti-tip wall strap"],
            "tags": ["bedroom", "traditional", "modern"],
        },
        {
            "name": "Under-Bed Storage Bags (Set of 4)",
            "price": 1800,
            "search_terms": "under bed storage bags set of 4",
            "platform": "Amazon",
            "features": ["Zip closure", "Non-slip base"],
            "tags": ["bedroom", "small", "minimalist", "kids"],
        },
        {
            "name": "Collapsible Storage Bins (Set of 6)",
            "price": 1500,
            "search_terms": "collapsible storage bins fabric set",
            "platform": "Home Centre",
            "features": ["Stackable", "Wipe clean"],
            "tags": ["kids", "small", "pooja", "all"],
        },
    ],
    "Decor & Accents": [
        {
            "name": "Set of 3 Framed Wall Art Prints",
            "price": 2400,
            "search_terms": "set of 3 framed wall art prints",
            "platform": "Amazon",
            "features": ["A4 prints", "Ready to hang"],
            "tags": ["living", "study", "modern", "boho", "minimalist"],
        },
        {
            "name": "Area Rug (6x4 ft)",
            "price": 3500,
            "search_terms": "area rug 6x4 feet anti slip washable",
            "platform": "Amazon",
            "features": ["Low pile", "Anti-slip backing"],
            "tags": ["living", "bedroom", "modern", "boho"],
        },
        {
            "name": "Elegant Vase Set (3 pc)",
            "price": 1700,
            "search_terms": "decorative vase set of 3 ceramic",
            "platform": "Home Centre",
            "features": ["Matte finish", "Dust covers"],
            "tags": ["dining", "living", "traditional", "modern"],
        },
        {
            "name": "Cushion Cover Set (Set of 4)",
            "price": 1400,
            "search_terms": "cushion cover set of 4 sofa decorative",
            "platform": "Amazon",
            "features": ["Zip closure", "Colourfast"],
            "tags": ["living", "boho", "modern", "scandinavian"],
        },
        {
            "name": "Indoor Plants (3 potted)",
            "price": 1200,
            "search_terms": "indoor plants low maintenance set of 3 with pots",
            "platform": "Amazon",
            "features": ["Low light tolerant", "Ceramic pots"],
            "tags": ["living", "office", "all"],
        },
    ],
    "Bedding & Textiles": [
        {
            "name": "Bedsheet Set with 2 Cushion Covers",
            "price": 2200,
            "search_terms": "bedsheet set king size with 2 pillow covers cotton",
            "platform": "Amazon",
            "features": ["300 TC cotton", "Fade resistant"],
            "tags": ["bedroom", "all"],
        },
        {
            "name": "Duvet / Comforter with Pillow",
            "price": 3200,
            "search_terms": "duvet comforter set with pillow queen",
            "platform": "Home Centre",
            "features": ["Microfibre fill", "Machine washable"],
            "tags": ["bedroom", "modern", "all"],
        },
        {
            "name": "Bath Towel Set (4 pc)",
            "price": 1900,
            "search_terms": "bath towel set of 4 soft cotton",
            "platform": "Home Centre",
            "features": ["600 GSM", "Quick dry"],
            "tags": ["bathroom", "all"],
        },
        {
            "name": "Window Curtains (Pair)",
            "price": 2800,
            "search_terms": "window curtains pair blackout eyelet",
            "platform": "Amazon",
            "features": ["Blackout", "Rod pocket"],
            "tags": ["living", "bedroom", "all", "modern"],
        },
    ],
    "Appliances": [
        {
            "name": "Air Purifier (30 sq ft)",
            "price": 14500,
            "search_terms": "hepa air purifier 30 square feet",
            "platform": "Amazon",
            "features": ["HEPA + carbon", "Sleep mode"],
            "tags": ["living", "bedroom", "kids", "all"],
        },
        {
            "name": "RO Water Purifier",
            "price": 12500,
            "search_terms": "RO water purifier under sink uv",
            "platform": "Amazon",
            "features": ["7L/day", "UV+RO"],
            "tags": ["kitchen", "all"],
        },
        {
            "name": "Robot Vacuum Cleaner",
            "price": 22000,
            "search_terms": "robot vacuum cleaner lidar mapping",
            "platform": "Amazon",
            "features": ["Mopping", "Auto-empty base"],
            "tags": ["living", "modern", "all"],
        },
        {
            "name": "Microwave Oven (20 L)",
            "price": 8500,
            "search_terms": "convection microwave oven 20 litre",
            "platform": "Flipkart",
            "features": ["Convection", "Auto-cook menus"],
            "tags": ["kitchen", "all"],
        },
    ],
    "Paint & Walls": [
        {
            "name": "Interior Wall Paint (Set of 4)",
            "price": 6500,
            "search_terms": "interior wall paint premium emulsion set",
            "platform": "Amazon",
            "features": ["Low odour", "10 yr durability"],
            "tags": ["all"],
        },
        {
            "name": "Decorative Wall Panel",
            "price": 5400,
            "search_terms": "3d decorative wall panel wooden slat",
            "platform": "Amazon",
            "features": ["Slatted wood look", "DIY install"],
            "tags": ["living", "study", "modern", "industrial"],
        },
    ],
    "Services & Installation": [
        {
            "name": "Full Home Deep Cleaning",
            "price": 4500,
            "search_terms": "full home deep cleaning service",
            "platform": "Urban Company",
            "features": ["Kitchen + bathroom", "2-3 hr job"],
            "tags": ["all"],
        },
        {
            "name": "Carpenter / Assembly Service",
            "price": 2000,
            "search_terms": "carpenter furniture assembly service home",
            "platform": "Urban Company",
            "features": ["On-demand", "2 hr window"],
            "tags": ["all"],
        },
        {
            "name": "Electrician + Painter Visit",
            "price": 3000,
            "search_terms": "electrician and painter service home visit",
            "platform": "Urban Company",
            "features": ["Switchboard check", "Small paint patch"],
            "tags": ["all"],
        },
    ],
    "Contingency": [
        {
            "name": "Unplanned Repair Buffer",
            "price": 0,
            "search_terms": "home improvement budget buffer",
            "platform": "Amazon",
            "features": ["Kept unspent for surprises", "Wall sockets, brackets, delivery"],
            "tags": ["all"],
        }
    ],
}

PARTY_CATALOG: dict[str, list[dict[str, Any]]] = {
    "Venue & Rentals": [
        {
            "name": "Party Hall / Banquet Booking",
            "price": 6000,
            "search_terms": "party hall booking for birthday small",
            "platform": "OYO",
            "features": ["Up to 40 guests", "4-hour slot", "Basic lighting"],
            "tags": ["birthday", "corporate", "anniversary", "hall"],
        },
        {
            "name": "Tent / Marquee for Outdoor Event",
            "price": 15000,
            "search_terms": "marriage tent marquee booking price",
            "platform": "BookMyEvents",
            "features": ["Side walls", "Accommodates 100+"],
            "tags": ["wedding", "engagement", "outdoor", "festival"],
        },
        {
            "name": "Chairs, Tables & Crockery Rental",
            "price": 4000,
            "search_terms": "chairs and tables party rental near me",
            "platform": "BookMyEvents",
            "features": ["Stools + dining combo", "5-day return"],
            "tags": ["all", "hall"],
        },
    ],
    "Food & Beverages": [
        {
            "name": "Catering Service (per guest)",
            "unit": "per_guest",
            "price": 450,
            "search_terms": "party catering service per plate veg",
            "platform": "Zomato",
            "features": ["Starters + mains + dessert", "Live counter option"],
            "tags": ["all", "wedding", "corporate"],
        },
        {
            "name": "Snacks & Starters Platter (per guest)",
            "unit": "per_guest",
            "price": 180,
            "search_terms": "party snacks platter catering start bbq",
            "platform": "Swiggy",
            "features": ["Veg + non-veg options", "Delivered hot"],
            "tags": ["birthday", "corporate", "all"],
        },
        {
            "name": "Cold Drinks & Mocktail Bar (per guest)",
            "unit": "per_guest",
            "price": 150,
            "search_terms": "mocktail bar cold drinks party catering",
            "platform": "Swiggy",
            "features": ["Fresh fruit", "Disposable glassware"],
            "tags": ["birthday", "engagement", "corporate", "all"],
        },
    ],
    "Decor & Theme": [
        {
            "name": "Theme Backdrop / Photo Corner",
            "price": 6000,
            "search_terms": "birthday theme backdrop decoration hire",
            "platform": "PartyKart",
            "features": ["Custom text", "Props included"],
            "tags": ["birthday", "anniversary", "baby shower", "all"],
        },
        {
            "name": "Balloon & Flower Decoration",
            "price": 4500,
            "search_terms": "balloon decoration flower arrangement party",
            "platform": "PartyKart",
            "features": ["Pastel + metallic mix", "Setup by vendor"],
            "tags": ["birthday", "baby shower", "all"],
        },
        {
            "name": "Fairy Lights & Table Centrepieces",
            "price": 2500,
            "search_terms": "fairy lights warm white string decoration set",
            "platform": "Amazon",
            "features": ["Warm white", "5m per string"],
            "tags": ["wedding", "engagement", "festival", "all"],
        },
    ],
    "Cake & Desserts": [
        {
            "name": "Custom Themed Cake",
            "price": 1500,
            "search_terms": "custom birthday cake order eggless",
            "platform": "Swiggy",
            "features": ["Eggless option", "Custom message"],
            "tags": ["birthday", "baby shower", "anniversary", "all"],
        },
        {
            "name": "Dessert Table (Cupcakes & Cookies)",
            "price": 2500,
            "search_terms": "cupcake dessert table party order",
            "platform": "Swiggy",
            "features": ["24 pieces", "Themed toppers"],
            "tags": ["birthday", "kids", "all"],
        },
    ],
    "Entertainment & Sound": [
        {
            "name": "DJ & Sound System",
            "price": 5000,
            "search_terms": "dj and sound system hire party",
            "platform": "BookMyEvents",
            "features": ["2-hour set", "Bluetooth + mixer"],
            "tags": ["birthday", "corporate", "anniversary", "all"],
        },
        {
            "name": "LED Dance Floor (per 100 sq ft)",
            "unit": "block",
            "price": 3500,
            "search_terms": "led dance floor hire lights",
            "platform": "BookMyEvents",
            "features": ["RGB panels", "Sound reactive"],
            "tags": ["engagement", "wedding", "corporate", "all"],
        },
    ],
    "Gifts & Favours": [
        {
            "name": "Return Gifts (per piece)",
            "unit": "per_person",
            "price": 250,
            "search_terms": "return gifts for party personalised set",
            "platform": "Amazon",
            "features": ["Name customisation", "Curated box"],
            "tags": ["birthday", "anniversary", "baby shower", "all"],
        },
        {
            "name": "Customised Mug / Keychain (per piece)",
            "unit": "per_person",
            "price": 120,
            "search_terms": "customised mug keychain bulk order personalized",
            "platform": "Amazon",
            "features": ["Photo print", "Bulk discounts"],
            "tags": ["corporate", "birthday", "all"],
        },
    ],
    "Photography & Content": [
        {
            "name": "Event Photographer (3 hours)",
            "price": 6000,
            "search_terms": "event photographer birthday party booking",
            "platform": "BookMyEvents",
            "features": ["50+ edited photos", "48 hr delivery"],
            "tags": ["birthday", "wedding", "corporate", "all"],
        },
        {
            "name": "360 Photo Booth",
            "price": 8000,
            "search_terms": "360 photo booth hire party",
            "platform": "BookMyEvents",
            "features": ["Instant social sharing", "Props included"],
            "tags": ["birthday", "corporate", "engagement", "all"],
        },
    ],
    "Miscellaneous": [
        {
            "name": "Invitations & Printed Material",
            "price": 1200,
            "search_terms": "party invitation cards digital whatsapp invite",
            "platform": "Amazon",
            "features": ["Digital + print set", "48 hr design"],
            "tags": ["all"],
        },
        {
            "name": "Ice, Cups, Cutlery & Cleaning",
            "price": 2000,
            "search_terms": "ice delivery party disposable cups cutlery bulk",
            "platform": "Amazon",
            "features": ["Holds 30 guests", "Post-event cleanup"],
            "tags": ["all"],
        },
    ],
    "Contingency": [
        {
            "name": "Last-Minute Buffer",
            "price": 0,
            "search_terms": "event budget buffer last minute",
            "platform": "Amazon",
            "features": ["Vendor overruns, extra guests, taxis", "Held aside"],
            "tags": ["all"],
        }
    ],
}

JEWELRY_CATALOG: dict[str, list[dict[str, Any]]] = {
    "Main Piece": [
        {
            "name": "Traditional Gold Necklace Set",
            "price": 120000,
            "search_terms": "gold necklace set hallmarked 22k",
            "platform": "Tanishq",
            "features": ["BIS hallmarked", "Includes matching earrings", "BIS buy-back eligible"],
            "tags": ["wedding", "engagement", "festival", "gold"],
        },
        {
            "name": "Diamond Solitaire Ring",
            "price": 90000,
            "search_terms": "diamond solitaire engagement ring certified",
            "platform": "CaratLane",
            "features": ["IGI certified", "Lifetime resizing", "Platinum band"],
            "tags": ["engagement", "wedding", "diamond"],
        },
        {
            "name": "Emerald Halo Ring",
            "price": 65000,
            "search_terms": "emerald ring halo gold engagement",
            "platform": "Bluestone",
            "features": ["Natural or lab-grown options", "Certification included"],
            "tags": ["engagement", "gold", "diamond"],
        },
        {
            "name": "Silver Oxidised Necklace (Festa)",
            "price": 9000,
            "search_terms": "oxidised silver necklace tribal design",
            "platform": "Myntra",
            "features": ["925 sterling", "Festa collection"],
            "tags": ["festival", "silver", "anniversary", "gift"],
        },
        {
            "name": "Swarovski Crystal Statement Necklace",
            "price": 12000,
            "search_terms": "crystal statement necklace swarovski",
            "platform": "Myntra",
            "features": ["Sparkling finish", "Adjustable chain"],
            "tags": ["party", "gift", "anniversary", "silver"],
        },
    ],
    "Matching Earrings": [
        {
            "name": "Jhumka Earrings",
            "price": 35000,
            "search_terms": "gold jhumka earrings traditional",
            "platform": "Tanishq",
            "features": ["22k/24k options", "Hand-crafted domes"],
            "tags": ["wedding", "festival", "engagement", "gold"],
        },
        {
            "name": "Diamond Stud Earrings",
            "price": 28000,
            "search_terms": "diamond stud earrings certified pair",
            "platform": "Bluestone",
            "features": ["Clasp-free", "Everyday wear"],
            "tags": ["engagement", "office", "diamond"],
        },
        {
            "name": "American Diamond Earrings",
            "price": 4500,
            "search_terms": "american diamond earrings price",
            "platform": "Myntra",
            "features": ["Silver-plated", "Party-ready"],
            "tags": ["party", "gift", "budget", "silver"],
        },
    ],
    "Pendant or Mangalsutra": [
        {
            "name": "Mangalsutra (18-22 ct)",
            "price": 75000,
            "search_terms": "mangalsutra gold black beads design",
            "platform": "Reliance Jewels",
            "features": ["Hallmarked", "Adjustable length"],
            "tags": ["wedding", "festival", "gold"],
        },
        {
            "name": "Birthstone Pendant",
            "price": 15000,
            "search_terms": "birthstone pendant chain gift",
            "platform": "CaratLane",
            "features": ["Personal engraving", "Gift boxed"],
            "tags": ["gift", "anniversary", "office"],
        },
    ],
    "Bangles or Bracelet": [
        {
            "name": "Gold Kada / Open Bangles",
            "price": 48000,
            "search_terms": "gold kada bangle pair hallmarked",
            "platform": "Malabar Gold",
            "features": ["Adjustable", "Traditional craft"],
            "tags": ["wedding", "festival", "gold"],
        },
        {
            "name": "Diamond Tennis Bracelet",
            "price": 180000,
            "search_terms": "diamond tennis bracelet certified",
            "platform": "Bluestone",
            "features": ["Secure clasp", "Graduated stones"],
            "tags": ["engagement", "wedding", "diamond", "luxury"],
        },
        {
            "name": "Silver Cuff / Bangle Stack",
            "price": 6000,
            "search_terms": "silver bangle set cuff stack",
            "platform": "Myntra",
            "features": ["925 sterling", "Oxidised finish"],
            "tags": ["festival", "party", "silver", "budget"],
        },
    ],
    "Nose Ring or Ear Studs": [
        {
            "name": "Diamond Nose Pin",
            "price": 8000,
            "search_terms": "diamond nose pin stud gold",
            "platform": "CaratLane",
            "features": ["Screw-back", "Skin friendly"],
            "tags": ["wedding", "festival", "diamond"],
        },
        {
            "name": "Everyday Stud Earrings (Pair)",
            "price": 7000,
            "search_terms": "everyday gold stud earrings pair",
            "platform": "Reliance Jewels",
            "features": ["Lightweight", "Office appropriate"],
            "tags": ["office", "engagement", "gold"],
        },
    ],
    "Certification & Making Charges": [
        {
            "name": "BIS Hallmark Certification",
            "price": 4500,
            "search_terms": "bis hallmarking charges gold per gram",
            "platform": "Tanishq",
            "features": ["Government assay", "Mandatory for 22k+"],
            "tags": ["gold", "all"],
        },
        {
            "name": "IGI Diamond Grading Report",
            "price": 6000,
            "search_terms": "igi diamond certification report cost",
            "platform": "CaratLane",
            "features": ["Independent grading", "Report card with invoice"],
            "tags": ["diamond", "engagement"],
        },
    ],
    "Insurance & Resale": [
        {
            "name": "Jewellery Insurance (1 year)",
            "price": 3500,
            "search_terms": "jewellery insurance policy annual premium",
            "platform": "Malabar Gold",
            "features": ["Theft + damage cover", "Underwriting on invoice"],
            "tags": ["all", "gold", "diamond"],
        },
        {
            "name": "Buy-Back / Resale Assurance",
            "price": 0,
            "search_terms": "jewellery buy back resale value gold",
            "platform": "Malabar Gold",
            "features": ["Transparent resale policy", "Encourage asking at purchase"],
            "tags": ["all"],
        },
    ],
    "Contingency": [
        {
            "name": "Price Movement Buffer",
            "price": 0,
            "search_terms": "gold price fluctuation buffer budget",
            "platform": "Tanishq",
            "features": ["Gold rate changes between visit and payment", "Keep 3-5% aside"],
            "tags": ["all", "gold"],
        }
    ],
}

CATALOGS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "home": HOME_CATALOG,
    "party": PARTY_CATALOG,
    "jewelry": JEWELRY_CATALOG,
}

# Maps free-text form values onto catalog tags.
HOME_ROOM_ROOM_TAGS = {
    "living room": "living",
    "bedroom": "bedroom",
    "kids room": "kids",
    "study": "study",
    "office": "office",
    "kitchen": "kitchen",
    "dining": "dining",
    "bathroom": "bathroom",
    "balcony": "living",
    "pooja room": "pooja",
}

HOME_STYLE_TAGS = {
    "modern": "modern",
    "minimalist": "minimalist",
    "traditional": "traditional",
    "industrial": "industrial",
    "scandinavian": "scandinavian",
    "boho": "boho",
}

PARTY_EVENT_TAGS = {
    "birthday": "birthday",
    "wedding": "wedding",
    "engagement": "engagement",
    "anniversary": "anniversary",
    "corporate": "corporate",
    "baby shower": "baby shower",
    "festivals": "festival",
    "graduation": "all",
}

JEWELRY_METAL_TAGS = {
    "gold": "gold",
    "silver": "silver",
    "diamond": "diamond",
    "platinum": "diamond",
    "fashion": "budget",
}


def catalog_for(plan_type: str) -> dict[str, list[dict[str, Any]]]:
    return CATALOGS.get(plan_type, HOME_CATALOG)


def score_item(item: dict[str, Any], desired_tags: list[str]) -> int:
    """Rank catalog items by how well their tags match the user's preferences."""
    tags = set(item.get("tags", []))
    score = 0
    for tag in desired_tags:
        if tag in tags:
            score += 2
        if tag != "all" and "all" in tags:
            score += 1
    return score


def filter_items(
    plan_type: str,
    category: str,
    desired_tags: list[str],
    *,
    max_price: float | None = None,
) -> list[dict[str, Any]]:
    """Return catalog items for a category, best match first, price-capped."""
    items = catalog_for(plan_type).get(category, [])
    if max_price is not None and max_price > 0:
        affordable = [i for i in items if 0 < i["price"] <= max_price]
        # A very small category budget should still show *something* useful.
        items = affordable or items
    return sorted(items, key=lambda i: (-score_item(i, desired_tags), i["price"]))
