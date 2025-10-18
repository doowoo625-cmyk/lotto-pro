from __future__ import annotations
import json, os, asyncio, random
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# ---------------- 기본 설정 ----------------
LIVE_FETCH = os.getenv("LIVE_FETCH", "1")  # 1: 실시간, 0: 캐시 전용
DH_BASE = "https://www.dhlottery.co.kr/common.do"
HEADERS = {"User-Agent": "lotto-predictor/6.0 (+Render)"}
TIMEOUT = httpx.Timeout(4.0, connect=3.0, read=3.0)
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = DATA_DIR / "recent.json"
SEED_PATH = DATA_DIR / "seed.json"

app = FastAPI(title="Lotto Predictor Stable v6")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = STATIC_DIR / "index.html"
    return html_path.read_text(encoding="utf-8") if html_path.exists() else "<h1>index.html not found</h1>"

# ---------------- 캐시 유틸 ----------------
def read_cache() -> Dict[str, dict]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    if SEED_PATH.exists():
        return json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return {}

def write_cache(cache: Dict[str, dict]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def max_cached_draw(cache: Dict[str, dict]) -> int:
    return max(map(int, cache.keys()), default=0)

# ---------------- 외부 호출 ----------------
async def http_get_json(url, params=None, retries=2):
    for _ in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
                r = await client.get(url, params=params)
            if r.status_code == 200:
                return r.json()
        except Exception:
            await asyncio.sleep(0.5)
    return None

async def fetch_draw(drw_no: int) -> Optional[dict]:
    params = {"method": "getLottoNumber", "drwNo": str(drw_no)}
    data = await http_get_json(DH_BASE, params)
    if not data or data.get("returnValue") != "success":
        return None
    nums = [data[f"drwtNo{i}"] for i in range(1, 7)]
    return {
        "draw_no": data["drwNo"],
        "numbers": sorted(map(int, nums)),
        "bonus": int(data["bnusNo"]),
        "date": data["drwNoDate"]
    }

async def find_latest_draw_no(cache: Dict[str, dict]) -> int:
    last = max_cached_draw(cache)
    if LIVE_FETCH != "1":
        return last
    cur = last + 1 if last else 1200
    for _ in range(20):
        ok = await fetch_draw(cur)
        if ok:
            cache[str(cur)] = ok
            return cur
        cur -= 1
    return last

# ---------------- 예측 로직 ----------------
def build_freq(items: List[dict]) -> Dict[int, int]:
    freq = {i: 0 for i in range(1, 46)}
    for it in items:
        for n in it["numbers"]:
            freq[n] += 1
    return freq

def score_combo(nums: List[int], freq: Dict[int, int]) -> tuple[float, float, float]:
    reward = sum(freq[n] for n in nums) / 6.0
    mean = sum(nums) / 6.0
    variance = sum((n - mean)**2 for n in nums) / 6.0
    risk = variance / 100.0
    return reward, risk, reward / (1 + risk)

def sample_pool(freq: Dict[int, int], strategy: str, seed: int) -> List[List[int]]:
    rnd = random.Random(seed)
    sorted_nums = sorted(freq.items(), key=lambda x: -x[1])
    top = [n for n, _ in sorted_nums[:20]]
    mid = [n for n, _ in sorted_nums[20:35]]
    low = [n for n, _ in sorted_nums[35:]]
    pool = set()
    while len(pool) < 60:
        if strategy == "보수형":
            picks = rnd.sample(top, 3) + rnd.sample(mid, 3)
        elif strategy == "균형형":
            picks = rnd.sample(top, 2) + rnd.sample(mid, 2) + rnd.sample(low, 2)
        else:
            picks = rnd.sample(low, 4) + rnd.sample(mid, 2)
        pool.add(tuple(sorted(picks)))
    return [list(p) for p in pool]

def make_result(items: List[dict], latest: int) -> dict:
    freq = build_freq(items)
    strategies = ["보수형", "균형형", "고위험형"]
    all_res, top_all = {}, []
    for i, s in enumerate(strategies):
        arr = []
        for combo in sample_pool(freq, s, latest * 37 + i):
            r, k, sc = score_combo(combo, freq)
            arr.append({
                "name": s, "numbers": combo,
                "reward": round(r, 2), "risk": round(k, 3), "score": round(sc, 3)
            })
        arr.sort(key=lambda x: x["score"], reverse=True)
        all_res[s] = arr[:5]
        top_all += arr[:3]
    top_all.sort(key=lambda x: x["score"], reverse=True)
    return {
        "best3_by_priority_korean": top_all[:3],
        "all_by_strategy_korean": all_res,
        "best_strategy_top5": top_all[:5]
    }

# ---------------- API ----------------
@app.get("/api/latest")
async def api_latest():
    cache = read_cache()
    latest = max_cached_draw(cache)
    try:
        newest = await find_latest_draw_no(cache)
        if newest > 0 and newest != latest:
            latest = newest
            write_cache(cache)
    except Exception:
        pass
    if latest <= 0 or str(latest) not in cache:
        return JSONResponse({"draw_no": 0, "numbers": [1,2,3,4,5,6], "bonus": 7, "date": None})
    return JSONResponse(cache[str(latest)])

@app.get("/api/dhlottery/recent")
async def api_recent(end_no: int = Query(...), n: int = Query(10)):
    cache = read_cache()
    have = sorted(map(int, cache.keys()))
    if not have:
        return JSONResponse({"items": []})
    end = end_no if end_no in have else have[-1]
    start = max(have[0], end - n + 1)
    return JSONResponse({"items": [cache[str(d)] for d in range(start, end + 1) if str(d) in cache]})

@app.get("/api/range_freq_by_end")
async def api_freq(end_no: int = Query(...), n: int = Query(10)):
    cache = read_cache()
    have = sorted(map(int, cache.keys()))
    if not have:
        return JSONResponse({"per": {}})
    end = end_no if end_no in have else have[-1]
    start = max(have[0], end - n + 1)
    nums = [cache[str(d)] for d in range(start, end + 1) if str(d) in cache]
    freq = build_freq(nums)
    buckets = {
        "1-10": {str(i): freq[i] for i in range(1,11)},
        "11-20": {str(i): freq[i] for i in range(11,21)},
        "21-30": {str(i): freq[i] for i in range(21,31)},
        "31-40": {str(i): freq[i] for i in range(31,41)},
        "41-45": {str(i): freq[i] for i in range(41,46)}
    }
    return JSONResponse({"per": buckets})

@app.post("/api/predict")
async def api_predict():
    cache = read_cache()
    latest = max_cached_draw(cache)
    if latest <= 0:
        try:
            latest = await find_latest_draw_no(cache)
        except Exception:
            latest = 0
    if latest <= 0:
        return JSONResponse({
            "best3_by_priority_korean": [],
            "all_by_strategy_korean": {},
            "best_strategy_top5": []
        })
    nums = [cache[str(d)] for d in range(max(1, latest - 50), latest + 1) if str(d) in cache]
    result = make_result(nums, latest)
    return JSONResponse(result)
