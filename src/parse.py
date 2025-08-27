from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
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

        # price: select first visible .price-item
        price = _text(card, ".price-item")

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

        results.append(
            {
                "productId": product_id,
                "brand": brand,
                "name": name,
                "subtitle": subtitle,
                "price": price,
                "currency": "TL",
                "rating": rating,
                "ratingCount": rating_count,
                "productUrl": abs_url,
                "imageUrl": image_url,
                "merchantId": merchant_id,
                "boutiqueId": boutique_id,
                "variantSummary": variant_summary,
                "badges": badges,
                "pageIndex": page_index,
                "collectedAt": now,
            }
        )

    return results
