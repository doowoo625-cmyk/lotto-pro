# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import requests, re
from typing import List, Dict, Any
from pathlib import Path

# ---- App ----
app = FastAPI(title="Lotto Predictor API", version="1.0.0")
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# CORS (allow all for convenience; restrict as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve /static and homepage
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---- Lotto helpers ----
HDRS = {"User-Agent": "Mozilla/5.0"}

def get_latest_round() -> int:
    # More stable approach: scrape the byWin page title containing "제xxxx회"
    url = "https://www.dhlottery.co.kr/gameResult.do?method=byWin"
    r = requests.get(url, headers=HDRS, timeout=10)
    m = re.search(r"제(\d+)회", r.text)
    if m:
        return int(m.group(1))
    # Fallback to 0
    return 0

def fetch_round_json(n: int) -> Dict[str, Any]:
    # Official JSON endpoint
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={n}"
    r = requests.get(url, headers=HDRS, timeout=10)
    j = r.json()
    if j.get("returnValue") != "success":
        raise ValueError(f"회차 {n} 데이터 없음")
    nums = [j["drwtNo1"], j["drwtNo2"], j["drwtNo3"], j["drwtNo4"], j["drwtNo5"], j["drwtNo6"]]
    bonus = j["bnusNo"]
    date = j.get("drwNoDate", "")
    return {"round": n, "date": date, "nums": nums, "bonus": bonus}

def fetch_all_rounds(start: int, end: int) -> List[Dict[str, Any]]:
    out = []
    for n in range(start, end + 1):
        try:
            out.append(fetch_round_json(n))
        except Exception:
            # skip missing rounds gracefully
            continue
    return out

# ---- API ----
@app.get("/api/latest")
def api_latest():
    latest = get_latest_round()
    return {"latest": latest}

@app.get("/api/all")
def api_all(start: int = 1, end: int | None = None):
    if end is None or end < 1:
        end = get_latest_round()
    if start < 1:
        start = 1
    if end < start:
        return JSONResponse({"rows": []})
    rows = fetch_all_rounds(start, end)
    return {"rows": rows}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def root():
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path)
