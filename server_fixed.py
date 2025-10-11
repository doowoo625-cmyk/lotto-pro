# server_fixed.py
import asyncio, time, re
from typing import Dict, Any, Optional, List
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

LOTTO_ROUND = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="

app = FastAPI(title="Lotto Pro Server (Render/EXE)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE: Dict[str, Any] = {}
TTL = 60 * 60  # 1 hour

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.dhlottery.co.kr/common.do?method=main",
    "Origin": "https://www.dhlottery.co.kr",
    "Connection": "keep-alive",
}

def cache_get(k: str):
    v = CACHE.get(k)
    if not v: return None
    if time.time() - v["ts"] > TTL:
        CACHE.pop(k, None)
        return None
    return v["val"]

def cache_set(k: str, val: Any):
    CACHE[k] = {"val": val, "ts": time.time()}

async def fetch_round_json(client: httpx.AsyncClient, rn: int):
    url = LOTTO_ROUND + str(rn)
    r = await client.get(url, headers=HEADERS, timeout=10.0)
    r.raise_for_status()
    j = r.json()
    if j.get("returnValue") != "success":
        return None
    return j

async def probe_latest(client: httpx.AsyncClient) -> int:
    n = 1024
    last_ok = 0
    for _ in range(15):
        try:
            j = await fetch_round_json(client, n)
            if j:
                last_ok = n
                n *= 2
            else:
                break
        except Exception:
            break
    if last_ok == 0:
        for a in [1536, 1400, 1200, 1100, 1000, 900, 800, 700, 600, 512, 400, 300, 256]:
            try:
                j = await fetch_round_json(client, a)
                if j:
                    last_ok = a
                    n = a * 2
                    break
            except Exception:
                pass
        if last_ok == 0:
            # Linear small scan fallback
            for a in range(1, 400):
                try:
                    j = await fetch_round_json(client, a)
                    if j: last_ok = a
                    else: break
                except Exception:
                    break
            if last_ok == 0:
                raise HTTPException(502, "Unable to determine latest draw")
    lo, hi = last_ok, n
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        try:
            j = await fetch_round_json(client, mid)
            if j: lo = mid
            else: hi = mid
        except Exception:
            hi = mid
    return lo

@app.get("/api/latest")
async def api_latest():
    key = "latest"
    c = cache_get(key)
    if c is not None:
        return {"latest": c, "cached": True}
    async with httpx.AsyncClient(verify=False) as client:
        latest = await probe_latest(client)
    cache_set(key, latest)
    return {"latest": latest, "cached": False}

@app.get("/api/round/{rn}")
async def api_round(rn: int):
    key = f"round:{rn}"
    c = cache_get(key)
    if c is not None: return c
    async with httpx.AsyncClient(verify=False) as client:
        j = await fetch_round_json(client, rn)
    if not j:
        raise HTTPException(404, f"round {rn} not found or not yet drawn")
    out = {
        "round": j["drwNo"],
        "date": j["drwNoDate"],
        "nums": [j[f"drwtNo{i}"] for i in range(1,7)],
        "bonus": j["bnusNo"]
    }
    cache_set(key, out)
    return out

@app.get("/api/all")
async def api_all(start: Optional[int] = None, end: Optional[int] = None):
    latest_resp = await api_latest()
    latest = latest_resp["latest"]
    s = 1 if start is None else max(1, int(start))
    e = latest if end is None else min(latest, int(end))
    if s > e:
        raise HTTPException(400, "invalid range")
    rows: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(verify=False, headers=HEADERS) as client:
        for rn in range(s, e+1):
            key = f"round:{rn}"
            c = cache_get(key)
            if c is not None:
                rows.append(c); continue
            try:
                j = await fetch_round_json(client, rn)
                if not j: continue
                out = {
                    "round": j["drwNo"],
                    "date": j["drwNoDate"],
                    "nums": [j[f"drwtNo{i}"] for i in range(1,7)],
                    "bonus": j["bnusNo"]
                }
                cache_set(key, out)
                rows.append(out)
            except Exception:
                pass
            if rn % 80 == 0:
                await asyncio.sleep(0.1)
    rows.sort(key=lambda x: x["round"])
    return {"latest": latest, "rows": rows}

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("static/index.html")
