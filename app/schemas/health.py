from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

# --- Meal Logging ---
class MealExtractionResponse(BaseModel):
    """What the Mock AI returns to the Frontend"""
    food_items: List[str]
    calories: int
    macros: Dict[str, int]
    confidence: float

class LogCreate(BaseModel):
    program_id: int
    log_type: str  # "NUTRITION", "WORKOUT", "CLINICAL"
    
    # We use a flexible Dict because payload varies by type
    # This matches our JSONB column in Postgres
    payload: Dict[str, Any] 

class LogResponse(LogCreate):
    id: int
    timestamp: datetime
    is_verified: bool
    
    class Config:
        from_attributes = True

# --- Adherence ---
class AdherenceResponse(BaseModel):
    date: str
    nutrition_score: float
    strength_score: float
    total_score: float
    details: Dict[str, Any] # "Target vs Actual"