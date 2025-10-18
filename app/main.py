# app/main.py  (Render 배포용 v5-fixed — 최소수정 안정화)
from __future__ import annotations

import json
import os
import asyncio
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# -------------------------
# 전역 설정
# -------------------------
LIVE_FETCH = os.getenv("LIVE_FETCH", "1")  # "1": 온라인, "0": 오프라인-캐시 우선
DH_BASE = "https://www.dhlottery.co.kr/common.do"
HEADERS = {"User-Agent": "lotto-predictor/5.0 (+render)"}
TIMEOUT = httpx.Timeout(4.0, connect=3.0, read=3.0)  # 짧게
RETRY = 2  # 재시도 횟수 (총 1+RETRY번)

# -------------------------
# 경로/정적 마운트
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = DATA_DIR / "recent.json"

app = FastAPI(title="Lotto Predictor API (v5-fixed)")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>index.html not found</h1>", status_code=404)
    return html_path.read_text(encoding="utf-8")

# -------------------------
# 공용 HTTP 유틸 (짧은 타임아웃 + 소프트 재시도)
# -------------------------
async def http_get_json(url, params=None, headers=None, retries: int = RETRY, backoff: float = 0.35):
    last_exc = None
    for i in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers or HEADERS) as client:
                r = await client.get(url, params=params)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            last_exc = e
        await asyncio.sleep(backoff * (2 ** i))
    if last_exc:
        # 호출부에서 실패를 None 처리하도록 에러는 넘기지 않음
        return None
    return None

# -------------------------
# 동행복권 1회차 조회
# -------------------------
async def fetch_draw(drw_no: int) -> Optional[dict]:
    params = {"method": "getLottoNumber", "drwNo": str(drw_no)}
    data = await http_get_json(DH_BASE, params=params)
    if not data or str(data.get("returnValue", "")).lower() != "success":
        return None
    nums = [data.get(f"drwtNo{i}") for i in range(1, 7)]
    if None in nums:
        return None
    nums = sorted(int(n) for n in nums)
    bn = int(data.get("bnusNo", 0))
    date = data.get("drwNoDate")
    return {"draw_no": int(data.get("drwNo")), "numbers": nums, "bonus": bn, "date": date}

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
# 최신 회차 탐색 (가벼운 하향/상향 스캔)
# -------------------------
def guess_anchor_from_time() -> int:
    # 2025-10 기준 대략 1200~1300대. 여유있게 1400에서 하향 스캔 시작.
    return int(os.getenv("LATEST_GUESS", "1400"))

async def find_latest_draw_no(cache: Dict[str, dict]) -> int:
    """
    네트워크를 최소화해서 최신 회차를 탐색.
    - LIVE_FETCH != "1"이면 캐시만 신뢰
    - 캐시가 있으면 +1부터 최대 +8까지만 확인
    - 캐시가 없으면 앵커에서 120회 하향 스캔
    """
    last = max_cached_draw(cache)

    if LIVE_FETCH != "1":
        return last

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

    anchor = guess_anchor_from_time()
    for d in range(anchor, max(1, anchor - 120), -1):
        ok = await fetch_draw(d)
        if ok:
            cache[str(ok["draw_no"])] = ok
            return ok["draw_no"]
    return 0

# -------------------------
# 최근 N회 확보 (캐시 우선, 부족분만 원격)
# -------------------------
async def ensure_recent(cache: Dict[str, dict], end_no: int, n: int) -> List[dict]:
    items: List[dict] = []
    need_range = range(max(1, end_no - n + 1), end_no + 1)

    # 캐시 우선
    for d in need_range:
        k = str(d)
        if k in cache:
            items.append(cache[k])

    have_set = set(int(x["draw_no"]) for x in items)

    # LIVE_FETCH=1에서만 부족분 원격 조회
    if LIVE_FETCH == "1":
        for d in need_range:
            if d in have_set:
                continue
            ok = await fetch_draw(d)
            if ok:
                cache[str(d)] = ok
                items.append(ok)

    # 캐시만으로라도 반환
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

    pool: set[tuple[int, ...]] = set()
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
            win = round(min(85.0, 20 + reward * 1.5 - risk * 10), 1)  # 표기용 대략치
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
    """
    - 캐시 최고값을 우선 사용
    - LIVE_FETCH=1이면 가볍게 최신 갱신 시도(비차단)
    - 실패해도 500을 내지 않고 캐시 기반으로 항상 200 응답
    """
    cache = read_cache()
    latest = max_cached_draw(cache)

    if LIVE_FETCH == "1":
        try:
            newest = await find_latest_draw_no(cache)
            if newest > 0 and newest != latest:
                latest = newest
                write_cache(cache)
        except Exception:
            pass

    if latest <= 0 or str(latest) not in cache:
        # 프런트가 비어도 동작하도록 안전 플레이스홀더
        return JSONResponse({"draw_no": 0, "numbers": [1,2,3,4,5,6], "bonus": 7, "date": None})

    return JSONResponse(cache[str(latest)])

@app.get("/api/dhlottery/recent")
async def api_recent(end_no: int = Query(..., gt=0), n: int = Query(10, gt=1, le=200)):
    """
    end_no 기준 이전 n개(포함) → 캐시 범위 내에서라도 오름차순 반환 (항상 200)
    """
    cache = read_cache()
    have = sorted(int(k) for k in cache.keys())
    if not have:
        return JSONResponse({"items": []})

    end = end_no if end_no in have else have[-1]
    start = max(have[0], end - n + 1)
    items = [cache[str(d)] for d in range(start, end + 1) if str(d) in cache]
    items.sort(key=lambda x: x["draw_no"])
    return JSONResponse({"items": items})

@app.get("/api/range_freq_by_end")
async def api_range_freq_by_end(end_no: int = Query(..., gt=0), n: int = Query(10, gt=1, le=200)):
    """
    end_no 기준 이전 n개(포함)의 번호 빈도 → 5구간 (항상 200)
    """
    cache = read_cache()
    have = sorted(int(k) for k in cache.keys())
    if not have:
        # 빈 결과라도 200
        per = {k: {str(x): 0 for x in bucket} for k, bucket in range_buckets()}
        return JSONResponse({"per": per})

    end = end_no if end_no in have else have[-1]
    start = max(have[0], end - n + 1)
    items = [cache[str(d)] for d in range(start, end + 1) if str(d) in cache]
    per = compute_range_freq(items)
    return JSONResponse(per)

@app.post("/api/predict")
async def api_predict():
    """
    - 최신 회차 확보 실패해도 캐시 최대 회차 기준으로 계산
    - 최근 100회가 부족하면 있는 범위 내에서 계산
    - 항상 200
    """
    cache = read_cache()
    latest = max_cached_draw(cache)

    if LIVE_FETCH == "1" and latest <= 0:
        try:
            newest = await find_latest_draw_no(cache)
            if newest > 0:
                latest = newest
                write_cache(cache)
        except Exception:
            pass

    if latest <= 0:
        return JSONResponse({
            "best3_by_priority_korean": [],
            "all_by_strategy_korean": {"보수형": [], "균형형": [], "고위험형": []},
            "best_strategy_top5": []
        })

    items = await ensure_recent(cache, latest, 100)
    write_cache(cache)

    if not items:
        return JSONResponse({
            "best3_by_priority_korean": [],
            "all_by_strategy_korean": {"보수형": [], "균형형": [], "고위험형": []},
            "best_strategy_top5": []
        })

    payload = make_strategy_result(items, latest_draw=latest)
    return JSONResponse(payload)

# -------------------------
# 기동 시 1회 웜업 (비차단)
# -------------------------
@app.on_event("startup")
async def on_startup():
    try:
        cache = read_cache()
        # LIVE_FETCH=1이면 백그라운드로 가볍게 최신화 시도
        if LIVE_FETCH == "1" and max_cached_draw(cache) <= 0:
            newest = await find_latest_draw_no(cache)
            if newest > 0:
                write_cache(cache)

        # 선택: 주기적 백그라운드 갱신(느리면 주석 처리)
        if LIVE_FETCH == "1":
            async def refresher():
                while True:
                    try:
                        newest = await find_latest_draw_no(cache)
                        if newest > 0:
                            write_cache(cache)
                    except Exception:
                        pass
                    await asyncio.sleep(300)  # 5분
            asyncio.create_task(refresher())
    except Exception:
        pass
