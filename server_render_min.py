# Minimal FastAPI server for Render (no BeautifulSoup/pandas)
import os
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests

app = FastAPI(title="Lotto Predictor (Render-Min)", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HDRS = {"User-Agent": "Mozilla/5.0"}

# Static
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

def get_latest_round():
    # Official JSON endpoint is stable and lightweight
    try:
        # Probe by requesting a large round until it fails would be heavier; instead, binary search is unnecessary.
        # We'll back off by incrementing from a known lower bound using HEAD request would still be N calls.
        # Simpler: hit webpage title requires bs4. So instead we step down from a high guess at most a few times.
        # But better: call byWin (HTML) avoided. We'll incrementally try the JSON; API returns returnValue=fail for out-of-range.
        # Start from a safe high guess (e.g., 1200) and step down. Keep it bounded to 30 tries.
        guess = 1200
        for _ in range(30):
            r = requests.get(f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={guess}", headers=HDRS, timeout=8)
            j = r.json()
            if j.get("returnValue") == "success":
                # Move up until it fails to find the latest
                lo = guess
                hi = guess + 200
                # binary search latest
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    r2 = requests.get(f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={mid}", headers=HDRS, timeout=8)
                    if r2.ok and r2.json().get("returnValue") == "success":
                        lo = mid
                    else:
                        hi = mid - 1
                return lo
            else:
                guess -= 20
        return 0
    except Exception:
        return 0

def fetch_round_json(n: int):
    r = requests.get(f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={n}", headers=HDRS, timeout=10)
    j = r.json()
    if j.get("returnValue") != "success":
        raise ValueError("no data")
    nums = [j["drwtNo1"], j["drwtNo2"], j["drwtNo3"], j["drwtNo4"], j["drwtNo5"], j["drwtNo6"]]
    return {"round": n, "date": j.get("drwNoDate",""), "nums": nums, "bonus": j.get("bnusNo")}

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
        try:
            rows.append(fetch_round_json(n))
        except Exception:
            continue
    return {"rows": rows}

@app.get("/")
def root():
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"ok": True, "tip": "upload static/index.html"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server_render_min:app", host="0.0.0.0", port=port)
