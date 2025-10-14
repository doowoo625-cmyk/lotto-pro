import os, csv, random
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

DATA_PATH = os.getenv("DATA_PATH", "static/sample_results.csv")
HIGH_CUT_DEFAULT = int(os.getenv("HIGH_CUT", "23"))

app = FastAPI(title="Lotto Predictor v2.1-stable", version="2.1-stable")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

def load_rows(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            try:
                row = {
                    "회차": int(rec["회차"]),
                    "날짜": str(rec["날짜"]),
                    "번호1": int(rec["번호1"]),
                    "번호2": int(rec["번호2"]),
                    "번호3": int(rec["번호3"]),
                    "번호4": int(rec["번호4"]),
                    "번호5": int(rec["번호5"]),
                    "번호6": int(rec["번호6"]),
                    "보너스": int(rec["보너스"]),
                }
            except:
                continue
            rows.append(row)
    rows.sort(key=lambda x: x["회차"])
    return rows

def build_weights(rows: List[Dict[str, Any]]):
    freq = [1.0]*46
    for r in rows:
        for k in ["번호1","번호2","번호3","번호4","번호5","번호6"]:
            n = r[k]
            if 1<=n<=45: freq[n]+=1.0
    return freq

def pick_weighted(weights):
    pool = list(range(1,46))
    w = [weights[n] for n in pool]
    chosen = []
    for _ in range(6):
        total = sum(w)
        r = random.random()*total
        idx=0
        while r>=w[idx]:
            r-=w[idx]; idx+=1
        chosen.append(pool[idx])
        pool.pop(idx); w.pop(idx)
    return sorted(chosen)

def summary(nums, high_cut: int):
    s = sum(nums)
    odd = sum(1 for x in nums if x%2==1)
    high = sum(1 for x in nums if x>=high_cut)
    return s, odd, high

@app.get("/api/analysis")
def api_analysis(last: Optional[int]=Query(default=10, ge=1, le=200),
                 high_cut: Optional[int]=Query(default=HIGH_CUT_DEFAULT, ge=1, le=45)):
    rows = load_rows(DATA_PATH)
    sub = rows[-last:] if last <= len(rows) else rows[:]
    recent = []
    for r in sub:
        nums = sorted([r["번호1"],r["번호2"],r["번호3"],r["번호4"],r["번호5"],r["번호6"]])
        s,odd,high = summary(nums, high_cut)
        item = dict(r)
        item.update({"sum": s, "odd": odd, "high": high})
        recent.append(item)

    weights = build_weights(rows)
    predicted_weighted = [pick_weighted(weights) for _ in range(5)]
    predicted_random = [sorted(random.sample(range(1,46), 6)) for _ in range(5)]

    buckets = {"1-9":0,"10-19":0,"20-29":0,"30-39":0,"40-45":0}
    total_balls = 0
    for r in sub:
        for k in ["번호1","번호2","번호3","번호4","번호5","번호6"]:
            n = r[k]; total_balls+=1
            if 1<=n<=9: buckets["1-9"]+=1
            elif n<=19: buckets["10-19"]+=1
            elif n<=29: buckets["20-29"]+=1
            elif n<=39: buckets["30-39"]+=1
            else: buckets["40-45"]+=1

    return JSONResponse({
        "ok": True,
        "sample_rounds": len(sub),
        "total_balls": total_balls,
        "recent": recent,
        "buckets": buckets,
        "predicted": {
            "weighted": predicted_weighted,
            "random": predicted_random
        }
    })
