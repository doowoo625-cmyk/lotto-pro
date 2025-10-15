
from __future__ import annotations
from pydantic import BaseModel, Field, conlist
from typing import Optional, List, Dict

class Draw(BaseModel):
    draw_no: int
    numbers: conlist(int, min_length=6, max_length=6)
    bonus: int
    date: str | None = None

class StrategyPick(BaseModel):
    name: str
    name_ko: str
    numbers: conlist(int, min_length=6, max_length=6)
    reward: float
    risk: float
    score: float
    rr: float
    win: float
    rationale: str

class PredictRequest(BaseModel):
    seed: Optional[int] = Field(default=None)
    count: int = Field(default=5, ge=1, le=50)

class PredictResponse(BaseModel):
    last_draw: Draw
    best_strategy_key: str
    best_strategy_name_ko: str
    best_strategy_top5: List[StrategyPick]
    best3_by_priority_korean: List[StrategyPick]
    all_by_strategy_korean: Dict[str, List[StrategyPick]]
