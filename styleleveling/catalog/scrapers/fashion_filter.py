"""Rules that keep the StyleLeveling catalog focused on wearable fashion."""

import re


# Check exclusions first. Some beauty names contain fashion-looking words such
# as "body" or "coat", so a positive match must never override these signals.
NON_FASHION_PATTERNS = (
    r"\b(face|skin|skincare|makeup|cosmetic|beauty|grooming|wellness)\b",
    r"\b(cream|moisturi[sz]er|serum|cleanser|toner|scrub|lotion|soap)\b",
    r"\b(shampoo|conditioner|haircare|hairspray|hair oil|scalp)\b",
    r"\b(mascara|lipstick|lip gloss|foundation|concealer|eyeliner)\b",
    r"\b(fragrance|perfume|aftershave|deodorant|sunscreen|spf)\b",
    r"\b(candle|diffuser|homeware|toothbrush|supplement|vitamin)\b",
    r"\b(body wash|body scrub|bath bomb|nail polish)\b",
)

# Products must contain at least one wearable-fashion signal. ASOS product
# names normally include the garment/accessory type, making this stricter and
# safer than accepting every item from its mixed sale catalog.
FASHION_PATTERNS = (
    r"\b(t-?shirt|tee|tank|top|blouse|shirt|cami|camisole)\b",
    r"\b(dress|gown|skirt|skort|jumpsuit|romper|playsuit|bodysuit)\b",
    r"\b(jeans?|pants?|trousers?|chinos?|shorts?|leggings?|jeggings?)\b",
    r"\b(jacket|coat|blazer|vest|waistcoat|parka|shacket|gilet)\b",
    r"\b(hoodie|sweatshirt|sweater|cardigan|jumper|pullover|fleece)\b",
    r"\b(shoes?|sneakers?|trainers?|boots?|sandals?|heels?|loafers?|flats?)\b",
    r"\b(bra|briefs?|boxers?|underwear|lingerie|socks?|tights?)\b",
    r"\b(swimwear|swimsuit|bikini|swim shorts?|trunks?)\b",
    r"\b(bag|backpack|purse|wallet|belt|hat|cap|beanie|scarf|gloves?)\b",
    r"\b(necklace|earrings?|bracelet|ring|jewelry|watch|sunglasses)\b",
    r"\b(suit|tie|bow tie|polo|tracksuit|joggers?|loungewear|pajamas?|pyjamas?)\b",
    r"\b(clothing|apparel|footwear|accessories)\b",
)


def _matches_any(text, patterns):
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def fashion_product_decision(name, category="", description=""):
    """Return ``(accepted, reason)`` for a prospective fashion listing."""

    # Ignore the generic fallback category because it does not prove that the
    # retailer item is clothing. Specific category and description values are
    # still useful evidence.
    useful_category = "" if category.strip().lower() == "clothing" else category
    text = " ".join((name, useful_category, description))

    if _matches_any(text, NON_FASHION_PATTERNS):
        return False, "matched a non-fashion product term"
    if _matches_any(text, FASHION_PATTERNS):
        return True, "matched a wearable fashion term"
    return False, "no reliable wearable fashion term"

