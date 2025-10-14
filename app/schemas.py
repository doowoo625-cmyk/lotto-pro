
from __future__ import annotations
from pydantic import BaseModel, Field, conlist
from typing import Optional, List, Dict

class Draw(BaseModel):
    draw_no: int = 0
    numbers: conlist(int, min_length=6, max_length=6)
    bonus: int = 0

class PredictRequest(BaseModel):
    seed: Optional[int] = Field(default=None)
    count: int = Field(default=5, ge=1, le=50)

class StrategyPick(BaseModel):
    name: str
    numbers: conlist(int, min_length=6, max_length=6)
    reward: float
    risk: float
    score: float
    rr: float
    win: float
    rationale: str

class PredictResponse(BaseModel):
    last_draw: Draw
    label: str = "Higher score = better (Reward ÷ (1+Risk))"
    priority_sorted: List[StrategyPick]  # descending by score
    all_candidates: Dict[str, List[StrategyPick]]
    range_freq: Dict[str, Dict[str, int]]  # per-number freq by ranges
    top_ranges: List[str]
    bottom_range: str
    basis_draw: Draw | None = None  # 기준 회차(최근10의 첫 항목)
    recent_last: Draw | None = None  # 직전 회차(최근10의 마지막 항목)
