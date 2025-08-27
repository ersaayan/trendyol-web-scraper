from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterable, List, Any


class BaseWriter:
    def write_many(self, rows: Iterable[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class CSVWriter(BaseWriter):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.file = self.path.open("w", newline="", encoding="utf-8")
        self.writer = None
        self.fieldnames: List[str] = []

    def write_many(self, rows: Iterable[Dict[str, Any]]) -> None:
        rows = list(rows)
        if not rows:
            return
        if not self.writer:
            self.fieldnames = list(rows[0].keys())
            self.writer = csv.DictWriter(self.file, fieldnames=self.fieldnames)
            self.writer.writeheader()
        for r in rows:
            self.writer.writerow({k: ("" if v is None else v) for k, v in r.items()})

    def close(self) -> None:
        try:
            if self.file:
                self.file.close()
        except Exception:
            pass


class NDJSONWriter(BaseWriter):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.file = self.path.open("w", encoding="utf-8")

    def write_many(self, rows: Iterable[Dict[str, Any]]) -> None:
        for r in rows:
            self.file.write(json.dumps(r, ensure_ascii=False) + "\n")

    def close(self) -> None:
        try:
            if self.file:
                self.file.close()
        except Exception:
            pass
