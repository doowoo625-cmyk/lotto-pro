# ==== (기존 app/main.py 상단/중간은 그대로 두고, 맨 아래 API들 아래에 이 블록을 추가) ====

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Dict, Tuple  # ✅ 이 줄 추가
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles


def build_freq(items: List[dict]) -> Dict[int, int]:
    freq = {i: 0 for i in range(1, 46)}
    for it in items:
        for n in it["numbers"]:
            freq[n] += 1
    return freq

def score_combo(nums: List[int], freq: Dict[int, int]) -> Tuple[float, float, float]:
    """reward, risk, score 계산"""
    nums = sorted(nums)
    # reward: 빈도 합의 평균
    reward = sum(freq[n] for n in nums) / 6.0
    # risk: 분산 + 인접 패널티(연속/근접 수 벌점)
    mean = sum(nums) / 6.0
    variance = sum((n - mean) ** 2 for n in nums) / 6.0
    adjacency_penalty = 0.0
    for a, b in zip(nums, nums[1:]):
        if abs(a - b) == 1:
            adjacency_penalty += 1.0
        elif abs(a - b) == 2:
            adjacency_penalty += 0.5
    risk = variance / 100.0 + adjacency_penalty * 0.3
    score = reward / (1.0 + risk)
    return reward, risk, score

def sample_pool_by_strategy(freq: Dict[int, int], strategy: str, seed: int) -> List[List[int]]:
    """
    간단 규칙 기반 샘플링:
      - 보수형: 상위 빈도 구간에서 고르게
      - 균형형: 상/중 빈도 섞기
      - 고위험형: 저빈도·극단값 가중, 연속 패널티 완화
    """
    rnd = random.Random(seed)
    items = sorted([(n, c) for n, c in freq.items()], key=lambda x: (-x[1], x[0]))
    top = [n for n, _ in items[:20]]
    mid = [n for n, _ in items[20:35]]
    low = [n for n, _ in items[35:]]

    pool = set()
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
        if len(picks) == 6 and max(picks) <= 45 and min(picks) >= 1:
            pool.add(tuple(sorted(picks)))
    return [list(t) for t in pool]

def make_strategy_result(items: List[dict], latest_draw: int) -> dict:
    """3전략 상위 5세트씩 + 전체 상위5 반환 구조 생성"""
    freq = build_freq(items)

    out_all: Dict[str, List[dict]] = {}
    order = ["보수형", "균형형", "고위험형"]

    for i, name in enumerate(order):
        combos = sample_pool_by_strategy(freq, name, seed=latest_draw * 31 + i * 7)
        scored = []
        for nums in combos:
            reward, risk, score = score_combo(nums, freq)
            rr = round((reward / (1.0 + risk)), 3)
            win = round(min(85.0, 20 + reward * 1.5 - risk * 10), 1)  # 대략치(표시용)
            scored.append({
                "name": name,
                "name_ko": name,
                "numbers": sorted(nums),
                "reward": round(reward, 3),
                "risk": round(risk, 3),
                "score": round(score, 3),
                "rr": rr,
                "win": win,
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        out_all[name] = scored[:5]

    # 전체 풀에서 상위 5 (전략 섞여도 OK)
    pool_top = []
    for name in order:
        pool_top += out_all[name]
    pool_top.sort(key=lambda x: x["score"], reverse=True)
    best_top5 = pool_top[:5]

    # 이번 주 추천 전략: 각 전략의 1위 → 합산점수 순으로 정렬
    best3 = [out_all[name][0] for name in order if out_all[name]]
    best3.sort(key=lambda x: x["score"], reverse=True)

    return {
        "best3_by_priority_korean": best3,
        "all_by_strategy_korean": out_all,
        "best_strategy_top5": best_top5,
    }

@app.post("/api/predict")
async def api_predict():
    """
    최신 회차 기준 최근 100회 데이터를 바탕으로 3전략 추천 세트를 만든다.
    프런트 요구 필드명에 맞춰 반환.
    """
    cache = read_cache()

    # 최신 회차 확보
    latest = max_cached_draw(cache)
    if latest <= 0:
        latest = await find_latest_draw_no(cache)
        cache = read_cache()  # find_latest_draw_no가 cache 갱신하므로 재로드

    # 최근 100회 확보 (캐시 보강)
    items = await ensure_recent(cache, latest, 100)
    write_cache(cache)

    payload = make_strategy_result(items, latest_draw=latest)
    return JSONResponse(payload)
