# app/main.py  (Render 최종 안정판 v7 — 요청 중 500 절대 금지)
from __future__ import annotations

import json, os, asyncio, random
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# ---------------- 기본 설정 ----------------
LIVE_FETCH = os.getenv("LIVE_FETCH", "1")  # "1": 온라인 보조, "0": 캐시/시드만
DH_BASE = "https://www.dhlottery.co.kr/common.do"
HEADERS = {"User-Agent": "lotto-predictor/7.0 (+render)"}
TIMEOUT = httpx.Timeout(3.5, connect=2.5, read=2.5)  # 짧게

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = DATA_DIR / "recent.json"
SEED_PATH = DATA_DIR / "seed.json"  # 초기 화면용 시드

app = FastAPI(title="Lotto Predictor – stable v7")

# 정적 & 루트
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = STATIC_DIR / "index.html"
    return html_path.read_text(encoding="utf-8") if html_path.exists() else "<h1>index.html not found</h1>"

# ---------------- 캐시/시드 ----------------
def read_cache() -> Dict[str, dict]:
    # 캐시 우선
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    # 캐시가 비면 시드로라도 채움
    if SEED_PATH.exists():
        try:
            seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
            if isinstance(seed, dict):
                return seed
        except Exception:
            pass
    return {}

def write_cache(cache: Dict[str, dict]) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # 쓰기 실패해도 서비스는 계속

def max_cached_draw(cache: Dict[str, dict]) -> int:
    try:
        return max(map(int, cache.keys())) if cache else 0
    except Exception:
        return 0

# ---------------- 외부 호출(절대 요청 경로에서 강제하지 않음) ----------------
async def http_get_json(url, params=None):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
            r = await client.get(url, params=params)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

async def fetch_draw(drw_no: int) -> Optional[dict]:
    if LIVE_FETCH != "1":
        return None  # 오프라인 모드면 요청 자체를 안 한다
    data = await http_get_json(DH_BASE, params={"method": "getLottoNumber", "drwNo": str(drw_no)})
    if not data or str(data.get("returnValue", "")).lower() != "success":
        return None
    nums = [data.get(f"drwtNo{i}") for i in range(1, 7)]
    if None in nums:
        return None
    return {
        "draw_no": int(data["drwNo"]),
        "numbers": sorted(int(n) for n in nums),
        "bonus": int(data.get("bnusNo", 0)),
        "date": data.get("drwNoDate"),
    }

async def find_latest_draw_no(cache: Dict[str, dict]) -> int:
    """
    요청 경로에서 '빠르게'만 동작하도록 설계:
    - LIVE_FETCH=0: 캐시/시드만 신뢰
    - LIVE_FETCH=1: 캐시가 있으면 +1만 퀵체크(최대 3회). 캐시 없으면 앵커에서 하향 20회만 체크.
    모두 실패해도 0 반환(절대 예외 X)
    """
    last = max_cached_draw(cache)
    if LIVE_FETCH != "1":
        return last

    # 캐시가 있으면 +1 ~ +3까지만 퀵체크
    if last > 0:
        cur = last + 1
        for _ in range(3):
            ok = await fetch_draw(cur)
            if ok:
                cache[str(ok["draw_no"])] = ok
                write_cache(cache)
                return ok["draw_no"]
            cur += 1
        return last

    # 캐시 없으면 앵커 시작(보수적)
    anchor = int(os.getenv("LATEST_GUESS", "1400"))
    for d in range(anchor, max(1, anchor - 20), -1):
        ok = await fetch_draw(d)
        if ok:
            cache[str(ok["draw_no"])] = ok
            write_cache(cache)
            return ok["draw_no"]
    return 0

# ---------------- 최근 N회 확보(요청 중 네트워크 없음) ----------------
async def ensure_recent(cache: Dict[str, dict], end_no: int, n: int) -> List[dict]:
    start = max(1, end_no - n + 1)
    items = [cache[str(d)] for d in range(start, end_no + 1) if str(d) in cache]
    # LIVE_FETCH=1이어도 '요청 처리 중'에는 원격 보강을 하지 않는다(속도/안정성 우선)
    items.sort(key=lambda x: x["draw_no"])
    return items

# ---------------- 구간 빈도 ----------------
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

# ---------------- 예측/전략 ----------------
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
    adjacency_penalty = sum(1.0 if b - a == 1 else 0.5 if b - a == 2 else 0.0 for a, b in zip(nums, nums[1:]))
    risk = variance / 100.0 + adjacency_penalty * 0.3
    score = reward / (1.0 + risk)
    return reward, risk, score

def sample_pool_by_strategy(freq: Dict[int, int], strategy: str, seed: int) -> List[List[int]]:
    rnd = random.Random(seed)
    items = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
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
            pool.add(tuple(picks))
    return [list(t) for t in pool]

def make_strategy_result(items: List[dict], latest_draw: int) -> dict:
    if not items:
        return {
            "best3_by_priority_korean": [],
            "all_by_strategy_korean": {"보수형": [], "균형형": [], "고위험형": []},
            "best_strategy_top5": []
        }
    freq = build_freq(items)
    order = ["보수형", "균형형", "고위험형"]
    out_all: Dict[str, List[dict]] = {}
    all_pool = []
    for i, name in enumerate(order):
        combos = sample_pool_by_strategy(freq, name, seed=latest_draw * 31 + i * 7)
        scored = []
        for nums in combos:
            reward, risk, score = score_combo(nums, freq)
            scored.append({
                "name": name,
                "name_ko": name,
                "numbers": nums,
                "reward": round(reward, 3),
                "risk": round(risk, 3),
                "score": round(score, 3),
                "rr": round(score, 3),
                "win": round(min(85.0, 20 + reward * 1.5 - risk * 10), 1),
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

# ---------------- API (항상 200 보장) ----------------
@app.get("/api/latest")
async def api_latest():
    cache = read_cache()
    latest = max_cached_draw(cache)

    # 빠른 최신화 시도 (비차단, 실패 무시)
    try:
        newest = await find_latest_draw_no(cache)
        if newest > 0 and newest != latest:
            latest = newest
            write_cache(cache)
    except Exception:
        pass

    if latest <= 0 or str(latest) not in cache:
        # 비어도 항상 200 (프런트는 플레이스홀더 처리)
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
    end = end_no if end_no in have else have[-1]
    start = max(have[0], end - n + 1)
    items = [cache[str(d)] for d in range(start, end + 1) if str(d) in cache]
    return JSONResponse(compute_range_freq(items))

@app.post("/api/predict")
async def api_predict():
    """
    - 최신 회차/네트워크 상태와 무관하게 반드시 200 응답
    - 캐시가 비어도 기본(균등 가중)으로 샘플링하여 5세트 생성
    - 기존 전략 점수 로직을 그대로 활용
    """
    cache = read_cache()
    latest = max_cached_draw(cache)

    # 최근 60회(없으면 0~N)를 최대한 모음 (요청 중 원격 호출 없음)
    items: List[dict] = []
    if latest > 0:
        start = max(1, latest - 59)
        items = [cache[str(d)] for d in range(start, latest + 1) if str(d) in cache]

    # 캐시가 완전 비어있으면 균등 가중으로라도 동작
    if not items:
        # 가짜 빈도(전부 1)로 동작하여 버튼이 반드시 결과를 보여주도록
        freq = {i: 1 for i in range(1, 46)}
        def _fake_result():
            import random
            rnd = random.Random(777)  # 고정 시드(요청 때마다 동일해도 됨)
            def pick6():
                return sorted(rnd.sample(range(1,46), 6))
            def score(nums):
                # 최소 점수 계산(간단): 보상=6, 위험=0 → score=6
                reward = 6.0
                risk = 0.0
                score = reward/(1.0 + risk)
                return reward, risk, score
            def pack(name, nums):
                r,k,s = score(nums)
                return {"name": name, "name_ko": name, "numbers": nums,
                        "reward": round(r,3), "risk": round(k,3),
                        "score": round(s,3), "rr": round(s,3), "win": 50.0}
            # 전략별 5세트
            res = {
                "보수형": [pack("보수형", pick6()) for _ in range(5)],
                "균형형": [pack("균형형", pick6()) for _ in range(5)],
                "고위험형": [pack("고위험형", pick6()) for _ in range(5)],
            }
            pool = (res["보수형"][:2] + res["균형형"][:2] + res["고위험형"][:2])[:5]
            return {
                "best3_by_priority_korean": [res["균형형"][0], res["보수형"][0], res["고위험형"][0]],
                "all_by_strategy_korean": res,
                "best_strategy_top5": pool
            }
        return JSONResponse(_fake_result())

    # 캐시가 있으면 기존 로직으로 계산
    payload = make_strategy_result(items, latest_draw=latest)
    return JSONResponse(payload)


# ---------------- 기동 시 비차단 웜업 ----------------
@app.on_event("startup")
async def on_startup():
    # 캐시가 완전히 비어 있으면 시드를 캐시로 저장(초기 구동 즉시 렌더링)
    cache = read_cache()
    if cache and not CACHE_PATH.exists():
        write_cache(cache)

    # LIVE_FETCH=1이면 5분 주기 백그라운드 최신화(요청 처리와 분리)
    if LIVE_FETCH == "1":
        async def refresher():
            local_cache = read_cache()
            while True:
                try:
                    newest = await find_latest_draw_no(local_cache)
                    if newest > 0:
                        write_cache(local_cache)
                except Exception:
                    pass
                await asyncio.sleep(300)
        asyncio.create_task(refresher())
