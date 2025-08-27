from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Optional, Set


def load_checkpoint(path: Path) -> Optional[Dict]:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_checkpoint(path: Path, data: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_seen_ids_from_output(path: Path, fmt: str) -> Set[int]:
    seen: Set[int] = set()
    if not path.exists():
        return seen
    try:
        if fmt == "ndjson":
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        obj = json.loads(line)
                        pid = obj.get("productId")
                        if isinstance(pid, int):
                            seen.add(pid)
                    except Exception:
                        continue
        else:  # csv
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pid = row.get("productId")
                    try:
                        if pid is not None and str(pid).strip() != "":
                            seen.add(int(str(pid)))
                    except Exception:
                        continue
    except Exception:
        # Best-effort
        pass
    return seen
