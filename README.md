# Trendyol Category Scraper

Small, fast CLI to scrape products from Trendyol search/category listings (`/sr?...`). Supports paging, dedupe, checkpoint/resume, and CSV/NDJSON outputs.


## Features

- HTML-first scraping using httpx + selectolax (fast and lightweight)
- Paging via `&pi=` parameter
- Retries with backoff for transient errors
- Output: CSV or NDJSON
- Deduplication by productId (also reads existing output to avoid duplicates)
- Checkpoint + resume support across runs
- Basic logging with configurable level
- Optional proxy and custom User-Agent


## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```


## Usage

Basic (2 pages to CSV):

```bash
python -m src.cli \
  --url "https://www.trendyol.com/sr?wc=998&sst=BEST_SELLER&os=1" \
  --max-pages 2 \
  --out products.csv \
  --format csv
```

Resume with checkpoint and write to NDJSON:

```bash
python -m src.cli \
  --url "https://www.trendyol.com/sr?wc=998&sst=BEST_SELLER&os=1" \
  --max-pages 50 \
  --out output.ndjson \
  --format ndjson \
  --checkpoint .checkpoints/run.json \
  --resume \
  --log-level INFO
```

Limit to N new items (stops early once written N unique):

```bash
python -m src.cli \
  --url "https://www.trendyol.com/sr?wc=998&sst=BEST_SELLER&os=1" \
  --max-pages 100 \
  --out output.ndjson \
  --format ndjson \
  --checkpoint .checkpoints/run.json \
  --resume \
  --max-items 150
```

CSV output example:

```bash
python -m src.cli --url "https://www.trendyol.com/sr?wc=998&sst=BEST_SELLER&os=1" --max-pages 3 --out products.csv --format csv
```

Debug logs:

```bash
python -m src.cli ... --log-level DEBUG
```


## Options (excerpt)

- `--url` (required): Trendyol listing URL (e.g. `https://www.trendyol.com/sr?...`).
- `--max-pages`: Max pages to fetch this run.
- `--delay-ms`: Delay between requests in milliseconds (default ~800).
- `--out`: Output file path.
- `--format`: `csv` or `ndjson`.
- `--user-agent`: Override User-Agent header.
- `--proxy`: HTTP/HTTPS proxy (e.g., `http://user:pass@host:port`).
- `--checkpoint`: Path to checkpoint file (JSON) to save progress.
- `--resume`: Resume from the given checkpoint file if exists.
- `--max-items`: Stop after writing this many new unique items in the current run.
- `--log-level`: Logging level (`ERROR`, `WARN`, `INFO`, `DEBUG`).


## Notes

- Respect the website Terms of Service. Keep request rates modest.
- If HTML changes or blocking appears, consider increasing delays or using a proxy.
- Parser selectors are in `src/parse.py`. Update there if Trendyol changes markup.


## Development

- Tests: `pytest -q`
- Code: main entry is `src/cli.py`; HTTP in `src/fetch.py`; parser in `src/parse.py`.
