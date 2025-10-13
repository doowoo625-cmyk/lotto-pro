# server_render.py — Render Rescue (boot-safe, fail-open, diag)
import os, time, asyncio, random, logging, socket, sys
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
<meta charset=\"utf-8\">
<title>로또 예측(Rescue)</title>
<body style=\"font-family:sans-serif;background:#0f172a;color:#e5e7eb;margin:0;padding:24px\">
  <h1>정적 파일 준비 중</h1>
  <p><code>static/index.html</code>이 없어서 대체 화면을 보여줍니다.</p>
</body>
"""

STATIC_DIR.mkdir(parents=True, exist_ok=True)
if not (STATIC_DIR / "index.html").exists():
    (STATIC_DIR / "index.html").write_text(DEFAULT_HTML, encoding="utf-8")

app = FastAPI(title="Lotto Predictor (Rescue)", version="2.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=500)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

HDRS = {"User-Agent": "Mozilla/5.0"}
BASE_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="

TTL_SEC = 1800
_round_cache: Dict[int, Dict[str, Any]] = {}
_round_ts: Dict[int, float] = {}
_latest_cache: Dict[str, Any] = {"value": None, "ts": 0}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lotto")

def _get_cache(n: int) -> Optional[Dict[str, Any]]:
    ts = _round_ts.get(n)
    if ts and (time.time() - ts) < TTL_SEC:
        return _round_cache.get(n)
    return None

def _set_cache(n: int, payload: Dict[str, Any]):
    _round_cache[n] = payload
    _round_ts[n] = time.time()

async def fetch_round_async(client: httpx.AsyncClient, n: int, timeout: float = 1.5) -> Optional[Dict[str, Any]]:
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
    except Exception as e:
        log.warning(f"fetch_round_async({n}) failed: {e}")
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
    try:
        async with httpx.AsyncClient(http2=True) as client:
            while lo < hi:
                mid = (lo + hi + 1) // 2
                res = await fetch_round_async(client, mid)
                if res: lo = mid
                else: hi = mid - 1
        _latest_cache.update({\"value\": lo, \"ts\": now})
        return lo
    except Exception as e:
        log.warning(f"get_latest_round fallback: {e}")
        return _latest_cache[\"value\"] or 1200

def features(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        nums = r[\"nums\"]
        s = sum(nums)
        odd = sum(1 for n in nums if n % 2 == 1)
        high = sum(1 for n in nums if n > 23)
        out.append({**r, \"sum\": s, \"odd\": odd, \"even\": 6 - odd, \"high\": high, \"low\": 6 - high})
    return out

def frequency(rows: List[Dict[str, Any]]) -> List[int]:
    f = [0]*46
    for r in rows:
        for n in r[\"nums\"]:
            f[n]+=1
    return f

def build_payload(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    feats = features(rows)
    freq = frequency(feats)
    latest = max((r[\"round\"] for r in rows), default=0)
    return {\"latest\": latest, \"count\": len(rows), \"freq\": freq, \"recent10\": feats[-10:][::-1]}

def fallback_demo() -> Dict[str, Any]:
    rnd = random.Random(42)
    rows=[]
    base_round=1200
    for i in range(30):
        nums = sorted(rnd.sample(range(1,46), 6))
        rows.append({\"round\": base_round-i, \"date\": f\"2024-01-{(i%28)+1:02d}\", \"nums\": nums, \"bonus\": rnd.randint(1,45)})
    return build_payload(rows)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/diag")
async def diag():
    info = {}
    try:
        info["python"] = sys.version
        info["cwd"] = str(APP_DIR)
        info["static_dir_exists"] = STATIC_DIR.exists()
        info["static_index_exists"] = (STATIC_DIR / "index.html").exists()
        info["env"] = {k: os.environ.get(k) for k in ("PORT",)}
        try:
            info["dns_dhlottery"] = socket.gethostbyname_ex("www.dhlottery.co.kr")[2]
        except Exception as e:
            info["dns_dhlottery"] = f"dns_error: {e}"
    except Exception as e:
        info["error"] = str(e)
    return JSONResponse(info)

@app.get("/api/probe")
async def api_probe():
    result = {"ok": False, "detail": None}
    try:
        async with httpx.AsyncClient(http2=True) as client:
            r = await client.get(f"{BASE_URL}1", headers=HDRS, timeout=1.5)
            result["status_code"] = r.status_code
            result["ok"] = r.status_code == 200
            try:
                j = r.json()
                result["returnValue"] = j.get("returnValue")
            except Exception as je:
                result["detail"] = f"json_error: {je}"
    except Exception as e:
        result["detail"] = f"request_error: {e}"
    return JSONResponse(result)

@app.get("/api/stats")
async def api_stats(last: int = Query(50, ge=5, le=2000), background_tasks: BackgroundTasks = None):
    try:
        latest = await get_latest_round()
        start = max(1, latest - (last - 1))
        rows = []
        try:
            rows = await asyncio.wait_for(fetch_range(start, latest, batch_size=25), timeout=1.8)
        except asyncio.TimeoutError:
            rows = []
        payload = build_payload(rows) if rows else fallback_demo()
        return JSONResponse(payload, headers={"Cache-Control": "public, max-age=60"})
    except Exception:
        return JSONResponse(fallback_demo(), headers={"Cache-Control": "no-store"})

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
