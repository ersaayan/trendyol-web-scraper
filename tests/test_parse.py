from __future__ import annotations

from src.parse import parse_products


def test_parse_empty():
    assert parse_products("<html></html>", page_index=1) == []
