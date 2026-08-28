import re

CATEGORY_CHOICES = [
    ("Tees & Tanks", "Tees & Tanks"), ("Graphic T-Shirts", "Graphic T-Shirts"),
    ("Blouses & Shirts", "Blouses & Shirts"), ("Shirts & Polos", "Shirts & Polos"),
    ("Sweats & Hoodies", "Sweats & Hoodies"), ("Sweaters", "Sweaters"),
    ("Jackets & Coats", "Jackets & Coats"), ("Suits & Blazers", "Suits & Blazers"),
    ("Jeans", "Jeans"), ("Denim Shorts", "Denim Shorts"), ("Shorts", "Shorts"),
    ("Pants", "Pants"), ("Pants & Chinos", "Pants & Chinos"), ("Joggers", "Joggers"),
    ("Skirts", "Skirts"), ("Dresses & Jumpsuits", "Dresses & Jumpsuits"),
    ("Activewear", "Activewear"), ("Sleepwear", "Sleepwear"), ("Swimwear", "Swimwear"),
    ("Lingerie & Underwear", "Lingerie & Underwear"), ("Socks & Underwear", "Socks & Underwear"),
    ("Shoes", "Shoes"), ("Bags & Belts", "Bags & Belts"), ("Jewelry", "Jewelry"),
    ("Hats & Sunglasses", "Hats & Sunglasses"), ("Uncategorized", "Uncategorized"),
]

RULES = [
    ("Denim Shorts", r"\bdenim\s+shorts?\b"), ("Graphic T-Shirts", r"\bgraphic\b.*\b(?:tee|t-?shirt)s?\b|\b(?:tee|t-?shirt)s?\b.*\bgraphic\b"),
    ("Dresses & Jumpsuits", r"\b(?:dress|jumpsuit|romper)s?\b"), ("Skirts", r"\bskirt\b"),
    ("Suits & Blazers", r"\b(?:suit|blazer)s?\b"), ("Jackets & Coats", r"\b(?:jacket|coat|outerwear|shacket|vest)s?\b"),
    ("Sweats & Hoodies", r"\b(?:hoodie|sweatshirt|sweatpant)s?\b"), ("Sweaters", r"\b(?:sweater|cardigan|knitwear)\b"),
    ("Joggers", r"\bjoggers?\b"), ("Jeans", r"\bjeans?\b"), ("Pants & Chinos", r"\bchinos?\b"),
    ("Pants", r"\b(?:pants?|trousers?)\b"), ("Shorts", r"\bshorts?\b"),
    ("Shirts & Polos", r"\b(?:polo|button[- ]?(?:up|down)|shirt)s?\b"), ("Blouses & Shirts", r"\bblouses?\b"),
    ("Tees & Tanks", r"\b(?:tee|t-?shirt|tank|cami)s?\b"), ("Sleepwear", r"\b(?:pajama|pyjama|sleepwear|nightgown)s?\b"),
    ("Swimwear", r"\b(?:swim|bikini|swimsuit|boardshort)s?\b"), ("Activewear", r"\b(?:activewear|workout|sports? bra|legging)s?\b"),
    ("Lingerie & Underwear", r"\b(?:bra|panty|panties|lingerie|bodysuit)s?\b"), ("Socks & Underwear", r"\b(?:sock|underwear|boxer|brief|trunk)s?\b"),
    ("Shoes", r"\b(?:shoe|sneaker|boot|sandal|slipper|heel|loafer)s?\b"), ("Bags & Belts", r"\b(?:bag|belt|wallet|purse|backpack)s?\b"),
    ("Jewelry", r"\b(?:jewelry|necklace|earring|bracelet|ring)s?\b"), ("Hats & Sunglasses", r"\b(?:hat|beanie|cap|sunglasses?)\b"),
]

def classify_category(name, source_category, audience):
    text = f"{source_category or ''} {name or ''}".lower()
    matches = [category for category, pattern in RULES if re.search(pattern, text)]
    unique = list(dict.fromkeys(matches))
    if "Denim Shorts" in unique and "Shorts" in unique: unique.remove("Shorts")
    if "Graphic T-Shirts" in unique and "Tees & Tanks" in unique: unique.remove("Tees & Tanks")
    if "Lingerie & Underwear" in unique and "Socks & Underwear" in unique: unique.remove("Socks & Underwear")
    if len(unique) == 1:
        category = unique[0]
        if audience == "women" and category == "Shirts & Polos": category = "Blouses & Shirts"
        if audience == "men" and category == "Blouses & Shirts": category = "Shirts & Polos"
        if audience == "women" and category == "Socks & Underwear": category = "Lingerie & Underwear"
        return category, 90, False
    return "Uncategorized", 0 if not unique else 45, True
