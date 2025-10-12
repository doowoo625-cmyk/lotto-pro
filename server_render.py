# Final FastAPI server (fail-open + background hydrate + optimized)
import os, time, asyncio, random
from typing import Optional, List, Dict, Any
from pathlib import Path

import httpx
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

DEFAULT_HTML = """<!doctype html>
<meta charset="utf-8">
<title>서비스 준비 중</title>
<body style="font-family:sans-serif;background:#0f172a;color:#e5e7eb;margin:0;padding:24px">
  <h1>정적 파일 준비 중</h1>
  <p>리포지토리에 <code>static/index.html</code>을 커밋하면 실제 UI가 표시됩니다.</p>
</body>
"""

STATIC_DIR.mkdir(parents=True, exist_ok=True)
if not (STATIC_DIR / "index.html").exists():
    (STATIC_DIR / "index.html").write_text(DEFAULT_HTML, encoding="utf-8")

app = FastAPI(title="Lotto Predictor", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=500)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

HDRS = {"User-Agent": "Mozilla/5.0"}
BASE_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="

TTL_SEC = 1800
_round_cache: Dict[int, Dict[str, Any]] = {}
_round_ts: Dict[int, float] = {}
_latest_cache: Dict[str, Any] = {"value": None, "ts": 0}
_last_stats: Dict[str, Any] = {"ts": 0, "payload": None}

def _get_cache(n: int) -> Optional[Dict[str, Any]]:
    ts = _round_ts.get(n)
    if ts and (time.time() - ts) < TTL_SEC:
        return _round_cache.get(n)
    return None

def _set_cache(n: int, payload: Dict[str, Any]):
    _round_cache[n] = payload
    _round_ts[n] = time.time()

async def fetch_round_async(client: httpx.AsyncClient, n: int, timeout: float = 3.0) -> Optional[Dict[str, Any]]:
    cached = _get_cache(n)
    if cached is not None:
        return cached
    try:
        r = await client.get(f"{BASE_URL}{n}", headers=HDRS, timeout=timeout)
        j = r.json()
        if j.get("returnValue") != "success":
            return None
        nums = [j["drwtNo1"], j["drwtNo2"], j["drwtNo3"], j["drwtNo4"], j["drwtNo5"], j["drwtNo6"]]
        data = {"round": n, "date": j.get("drwNoDate",""), "nums": nums, "bonus": j.get("bnusNo")}
        _set_cache(n, data)
        return data
    except Exception:
        return None

async def fetch_range(start: int, end: int, batch_size: int = 25) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(http2=True) as client:
        for b in range(start, end+1, batch_size):
            e = min(end, b + batch_size - 1)
            tasks = [fetch_round_async(client, n) for n in range(b, e+1)]
            chunk = await asyncio.gather(*tasks)
            results.extend([x for x in chunk if x])
    return results

async def get_latest_round(lo: int = 1, hi: int = 1500) -> int:
    now = time.time()
    if _latest_cache["value"] and (now - _latest_cache["ts"]) < 600:
        return _latest_cache["value"]
    async with httpx.AsyncClient(http2=True) as client:
        while lo < hi:
            mid = (lo + hi + 1) // 2
            res = await fetch_round_async(client, mid)
            if res: lo = mid
            else: hi = mid - 1
    _latest_cache.update({"value": lo, "ts": now})
    return lo

def features(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        nums = r["nums"]
        s = sum(nums)
        odd = sum(1 for n in nums if n % 2 == 1)
        high = sum(1 for n in nums if n > 23)
        out.append({**r, "sum": s, "odd": odd, "even": 6 - odd, "high": high, "low": 6 - high})
    return out

def frequency(rows: List[Dict[str, Any]]) -> List[int]:
    f = [0]*46
    for r in rows:
        for n in r["nums"]:
            f[n]+=1
    return f

def tier_marks(freq: List[int]) -> Dict[str, Any]:
    counts = [freq[n] for n in range(1,46)]
    if not counts or max(counts)==0:
        return {"top1": [], "top2": [], "low": [], "values": {"top1": None, "top2": None, "low": None}}
    uniq = sorted(set(counts), reverse=True)
    top1 = uniq[0]
    top2 = uniq[1] if len(uniq) >= 2 else None
    low  = uniq[-1]
    return {
        "top1": [n for n in range(1,46) if freq[n]==top1],
        "top2": [n for n in range(1,46) if (top2 is not None and freq[n]==top2)],
        "low":  [n for n in range(1,46) if freq[n]==low],
        "values": {"top1": top1, "top2": top2, "low": low}
    }

def build_payload(rows: List[Dict[str, Any]]):
    feats = features(rows)
    freq = frequency(feats)
    tiers = tier_marks(freq)
    latest = max((r["round"] for r in rows), default=0)
    return {"latest": latest, "count": len(rows), "freq": freq, "tiers": tiers, "recent10": feats[-10:][::-1]}

def fallback_demo():
    rnd = random.Random(42)
    rows=[]
    base_round=1200
    for i in range(30):
        nums = sorted(rnd.sample(range(1,46), 6))
        rows.append({"round": base_round-i, "date": f"2024-01-{(i%28)+1:02d}", "nums": nums, "bonus": rnd.randint(1,45)})
    return build_payload(rows)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/latest")
async def api_latest():
    latest = await get_latest_round()
    return JSONResponse({"latest": latest}, headers={"Cache-Control": "public, max-age=300"})

@app.get("/api/all")
async def api_all(start: int = 1, end: Optional[int] = None):
    try:
        if not end or end < 1:
            end = await get_latest_round()
        start = max(1, start)
        rows = await fetch_range(start, end)
        return JSONResponse({"rows": rows}, headers={"Cache-Control": "public, max-age=120"})
    except Exception as e:
        return JSONResponse({"error":"upstream_error","detail":str(e)}, status_code=502)

@app.get("/api/stats")
async def api_stats(last: int = Query(50, ge=5, le=2000), background_tasks: BackgroundTasks = None):
    now = time.time()
    if _last_stats["payload"] and (now - _last_stats["ts"]) < 300:
        return JSONResponse(_last_stats["payload"], headers={"Cache-Control": "public, max-age=60"})
    try:
        latest = await get_latest_round()
        start = max(1, latest - (last - 1))
        rows = []
        try:
            rows = await asyncio.wait_for(fetch_range(start, latest, batch_size=25), timeout=2.0)
        except asyncio.TimeoutError:
            rows = []
        if rows:
            payload = build_payload(rows)
            _last_stats.update({"ts": now, "payload": payload})
            if background_tasks:
                background_tasks.add_task(hydrate_background, latest)
            return JSONResponse(payload, headers={"Cache-Control": "public, max-age=60"})
        else:
            payload = fallback_demo()
            _last_stats.update({"ts": now, "payload": payload})
            if background_tasks:
                background_tasks.add_task(hydrate_background, latest or 1200)
            return JSONResponse(payload, headers={"Cache-Control": "no-store"})
    except Exception:
        payload = fallback_demo()
        _last_stats.update({"ts": now, "payload": payload})
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})

async def hydrate_background(latest: int):
    try:
        start = max(1, latest - 199)
        rows = await fetch_range(start, latest, batch_size=25)
        if rows:
            payload = build_payload(rows)
            _last_stats.update({"ts": time.time(), "payload": payload})
    except Exception:
        pass

@app.get("/")
def root():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return HTMLResponse(DEFAULT_HTML)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server_render:app", host="0.0.0.0", port=port)
