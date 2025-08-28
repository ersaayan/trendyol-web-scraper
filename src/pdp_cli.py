from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterable, List, Optional

from .fetch import Fetcher
from .parse_pdp import parse_pdp


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Trendyol PDP scraper: URL listesi alır, her bir ürün sayfasını parse eder."
    )
    p.add_argument("--urls", nargs="+", help="Ürün sayfası URL(ler)i", required=True)
    p.add_argument("--out", type=str, default="pdp.ndjson", help="Çıktı NDJSON dosyası")
    p.add_argument(
        "--delay-ms", type=int, default=800, help="İstekler arası gecikme (ms)"
    )
    p.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
    )
    return p


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("trendyol.pdp")

    fetcher = Fetcher(delay_ms=args.delay_ms)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out_path.open("a", encoding="utf-8") as f:
        for url in args.urls:
            try:
                html = fetcher.get_page(url)
                data = parse_pdp(html)
                data["sourceUrl"] = url
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
                written += 1
                log.info("Yazıldı: %s", url)
            except Exception as e:
                log.exception("Hata: %s", url)
    log.info("Bitti. Toplam yazılan: %d", written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
