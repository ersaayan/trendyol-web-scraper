from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Generator, Optional, Tuple
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


DEFAULT_UAS = [
    # A few desktop UA strings; can be extended
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


@dataclass
class Fetcher:
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    delay_ms: int = 800

    def _headers(self) -> dict:
        ua = self.user_agent or random.choice(DEFAULT_UAS)
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.trendyol.com/",
        }

    def _next_url(self, url: str, page: int) -> str:
        """Ensure &pi=page in query string."""
        u = urlparse(url)
        q = parse_qs(u.query)
        q["pi"] = [str(page)]
        new_q = urlencode({k: v[0] if isinstance(v, list) else v for k, v in q.items()})
        return urlunparse((u.scheme, u.netloc, u.path, u.params, new_q, u.fragment))

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.8, min=1, max=8),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _get(self, client: httpx.Client, url: str) -> httpx.Response:
        r = client.get(url, headers=self._headers(), timeout=20.0)
        r.raise_for_status()
        return r

    def iter_pages(
        self, url: str, max_pages: int = 1, start_page: int = 1
    ) -> Generator[Tuple[int, str], None, None]:
        proxies = (
            {"http://": self.proxy, "https://": self.proxy} if self.proxy else None
        )
        # Use HTTP/1.1 for simplicity; avoids requiring h2 dependency
        with httpx.Client(
            http2=False, follow_redirects=True, proxies=proxies
        ) as client:
            for pi in range(start_page, start_page + max_pages):
                u = self._next_url(url, pi)
                resp = self._get(client, u)
                yield pi, resp.text
                # polite delay
                time.sleep(max(0, self.delay_ms) / 1000.0)
