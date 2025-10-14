
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LAST_DRAW_PATH = DATA_DIR / "last_draw.json"
RECENT10_PATH = DATA_DIR / "recent10.json"

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

def read_recent10() -> List[Dict[str, Any]]:
    if RECENT10_PATH.exists():
        try:
            with open(RECENT10_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and all(isinstance(x.get("numbers"), list) and len(x["numbers"])==6 for x in data):
                    return data[-10:] if len(data)>0 else []
        except Exception:
            pass
    last = read_last_draw()
    seed = [{"draw_no": last["draw_no"], "numbers": last["numbers"], "bonus": last["bonus"]}]
    with open(RECENT10_PATH, "w", encoding="utf-8") as f:
        json.dump(seed, f, ensure_ascii=False, indent=2)
    return seed

def write_recent10(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    clean: List[Dict[str, Any]] = []
    for it in items:
        nums = sorted({int(x) for x in it.get("numbers", []) if 1 <= int(x) <= 45})
        if len(nums) != 6:
            raise ValueError("Each draw must have exactly 6 unique numbers 1..45")
        clean.append({
            "draw_no": int(it.get("draw_no", 0)),
            "numbers": nums,
            "bonus": int(it.get("bonus", 0)) if 1 <= int(it.get("bonus", 0)) <= 45 else 0,
        })
    with open(RECENT10_PATH, "w", encoding="utf-8") as f:
        json.dump(clean[-10:], f, ensure_ascii=False, indent=2)
    return clean[-10:]
