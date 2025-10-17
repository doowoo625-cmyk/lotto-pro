# app/main.py  (Render 배포용 단일 파일 구현 v4)
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# -------------------------
# 기본 경로/정적 파일 마운트
# -------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = DATA_DIR / "recent.json"

app = FastAPI(title="Lotto Predictor API (v4)")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# -------------------------
# 동행복권 JSON API
# -------------------------
DH_BASE = "https://www.dhlottery.co.kr/common.do"
TIMEOUT = httpx.Timeout(8.0, connect=5.0, read=5.0)
HEADERS = {"User-Agent": "lotto-predictor/4.0 (+render)"}  # 보수적 UA

async def fetch_draw(drw_no: int) -> Optional[dict]:
    """특정 회차 1건 조회 (성공 시 표준화 dict 반환, 실패/미등록 시 None)"""
    params = {"method": "getLottoNumber", "drwNo": str(drw_no)}
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        r = await client.get(DH_BASE, params=params)
    if r.status_code != 200:
        return None
    data = r.json()
    # 동행복권 성공 시 returnValue == "success"
    if not data or str(data.get("returnValue", "")).lower() != "success":
        return None
    nums = [data.get(f"drwtNo{i}") for i in range(1, 7)]
    if None in nums:
        return None
    nums = sorted(int(n) for n in nums)
    bn = int(data.get("bnusNo", 0))
    date = data.get("drwNoDate")  # "YYYY-MM-DD"
    return {
        "draw_no": int(data.get("drwNo")),
        "numbers": nums,
        "bonus": bn,
        "date": date,
    }


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
# 최신 회차 빠른 탐색
#   - 지수 증가 → 경계 찾기 → 이분 탐색
#   - 캐시가 있으면 그 다음부터 확인
# -------------------------
async def find_latest_draw_no(cache: Dict[str, dict]) -> int:
    last = max_cached_draw(cache)
    if last <= 0:
        # 합리적 시작점 (1000회 이후는 안정적), 없으면 512부터
        probe = 1024
    else:
        probe = last + 1

    # 1) 상한 찾기 (성공하는 한 2배씩 증가)
    lo_success = 0
    hi_fail = 0
    step = probe
    while True:
        ok = await fetch_draw(step)
        if ok:
            cache[str(ok["draw_no"])] = ok
            lo_success = step
            step *= 2
            if step > 8192:  # 안전 상한
                break
        else:
            hi_fail = step
            break

    if lo_success == 0 and hi_fail == 0:
        # 첫 시도부터 실패한 경우: 1부터 상승
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

    # 2) 이분 탐색으로 마지막 성공 지점 찾기
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
        # 경계가 바로 이웃하거나 상한 도달
        latest = lo_success

    return latest


# -------------------------
# 최근 N회 수집/반환
# -------------------------
async def ensure_recent(cache: Dict[str, dict], end_no: int, n: int) -> List[dict]:
    """end_no부터 과거로 n개 확보 (캐시 보강) → 오름차순 정렬하여 반환"""
    items: List[dict] = []
    need_range = range(max(1, end_no - n + 1), end_no + 1)
    # 캐시에서 먼저 추출
    for d in need_range:
        k = str(d)
        if k in cache:
            items.append(cache[k])

    # 부족분만 원격 조회
    have_set = set(int(x["draw_no"]) for x in items)
    for d in need_range:
        if d in have_set:
            continue
        ok = await fetch_draw(d)
        if ok:
            cache[str(d)] = ok
            items.append(ok)

    # 정렬 (오름차순)
    items.sort(key=lambda x: x["draw_no"])
    return items


# -------------------------
# 범위별 빈도
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


# =========================
#          API
# =========================
@app.get("/api/latest")
async def api_latest():
    """
    최신 회차 1건.
    - 캐시에 없거나 draw_no==0이면 원격 탐색으로 최신을 보장.
    """
    cache = read_cache()

    # 캐시가 더미인 경우 보강
    latest = max_cached_draw(cache)
    if latest <= 0:
        latest = await find_latest_draw_no(cache)
        write_cache(cache)

    # 최신이더라도, 더 새로운 회차가 열렸을 수 있으니 한 번 더 체크
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
    """
    end_no 기준 이전 n개(포함) → 오름차순 배열
    """
    cache = read_cache()
    items = await ensure_recent(cache, end_no, n)
    write_cache(cache)
    return JSONResponse({"items": items})


@app.get("/api/range_freq_by_end")
async def api_range_freq_by_end(end_no: int = Query(..., gt=0), n: int = Query(10, gt=0, le=200)):
    """
    end_no 기준 이전 n개(포함)의 번호 빈도 → 5구간(1-10, …, 41-45)
    """
    cache = read_cache()
    items = await ensure_recent(cache, end_no, n)
    write_cache(cache)
    per = compute_range_freq(items)
    return JSONResponse(per)


# -------------------------
# 기동 시 1회 캐시웜업 (비차단)
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
        # 배포 첫 부팅에서 실패해도 앱은 살아 있어야 한다.
        pass
