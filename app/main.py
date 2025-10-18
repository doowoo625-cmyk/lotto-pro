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

import asyncio
import os

# ---- 기존 TIMEOUT 유지 or 살짝 단축 가능
TIMEOUT = httpx.Timeout(4.0, connect=3.0, read=3.0)

async def http_get_json(url, params=None, headers=None, retries=2, backoff=0.4):
    """네트워크 불안정 대비: 짧은 타임아웃 + 소프트 재시도"""
    last_exc = None
    for i in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, headers=headers or HEADERS) as client:
                r = await client.get(url, params=params)
            if r.status_code == 200:
                return r.json()
            # 4xx/5xx도 재시도 1회 정도
        except Exception as e:
            last_exc = e
        await asyncio.sleep(backoff * (2 ** i))
    if last_exc:
        raise last_exc
    return None


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
    """특정 회차 1건 조회 (성공 시 표준화 dict, 실패/미등록 시 None)"""
    params = {"method": "getLottoNumber", "drwNo": str(drw_no)}
    try:
        data = await http_get_json(DH_BASE, params=params)
    except Exception:
        return None
    if not data or str(data.get("returnValue", "")).lower() != "success":
        return None
    nums = [data.get(f"drwtNo{i}") for i in range(1, 7)]
    if None in nums:
        return None
    nums = sorted(int(n) for n in nums)
    bn = int(data.get("bnusNo", 0))
    date = data.get("drwNoDate")
    return {"draw_no": int(data.get("drwNo")), "numbers": nums, "bonus": bn, "date": date}

def guess_anchor_from_time() -> int:
    """대략적인 최신 회차 추정치(매주 1회, 2002년 12월 7일 1회차 기준)"""
    # 2025년 10월 기준 러프하게 1200~1300대. 안전하게 1400로 잡고 내려감.
    return int(os.getenv("LATEST_GUESS", "1400"))

async def find_latest_draw_no(cache: Dict[str, dict]) -> int:
    """가벼운 최신 탐색: 추정치에서 아래로 내려가며 첫 성공을 최신으로 간주."""
    # 캐시에 이미 있으면 바로 반환
    last = max_cached_draw(cache)
    if last > 0:
        # 혹시 +1이 열렸는지만 빠르게 확인
        ok = await fetch_draw(last + 1)
        if ok:
            cache[str(ok["draw_no"])] = ok
            return ok["draw_no"]
        return last

    # 캐시가 없으면 추정치(anchor)에서 아래로 스캔(최대 120회)
    anchor = guess_anchor_from_time()
    for d in range(anchor, max(1, anchor - 120), -1):
        ok = await fetch_draw(d)
        if ok:
            cache[str(ok["draw_no"])] = ok
            return ok["draw_no"]
    # 그래도 못 찾으면 0
    return 0


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
    """
    - 우선 캐시 최고값 사용
    - 네트워크 성공하면 최신 덮어씀
    - 실패해도 500 안 내고 캐시 기반으로 응답
    """
    cache = read_cache()
    latest = max_cached_draw(cache)

    # LIVE_FETCH=0 이면 네트워크 시도 최소화
    live = os.getenv("LIVE_FETCH", "1") == "1"

    if live or latest <= 0:
        try:
            newest = await find_latest_draw_no(cache)
            if newest > 0:
                latest = newest
                write_cache(cache)
        except Exception:
            pass

    # 그래도 없으면 503로 명확히 안내(프런트는 로컬 플레이스홀더 표기 가능)
    if latest <= 0 or str(latest) not in cache:
        raise HTTPException(status_code=503, detail="latest unavailable (network/cache)")

    return JSONResponse(cache[str(latest)])

@app.post("/api/predict")
async def api_predict():
    """
    - 최신 회차가 없으면 캐시 최대 회차로 대체
    - 최근 100회가 안 모이면 가능한 범위 내에서 계산
    - 절대 500 내지 않고 최소 추천이라도 반환
    """
    cache = read_cache()
    latest = max_cached_draw(cache)

    if latest <= 0:
        try:
            newest = await find_latest_draw_no(cache)
            if newest > 0:
                latest = newest
                write_cache(cache)
        except Exception:
            pass

    if latest <= 0:
        # 최소 안전 응답
        return JSONResponse({
            "best3_by_priority_korean": [],
            "all_by_strategy_korean": {"보수형": [], "균형형": [], "고위험형": []},
            "best_strategy_top5": []
        })

    # 확보 가능한 범위 내에서 최대치만큼
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
