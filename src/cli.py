from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Optional

from .fetch import Fetcher
from .parse import parse_products
from .writer import NDJSONWriter, CSVWriter


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Trendyol 'sr' sayfalarından ürünleri çeken basit scraper",
    )
    p.add_argument("--url", required=True, help="Başlangıç sr URL'si")
    p.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Çekilecek en fazla sayfa sayısı (varsayılan 1)",
    )
    p.add_argument(
        "--delay-ms", type=int, default=800, help="İstekler arası gecikme (ms)"
    )
    p.add_argument("--out", type=str, default="products.csv", help="Çıktı dosyası")
    p.add_argument(
        "--format", choices=["csv", "ndjson"], default="csv", help="Çıktı formatı"
    )
    p.add_argument("--user-agent", type=str, default=None, help="Özel User-Agent")
    p.add_argument(
        "--proxy",
        type=str,
        default=None,
        help="HTTP proxy (örn. http://user:pass@host:port)",
    )
    return p


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)

    fetcher = Fetcher(
        user_agent=args.user_agent, proxy=args.proxy, delay_ms=args.delay_ms
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    writer = CSVWriter(out_path) if args.format == "csv" else NDJSONWriter(out_path)

    total = 0
    try:
        for page_idx, html in fetcher.iter_pages(args.url, max_pages=args.max_pages):
            products = parse_products(html, page_index=page_idx)
            if not products:
                # Boş sayfa geldiyse dur
                break
            writer.write_many(products)
            total += len(products)
    finally:
        writer.close()

    print(f"Toplam ürün yazıldı: {total} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
