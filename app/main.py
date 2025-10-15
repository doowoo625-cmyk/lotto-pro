
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional
from .schemas import PredictRequest, PredictResponse, StrategyPick, Draw
from .logic import compute_all, range_freq_from_draws
from .storage import read_last_draw, write_last_draw, read_recent, write_recent
from .fetcher import fetch_draw, fetch_recent

app = FastAPI(title="Lotto Prediction System v3.1-final", version="3.1-final-clean")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {"ok": True, "version": "3.1-final-clean"}

@app.get("/api/dhlottery/draw", response_model=Draw)
async def api_draw(no: int):
    try:
        data = await fetch_draw(no)
        return Draw(**data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"동행복권 조회 실패: {e}")

@app.get("/api/dhlottery/recent")
async def api_recent(end_no: int, n: int = 10):
    try:
        items = await fetch_recent(end_no, n)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"동행복권 최근회차 조회 실패: {e}")

@app.post("/api/sync_recent")
async def api_sync(end_no: int, n: int = 10):
    items = await fetch_recent(end_no, n)
    write_recent(items)
    return {"ok": True, "count": len(items)}

@app.post("/api/predict", response_model=PredictResponse)
async def predict(req: PredictRequest, end_no: Optional[int] = None, n: int = 10):
    if end_no:
        items = await fetch_recent(end_no, n)
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
    items = await fetch_recent(end_no, n)
    per, top2, bottom = range_freq_from_draws(items)
    return {"per": per, "top2": top2, "bottom": bottom, "end_no": end_no, "n": n}
