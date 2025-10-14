import os, random
from typing import Optional
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.staticfiles import StaticFiles

DATA_PATH = os.getenv("DATA_PATH", "static/sample_results.csv")
HIGH_CUT_DEFAULT = int(os.getenv("HIGH_CUT", "23"))

app = FastAPI(title="Lotto Predictor v2.1-fix", version="2.1-fix")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

def load_df(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8")
    needed = ["회차","날짜","번호1","번호2","번호3","번호4","번호5","번호6","보너스"]
    for c in needed:
        if c not in df.columns:
            raise ValueError(f"CSV에 '{c}' 컬럼이 없습니다.")
    num_cols = ["회차","번호1","번호2","번호3","번호4","번호5","번호6","보너스"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=num_cols)
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce").dt.date.astype(str)
    df = df.sort_values("회차").reset_index(drop=True)
    return df

def build_weights(df: pd.DataFrame):
    freq = [1.0]*46  # +1 smoothing
    for _,row in df.iterrows():
        for i in range(1,7):
            n = int(row[f"번호{i}"])
            if 1<=n<=45:
                freq[n]+=1.0
    return freq

def pick_weighted(weights):
    pool = list(range(1,46))
    w = [weights[n] for n in pool]
    chosen = []
    for _ in range(6):
        total = sum(w)
        r = random.random()*total
        idx = 0
        while r>=w[idx]:
            r -= w[idx]; idx += 1
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
    df = load_df(DATA_PATH)
    sub = df.tail(last).copy()
    recent = []
    for _,row in sub.iterrows():
        nums = sorted([int(row[f"번호{i}"]) for i in range(1,7)])
        s,odd,high = summary(nums, high_cut)
        recent.append({
            "회차": int(row["회차"]),
            "날짜": row["날짜"],
            "번호1": int(row["번호1"]),
            "번호2": int(row["번호2"]),
            "번호3": int(row["번호3"]),
            "번호4": int(row["번호4"]),
            "번호5": int(row["번호5"]),
            "번호6": int(row["번호6"]),
            "보너스": int(row["보너스"]),
            "sum": s, "odd": odd, "high": high
        })

    weights = build_weights(df)
    predicted_weighted = [pick_weighted(weights) for _ in range(5)]
    predicted_random = [sorted(random.sample(range(1,46), 6)) for _ in range(5)]

    buckets = {"1-9":0,"10-19":0,"20-29":0,"30-39":0,"40-45":0}
    total_balls = 0
    for _,row in sub.iterrows():
        for i in range(1,7):
            n = int(row[f"번호{i}"]); total_balls+=1
            if 1<=n<=9: buckets["1-9"]+=1
            elif n<=19: buckets["10-19"]+=1
            elif n<=29: buckets["20-29"]+=1
            elif n<=39: buckets["30-39"]+=1
            else: buckets["40-45"]+=1

    return JSONResponse({
        "ok": True,
        "sample_rounds": int(len(sub)),
        "total_balls": int(total_balls),
        "recent": recent,
        "buckets": buckets,
        "predicted": {
            "weighted": predicted_weighted,
            "random": predicted_random
        }
    })
