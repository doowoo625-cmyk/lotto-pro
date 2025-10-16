from __future__ import annotations
from typing import List
from pydantic import BaseModel, Field
from typing_extensions import Annotated

SixNums = Annotated[List[int], Field(min_length=6, max_length=6)]

class Draw(BaseModel):
    draw_no: int
    numbers: SixNums
    bonus: int = 0
    date: str | None = None

class StrategyPick(BaseModel):
    name: str | None = None
    name_ko: str | None = None
    numbers: SixNums
    score: float = 0.0
    rr: float = 0.0
    win: float = 0.0
    rationale: str | None = None

class PredictRequest(BaseModel):
    seed: int | None = None
    count: int = 5

class PredictResponse(BaseModel):
    last_draw: Draw
    best_strategy_key: str
    best_strategy_name_ko: str
    best_strategy_top5: List[StrategyPick]
    best3_by_priority_korean: List[StrategyPick]
    all_by_strategy_korean: dict[str, List[StrategyPick]]
