from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .analysis.prepare import parse_price_str, read_ndjson, read_csv, percentiles
from .analysis.pricing import (
    ShippingTier,
    normalize_tiers,
    shipping_fee,
    commission_amount,
    profit,
    break_even,
    ladder_prices,
)
from .analysis.llm_client import call_llm


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kategori verilerini fiyat/karlılık açısından analiz eder"
    )
    p.add_argument(
        "--in", dest="inp", required=True, help="Girdi dosyası (NDJSON veya CSV)"
    )
    p.add_argument(
        "--format", choices=["ndjson", "csv"], default="ndjson", help="Girdi formatı"
    )
    p.add_argument(
        "--commission", type=float, required=True, help="Komisyon yüzdesi (örn 12.0)"
    )
    p.add_argument(
        "--default-cost",
        type=float,
        required=True,
        help="Varsayılan ürün maliyeti (TL)",
    )
    p.add_argument(
        "--tiers",
        type=str,
        default='[{"up_to":150,"fee":42.70},{"up_to":300,"fee":72.20}]',
        help='Kargo baremleri JSON listesi (örn: [{"up_to":150,"fee":42.7},{"up_to":300,"fee":72.2}])',
    )
    p.add_argument(
        "--margins",
        type=str,
        default="5,10,15",
        help="Break-even üzerine yüzde marjlar (virgülle, örn: 5,10,15)",
    )
    p.add_argument("--out-dir", type=str, default="analysis", help="Çıktı klasörü")
    p.add_argument(
        "--use-llm",
        action="store_true",
        help="LLM ile ek kategori içgörüleri üret (OPENAI_API_KEY gerekir)",
    )
    p.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help="LLM modeli (örn: gpt-4o-mini). Boşsa OPENAI_MODEL veya varsayılan kullanılır",
    )
    return p


def load_items(path: Path, fmt: str) -> List[Dict[str, Any]]:
    if fmt == "ndjson":
        return read_ndjson(path)
    return read_csv(path)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    inp = Path(args.inp)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Shipping tiers
    try:
        raw = json.loads(args.tiers)
        tiers = normalize_tiers([(d.get("up_to"), float(d["fee"])) for d in raw])
    except Exception:
        tiers = normalize_tiers([(150.0, 42.70), (300.0, 72.20)])

    margins = [float(x) for x in str(args.margins).split(",") if x.strip()]

    items = load_items(inp, args.format)
    # parse numeric prices
    prices: List[float] = []
    for it in items:
        p = parse_price_str(it.get("price"))
        if p is not None:
            prices.append(p)

    price_stats = percentiles(prices, [10, 25, 50, 75, 90]) if prices else {}

    # Determine a recommended minimal profitable price at dataset-level using default cost
    be = break_even(
        cost=float(args.default_cost),
        commission_rate_percent=float(args.commission),
        tiers=tiers,
    )
    ladder = ladder_prices(be, margins)

    # Per-item evaluation at current price
    per_item: List[Dict[str, Any]] = []
    for it in items:
        current_price = parse_price_str(it.get("price"))
        if current_price is None:
            continue
        pf = profit(
            current_price, float(args.default_cost), float(args.commission), tiers
        )
        per_item.append(
            {
                "productId": it.get("productId"),
                "name": it.get("name"),
                "brand": it.get("brand"),
                "currentPrice": current_price,
                "shippingFee": shipping_fee(current_price, tiers),
                "commissionFee": commission_amount(
                    current_price, float(args.commission)
                ),
                "profit": round(pf, 2),
                "profitable": pf > 0,
                "rating": it.get("rating"),
                "ratingCount": it.get("ratingCount"),
                "soldLast3Days": it.get("soldLast3Days"),
                "favoritedCount": it.get("favoritedCount"),
            }
        )

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_json = out_dir / f"analysis-{ts}.json"
    out_md = out_dir / f"analysis-{ts}.md"

    result: Dict[str, Any] = {
        "input": str(inp),
        "count": len(items),
        "commissionPercent": float(args.commission),
        "defaultCost": float(args.default_cost),
        "shippingTiers": [dict(up_to=t.up_to, fee=t.fee) for t in tiers],
        "priceStats": price_stats,
        "breakEven": round(be, 2),
        "ladder": [round(x, 2) for x in ladder],
        "itemsEvaluated": per_item[:100],  # cap preview
    }

    # Optional LLM summary
    if bool(getattr(args, "use_llm", False)):
        summary = {
            "count": result["count"],
            "commissionPercent": result["commissionPercent"],
            "defaultCost": result["defaultCost"],
            "shippingTiers": result["shippingTiers"],
            "priceStats": result.get("priceStats", {}),
            "breakEven": result["breakEven"],
            "ladder": result["ladder"],
        }
        used_model = args.llm_model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        try:
            llm_out = call_llm(summary, model=args.llm_model)
            result["llm"] = {"model": used_model, "output": llm_out}
        except Exception as e:
            result["llm"] = {"model": used_model, "error": str(e)}

    out_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Markdown summary
    lines = []
    lines.append(f"# Analiz Özeti\n")
    lines.append(f"Girdi: `{inp}`  ")
    lines.append(f"Toplam ürün: {len(items)}  ")
    lines.append(f"Komisyon: {args.commission}%  ")
    lines.append(f"Varsayılan Maliyet: {args.default_cost} TL  ")
    lines.append(
        f"Kargo Baremleri: {json.dumps(result['shippingTiers'], ensure_ascii=False)}  "
    )
    if price_stats:
        lines.append("\n## Fiyat Dağılımı (TL)")
        for k in [10.0, 25.0, 50.0, 75.0, 90.0]:
            v = price_stats.get(k)
            if v is not None:
                lines.append(f"- P{k:.0f}: {v:.2f}")
    lines.append("\n## Kârlılık Eşiği")
    lines.append(f"- Break-even: {result['breakEven']} TL")
    lines.append(
        f"- Öneri Merdiveni (%{','.join(str(int(m)) for m in margins)}): {', '.join(str(round(x,2)) for x in result['ladder'])}"
    )
    lines.append("\n_Not: Break-even ve merdiven varsayılan maliyete göredir._\n")

    # Append LLM insights if available
    if result.get("llm"):
        lines.append("\n## LLM Özet İçgörüler")
        llm = result["llm"]
        if "output" in llm:
            try:
                pretty = json.dumps(llm["output"], ensure_ascii=False, indent=2)
                lines.append("\n```json\n" + pretty + "\n```\n")
            except Exception:
                lines.append(str(llm["output"]))
        if "error" in llm:
            lines.append(f"Hata: {llm['error']}")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"Analiz üretildi: {out_json} ve {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
