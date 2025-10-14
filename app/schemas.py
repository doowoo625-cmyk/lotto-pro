
from __future__ import annotations
from pydantic import BaseModel, Field, conlist
from typing import Optional, List, Dict

class Draw(BaseModel):
    draw_no: int = 0
    numbers: conlist(int, min_length=6, max_length=6)
    bonus: int = 0

class PredictRequest(BaseModel):
    seed: Optional[int] = Field(default=None, description="Optional seed for reproducibility")
    count: int = Field(default=5, ge=1, le=50, description="How many candidate sets to generate per strategy")

class StrategyPick(BaseModel):
    name: str
    numbers: conlist(int, min_length=6, max_length=6)
    score: float
    rationale: str

class PredictResponse(BaseModel):
    last_draw: Draw
    label: str = "Lower score = higher probability"
    priority_sorted: List[StrategyPick]
    all_candidates: Dict[str, List[StrategyPick]]
