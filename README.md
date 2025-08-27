# Trendyol Category Scraper

A lightweight Python CLI to scrape all products from a Trendyol search/category listing (sr pages), with paging and CSV/NDJSON outputs.

Features
- HTML scraping via httpx + selectolax (fast, resilient)
- Paging with &pi=... detection
- Backoff/retries for transient errors
- CSV and NDJSON export
- Simple tests and example config

Quickstart
1) Create venv and install deps
2) Run a small scrape (1-2 pages)

Usage
- CLI entry: python -m src.cli --url "https://www.trendyol.com/sr?wc=998&sst=BEST_SELLER&os=1" --max-pages 2 --out products.csv --format csv

Notes
- Respect site ToS. Use low request rates and retry/backoff.
- If HTML blocks, we can add Playwright fallback.
