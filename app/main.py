
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import Optional
from .schemas import PredictRequest, PredictResponse, StrategyPick, Draw
from .logic import compute_all, range_freq
from .storage import read_last_draw, write_last_draw, read_recent, write_recent

app = FastAPI(title="Lotto Prediction System v3.1-final", version="3.1-final")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")

@app.get("/api/health")
def health():
    return {"ok": True, "version": "3.1-final"}

@app.get("/api/last_draw", response_model=Draw)
def get_last_draw():
    return Draw(**read_last_draw())

@app.post("/api/last_draw", response_model=Draw)
def set_last_draw(payload: Draw):
    try:
        out = write_last_draw(payload.dict())
        return Draw(**out)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/recent")
def get_recent():
    return {"items": read_recent()}

@app.post("/api/recent")
def set_recent(items: list[dict]):
    try:
        out = write_recent(items)
        return {"items": out}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/range_freq")
def get_range_freq(window: Optional[int] = 10):
    if window is None or window <= 0:
        window = 10
    per, top2, bottom = range_freq(window)
    return {"per": per, "top2": top2, "bottom": bottom}

@app.post("/api/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    data = compute_all(req.seed, req.count, window=10)
    return PredictResponse(
        last_draw=Draw(**data["last"]),
        best_strategy_key=data["best_key"],
        best_strategy_name_ko=data["best_name_ko"],
        best_strategy_top5=[StrategyPick(**x) for x in data["best_top5"]],
        best3_by_priority_korean=[StrategyPick(**x) for x in data["best3"]],
        all_by_strategy_korean={k: [StrategyPick(**x) for x in v] for k, v in data["all_korean"].items()},
    )
