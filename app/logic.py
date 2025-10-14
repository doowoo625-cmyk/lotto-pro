
from __future__ import annotations
import random
from typing import List, Dict, Tuple
from .storage import read_last_draw
import math

NUM_RANGE = range(1, 46)

def _score_set(nums: List[int], last_nums: List[int]) -> float:
    # Heuristic score: lower is "better"
    # Components: distance from last draw, sum near mid, spread balance, odd-even balance
    nums_sorted = sorted(nums)
    last_set = set(last_nums)
    overlap = len(last_set.intersection(nums_sorted))
    # Prefer lower overlap with last draw (freshness)
    overlap_penalty = overlap * 2.5
    # Sum closeness to mid (~138 average sum for 6 numbers 1..45)
    target_sum = 138
    sum_dev = abs(sum(nums_sorted) - target_sum) / 10.0
    # Spread: prefer larger spread (max-min) and moderate gaps variance
    spread = nums_sorted[-1] - nums_sorted[0]
    spread_score = max(0, 25 - spread) / 8.0
    # Odd-even balance
    odd = sum(1 for n in nums_sorted if n % 2)
    even = 6 - odd
    balance_score = abs(odd - even) * 0.7
    # Adjacent penalty
    adj_pairs = sum(1 for a,b in zip(nums_sorted, nums_sorted[1:]) if b == a+1)
    adjacent_penalty = adj_pairs * 0.9
    # Duplicate endings penalty (same last digit)
    endings = [n % 10 for n in nums_sorted]
    dup_end_penalty = (6 - len(set(endings))) * 0.4
    return overlap_penalty + sum_dev + spread_score + balance_score + adjacent_penalty + dup_end_penalty

def _gen_candidates(strategy: str, count: int, rng: random.Random) -> List[List[int]]:
    # Different candidate generation styles
    if strategy == "Conservative":
        # Prefer mid-range numbers, avoid many adjacents
        pool = [n for n in NUM_RANGE if 8 <= n <= 38]
    elif strategy == "Balanced":
        pool = list(NUM_RANGE)
    elif strategy == "High-Risk":
        # Extremes & clusters
        pool = [n for n in NUM_RANGE if n <= 10 or n >= 36]
    else:
        pool = list(NUM_RANGE)
    cands = []
    while len(cands) < count:
        pick = sorted(rng.sample(pool, 6))
        if len({b-a for a,b in zip(pick, pick[1:]) if b==a+1}) <= 2:  # allow up to 2 adjacent steps patterns
            cands.append(pick)
    return cands

def generate_predictions(seed: int | None, count: int = 5):
    last = read_last_draw()
    last_nums = last["numbers"]
    rng = random.Random(seed)
    strategies = ["Conservative", "Balanced", "High-Risk"]
    result = {}
    best = []
    for s in strategies:
        cands = _gen_candidates(s, count, rng)
        scored = []
        for nums in cands:
            score = _score_set(nums, last_nums)
            rationale = []
            rationale.append(f"overlap_with_last={len(set(nums).intersection(last_nums))}")
            rationale.append(f"spread={nums[-1]-nums[0]}")
            rationale.append(f"odd_even={sum(1 for n in nums if n%2)}:{6 - sum(1 for n in nums if n%2)}")
            rationale.append("adjacents=" + str(sum(1 for a,b in zip(nums, nums[1:]) if b==a+1)))
            scored.append({
                "name": s,
                "numbers": nums,
                "score": round(float(score), 3),
                "rationale": ", ".join(rationale)
            })
        scored.sort(key=lambda x: x["score"])
        result[s] = scored
        best.append(scored[0])
    best.sort(key=lambda x: x["score"])
    return last, best, result
