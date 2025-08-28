from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .analysis.llm_client import call_llm


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="PDP NDJSON girdisinden ürün başına LLM değerlendirmesi üretir"
    )
    p.add_argument("--in", dest="inp", required=True, help="PDP NDJSON girdisi")
    p.add_argument(
        "--out", dest="out", default="pdp_scored.ndjson", help="Çıktı NDJSON"
    )
    p.add_argument(
        "--llm-model",
        dest="llm_model",
        default=None,
        help="LLM modeli (örn: gpt-4o-mini)",
    )
    p.add_argument(
        "--rate-limit-ms",
        dest="rate_limit_ms",
        type=int,
        default=0,
        help="İstekler arası bekleme (ms)",
    )
    return p


def make_prompt_obj(prod: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "productId": prod.get("productId"),
        "name": prod.get("name"),
        "brand": prod.get("brand"),
        "price": prod.get("price"),
        "rating": prod.get("rating"),
        "ratingCount": prod.get("ratingCount"),
        "favoriteCount": prod.get("favoriteCount"),
        "categoryPath": prod.get("categoryPath"),
        "seller": prod.get("seller"),
        "badges": prod.get("badges"),
    }


def evaluate_product(prod: Dict[str, Any], model: Optional[str]) -> Dict[str, Any]:
    # Expected JSON schema from LLM; we don't enforce, but encourage via prompt
    summary = {
        "task": "ürün değerlendirme",
        "requirements": {
            "scores": ["product_score", "title_score"],
            "checks": ["category_fit", "compliance", "clarity"],
            "suggestions": ["title", "bullets"],
        },
        "product": make_prompt_obj(prod),
    }
    out = call_llm(summary, model=model)
    return out


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    inp = Path(args.inp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Stream input lines and write sidecar scores per product
    total = 0
    ok = 0
    rate_sleep = max(0, int(args.rate_limit_ms)) / 1000.0
    with inp.open("r", encoding="utf-8", errors="ignore") as f, out_path.open(
        "a", encoding="utf-8"
    ) as w:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                prod = json.loads(line)
            except Exception:
                continue
            try:
                llm = evaluate_product(prod, model=args.llm_model)
                rec = {
                    "productId": prod.get("productId"),
                    "name": prod.get("name"),
                    "brand": prod.get("brand"),
                    "sourceUrl": prod.get("sourceUrl"),
                    "llm": llm,
                }
                w.write(json.dumps(rec, ensure_ascii=False) + "\n")
                ok += 1
            except Exception as e:
                err = {
                    "productId": prod.get("productId"),
                    "error": str(e),
                }
                w.write(json.dumps(err, ensure_ascii=False) + "\n")
            if rate_sleep:
                time.sleep(rate_sleep)

    print(f"Scoring tamamlandı. Toplam: {total}, Başarılı: {ok}, Çıktı: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
