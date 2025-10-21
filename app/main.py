# app/main.py — Render 안정판 SAFE
from __future__ import annotations
import json, os, asyncio, random
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

LIVE_FETCH = os.getenv("LIVE_FETCH", "1")     # "0"이면 절대 외부 호출 안 함
DH_BASE    = "https://www.dhlottery.co.kr/common.do"
HEADERS    = {"User-Agent": "lotto-predictor/safe"}
TIMEOUT    = httpx.Timeout(3.0, connect=2.0, read=2.0)

BASE_DIR   = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR   = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = DATA_DIR / "recent.json"
SEED_PATH  = DATA_DIR / "seed.json"

app = FastAPI(title="Lotto Predictor SAFE")

# 정적/루트
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    html = STATIC_DIR / "index.html"
    return html.read_text(encoding="utf-8") if html.exists() else "<h1>index.html not found</h1>"

# 파비콘 & 헬스
@app.get("/favicon.ico")
async def favicon():
    svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><rect width='16' height='16' rx='3' fill='#2563eb'/><text x='8' y='10' text-anchor='middle' font-size='10' fill='white'>L</text></svg>"
    return Response(content=svg, media_type="image/svg+xml")

@app.get("/healthz")
async def healthz():
    return {"ok": True, "live_fetch": LIVE_FETCH}

# 캐시/시드
def read_cache() -> Dict[str, dict]:
    if CACHE_PATH.exists():
        try: return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception: pass
    if SEED_PATH.exists():
        try:
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            if isinstance(seed, dict): return seed
        except Exception: pass
    return {}

def write_cache(cache: Dict[str, dict]) -> None:
    try: CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception: pass

def max_cached_draw(cache: Dict[str, dict]) -> int:
    try: return max(map(int, cache.keys())) if cache else 0
    except Exception: return 0

# 외부 호출(요청 경로에서 강제하지 않음)
async def http_get_json(url, params=None):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
            r = await client.get(url, params=params)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

async def fetch_draw(drw_no: int) -> Optional[dict]:
    if LIVE_FETCH != "1":
        return None
    data = await http_get_json(DH_BASE, params={"method": "getLottoNumber", "drwNo": str(drw_no)})
    if not data or str(data.get("returnValue", "")).lower() != "success":
        return None
    nums = [data.get(f"drwtNo{i}") for i in range(1, 7)]
    if None in nums: return None
    return {
        "draw_no": int(data["drwNo"]),
        "numbers": sorted(int(n) for n in nums),
        "bonus": int(data.get("bnusNo", 0)),
        "date": data.get("drwNoDate"),
    }

async def find_latest_draw_no(cache: Dict[str, dict]) -> int:
    last = max_cached_draw(cache)
    if LIVE_FETCH != "1":
        return last
    if last > 0:
        # +1~+3 퀵 체크
        cur = last + 1
        for _ in range(3):
            ok = await fetch_draw(cur)
            if ok:
                cache[str(ok["draw_no"])] = ok
                write_cache(cache)
                return ok["draw_no"]
            cur += 1
        return last
    # 캐시 없음: 앵커 1400부터 하향 20회만
    anchor = int(os.getenv("LATEST_GUESS", "1400"))
    for d in range(anchor, max(1, anchor - 20), -1):
        ok = await fetch_draw(d)
        if ok:
            cache[str(ok["draw_no"])] = ok
            write_cache(cache)
            return ok["draw_no"]
    return 0

async def ensure_recent(cache: Dict[str, dict], end_no: int, n: int) -> List[dict]:
    start = max(1, end_no - n + 1)
    items = [cache[str(d)] for d in range(start, end_no + 1) if str(d) in cache]
    items.sort(key=lambda x: x["draw_no"])
    return items

# 구간/빈도
def range_buckets() -> List[Tuple[str, range]]:
    return [("1-10", range(1,11)), ("11-20", range(11,21)), ("21-30", range(21,31)),
            ("31-40", range(31,41)), ("41-45", range(41,46))]

def compute_range_freq(items: List[dict]) -> dict:
    per = {k: {str(n): 0 for n in bucket} for k, bucket in range_buckets()}
    for it in items:
        for n in it["numbers"]:
            for k, bucket in range_buckets():
                if n in bucket:
                    per[k][str(n)] += 1
                    break
    return {"per": per}

# 예측/점수
def build_freq(items: List[dict]) -> Dict[int, int]:
    freq = {i: 0 for i in range(1, 46)}
    for it in items:
        for n in it["numbers"]:
            freq[n] += 1
    return freq

def score_combo(nums: List[int], freq: Dict[int, int]) -> tuple[float, float, float]:
    nums = sorted(nums)
    reward = sum(freq[n] for n in nums) / 6.0
    mean = sum(nums) / 6.0
    variance = sum((n - mean) ** 2 for n in nums) / 6.0
    adjacency_penalty = sum(1.0 if b-a==1 else 0.5 if b-a==2 else 0.0 for a,b in zip(nums, nums[1:]))
    risk = variance / 100.0 + adjacency_penalty * 0.3
    score = reward / (1.0 + risk)
    return reward, risk, score

def sample_pool_by_strategy(freq: Dict[int, int], strategy: str, seed: int) -> List[List[int]]:
    rnd = random.Random(seed)
    items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    top = [n for n,_ in items[:20]]
    mid = [n for n,_ in items[20:35]]
    low = [n for n,_ in items[35:]]

    pool: set[tuple[int,...]] = set()
    tries = 0
    while len(pool) < 80 and tries < 2000:
        tries += 1
        if strategy == "보수형":
            picks = rnd.sample(top,3) + rnd.sample(mid,2) + rnd.sample(range(1,46),1)
        elif strategy == "균형형":
            picks = rnd.sample(top,2) + rnd.sample(mid,3) + rnd.sample(low,1)
        else:
            picks = rnd.sample(low,3) + rnd.sample(mid,2) + rnd.sample(range(1,46),1)
        picks = sorted(set(picks))[:6]
        if len(picks) == 6 and 1 <= min(picks) <= 45 and 1 <= max(picks) <= 45:
            pool.add(tuple(picks))
    return [list(t) for t in pool]

def make_strategy_result(items: List[dict], latest_draw: int) -> dict:
    if not items:
        # 빈 화면 방지용 기본 결과(균등 가중)
        rnd = random.Random(777)
        def pick6(): return sorted(rnd.sample(range(1,46), 6))
        def pack(name, nums, s=6.0):
            return {"name": name, "name_ko": name, "numbers": nums,
                    "reward": 6.0, "risk": 0.0, "score": s, "rr": s, "win": 50.0}
        res = { "보수형": [pack("보수형", pick6()) for _ in range(5)],
                "균형형": [pack("균형형", pick6()) for _ in range(5)],
                "고위험형": [pack("고위험형", pick6()) for _ in range(5)] }
        pool = (res["보수형"][:2] + res["균형형"][:2] + res["고위험형"][:2])[:5]
        return {
            "best3_by_priority_korean": [res["균형형"][0], res["보수형"][0], res["고위험형"][0]],
            "all_by_strategy_korean": res,
            "best_strategy_top5": pool
        }
    freq  = build_freq(items)
    order = ["보수형","균형형","고위험형"]
    out_all: Dict[str, List[dict]] = {}
    all_pool = []
    for i, name in enumerate(order):
        combos = sample_pool_by_strategy(freq, name, seed=latest_draw * 31 + i * 7)
        scored = []
        for nums in combos:
            reward, risk, score = score_combo(nums, freq)
            scored.append({
                "name": name, "name_ko": name, "numbers": nums,
                "reward": round(reward,3), "risk": round(risk,3),
                "score": round(score,3), "rr": round(score,3),
                "win": round(min(85.0, 20 + reward*1.5 - risk*10), 1),
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        out_all[name] = scored[:5]
        all_pool += scored[:5]
    all_pool.sort(key=lambda x: x["score"], reverse=True)
    best3 = [out_all[name][0] for name in order if out_all[name]]
    best3.sort(key=lambda x: x["score"], reverse=True)
    return {
        "best3_by_priority_korean": best3[:3],
        "all_by_strategy_korean": out_all,
        "best_strategy_top5": all_pool[:5],
    }

# ---- API: 항상 200 ----
@app.get("/api/latest")
async def api_latest():
    cache = read_cache()
    latest = max_cached_draw(cache)
    # 빠른 최신화(비차단): 실패 무시
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
    end   = end_no if end_no in have else have[-1]
    start = max(have[0], end - n + 1)
    items = [cache[str(d)] for d in range(start, end + 1) if str(d) in cache]
    items.sort(key=lambda x: x["draw_no"])
    return JSONResponse({"items": items})

@app.get("/api/range_freq_by_end")
async def api_range_freq_by_end(end_no: int = Query(...), n: int = Query(10)):
    cache = read_cache()
    have = sorted(map(int, cache.keys()))
    if not have:
        per = {k: {str(x): 0 for x in bucket} for k, bucket in range_buckets()}
        return JSONResponse({"per": per})
    end   = end_no if end_no in have else have[-1]
    start = max(have[0], end - n + 1)
    items = [cache[str(d)] for d in range(start, end + 1) if str(d) in cache]
    return JSONResponse(compute_range_freq(items))

# 예측: GET/POST 허용
@app.post("/api/predict")
@app.get("/api/predict")
async def api_predict():
    cache  = read_cache()
    latest = max_cached_draw(cache)
    items: List[dict] = []
    if latest > 0:
        start = max(1, latest - 59)
        items = [cache[str(d)] for d in range(start, latest + 1) if str(d) in cache]
    payload = make_strategy_result(items, latest_draw=latest or 1000)
    return JSONResponse(payload)

# 시작 시 비차단 백그라운드(요청과 분리)
@app.on_event("startup")
async def on_startup():
    cache = read_cache()
    if cache and not CACHE_PATH.exists():
        write_cache(cache)
    if LIVE_FETCH == "1":
        async def refresher():
            local = read_cache()
            while True:
                try:
                    newest = await find_latest_draw_no(local)
                    if newest > 0:
                        write_cache(local)
                except Exception:
                    pass
                await asyncio.sleep(300)
        asyncio.create_task(refresher())
