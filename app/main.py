from __future__ import annotations
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, List, Dict, Any
from .schemas import PredictRequest, PredictResponse, StrategyPick, Draw
from .logic import compute_all, range_freq_from_draws
from .storage import read_last_draw, write_last_draw, read_recent, write_recent
from .fetcher import fetch_draw, fetch_recent, latest_draw_no

app = FastAPI(title="Lotto v3.1-final SWR", version="3.1-SWR")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

# ---- SWR helpers (항상 즉시 응답, 최신화는 뒤에서) ----
async def _refresh_recent(end_no: int, n: int = 10):
    try:
        items = await fetch_recent(end_no, n)
        if items:
            write_recent(items)
            write_last_draw(items[-1])
    except Exception:
        pass

async def _refresh_latest():
    try:
        no = await latest_draw_no(9999)
        data = await fetch_draw(no)
        items = read_recent()
        if not items or items[-1]["draw_no"] < data["draw_no"]:
            last10 = (items + [data])[-10:] if items else [data]
            write_recent(last10)
            write_last_draw(last10[-1])
    except Exception:
        pass

@app.on_event("startup")
async def startup():
    asyncio.create_task(_refresh_latest())

@app.get("/api/latest")
async def api_latest():
    last = read_last_draw()                 # 1) 즉시 캐시 리턴
    asyncio.create_task(_refresh_latest())  # 2) 뒤에서 최신화
    return last

@app.get("/api/dhlottery/recent")
async def api_recent(end_no: Optional[int] = None, n: int = 10):
    items = read_recent()
    if end_no and items and end_no >= items[-1]["draw_no"]:
        view = items[-n:]
    elif end_no:
        view = [x for x in items if x["draw_no"] <= end_no][-n:]
    else:
        view = items[-n:]
    if end_no:
        asyncio.create_task(_refresh_recent(end_no, n))
    else:
        last_no = items[-1]["draw_no"] if items else 1
        asyncio.create_task(_refresh_recent(last_no, n))
    return {"items": view}

@app.get("/api/range_freq_by_end")
async def api_range_freq(end_no: Optional[int] = None, n: int = 10):
    items_all = read_recent()
    base_end = end_no or (items_all[-1]["draw_no"] if items_all else 1)
    window = [x for x in items_all if x["draw_no"] <= base_end][-n:]
    per, top2, bottom = range_freq_from_draws(window)
    asyncio.create_task(_refresh_recent(base_end, n))
    return {"per": per, "top2": top2, "bottom": bottom, "end_no": base_end, "n": n}

@app.post("/api/predict", response_model=PredictResponse)
async def predict(req: PredictRequest, end_no: Optional[int] = None, n: int = 10):
    items = read_recent()
    base_end = end_no or (items[-1]["draw_no"] if items else 1)
    window = [x for x in items if x["draw_no"] <= base_end][-n:]
    data = compute_all(req.seed, window, req.count, window=n)
    last = window[-1] if window else read_last_draw()
    asyncio.create_task(_refresh_recent(base_end, n))
    return PredictResponse(
        last_draw=Draw(**last),
        best_strategy_key=data["best_key"],
        best_strategy_name_ko=data["best_name_ko"],
        best_strategy_top5=[StrategyPick(**x) for x in data["best_top5"]],
        best3_by_priority_korean=[StrategyPick(**x) for x in data["best3"]],
        all_by_strategy_korean={k: [StrategyPick(**x) for x in v] for k, v in data["all_korean"].items()},
    )
