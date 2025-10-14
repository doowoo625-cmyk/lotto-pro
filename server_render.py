# server_render.py — v3.0-final (Render-ready, cached, robust)
import os, time, asyncio, random, logging, webbrowser
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
STATIC_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HTML = "<!doctype html><meta charset='utf-8'><title>준비중</title><body>static/index.html 필요</body>"
if not (STATIC_DIR / "index.html").exists():
    (STATIC_DIR / "index.html").write_text(DEFAULT_HTML, encoding="utf-8")

app = FastAPI(title="Lotto Predictor", version="3.0-final")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=700)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ---------------- Fetch & Cache ----------------
HDRS = {"User-Agent": "Mozilla/5.0"}
BASE_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo="
TTL_SEC = 1800  # 30m
_round_cache: Dict[int, Dict[str, Any]] = {}
_round_ts: Dict[int, float] = {}
_latest_cache = {"value": None, "ts": 0.0}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lotto")

def _get_cache(n: int) -> Optional[Dict[str, Any]]:
    ts = _round_ts.get(n)
    if ts and (time.time() - ts) < TTL_SEC:
        return _round_cache.get(n)
    return None

def _set_cache(n: int, payload: Dict[str, Any]) -> None:
    _round_cache[n] = payload
    _round_ts[n] = time.time()

async def fetch_round_async(client: httpx.AsyncClient, n: int, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
    c = _get_cache(n)
    if c is not None:
        return c
    try:
        r = await client.get(f"{BASE_URL}{n}", headers=HDRS, timeout=timeout)
        j = r.json()
        if j.get("returnValue") != "success":
            return None
        nums = [j["drwtNo1"], j["drwtNo2"], j["drwtNo3"], j["drwtNo4"], j["drwtNo5"], j["drwtNo6"]]
        d = {"round": n, "date": j.get("drwNoDate",""), "nums": nums, "bonus": j.get("bnusNo")}
        _set_cache(n, d)
        return d
    except Exception as e:
        log.warning(f"fetch_round_async({n}) failed: {e}")
        return None

async def fetch_range(start: int, end: int, batch: int = 25) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    async with httpx.AsyncClient(http2=True) as client:
        for b in range(start, end+1, batch):
            e = min(end, b + batch - 1)
            tasks = [fetch_round_async(client, n) for n in range(b, e+1)]
            chunk = await asyncio.gather(*tasks)
            out.extend([x for x in chunk if x])
    return out

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

# ---------------- Analytics ----------------
def features(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        nums = r["nums"]; s = sum(nums)
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
    tot = sum(freq[1:]) or 1
    return [0.0]+[freq[i]/tot for i in range(1,46)]

def pick_set_by_weights(wts: List[float], power: float = 1.0, seed: Optional[int]=None) -> List[int]:
    import random as R
    rnd = R.Random(seed) if seed is not None else R
    w = [0.0]+[max(1e-9, pow(wts[i], power)) for i in range(1,46)]
    s=[]; trials=0
    while len(s)<6 and trials<500:
        trials+=1; r = rnd.random()*sum(w[1:]); acc=0.0
        for i in range(1,46):
            acc+=w[i]
            if r<=acc and i not in s:
                s.append(i); break
    s.sort(); return s

def explain_set(ns: List[int], freq: List[int]) -> List[Dict[str, Any]]:
    vals=[freq[n] for n in ns]; denom=sum(vals) or 1
    return [{"n": n, "pct": round(100.0 * v / denom, 1), "basis": "출현빈도", "freq": v} for n,v in zip(ns, vals)]

def rr_score(ns: List[int], freq: List[int]):
    vals=[freq[n] for n in ns]
    if not vals: return (0.0,0.0,0.0)
    m = sum(vals)/len(vals)
    var = sum((v-m)**2 for v in vals)/len(vals)
    adj = sum(1 for a,b in zip(ns,ns[1:]) if abs(a-b)==1)
    risk = var/10.0 + adj*0.2
    reward = m
    score = reward / (1.0 + risk)
    return (round(reward,2), round(risk,2), round(score,2))

def top_k_sets(freq: List[int], strategy: str, k: int = 5) -> List[Dict[str, Any]]:
    p = freq_prob(freq); out=[]
    seed_base = {"보수형":11,"균형형":22,"고위험형":33}.get(strategy,0)
    import random as R
    for i in range(k*3):
        if strategy=="보수형":
            s = pick_set_by_weights(p, power=1.5, seed=seed_base+i)
        elif strategy=="고위험형":
            s = pick_set_by_weights(p, power=0.6, seed=seed_base+i)
            rnd = R.Random(seed_base+i)
            for _ in range(rnd.randint(1,2)):
                rep = rnd.randint(1,45)
                if rep not in s:
                    s[rnd.randrange(0,6)] = rep
            s = sorted(set(s))
            while len(s)<6:
                x=rnd.randint(1,45)
                if x not in s: s.append(x)
            s.sort()
        else:
            s = pick_set_by_weights(p, power=1.0, seed=seed_base+i)
        reward, risk, score = rr_score(s, freq)
        out.append({"numbers": s, "reward": reward, "risk": risk, "score": score})
    if strategy=="고위험형":
        out.sort(key=lambda x:(x["score"], x["reward"]), reverse=True)
    else:
        out.sort(key=lambda x:x["score"], reverse=True)
    return out[:k]

def weekly_best_strategy(freq: List[int], recent10: List[Dict[str, Any]]) -> Dict[str, Any]:
    diversity = len(set(sum([r["nums"] for r in recent10], []))) if recent10 else 0
    top = sorted([(n,freq[n]) for n in range(1,46)], key=lambda x:x[1], reverse=True)[:10]
    top_sum = sum(f for n,f in top)
    if diversity >= 35 and top_sum <= 30: name="균형형"
    elif diversity < 28: name="고위험형"
    else: name="보수형"
    combos = top_k_sets(freq, name, k=1)
    combo = combos[0] if combos else {"numbers":[1,2,3,4,5,6], "score":0, "reward":0, "risk":0}
    winrate = round(min(2.0 + (combo["score"]/10.0), 9.5), 2)
    rr = round((combo["reward"] / (1 + combo["risk"])), 2)
    return {"name": name, "avg_score": combo["score"], "rr": rr, "winrate": winrate, "set": combo["numbers"]}

def interval_freq(freq: List[int]) -> Dict[str, Any]:
    groups=[]; ranges=[(1,10),(11,20),(21,30),(31,40),(41,45)]
    for a,b in ranges:
        items=[{"n":n,"freq":freq[n]} for n in range(a,b+1)]
        total=sum(x["freq"] for x in items)
        items.sort(key=lambda x:(x["freq"], x["n"]))
        groups.append({"range": f"{a}~{b}", "items": items, "total": total})
    return {"groups": groups}

# ---------------- API ----------------
def build_payload(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    feats = features(rows); freq_arr = frequency(feats)
    latest = max((r["round"] for r in rows), default=0)
    return {"latest": latest, "count": len(rows), "freq": freq_arr, "recent10": feats[-10:][::-1]}

def fallback_demo(n: int = 120) -> Dict[str, Any]:
    rnd = R = random.Random(42); rows=[]; base_round=1200
    for i in range(n):
        nums = sorted(random.sample(range(1,46), 6))
        rows.append({"round": base_round-i, "date": f"2024-01-{(i%28)+1:02d}", "nums": nums, "bonus": random.randint(1,45)})
    return build_payload(rows)

@app.get("/health")
def health(): return {"ok": True}

@app.get("/api/analysis")
async def api_analysis(
    last: int = Query(10, ge=10, le=2000, description="가져올 회차 수(최신 기준)"),
    anchor: Optional[int] = Query(None, description="기준 회차(이 회차 포함 최근 last개)"),
):
    try:
        latest = await get_latest_round()
        end = anchor if anchor else latest
        start = max(1, end - (last - 1))
        try:
            rows = await asyncio.wait_for(fetch_range(start, end, batch=25), timeout=3.0)
        except asyncio.TimeoutError:
            rows = []
        base = build_payload(rows) if rows else fallback_demo(last)
        freq_arr = base["freq"]
        prob = [0.0]+[max(1e-9, f)/max(1, sum(freq_arr[1:])) for f in freq_arr[1:]]
        # picks (5 sets)
        def one_set(seed):
            ns = pick_set_by_weights(prob, power=1.0, seed=seed)
            return {"numbers": ns, "reasons": explain_set(ns, freq_arr)}
        picks = [one_set(100+i) for i in range(5)]
        weekly = weekly_best_strategy(freq_arr, base["recent10"])
        intervals = interval_freq(freq_arr)
        strategies = [{"name": name, "combos": top_k_sets(freq_arr, name, k=5), "note": "빈도·다양성 휴리스틱 기반"}
                      for name in ["보수형","균형형","고위험형"]]
        return JSONResponse({
            "anchor": end, "latest": latest, "count": base["count"],
            "recent10": base["recent10"], "freq": freq_arr,
            "picks": picks, "weekly": weekly, "intervals": intervals,
            "strategies": strategies
        }, headers={"Cache-Control": "public, max-age=60"})
    except Exception as e:
        log.warning(f"/api/analysis fail: {e}")
        demo = fallback_demo(last)
        freq_arr = demo["freq"]
        prob = [0.0]+[max(1e-9, f)/max(1, sum(freq_arr[1:])) for f in freq_arr[1:]]
        def one_set(seed):
            ns = pick_set_by_weights(prob, power=1.0, seed=seed)
            return {"numbers": ns, "reasons": explain_set(ns, freq_arr)}
        picks = [one_set(200+i) for i in range(5)]
        weekly = weekly_best_strategy(freq_arr, demo["recent10"])
        intervals = interval_freq(freq_arr)
        strategies = [{"name": name, "combos": top_k_sets(freq_arr, name, k=5), "note": "데모"} for name in ["보수형","균형형","고위험형"]]
        return JSONResponse({
            "anchor": None, "latest": demo["latest"], "count": demo["count"],
            "recent10": demo["recent10"], "freq": demo["freq"],
            "picks": picks, "weekly": weekly, "intervals": intervals,
            "strategies": strategies
        }, headers={"Cache-Control": "no-store"})

@app.get("/")
def root():
    idx = STATIC_DIR / "index.html"
    if idx.exists(): return FileResponse(idx)
    return HTMLResponse(DEFAULT_HTML)
