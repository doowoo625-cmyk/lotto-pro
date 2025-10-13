# server_render.py — Full UI backend with /api/analysis
import os, time, asyncio, random, logging, socket, sys, math
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

DEFAULT_HTML = """<!doctype html>
<meta charset="utf-8">
<title>로또 예측 (준비중)</title>
<body style="font-family:system-ui;background:#0f172a;color:#e5e7eb;margin:0;padding:24px">
  <h1>정적 파일 준비 중</h1>
  <p><code>static/index.html</code>을 커밋하면 UI가 표시됩니다.</p>
</body>
"""

STATIC_DIR.mkdir(parents=True, exist_ok=True)
if not (STATIC_DIR / "index.html").exists():
    (STATIC_DIR / "index.html").write_text(DEFAULT_HTML, encoding="utf-8")

app = FastAPI(title="Lotto Predictor", version="3.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=700)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

HDRS = {"User-Agent": "Mozilla/5.0"}
BASE_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="

TTL_SEC = 1800
_round_cache: Dict[int, Dict[str, Any]] = {}
_round_ts: Dict[int, float] = {}
_latest_cache: Dict[str, Any] = {"value": None, "ts": 0}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lotto")

# ---------- Data fetch ----------
def _get_cache(n: int) -> Optional[Dict[str, Any]]:
    ts = _round_ts.get(n)
    if ts and (time.time() - ts) < TTL_SEC:
        return _round_cache.get(n)
    return None

def _set_cache(n: int, payload: Dict[str, Any]):
    _round_cache[n] = payload
    _round_ts[n] = time.time()

async def fetch_round_async(client: httpx.AsyncClient, n: int, timeout: float = 1.8) -> Optional[Dict[str, Any]]:
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
        _latest_cache.update({"value": lo, "ts": now})
        return lo
    except Exception as e:
        log.warning(f"get_latest_round fallback: {e}")
        return _latest_cache["value"] or 1200

# ---------- Feature engineering ----------
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

def freq_prob(freq: List[int]) -> List[float]:
    total = sum(freq[1:])
    if total == 0: return [0.0]*46
    return [0.0]+[freq[i]/total for i in range(1,46)]

def pick_set_by_weights(weights: List[float], power: float = 1.0, seed: Optional[int]=None) -> List[int]:
    rnd = random.Random(seed) if seed is not None else random
    w = [0.0]+[max(1e-9, pow(weights[i], power)) for i in range(1,46)]
    s = []
    trials=0
    while len(s)<6 and trials<500:
        trials+=1
        r = rnd.random()*sum(w[1:])
        acc=0.0
        for i in range(1,46):
            acc+=w[i]
            if r<=acc:
                if i not in s: s.append(i)
                break
    s.sort()
    return s

def explain_set(set_nums: List[int], freq: List[int]) -> List[Dict[str, Any]]:
    vals = [freq[n] for n in set_nums]
    denom = sum(vals) or 1
    out = []
    for n,v in zip(set_nums, vals):
        pct = round(100.0 * v / denom, 1)
        basis = "출현빈도 기반"
        out.append({"n": n, "pct": pct, "basis": basis, "freq": v})
    return out

def rr_score(set_nums: List[int], freq: List[int]) -> Tuple[float,float,float]:
    # reward ~ 평균 빈도, risk ~ 편차(분산) + 연속/근접 패널티, score ~ reward / (1+risk)
    vals = [freq[n] for n in set_nums]
    if not vals: return (0.0, 0.0, 0.0)
    mean = sum(vals)/len(vals)
    var = sum((v-mean)**2 for v in vals)/len(vals)
    # 근접 패널티: 인접 숫자 많이 포함될수록 위험 증가
    adj = sum(1 for a,b in zip(set_nums,set_nums[1:]) if abs(a-b)==1)
    risk = var/10.0 + adj*0.2
    reward = mean
    score = reward / (1.0 + risk)
    return (reward, risk, score)

def top_k_sets(freq: List[int], strategy: str, k: int = 5) -> List[Dict[str, Any]]:
    p = freq_prob(freq)
    results = []
    seed_base = {"보수형": 11, "균형형": 22, "고위험형": 33}.get(strategy, 0)
    for i in range(k*3):  # generate pool
        if strategy=="보수형":
            s = pick_set_by_weights(p, power=1.5, seed=seed_base+i)
        elif strategy=="고위험형":
            # 더 평탄하게 + 일부 랜덤 치환
            s = pick_set_by_weights(p, power=0.6, seed=seed_base+i)
            # 랜덤 치환 1~2개
            rnd = random.Random(seed_base+i)
            for _ in range(rnd.randint(1,2)):
                rep = rnd.randint(1,45)
                if rep not in s:
                    s[rnd.randrange(0,6)] = rep
            s = sorted(set(s))
            while len(s)<6:
                x = rnd.randint(1,45)
                if x not in s: s.append(x)
            s.sort()
        else: # 균형형
            s = pick_set_by_weights(p, power=1.0, seed=seed_base+i)
        reward, risk, score = rr_score(s, freq)
        results.append({"numbers": s, "reward": round(reward,2), "risk": round(risk,2), "score": round(score,2)})
    # 정렬 기준: 보수형/균형형은 score 내림차순, 고위험형은 reward 우선
    if strategy=="고위험형":
        results.sort(key=lambda x:(x["score"], x["reward"]), reverse=True)
    else:
        results.sort(key=lambda x:x["score"], reverse=True)
    return results[:k]

def weekly_best_strategy(freq: List[int], recent10: List[Dict[str, Any]]) -> Dict[str, Any]:
    # 다양성 지표 + 상위빈도 집중 지표로 간단 판단
    diversity = len(set(sum([r["nums"] for r in recent10], []))) if recent10 else 0
    top = sorted([(n,freq[n]) for n in range(1,46)], key=lambda x:x[1], reverse=True)[:10]
    top_sum = sum(f for n,f in top)
    # 휴리스틱: 다양성 높고 top_sum 낮으면 균형형, 다양성 낮으면 고위험형, 그 외 보수형
    if diversity >= 35 and top_sum <= 30: name="균형형"
    elif diversity < 28: name="고위험형"
    else: name="보수형"
    combos = top_k_sets(freq, name, k=1)
    combo = combos[0] if combos else {"numbers":[1,2,3,4,5,6], "score":0, "reward":0, "risk":0}
    # 추정 승률: 순위합으로 간단 근사 (표시용)
    winrate = round(min(2.0 + (combo["score"]/10.0), 9.5), 2)  # 0~9.5% 범위 느낌값
    rr = round((combo["reward"] / (1 + combo["risk"])), 2)
    return {"name": name, "avg_score": combo["score"], "rr": rr, "winrate": winrate, "set": combo["numbers"]}

def interval_freq(freq: List[int]) -> Dict[str, Any]:
    groups = []
    ranges = [(1,10),(11,20),(21,30),(31,40),(41,45)]
    for a,b in ranges:
        items=[{"n":n,"freq":freq[n]} for n in range(a,b+1)]
        total=sum(x["freq"] for x in items)
        items.sort(key=lambda x:(x["freq"], x["n"]))  # 오름차순
        groups.append({"range": f"{a}~{b}", "items": items, "total": total})
    return {"groups": groups}

# ---------- API ----------
def build_payload(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    feats = features(rows)
    freq_arr = frequency(feats)
    latest = max((r["round"] for r in rows), default=0)
    return {"latest": latest, "count": len(rows), "freq": freq_arr, "recent10": feats[-10:][::-1]}

def fallback_demo() -> Dict[str, Any]:
    rnd = random.Random(42)
    rows=[]
    base_round=1200
    for i in range(50):
        nums = sorted(rnd.sample(range(1,46), 6))
        rows.append({"round": base_round-i, "date": f"2024-01-{(i%28)+1:02d}", "nums": nums, "bonus": rnd.randint(1,45)})
    return build_payload(rows)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/analysis")
async def api_analysis(last: int = Query(100, ge=20, le=2000)):
    try:
        latest = await get_latest_round()
        start = max(1, latest - (last - 1))
        try:
            rows = await asyncio.wait_for(fetch_range(start, latest, batch_size=25), timeout=2.5)
        except asyncio.TimeoutError:
            rows = []
        base = build_payload(rows) if rows else fallback_demo()
        freq_arr = base["freq"]
        # ① 예측 번호 5세트 + 근거%
        prob = freq_prob(freq_arr)
        picks = []
        for i in range(5):
            s = pick_set_by_weights(prob, power=1.0, seed=100+i)
            picks.append({"numbers": s, "reasons": explain_set(s, freq_arr)})
        # ② 이번주 전략카드
        weekly = weekly_best_strategy(freq_arr, base["recent10"])
        # ③ 최근10회는 base["recent10"] 그대로, round jump는 프론트 입력으로 처리
        # ④ 구간별 번호 빈도
        intervals = interval_freq(freq_arr)
        # ⑤ 전략별 추천 상세
        strat_detail = []
        for name in ["보수형","균형형","고위험형"]:
            combos = top_k_sets(freq_arr, name, k=5)
            strat_detail.append({"name": name, "combos": combos, "note": "빈도·다양성 휴리스틱 기반"})
        payload = {
            "latest": base["latest"],
            "count": base["count"],
            "recent10": base["recent10"],
            "freq": freq_arr,
            "picks": picks,
            "weekly": weekly,
            "intervals": intervals,
            "strategies": strat_detail
        }
        return JSONResponse(payload, headers={"Cache-Control": "public, max-age=60"})
    except Exception as e:
        log.warning(f"/api/analysis fail: {e}")
        demo = fallback_demo()
        freq_arr = demo["freq"]
        prob = freq_prob(freq_arr)
        picks = []
        for i in range(5):
            s = pick_set_by_weights(prob, power=1.0, seed=200+i)
            picks.append({"numbers": s, "reasons": explain_set(s, freq_arr)})
        intervals = interval_freq(freq_arr)
        weekly = weekly_best_strategy(freq_arr, demo["recent10"])
        strat_detail = []
        for name in ["보수형","균형형","고위험형"]:
            combos = top_k_sets(freq_arr, name, k=5)
            strat_detail.append({"name": name, "combos": combos, "note": "데모"})
        return JSONResponse({
            "latest": demo["latest"], "count": demo["count"],
            "recent10": demo["recent10"], "freq": demo["freq"],
            "picks": picks, "weekly": weekly, "intervals": intervals,
            "strategies": strat_detail
        }, headers={"Cache-Control": "no-store"})

@app.get("/")
def root():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return HTMLResponse(DEFAULT_HTML)
