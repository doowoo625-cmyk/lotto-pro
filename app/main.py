# app/main.py
from __future__ import annotations
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional, List, Dict, Any
from .schemas import PredictRequest, PredictResponse, StrategyPick, Draw
from .logic import compute_all, range_freq_from_draws
from .storage import read_last_draw, write_last_draw, read_recent, write_recent
from .fetcher import fetch_draw, fetch_recent, latest_draw_no

# 🔧 라이브 조회 토글 (기본 OFF)
LIVE_FETCH = os.getenv("LIVE_FETCH","0") == "1"

app = FastAPI(title="Lotto Prediction System v3.1-final", version="3.1-final-clean")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {"ok": True, "version": "3.1-final-clean", "live_fetch": LIVE_FETCH}

@app.get("/api/latest")
async def api_latest():
    # 라이브가 꺼져 있거나 실패하면 로컬 캐시 사용
    if not LIVE_FETCH:
        items = read_recent()
        last = items[-1] if items else read_last_draw()
        return last
    try:
        no = await latest_draw_no(9999)
        data = await fetch_draw(no)
        return data
    except Exception:
        items = read_recent()
        last = items[-1] if items else read_last_draw()
        return last

@app.get("/api/dhlottery/draw", response_model=Draw)
async def api_draw(no: int):
    if not LIVE_FETCH:
        items = read_recent()
        for it in items:
            if it.get("draw_no")==no:
                return Draw(**it)
        return Draw(**(items[-1] if items else read_last_draw()))
    try:
        data = await fetch_draw(no)
        return Draw(**data)
    except Exception:
        items = read_recent()
        return Draw(**(items[-1] if items else read_last_draw()))

@app.get("/api/dhlottery/recent")
async def api_recent(end_no: int, n: int = 10):
    if not LIVE_FETCH:
        items = read_recent()
        return {"items": items[-n:]}
    try:
        items = await fetch_recent(end_no, n)
        return {"items": items}
    except Exception:
        items = read_recent()
        return {"items": items[-n:]}

@app.post("/api/predict", response_model=PredictResponse)
async def predict(req: PredictRequest, end_no: Optional[int] = None, n: int = 10):
    # 라이브 실패/비활성 시 즉시 로컬로 처리
    items: List[Dict[str, Any]] = []
    if LIVE_FETCH:
        try:
            if end_no:
                items = await fetch_recent(end_no, n)
            else:
                latest = await latest_draw_no(9999)
                items = await fetch_recent(latest, n)
        except Exception:
            items = read_recent()
    else:
        items = read_recent()

    data = compute_all(req.seed, items, req.count, window=n)
    last = items[-1] if items else read_last_draw()
    return PredictResponse(
        last_draw=Draw(**last),
        best_strategy_key=data["best_key"],
        best_strategy_name_ko=data["best_name_ko"],
        best_strategy_top5=[StrategyPick(**x) for x in data["best_top5"]],
        best3_by_priority_korean=[StrategyPick(**x) for x in data["best3"]],
        all_by_strategy_korean={k: [StrategyPick(**x) for x in v] for k, v in data["all_korean"].items()},
    )

@app.get("/api/range_freq_by_end")
async def api_range_freq(end_no: int, n: int = 10):
    if LIVE_FETCH:
        try:
            items = await fetch_recent(end_no, n)
            per, top2, bottom = range_freq_from_draws(items)
            return {"per": per, "top2": top2, "bottom": bottom, "end_no": end_no, "n": n}
        except Exception:
            pass
    items = read_recent()[-n:]
    per, top2, bottom = range_freq_from_draws(items)
    return {"per": per, "top2": top2, "bottom": bottom, "end_no": end_no, "n": n}
