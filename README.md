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
- Built-in analysis CLI for profitability and price ladders
- Optional LLM-powered insights (OpenAI) on analysis summary


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

### Analysis CLI

Generate profitability summary and price recommendations:

```bash
python -m src.analyze \
  --in output.ndjson \
  --format ndjson \
  --commission 12 \
  --default-cost 80 \
  --tiers '[{"up_to":150,"fee":42.7},{"up_to":300,"fee":72.2}]' \
  --margins 5,10,15 \
  --out-dir analysis
```

Enable LLM insights (requires environment variable OPENAI_API_KEY):

```bash
export OPENAI_API_KEY=sk-...   # set your key
python -m src.analyze --in output.ndjson --format ndjson --commission 12 --default-cost 80 --use-llm --llm-model gpt-4o-mini
```

Outputs: `analysis/analysis-YYYYMMDD-HHMMSS.json` and `.md`. JSON includes an optional `llm` block.


### Product Page (PDP) Scraper

Scrape one or more product detail pages and write a line-delimited JSON file:

```bash
python -m src.pdp_cli \
  --out pdp.ndjson \
  --delay-ms 800 \
  "https://www.trendyol.com/yatas/eco-touch-sivi-gecirmez-alez-p-214070920?boutiqueId=61&merchantId=106771"
```

Each line contains fields like: `productId, productCode, name, brand, price, rating, ratingCount, favoriteCount, categoryPath[], seller, sellerId, variants[], images[], badges[]`.


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
- Web UI: `uvicorn src.server:app --reload` then open <http://127.0.0.1:8000>. Start scrapes and analyses from the dashboard. Recent analyses are browsable and JSON entries can open an LLM summary modal.

### API additions

- Start PDP scrape job:
  - POST `/api/pdp`
  - Body: `{ "urls": ["https://..."], "out": "pdp.ndjson", "delay_ms": 800, "log_level": "INFO" }`
  - Response: `{ job_id, pid }`

### Environment

- `OPENAI_API_KEY`: required if using `--use-llm`
- `OPENAI_MODEL` (optional): default model if not passed via `--llm-model`
