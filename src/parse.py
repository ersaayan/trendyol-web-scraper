from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

from selectolax.parser import HTMLParser

BASE = "https://www.trendyol.com"


@dataclass
class Product:
    productId: int
    brand: Optional[str]
    name: Optional[str]
    subtitle: Optional[str]
    price: Optional[str]
    currency: str
    rating: Optional[float]
    ratingCount: Optional[int]
    productUrl: Optional[str]
    imageUrl: Optional[str]
    merchantId: Optional[int]
    boutiqueId: Optional[int]
    variantSummary: Optional[str]
    badges: List[str]
    pageIndex: int
    collectedAt: str


def _text(node, sel: str) -> Optional[str]:
    n = node.css_first(sel)
    if not n:
        return None
    return n.text(strip=True) or None


def _attr(node, sel: str, attr: str) -> Optional[str]:
    n = node.css_first(sel)
    if not n:
        return None
    return n.attributes.get(attr)


def _parse_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else None


def _parse_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    try:
        return float(str(s).replace(",", "."))
    except Exception:
        return None


def _text_any(node, selectors: List[str]) -> Optional[str]:
    for sel in selectors:
        v = _text(node, sel)
        if v:
            return v
    return None


def _parse_turkish_compact_number(s: Optional[str]) -> Optional[int]:
    """
    Parse strings like "1B+", "4,6B", "147,1B", "100+" to integers.
    Assumptions:
    - B ~ Bin (thousand)
    - M/Mn ~ Milyon (million)
    - Comma is decimal separator.
    """
    if not s:
        return None
    txt = s.strip()
    # Keep only relevant chars
    core = "".join(ch for ch in txt if ch.isdigit() or ch in ",[+BMnm]")
    if not core:
        # fallback: just digits from original
        return _parse_int(txt)
    # Normalize decimal comma
    core = core.replace(",", ".")
    mult = 1
    if "B" in core or "b" in core:
        mult = 1_000
    if "M" in core or "m" in core or "Mn" in core:
        mult = 1_000_000
    # strip suffixes
    core = (
        core.replace("B", "")
        .replace("b", "")
        .replace("Mn", "")
        .replace("m", "")
        .replace("M", "")
        .replace("+", "")
    )
    try:
        if "." in core:
            val = float(core)
        else:
            val = float(int(core))
        return int(round(val * mult))
    except Exception:
        return _parse_int(txt)


def _extract_social_proof(card) -> Tuple[List[str], Dict[str, Optional[int]]]:
    texts: List[str] = []
    data: Dict[str, Optional[int]] = {
        "soldLast3Days": None,
        "addedToBasket3Days": None,
        "favoritedCount": None,
        "viewedLast24Hours": None,
    }
    # Collect raw texts
    for n in card.css(".social-proof .social-proof-text"):
        t = n.text(strip=True)
        if t:
            texts.append(t)
            low = t.lower()
            # Try to find a highlighted number span first
            focused = n.css_first(".focused-text")
            focused_txt = focused.text(strip=True) if focused else None
            num = _parse_turkish_compact_number(focused_txt or t)
            if "satıldı" in low and "son 3 günde" in low:
                data["soldLast3Days"] = max(data["soldLast3Days"] or 0, num or 0) or num
            elif "ekledi" in low and "3 günde" in low:
                data["addedToBasket3Days"] = (
                    max(data["addedToBasket3Days"] or 0, num or 0) or num
                )
            elif "favoriledi" in low:
                data["favoritedCount"] = (
                    max(data["favoritedCount"] or 0, num or 0) or num
                )
            elif "inceledi" in low and "24 saatte" in low:
                data["viewedLast24Hours"] = (
                    max(data["viewedLast24Hours"] or 0, num or 0) or num
                )
    return texts, data


def parse_products(html: str, page_index: int) -> List[Dict[str, Any]]:
    tree = HTMLParser(html)
    cards = tree.css("div.p-card-wrppr")
    results: List[Dict[str, Any]] = []
    if not cards:
        return results

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    for card in cards:
        pid = _attr(card, "div.p-card-wrppr", "data-id") or card.attributes.get(
            "data-id"
        )
        product_id = _parse_int(pid)
        href = _attr(card, "a.p-card-chldrn-cntnr", "href")
        abs_url = urljoin(BASE, href) if href else None

        # Query params
        boutique_id = merchant_id = None
        if href:
            try:
                q = parse_qs(urlparse(href).query)
                boutique_id = _parse_int((q.get("boutiqueId") or [None])[0])
                merchant_id = _parse_int((q.get("merchantId") or [None])[0])
            except Exception:
                pass

        brand = _text(card, ".prdct-desc-cntnr-ttl")
        name = _text(card, ".prdct-desc-cntnr-name")
        subtitle = _text(card, ".product-desc-sub-text")

        # price details
        price_discounted = _text_any(
            card,
            [
                ".price-item.lowest-price-discounted",
                ".price-item.discounted",
            ],
        )
        price_original = _text_any(card, [".price-item.lowest-price-original"])
        # legacy price
        price = price_discounted or _text(card, ".price-item") or price_original

        rating = _parse_float(_text(card, ".rating-score"))
        rating_count = _parse_int(_text(card, ".ratingCount"))

        image_url = _attr(card, ".p-card-img", "src")

        variant_summary = None
        v_value = _text(card, ".variant-options-overlay .variant-value")
        v_more = _text(card, ".variant-options-overlay .other-variant-count")
        if v_value or v_more:
            variant_summary = " | ".join([x for x in [v_value, v_more] if x])

        badges: List[str] = []
        for b in card.css(".badges-wrapper .product-badge .name"):
            t = b.text(strip=True)
            if t:
                badges.append(t)

        # Top badge wrapper (e.g., "En Çok Satan 1. Ürün")
        top_badges: List[str] = []
        for b in card.css(".badge-wrapper .badge-title"):
            t = b.text(strip=True)
            if t:
                top_badges.append(t)

        # Price labels (e.g., Son 30 Günün En Düşük Fiyatı!)
        price_labels: List[str] = []
        for n in card.css(".price-label-wrapper .low-price-title"):
            t = n.text(strip=True)
            if t:
                price_labels.append(t)

        # Social proof
        social_texts, social = _extract_social_proof(card)

        results.append(
            {
                "productId": product_id,
                "brand": brand,
                "name": name,
                "subtitle": subtitle,
                "price": price,
                "priceOriginal": price_original,
                "priceDiscounted": price_discounted,
                "priceLabels": price_labels,
                "currency": "TL",
                "rating": rating,
                "ratingCount": rating_count,
                "productUrl": abs_url,
                "imageUrl": image_url,
                "merchantId": merchant_id,
                "boutiqueId": boutique_id,
                "variantSummary": variant_summary,
                "badges": badges,
                "topBadges": top_badges,
                "socialProof": social_texts,
                # normalized social proof
                **social,
                "pageIndex": page_index,
                "collectedAt": now,
            }
        )

    return results
