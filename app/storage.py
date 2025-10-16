from __future__ import annotations
from pathlib import Path
import json
from typing import List, Dict, Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RECENT_PATH = DATA_DIR / "recent.json"
LAST_PATH = DATA_DIR / "last.json"

# 즉시 응답용 기본 스냅샷(없으면 이걸로 화면을 채움; 원하면 네 최신 10회로 바꿔두면 됨)
DEFAULT_RECENT: List[Dict[str, Any]] = [
    {"draw_no": 1184, "numbers":[2,5,12,19,28,41], "bonus":8,  "date":"2024-08-10"},
    {"draw_no": 1185, "numbers":[1,3,9,15,34,45],  "bonus":23, "date":"2024-08-17"},
    {"draw_no": 1186, "numbers":[4,6,7,21,36,39],  "bonus":12, "date":"2024-08-24"},
    {"draw_no": 1187, "numbers":[10,11,14,16,24,42],"bonus":31,"date":"2024-08-31"},
    {"draw_no": 1188, "numbers":[2,13,18,26,33,41], "bonus":27,"date":"2024-09-07"},
    {"draw_no": 1189, "numbers":[5,7,8,25,29,40],   "bonus":2,  "date":"2024-09-14"},
    {"draw_no": 1190, "numbers":[3,6,12,15,23,39],  "bonus":17, "date":"2024-09-21"},
    {"draw_no": 1191, "numbers":[1,4,14,16,38,41],  "bonus":20, "date":"2024-09-28"},
    {"draw_no": 1192, "numbers":[1,2,3,4,6,7],      "bonus":9,  "date":"2024-10-05"},
    {"draw_no": 1193, "numbers":[1,2,5,9,15,34],    "bonus":23, "date":"2024-10-12"},
]

def _safe_read(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def read_recent() -> List[Dict[str, Any]]:
    data = _safe_read(RECENT_PATH, DEFAULT_RECENT)
    data = sorted(data, key=lambda x: int(x.get("draw_no", 0)))
    for it in data:
        it["numbers"] = sorted([int(n) for n in it.get("numbers", [])])
        it["bonus"] = int(it.get("bonus", 0))
        it["draw_no"] = int(it.get("draw_no", 0))
    return data

def write_recent(items: List[Dict[str, Any]]):
    try:
        RECENT_PATH.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

def read_last_draw() -> Dict[str, Any]:
    items = read_recent()
    return items[-1] if items else DEFAULT_RECENT[-1]

def write_last_draw(item: Dict[str, Any]):
    try:
        LAST_PATH.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
