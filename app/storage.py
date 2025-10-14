
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LAST_DRAW_PATH = DATA_DIR / "last_draw.json"

DEFAULT_LAST_DRAW = {"draw_no": 0, "numbers": [1,2,3,4,5,6], "bonus": 7}

def read_last_draw() -> Dict[str, Any]:
    if LAST_DRAW_PATH.exists():
        try:
            with open(LAST_DRAW_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
                if isinstance(payload.get("numbers"), list) and len(payload["numbers"])==6:
                    return payload
        except Exception:
            pass
    write_last_draw(DEFAULT_LAST_DRAW)
    return DEFAULT_LAST_DRAW

def write_last_draw(payload: Dict[str, Any]) -> Dict[str, Any]:
    nums = sorted({int(x) for x in payload.get("numbers", []) if 1 <= int(x) <= 45})
    if len(nums) != 6:
        raise ValueError("numbers must be 6 unique integers between 1 and 45")
    out = {
        "draw_no": int(payload.get("draw_no", 0)),
        "numbers": nums,
        "bonus": int(payload.get("bonus", 0)) if 1 <= int(payload.get("bonus", 0)) <= 45 else 0,
    }
    with open(LAST_DRAW_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out
