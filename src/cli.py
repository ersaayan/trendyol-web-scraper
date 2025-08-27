from __future__ import annotations

import argparse
import logging
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Optional

from .fetch import Fetcher
from .parse import parse_products
from .writer import NDJSONWriter, CSVWriter
from .state import load_checkpoint, save_checkpoint, read_seen_ids_from_output


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
        "--log-level",
        type=str,
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Log seviyesi (varsayılan INFO)",
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
    p.add_argument(
        "--checkpoint",
        type=str,
        default=".checkpoints/scrape.json",
        help="Checkpoint dosya yolu (devre dışı bırakmak için boş bırak)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Checkpoint varsa kaldığı yerden devam et",
    )
    p.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Toplam yazılacak maksimum ürün sayısı (opsiyonel)",
    )
    return p


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)

    # Logging setup
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("trendyol.scraper")

    fetcher = Fetcher(
        user_agent=args.user_agent, proxy=args.proxy, delay_ms=args.delay_ms
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    writer = CSVWriter(out_path) if args.format == "csv" else NDJSONWriter(out_path)

    # Deduplication: previously written productIds
    seen_ids = read_seen_ids_from_output(out_path, args.format)
    if seen_ids:
        log.info("Önceden yazılmış ürün sayısı (seen set): %d", len(seen_ids))

    # Checkpoint
    start_page = 1
    last_written = 0
    if args.resume and args.checkpoint:
        cp = load_checkpoint(Path(args.checkpoint))
        if cp and cp.get("url") == args.url:
            start_page = int(cp.get("nextPage", start_page))
            last_written = int(cp.get("written", 0))
            log.info(
                "Checkpoint yüklendi: nextPage=%s, written=%s", start_page, last_written
            )

    log.info(
        "Başlıyor: url=%s, out=%s, format=%s, start_page=%d, max_pages=%d, delay_ms=%d",
        args.url,
        out_path,
        args.format,
        start_page,
        args.max_pages,
        args.delay_ms,
    )

    total = 0
    try:
        for page_idx, html in fetcher.iter_pages(
            args.url, max_pages=args.max_pages, start_page=start_page
        ):
            products = parse_products(html, page_index=page_idx)
            log.info("Sayfa %d: %d ürün bulundu", page_idx, len(products))
            if not products:
                log.info("Boş sayfa geldi, durduruluyor")
                break
            # dedupe
            to_write = []
            for p in products:
                pid = p.get("productId")
                if isinstance(pid, int) and pid in seen_ids:
                    continue
                to_write.append(p)
                if isinstance(pid, int):
                    seen_ids.add(pid)

            if not to_write:
                log.info("Sayfa %d: yazılacak yeni ürün yok (tamamı duplike)", page_idx)
                continue

            writer.write_many(to_write)
            total += len(to_write)
            last_written += len(to_write)
            log.info("Sayfa %d: yazıldı=%d, toplam=%d", page_idx, len(to_write), total)

            # max-items sınırı
            if args.max_items is not None and total >= args.max_items:
                log.info("Max items sınırına ulaşıldı: %d", args.max_items)
                break

            # checkpoint kaydet
            if args.checkpoint:
                save_checkpoint(
                    Path(args.checkpoint),
                    {
                        "url": args.url,
                        "nextPage": page_idx + 1,
                        "written": last_written,
                        "out": str(out_path),
                        "format": args.format,
                    },
                )
                log.debug("Checkpoint güncellendi: nextPage=%d", page_idx + 1)
    finally:
        writer.close()

    log.info("Bitti: toplam yazılan=%d, dosya=%s", total, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
