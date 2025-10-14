
from __future__ import annotations
import random
from typing import List, Dict
from collections import Counter
from .storage import read_last_draw, read_recent10

NUM_RANGE = range(1,46)

def _recent_freq()->Counter:
    draws = read_recent10()
    cnt = Counter()
    for d in draws:
        cnt.update(d["numbers"])
    return cnt

def _range_buckets()->Dict[str, List[int]]:
    return {
        "1-10": list(range(1,11)),
        "11-20": list(range(11,21)),
        "21-30": list(range(21,31)),
        "31-40": list(range(31,41)),
        "41-45": list(range(41,46)),
    }

def _per_number_range_freq(cnt: Counter)->Dict[str, Dict[str,int]]:
    out: Dict[str, Dict[str,int]] = {}
    for label, nums in _range_buckets().items():
        out[label] = {str(n): int(cnt.get(n,0)) for n in nums}
    return out

def _range_strengths(per: Dict[str, Dict[str,int]]):
    strengths = {label: sum(d.values()) for label, d in per.items()}
    sortd = sorted(strengths.items(), key=lambda x: x[1], reverse=True)
    top2 = [sortd[0][0], sortd[1][0]] if len(sortd)>=2 else [sortd[0][0]]
    bottom = sortd[-1][0]
    return strengths, top2, bottom

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
    basis = "최근10회"
    details = " | ".join([f"{n:02d}/{f}/{p}%/{basis}" for n,f,p in zip(nums, fvals, perc)])
    win = min(95.0, max(5.0, score*100.0/(reward+1.0)))
    return dict(reward=round(reward,3), risk=round(risk,3), score=round(score,3),
                rr=round(rr,3), win=round(win,1), rationale=details)

def generate_predictions(seed: int | None, count: int = 5):
    last = read_last_draw()
    recent = read_recent10()
    recent_cnt = _recent_freq()
    weights = {n: (recent_cnt.get(n,0) + 1) for n in range(1,46)}

    rng = random.Random(seed)
    strategies = ["Conservative","Balanced","High-Risk"]
    all_by_strategy: Dict[str, List[Dict]] = {}
    best_per_strategy: List[Dict] = []
    global_max_score = 1e-9

    # score 계산 및 전역 최대값 파악
    for s in strategies:
        cands = _gen_candidates(s, count, rng, weights)
        scored = []
        for nums in cands:
            m = _metrics(nums, recent_cnt)
            global_max_score = max(global_max_score, m["score"])
            scored.append({"name": s, "numbers": nums, **m})
        scored.sort(key=lambda x: x["score"], reverse=True)
        all_by_strategy[s] = scored
        best_per_strategy.append(scored[0])

    # best 3를 score 내림차순(우선순위 1,2,3)으로 정렬
    best_per_strategy.sort(key=lambda x: x["score"], reverse=True)

    per = _per_number_range_freq(recent_cnt)
    _, top2, bottom = _range_strengths(per)

    basis = None
    recent_last = None
    if recent:
        basis = {"draw_no": recent[0]["draw_no"], "numbers": recent[0]["numbers"], "bonus": recent[0]["bonus"]}
        recent_last = {"draw_no": recent[-1]["draw_no"], "numbers": recent[-1]["numbers"], "bonus": recent[-1]["bonus"]}

    return last, basis, recent_last, best_per_strategy, all_by_strategy, per, top2, bottom
