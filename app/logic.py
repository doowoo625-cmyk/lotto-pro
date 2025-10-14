
from __future__ import annotations
import random
from typing import List, Dict
from collections import Counter
from .storage import read_last_draw, read_recent

NUM_RANGE = range(1,46)

STRAT_KEYS = ["Conservative","Balanced","High-Risk"]
STRAT_KO = {"Conservative":"보수형","Balanced":"균형형","High-Risk":"고위험형"}

def _recent_freq(window:int|None=None)->Counter:
    draws = read_recent()
    if window is not None and window>0 and len(draws)>window:
        draws = draws[-window:]
    cnt = Counter()
    for d in draws:
        cnt.update(d["numbers"])
    return cnt

def _gen_candidates(strategy: str, count: int, rng: random.Random, weights: Dict[int, float]) -> List[List[int]]:
    pool = list(NUM_RANGE)
    if strategy == "Conservative":
        pool = [n for n in pool if 8 <= n <= 38]
    elif strategy == "High-Risk":
        pool = [n for n in pool if n <= 10 or n >= 36]
    cands = []
    while len(cands) < count:
        pick = []
        available = pool[:]
        local_w = [weights.get(n, 1.0) for n in available]
        for _ in range(6):
            tot = sum(local_w)
            r = rng.random() * tot
            acc = 0.0
            idx = 0
            for i, w in enumerate(local_w):
                acc += w
                if acc >= r:
                    idx = i
                    break
            pick.append(available[idx])
            available.pop(idx); local_w.pop(idx)
        pick.sort()
        cands.append(pick)
    return cands

def _metrics(nums: List[int], freq: Dict[int,int]):
    fvals = [freq.get(n,0) for n in nums]
    reward = sum(fvals)/len(fvals)
    mean = sum(nums)/len(nums)
    var = sum((x-mean)**2 for x in nums)/len(nums)
    adj = sum(1 for a,b in zip(nums, nums[1:]) if b==a+1)
    risk = (var/100.0) + (adj*0.8)
    score = reward / (1.0 + risk)
    rr = reward / (risk + 1e-6)
    total_counts = sum(freq.values()) or 1
    perc = [round((freq.get(n,0)/total_counts)*100,1) for n in nums]
    basis = "최근N회"
    details = " | ".join([f"{n:02d}/{f}/{p}%/{basis}" for n,f,p in zip(nums, fvals, perc)])
    win = min(95.0, max(5.0, score*100.0/(reward+1.0)))
    return dict(reward=round(reward,3), risk=round(risk,3), score=round(score,3),
                rr=round(rr,3), win=round(win,1), rationale=details)

def compute_all(seed:int|None, count:int=5, window:int=10):
    last = read_last_draw()
    recent_cnt = _recent_freq(window)
    weights = {n: (recent_cnt.get(n,0) + 1) for n in range(1,46)}
    rng = random.Random(seed)

    all_by_strategy: Dict[str, List[Dict]] = {}
    best_per_strategy: Dict[str, Dict] = {}
    best_key = None; best_score = -1e9

    for s in STRAT_KEYS:
        cands = _gen_candidates(s, count, rng, weights)
        scored = []
        for nums in cands:
            m = _metrics(nums, recent_cnt)
            scored.append({"name": s, "name_ko": STRAT_KO[s], "numbers": nums, **m})
        scored.sort(key=lambda x: x["score"], reverse=True)
        all_by_strategy[s] = scored
        best_per_strategy[s] = scored[0]
        if scored[0]["score"] > best_score:
            best_score = scored[0]["score"]; best_key = s

    best_top5 = all_by_strategy[best_key][:5]
    # section 2 order: 균형형 → 보수형 → 고위험형
    best3 = [best_per_strategy[k] for k in ["Balanced","Conservative","High-Risk"]]
    # section 3 order: 보수형 → 균형형 → 고위험형
    all_korean = {STRAT_KO[k]: all_by_strategy[k] for k in ["Conservative","Balanced","High-Risk"]}

    return dict(last=last, best_key=best_key, best_name_ko=STRAT_KO[best_key],
                best_top5=best_top5, best3=best3, all_korean=all_korean)

def range_freq(window:int=10):
    draws = read_recent()
    if window>0 and len(draws)>window:
        draws = draws[-window:]
    cnt = Counter()
    for d in draws:
        cnt.update(d["numbers"])
    groups = {
        "1-10": list(range(1,11)),
        "11-20": list(range(11,21)),
        "21-30": list(range(21,31)),
        "31-40": list(range(31,41)),
        "41-45": list(range(41,46)),
    }
    out = {}
    for label, nums in groups.items():
        out[label] = {str(n): int(cnt.get(n,0)) for n in nums}
    strengths = {label: sum(v.values()) for label,v in out.items()}
    sorted_groups = sorted(strengths.items(), key=lambda x: x[1], reverse=True)
    top2 = [sorted_groups[0][0], sorted_groups[1][0]] if len(sorted_groups)>=2 else [sorted_groups[0][0]]
    bottom = sorted_groups[-1][0]
    return out, top2, bottom
