import re

CATEGORY_NAMES = [
    "Tees & Tanks", "Graphic T-Shirts", "Blouses & Shirts", "Shirts & Polos",
    "Sweats & Hoodies", "Sweaters", "Jackets & Coats", "Suits & Blazers",
    "Jeans", "Denim Shorts", "Shorts", "Pants", "Pants & Chinos", "Joggers",
    "Skirts", "Dresses & Jumpsuits", "Activewear", "Sleepwear", "Swimwear",
    "Lingerie & Underwear", "Socks & Underwear", "Shoes", "Bags & Belts",
    "Jewelry", "Hats & Sunglasses", "Other Clothing", "Other Accessories",
    "Uncategorized",
]
CATEGORY_CHOICES = [(name, name) for name in CATEGORY_NAMES]

# Ordered from the most specific names to broader clothing terms. First match wins.
RULES = [
    ("Denim Shorts", r"\b(?:denim\s+shorts?|jorts?)\b"),
    ("Graphic T-Shirts", r"\bgraphic\b.*\b(?:tee|t-?shirt)s?\b|\b(?:tee|t-?shirt)s?\b.*\bgraphic\b"),
    ("Dresses & Jumpsuits", r"\b(?:dress|jumpsuit|romper)s?\b"), ("Skirts", r"\b(?:skirt|skort)s?\b"),
    ("Suits & Blazers", r"\b(?:suit|blazer)s?\b"), ("Jackets & Coats", r"\b(?:jacket|coat|outerwear|shacket|vest)s?\b"),
    ("Sweats & Hoodies", r"\b(?:hoodie|sweatshirt|sweatpant)s?\b"), ("Sweaters", r"\b(?:sweater|cardigan|knitwear)\b"),
    ("Joggers", r"\bjoggers?\b"), ("Jeans", r"\bjeans?\b"), ("Pants & Chinos", r"\bchinos?\b"),
    ("Pants", r"\b(?:pants?|trousers?)\b"), ("Shorts", r"\bshorts?\b"),
    ("Shirts & Polos", r"\b(?:polo|button[- ]?(?:up|down)|shirt)s?\b"), ("Blouses & Shirts", r"\bblouses?\b"),
    ("Tees & Tanks", r"\b(?:tee|t-?shirt|tank|cami)s?\b"), ("Sleepwear", r"\b(?:pajama|pyjama|sleepwear|nightgown)s?\b"),
    ("Swimwear", r"\b(?:swim|bikini|swimsuit|boardshort)s?\b"), ("Activewear", r"\b(?:activewear|workout|sports? bra|legging|gym short)s?\b"),
    ("Lingerie & Underwear", r"\b(?:bra|panty|panties|lingerie|bodysuit)s?\b"), ("Socks & Underwear", r"\b(?:sock|underwear|boxer|brief|trunk)s?\b"),
    ("Shoes", r"\b(?:shoe|sneaker|boot|sandal|slipper|heel|loafer)s?\b"), ("Bags & Belts", r"\b(?:bag|belt|wallet|purse|backpack)s?\b"),
    ("Jewelry", r"\b(?:jewelry|necklace|earring|bracelet|ring)s?\b"), ("Hats & Sunglasses", r"\b(?:hat|beanie|cap|sunglasses?)\b"),
]

SOURCE_MAP = {
    "tops": ("Tees & Tanks", 65, True), "accessories": ("Other Accessories", 55, True),
    "clothing": ("Other Clothing", 30, True), "denim": ("Jeans", 60, True),
    "bottoms": ("Pants", 45, True),
}

def classify_category(name, source_category, audience):
    name_text = (name or "").lower()
    for category, pattern in RULES:
        if re.search(pattern, name_text):
            if audience == "women" and category == "Shirts & Polos": category = "Blouses & Shirts"
            if audience == "men" and category == "Blouses & Shirts": category = "Shirts & Polos"
            if audience == "women" and category == "Socks & Underwear": category = "Lingerie & Underwear"
            return category, 92, False
    source = " ".join((source_category or "").split()).strip()
    if source in CATEGORY_NAMES and source != "Uncategorized":
        return source, 85, False
    return SOURCE_MAP.get(source.lower(), ("Other Clothing", 15, True))
