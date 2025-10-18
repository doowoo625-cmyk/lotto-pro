# app/main.py  (Render 배포용 v5 — app 생성 순서 고정 + 모든 API 포함)
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import os
import asyncio

LIVE_FETCH = os.getenv("LIVE_FETCH", "1")  # "1": 온라인, "0": 오프라인-캐시 우선
TIMEOUT = httpx.Timeout(5.0, connect=3.0, read=3.0)  # 더 짧게
RETRY = 2  # 네트워크 재시도 횟수 (총 1+RETRY 번)

# -------------------------
# 경로/폴더 준비
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = DATA_DIR / "recent.json"

# -------------------------
# ★ 여기서 가장 먼저 app을 만든다 ★
# -------------------------
app = FastAPI(title="Lotto Predictor API (v5)")

# 정적 파일과 index.html 서빙
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>index.html not found</h1>", status_code=404)
    return html_path.read_text(encoding="utf-8")

# -------------------------
# 동행복권 JSON API 설정
# -------------------------
DH_BASE = "https://www.dhlottery.co.kr/common.do"
TIMEOUT = httpx.Timeout(8.0, connect=5.0, read=5.0)
HEADERS = {"User-Agent": "lotto-predictor/5.0 (+render)"}

async def fetch_draw(drw_no: int) -> Optional[dict]:
    """특정 회차 1건 조회 (성공 시 표준화 dict, 실패/미등록 시 None)
       - 짧은 타임아웃 + 재시도
    """
    if LIVE_FETCH != "1":
        return None  # 오프라인 모드: 네트워크 시도 안 함

    params = {"method": "getLottoNumber", "drwNo": str(drw_no)}
    last_exc = None
    for _ in range(1 + RETRY):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
                r = await client.get(DH_BASE, params=params)
            if r.status_code != 200:
                last_exc = RuntimeError(f"status={r.status_code}")
                await asyncio.sleep(0.1)
                continue
            data = r.json()
            if not data or str(data.get("returnValue", "")).lower() != "success":
                return None
            nums = [data.get(f"drwtNo{i}") for i in range(1, 7)]
            if None in nums:
                return None
            nums = sorted(int(n) for n in nums)
            bn = int(data.get("bnusNo", 0))
            date = data.get("drwNoDate")
            return {"draw_no": int(data.get("drwNo")), "numbers": nums, "bonus": bn, "date": date}
        except Exception as e:
            last_exc = e
            await asyncio.sleep(0.1)
    # 재시도 실패 → None
    return None


# -------------------------
# 캐시 I/O
# -------------------------
def read_cache() -> Dict[str, dict]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def write_cache(cache: Dict[str, dict]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def max_cached_draw(cache: Dict[str, dict]) -> int:
    if not cache:
        return 0
    return max(int(k) for k in cache.keys())

# -------------------------
# 최신 회차 탐색 (경계 찾기 + 이분 탐색)
# -------------------------

async def find_latest_draw_no(cache: Dict[str, dict]) -> int:
    """네트워크를 최소화해서 최신 회차를 탐색.
       - 캐시에 값이 있으면 그 이후로 최대 +8까지만 확인
       - 캐시가 전혀 없고 LIVE_FETCH=0이면 0 반환 (캐시만 사용)
    """
    last = max_cached_draw(cache)

    # 오프라인 모드: 캐시만 신뢰
    if LIVE_FETCH != "1":
        return last

    # 캐시가 있으면 그 다음부터 +8까지만 순차 확인 (빠르고 안전)
    if last > 0:
        cur = last + 1
        newest = last
        for _ in range(8):
            ok = await fetch_draw(cur)
            if ok:
                cache[str(ok["draw_no"])] = ok
                newest = ok["draw_no"]
                cur += 1
            else:
                break
        return newest

    # 캐시가 없으면 합리적 시작점부터 최대 32회만 순차 확인
    start = 1100
    newest = 0
    cur = start
    for _ in range(32):
        ok = await fetch_draw(cur)
        if ok:
            cache[str(ok["draw_no"])] = ok
            newest = ok["draw_no"]
            cur += 1
        else:
            break
    return newest


# -------------------------
# 최근 N회 확보
# -------------------------
async def ensure_recent(cache: Dict[str, dict], end_no: int, n: int) -> List[dict]:
    items: List[dict] = []
    need_range = range(max(1, end_no - n + 1), end_no + 1)
    for d in need_range:
        k = str(d)
        if k in cache:
            items.append(cache[k])
    have_set = set(int(x["draw_no"]) for x in items)
    for d in need_range:
        if d in have_set:
            continue
        ok = await fetch_draw(d)
        if ok:
            cache[str(d)] = ok
            items.append(ok)
    items.sort(key=lambda x: x["draw_no"])
    return items

# -------------------------
# 구간 빈도 계산
# -------------------------
def range_buckets() -> List[Tuple[str, range]]:
    return [
        ("1-10", range(1, 11)),
        ("11-20", range(11, 21)),
        ("21-30", range(21, 31)),
        ("31-40", range(31, 41)),
        ("41-45", range(41, 46)),
    ]

def compute_range_freq(items: List[dict]) -> dict:
    per = {k: {str(n): 0 for n in bucket} for k, bucket in range_buckets()}
    for it in items:
        for n in it["numbers"]:
            for k, bucket in range_buckets():
                if n in bucket:
                    per[k][str(n)] += 1
                    break
    return {"per": per}

# -------------------------
# 예측(전략) 점수/샘플링
# -------------------------
from itertools import combinations
import random

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
    adjacency_penalty = 0.0
    for a, b in zip(nums, nums[1:]):
        if abs(a - b) == 1:
            adjacency_penalty += 1.0
        elif abs(a - b) == 2:
            adjacency_penalty += 0.5
    risk = variance / 100.0 + adjacency_penalty * 0.3
    score = reward / (1.0 + risk)
    return reward, risk, score

def sample_pool_by_strategy(freq: Dict[int, int], strategy: str, seed: int) -> List[List[int]]:
    rnd = random.Random(seed)
    items = sorted([(n, c) for n, c in freq.items()], key=lambda x: (-x[1], x[0]))
    top = [n for n, _ in items[:20]]
    mid = [n for n, _ in items[20:35]]
    low = [n for n, _ in items[35:]]

    pool = set()
    tries = 0
    while len(pool) < 80 and tries < 2000:
        tries += 1
        if strategy == "보수형":
            picks = rnd.sample(top, 3) + rnd.sample(mid, 2) + rnd.sample(range(1, 46), 1)
        elif strategy == "균형형":
            picks = rnd.sample(top, 2) + rnd.sample(mid, 3) + rnd.sample(low, 1)
        else:  # 고위험형
            picks = rnd.sample(low, 3) + rnd.sample(mid, 2) + rnd.sample(range(1, 46), 1)
        picks = sorted(set(picks))[:6]
        if len(picks) == 6 and 1 <= min(picks) and max(picks) <= 45:
            pool.add(tuple(sorted(picks)))
    return [list(t) for t in pool]

def make_strategy_result(items: List[dict], latest_draw: int) -> dict:
    freq = build_freq(items)
    out_all: Dict[str, List[dict]] = {}
    order = ["보수형", "균형형", "고위험형"]

    for i, name in enumerate(order):
        combos = sample_pool_by_strategy(freq, name, seed=latest_draw * 31 + i * 7)
        scored = []
        for nums in combos:
            reward, risk, score = score_combo(nums, freq)
            rr = round((reward / (1.0 + risk)), 3)
            win = round(min(85.0, 20 + reward * 1.5 - risk * 10), 1)  # 표시용 대략치
            scored.append({
                "name": name,
                "name_ko": name,
                "numbers": sorted(nums),
                "reward": round(reward, 3),
                "risk": round(risk, 3),
                "score": round(score, 3),
                "rr": rr,
                "win": win,
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        out_all[name] = scored[:5]

    pool_top = []
    for name in order:
        pool_top += out_all[name]
    pool_top.sort(key=lambda x: x["score"], reverse=True)
    best_top5 = pool_top[:5]

    best3 = [out_all[name][0] for name in order if out_all[name]]
    best3.sort(key=lambda x: x["score"], reverse=True)

    return {
        "best3_by_priority_korean": best3,
        "all_by_strategy_korean": out_all,
        "best_strategy_top5": best_top5,
    }

# =========================
#            API
# =========================
@app.get("/api/latest")
async def api_latest():
    cache = read_cache()
    latest = max_cached_draw(cache)

    # 1) 최신 확인 시도 (오프라인이면 캐시 그대로)
    newest = await find_latest_draw_no(cache)
    if newest > latest:
        latest = newest
        write_cache(cache)

    # 2) 캐시에서 꺼내되, 없으면 마지막으로라도 "가장 큰 키" 시도
    if latest <= 0 and cache:
        latest = max_cached_draw(cache)

    # 3) 그래도 없으면, 더미 대신 "안전 200 응답"을 반환해서 프런트가 멈추지 않게
    item = cache.get(str(latest))
    if not item:
        return JSONResponse({"draw_no": 0, "numbers": [], "bonus": 0, "date": None}, status_code=200)

    return JSONResponse(item)


@app.get("/api/dhlottery/recent")
async def api_recent(end_no: int = Query(..., gt=0), n: int = Query(10, gt=0, le=200)):
    cache = read_cache()
    try:
        items = await ensure_recent(cache, end_no, n)
        write_cache(cache)
        return JSONResponse({"items": items})
    except Exception:
        # 실패하더라도 200 + 빈 배열 → 프런트는 화면을 그대로 유지
        return JSONResponse({"items": []})


@app.get("/api/range_freq_by_end")
async def api_range_freq_by_end(end_no: int = Query(..., gt=0), n: int = Query(10, gt=0, le=200)):
    cache = read_cache()
    try:
        items = await ensure_recent(cache, end_no, n)
        write_cache(cache)
        per = compute_range_freq(items)
        return JSONResponse(per)
    except Exception:
        # 실패 시에도 200 + 빈 구조
        empty = {k: {str(x): 0 for x in r} for k, r in range_buckets()}
        return JSONResponse({"per": empty})

@app.post("/api/predict")
async def api_predict():
    cache = read_cache()
    latest = max_cached_draw(cache)

    # 최신(짧게) 확인
    newest = await find_latest_draw_no(cache)
    if newest > latest:
        latest = newest
        write_cache(cache)

    if latest <= 0:
        # 캐시가 전혀 없을 때도 200 + 빈 구조
        return JSONResponse({"best3_by_priority_korean": [], "all_by_strategy_korean": {}, "best_strategy_top5": []})

    # 최근 100회 확보하되, 실패해도 가진 만큼으로 계산
    items = []
    try:
        items = await ensure_recent(cache, latest, 100)
        write_cache(cache)
    except Exception:
        items = [cache[str(k)] for k in sorted(map(int, cache.keys())) if k <= latest][-30:]  # 최소 보정

    payload = make_strategy_result(items, latest_draw=latest) if items else {
        "best3_by_priority_korean": [],
        "all_by_strategy_korean": {},
        "best_strategy_top5": []
    }
    return JSONResponse(payload)



# -------------------------
# 기동 시 1회 캐시웜업 (비차단)
# -------------------------

@app.on_event("startup")
async def on_startup():
    # 부팅은 논블로킹: 실패해도 앱은 바로 응답
    try:
        cache = read_cache()
        if LIVE_FETCH == "1" and max_cached_draw(cache) <= 0:
            newest = await find_latest_draw_no(cache)
            if newest > 0:
                write_cache(cache)
    except Exception:
        pass
