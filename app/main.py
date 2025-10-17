# app/main.py  (v5 - Render drop-in)
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# -------------------------
# 경로/정적
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = DATA_DIR / "recent.json"

app = FastAPI(title="Lotto Predictor API (v5)")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# -------------------------
# 외부 API (동행복권)
# -------------------------
DH_BASE = "https://www.dhlottery.co.kr/common.do"
TIMEOUT = httpx.Timeout(8.0, connect=5.0, read=5.0)
HEADERS = {"User-Agent": "lotto-predictor/5.0 (+render)"}

async def fetch_draw(drw_no: int) -> Optional[dict]:
    params = {"method": "getLottoNumber", "drwNo": str(drw_no)}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        r = await client.get(DH_BASE, params=params)
    if r.status_code != 200:
        return None
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

# -------------------------
# 캐시
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
# 최신 회차 찾기
# -------------------------
async def find_latest_draw_no(cache: Dict[str, dict]) -> int:
    last = max_cached_draw(cache)
    probe = last + 1 if last > 0 else 1024

    lo_success = 0
    hi_fail = 0
    step = probe
    while True:
        ok = await fetch_draw(step)
        if ok:
            cache[str(ok["draw_no"])] = ok
            lo_success = step
            step *= 2
            if step > 8192:
                break
        else:
            hi_fail = step
            break

    if lo_success == 0 and hi_fail == 0:
        step = 1
        while True:
            ok = await fetch_draw(step)
            if ok:
                cache[str(ok["draw_no"])] = ok
                lo_success = step
                step *= 2
            else:
                hi_fail = step
                break

    if lo_success and hi_fail and hi_fail - lo_success > 1:
        lo, hi = lo_success, hi_fail
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            ok = await fetch_draw(mid)
            if ok:
                cache[str(ok["draw_no"])] = ok
                lo = mid
            else:
                hi = mid
        latest = lo
    else:
        latest = lo_success
    return latest

# -------------------------
# 최근 N 확보
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
# 구간 빈도
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
# 점수/전략 생성 (간단/견고)
# -------------------------
def freq_table(items: List[dict]) -> Dict[int, int]:
    ft = {n: 0 for n in range(1, 46)}
    for it in items:
        for n in it["numbers"]:
            ft[n] += 1
    return ft

def combo_score(nums: List[int], ft: Dict[int, int]) -> Tuple[float, float, float]:
    """(score, rr, win%) 계산: reward=평균빈도, risk=분산+인접패널티"""
    reward = sum(ft[n] for n in nums) / 6.0
    # 분산
    mean = sum(nums) / 6.0
    var = sum((n - mean) ** 2 for n in nums) / 6.0
    # 인접 패널티
    adj = 0
    for i in range(5):
        if nums[i + 1] - nums[i] == 1:
            adj += 1
    risk = (var / 100.0) + (adj * 0.5)  # 스케일 조정
    score = reward / (1.0 + risk)
    # R/R은 간단히 reward / (1 + adj)
    rr = round(reward / (1.0 + adj), 2)
    # 승률 추정: 보정된 sigmoid
    win = round(100 / (1 + math.exp(-(reward - 3.0))), 1)
    return round(score, 2), rr, win

def gen_candidate_sets(ft: Dict[int, int], mode: str) -> List[List[int]]:
    """mode: '보수형'|'균형형'|'고위험형' 에 따라 후보 조합 생성"""
    # 빈도 순 정렬
    top = sorted(range(1, 46), key=lambda x: ft[x], reverse=True)
    mid = sorted(range(1, 46), key=lambda x: abs(ft[x] - (sum(ft.values())/45)))
    low = sorted(range(1, 46), key=lambda x: ft[x])

    picks: List[List[int]] = []
    if mode == "보수형":
        # 상위 빈도에서 간격 넓게 추출
        pool = top[:20]
        bases = [
            [pool[i] for i in [0,3,6,9,12,15]],
            [pool[i] for i in [1,4,7,10,13,16]],
            [pool[i] for i in [2,5,8,11,14,17]],
            [pool[i] for i in [0,5,6,11,12,17]],
            [pool[i] for i in [3,4,9,10,15,16]],
        ]
        picks = [sorted(b) for b in bases]
    elif mode == "균형형":
        # 상/중/하 빈도 골고루
        pool_h = top[:15]
        pool_m = mid[:15]
        pool_l = low[:15]
        bases = [
            [pool_h[0], pool_h[5], pool_m[2], pool_m[7], pool_l[1], pool_l[6]],
            [pool_h[1], pool_h[6], pool_m[3], pool_m[8], pool_l[2], pool_l[7]],
            [pool_h[2], pool_h[7], pool_m[4], pool_m[9], pool_l[3], pool_l[8]],
            [pool_h[3], pool_h[8], pool_m[5], pool_m[10], pool_l[4], pool_l[9]],
            [pool_h[4], pool_h[9], pool_m[6], pool_m[11], pool_l[5], pool_l[10]],
        ]
        picks = [sorted(b) for b in bases]
    else:  # 고위험형
        # 낮은 빈도 + 간격 좁힘(변동성↑)
        pool = low[:25]
        bases = [
            [pool[i] for i in [0,1,2,7,12,18]],
            [pool[i] for i in [1,2,3,8,13,19]],
            [pool[i] for i in [2,3,4,9,14,20]],
            [pool[i] for i in [3,4,5,10,15,21]],
            [pool[i] for i in [4,5,6,11,16,22]],
        ]
        picks = [sorted(b) for b in bases]
    # 1~45 범위 보정
    normed = []
    for s in picks:
        ss = [min(45, max(1, int(x))) for x in s]
        # 정렬·중복 제거 보정
        uniq = sorted(dict.fromkeys(ss))
        while len(uniq) < 6:
            # 부족하면 높은쪽에서 채우기
            for k in range(45, 0, -1):
                if k not in uniq:
                    uniq.append(k)
                    break
            uniq = sorted(uniq)
        normed.append(uniq[:6])
    return normed

def build_strategy_payload(items: List[dict]) -> dict:
    ft = freq_table(items)
    out: Dict[str, List[dict]] = {}
    for mode in ["보수형", "균형형", "고위험형"]:
        cands = gen_candidate_sets(ft, mode)
        scored: List[dict] = []
        for s in cands:
            score, rr, win = combo_score(s, ft)
            scored.append({"numbers": s, "score": score, "rr": rr, "win": win, "name": mode, "name_ko": mode})
        # 점수 내림차순
        scored.sort(key=lambda x: x["score"], reverse=True)
        out[mode] = scored[:5]
    # 전체 풀에서 상위 3 추출(각 전략 1세트씩 대표)
    best3 = [out["균형형"][0], out["보수형"][0], out["고위험형"][0]]
    best3.sort(key=lambda x: x["score"], reverse=True)
    return {
        "all_by_strategy_korean": out,
        "best3_by_priority_korean": best3,
    }

# =========================
#           API
# =========================
@app.get("/api/latest")
async def api_latest():
    cache = read_cache()
    latest = max_cached_draw(cache)
    if latest <= 0:
        latest = await find_latest_draw_no(cache)
        write_cache(cache)
    newest = await find_latest_draw_no(cache)
    if newest != latest:
        latest = newest
        write_cache(cache)
    item = cache.get(str(latest))
    if not item:
        raise HTTPException(500, "latest not found after refresh")
    return JSONResponse(item)

@app.get("/api/dhlottery/recent")
async def api_recent(end_no: int = Query(..., gt=0), n: int = Query(10, gt=0, le=200)):
    cache = read_cache()
    items = await ensure_recent(cache, end_no, n)
    write_cache(cache)
    return JSONResponse({"items": items})

@app.get("/api/range_freq_by_end")
async def api_range_freq_by_end(end_no: int = Query(..., gt=0), n: int = Query(10, gt=0, le=200)):
    cache = read_cache()
    items = await ensure_recent(cache, end_no, n)
    write_cache(cache)
    per = compute_range_freq(items)
    return JSONResponse(per)

@app.post("/api/predict")
async def api_predict(
    end_no: Optional[int] = None,
    n: int = Query(30, gt=5, le=200)  # 최근 30회 기반으로 스코어링(가벼움+안정)
):
    """
    예측 API:
    - 기본은 최신 회차 기준 최근 n회로 빈도/점수 계산
    - 응답 구조는 프론트(app.js) 기대값에 맞춤
    """
    cache = read_cache()
    latest = max_cached_draw(cache)
    if latest <= 0:
        latest = await find_latest_draw_no(cache)
    use_end = end_no or latest
    items = await ensure_recent(cache, use_end, n)
    write_cache(cache)

    if not items:
        raise HTTPException(500, "no recent items available")

    payload = build_strategy_payload(items)

    # 전체 후보에서 스코어 상위 5 (전략 섞임)
    pool = []
    for arr in payload["all_by_strategy_korean"].values():
        pool.extend(arr)
    pool.sort(key=lambda x: x["score"], reverse=True)
    top5 = pool[:5]

    # 최종 응답
    return JSONResponse({
        "all_by_strategy_korean": payload["all_by_strategy_korean"],
        "best3_by_priority_korean": payload["best3_by_priority_korean"],
        "best_strategy_top5": top5
    })

# -------------------------
# index.html 서빙
# -------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>index.html not found</h1>", status_code=404)
    return html_path.read_text(encoding="utf-8")

# -------------------------
# 기동시 웜업 (non-blocking)
# -------------------------
@app.on_event("startup")
async def on_startup():
    try:
        cache = read_cache()
        if max_cached_draw(cache) <= 0:
            latest = await find_latest_draw_no(cache)
            if latest > 0:
                write_cache(cache)
    except Exception:
        pass
