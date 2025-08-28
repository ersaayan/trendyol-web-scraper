from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

from selectolax.parser import HTMLParser


@dataclass
class PDPProduct:
    productId: int
    productCode: Optional[str]
    name: Optional[str]
    brand: Optional[str]
    price: Optional[float]
    currency: str
    rating: Optional[float]
    ratingCount: Optional[int]
    favoriteCount: Optional[int]
    categoryPath: List[str]
    seller: Optional[str]
    sellerId: Optional[int]
    variants: List[Dict[str, Any]]
    images: List[str]
    badges: List[str]


# Helpers


def _parse_int(v: Optional[str]) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(str(v))
    except Exception:
        # try digits-only
        digits = "".join(ch for ch in str(v) if ch.isdigit())
        return int(digits) if digits else None


def _parse_float(v: Optional[str]) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return None


# Core parser


def parse_pdp(html: str) -> Dict[str, Any]:
    """
    Parse Trendyol PDP. Prefers embedded JSON-like window["__envoy_*__PROPS"] when present,
    with fallbacks to visible DOM.
    Returns a flat dict safe for NDJSON.
    """
    tree = HTMLParser(html)

    # 1) Try to extract from embedded scripts that include product fields
    # We scan <script> tags text and look for patterns like '"product":{"id":...}
    product: Dict[str, Any] = {}
    images: List[str] = []
    variants: List[Dict[str, Any]] = []
    category_tree: List[str] = []
    seller_name: Optional[str] = None
    seller_id: Optional[int] = None
    favorite_count: Optional[int] = None

    for script in tree.css("script"):
        txt = script.text() or ""
        if (
            '"product"' in txt
            and '"id":' in txt
            and '"name":' in txt
            and '"brand"' in txt
        ):
            # crude slicing to the product object JSON
            try:
                # Find product object boundaries
                start = txt.find('"product"')
                if start == -1:
                    continue
                start = txt.find("{", start)
                # Balance braces to extract JSON object
                depth = 0
                end = start
                while end < len(txt):
                    if txt[end] == "{":
                        depth += 1
                    elif txt[end] == "}":
                        depth -= 1
                        if depth == 0:
                            end += 1
                            break
                    end += 1
                blob = txt[start:end]
                # Minify keys that we care about
                # Use simple json parsing after fixing escaped sequences
                import json, re

                # Clean up invalid trailing commas etc. Attempt a best-effort parse
                cleaned = blob
                # Some windows props are JS, but often valid JSON
                product_obj = json.loads(cleaned)
                product = product_obj
            except Exception:
                continue
        if '"favoriteCount"' in txt and favorite_count is None:
            # rough parse for favoriteCount
            import re

            m = re.search(r'"favoriteCount"\s*:\s*(\d+)', txt)
            if m:
                favorite_count = _parse_int(m.group(1))
        if '"images"' in txt and not images:
            try:
                import json

                # naive parse for images array
                idx = txt.find('"images"')
                if idx != -1:
                    start = txt.find("[", idx)
                    depth = 0
                    j = start
                    while j < len(txt):
                        if txt[j] == "[":
                            depth += 1
                        elif txt[j] == "]":
                            depth -= 1
                            if depth == 0:
                                j += 1
                                break
                        j += 1
                    arr = txt[start:j]
                    images = json.loads(arr)
            except Exception:
                pass
        if '"variants"' in txt and not variants:
            try:
                import json

                idx = txt.find('"variants"')
                if idx != -1:
                    start = txt.find("[", idx)
                    depth = 0
                    j = start
                    while j < len(txt):
                        if txt[j] == "[":
                            depth += 1
                        elif txt[j] == "]":
                            depth -= 1
                            if depth == 0:
                                j += 1
                                break
                        j += 1
                    arr = txt[start:j]
                    variants = json.loads(arr)
            except Exception:
                pass
        if '"webCategoryTree"' in txt and not category_tree:
            try:
                import json

                idx = txt.find('"webCategoryTree"')
                if idx != -1:
                    start = txt.find("[", idx)
                    depth = 0
                    j = start
                    while j < len(txt):
                        if txt[j] == "[":
                            depth += 1
                        elif txt[j] == "]":
                            depth -= 1
                            if depth == 0:
                                j += 1
                                break
                        j += 1
                    arr = txt[start:j]
                    cats = json.loads(arr)
                    category_tree = [
                        c.get("name")
                        for c in cats
                        if isinstance(c, dict) and c.get("name")
                    ]
            except Exception:
                pass
        if '"merchantListing"' in txt and seller_id is None:
            try:
                import re

                m1 = re.search(
                    r'"merchant"\s*:\s*\{[^}]*"id"\s*:\s*(\d+)[^}]*"name"\s*:\s*"([^"]+)"',
                    txt,
                )
                if m1:
                    seller_id = _parse_int(m1.group(1))
                    seller_name = m1.group(2)
            except Exception:
                pass

    # Fallbacks from visible DOM
    title = None
    brand = None
    rating_val = None
    rating_count = None
    price_val = None
    currency = "TL"

    h1 = tree.css_first('[data-testid="product-title"], h1.product-title')
    if h1:
        title = h1.text(strip=True)
        # brand may be inside a strong or anchor within h1
        b = h1.css_first("strong")
        if b:
            brand = b.text(strip=True)
            # remove brand from title if duplicated
            if title.startswith(brand):
                title = title[len(brand) :].strip("- ").strip()

    # rating
    rv = tree.css_first(".reviews-summary-average-rating")
    if rv:
        rating_val = _parse_float(rv.text(strip=True))
    rc = tree.css_first(".reviews-summary-reviews-detail b")
    if rc:
        rating_count = _parse_int(rc.text(strip=True))

    # price (try various selectors)
    price_node = (
        tree.css_first('[data-testid="price-current-price"]')
        or tree.css_first(".prc-dsc")
        or tree.css_first(".product-price .pr-bx-w .prc-dsc")
    )
    if price_node:
        price_val = _parse_float(price_node.text(strip=True))

    # badges
    badges: List[str] = []
    for n in tree.css(
        ".category-top-ranking-wrap-text, .badge__text-wrapper span, .badge-title"
    ):
        t = n.text(strip=True)
        if t and t not in badges:
            badges.append(t)

    # Compose result, preferring script data if available
    pid = _parse_int(str(product.get("id"))) if product else None
    product_code = product.get("productCode") if isinstance(product, dict) else None
    brand_final = (
        (product.get("brand") or {}).get("name")
        if isinstance(product, dict) and isinstance(product.get("brand"), dict)
        else brand
    )
    name_final = product.get("name") if isinstance(product, dict) else title

    # price from product object if present
    try:
        p_price = None
        if isinstance(product, dict):
            winner = product.get("winnerVariant") or {}
            price_obj = winner.get("price") or {}
            p_price = price_obj.get("discountedPrice", {}).get(
                "value"
            ) or price_obj.get("sellingPrice", {}).get("value")
        price_val = float(p_price) if p_price is not None else price_val
    except Exception:
        pass

    # rating from product object
    if isinstance(product, dict) and not rating_val:
        rs = product.get("ratingScore") or {}
        rating_val = rs.get("averageRating")
        rating_count = rs.get("totalCount") or rating_count

    # favorites from script
    if favorite_count is None and isinstance(product, dict):
        favorite_count = product.get("favoriteCount")

    out: Dict[str, Any] = {
        "productId": pid,
        "productCode": product_code,
        "name": name_final,
        "brand": brand_final,
        "price": price_val,
        "currency": currency,
        "rating": rating_val,
        "ratingCount": rating_count,
        "favoriteCount": favorite_count,
        "categoryPath": category_tree,
        "seller": seller_name,
        "sellerId": seller_id,
        "variants": variants,
        "images": images,
        "badges": badges,
    }

    return out
