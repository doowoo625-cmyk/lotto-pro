# Render-ready FastAPI server
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests

app = FastAPI(title="Lotto Predictor", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HDRS = {"User-Agent": "Mozilla/5.0"}

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def fetch_round_json(n: int):
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={n}"
    r = requests.get(url, headers=HDRS, timeout=10)
    j = r.json()
    if j.get("returnValue") != "success":
        return None
    nums = [j["drwtNo1"], j["drwtNo2"], j["drwtNo3"], j["drwtNo4"], j["drwtNo5"], j["drwtNo6"]]
    return {"round": n, "date": j.get("drwNoDate",""), "nums": nums, "bonus": j.get("bnusNo")}

def get_latest_round():
    lo, hi = 1, 1500
    while lo < hi:
        mid = (lo + hi + 1) // 2
        j = fetch_round_json(mid)
        if j: lo = mid
        else: hi = mid - 1
    return lo

@app.get("/api/latest")
def api_latest():
    return {"latest": get_latest_round()}

@app.get("/api/all")
def api_all(start: int = 1, end: int | None = None):
    if end is None or end < 1:
        end = get_latest_round()
    if start < 1:
        start = 1
    rows = []
    for n in range(start, end+1):
        j = fetch_round_json(n)
        if j: rows.append(j)
    return {"rows": rows}

@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server_render:app", host="0.0.0.0", port=port)
