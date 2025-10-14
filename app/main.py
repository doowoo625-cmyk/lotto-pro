
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .schemas import PredictRequest, PredictResponse, StrategyPick, Draw
from .logic import generate_predictions
from .storage import read_last_draw, write_last_draw

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

@app.post("/api/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    last, best, all_cands = generate_predictions(req.seed, req.count)
    return PredictResponse(
        last_draw=Draw(**last),
        label="Lower score = higher probability",
        priority_sorted=[StrategyPick(**b) for b in best],
        all_candidates={k: [StrategyPick(**x) for x in v] for k,v in all_cands.items()}
    )
