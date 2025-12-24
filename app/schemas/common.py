from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# Base for all responses
class MemberBase(BaseModel):
    name: str
    age: int
    gender: Optional[str] = None
    relation_type: str

class MemberCreate(MemberBase):
    user_id: int

class MemberResponse(MemberBase):
    id: int
    class Config:
        from_attributes = True


class ProgramConfigCreate(BaseModel):
    nutrition_goals: Dict[str, Any] # e.g. {"calories": 1500, "protein_g": 80}
    strength_goals: Dict[str, Any]  # e.g. {"sessions_per_week": 4}
    clinical_goals: Dict[str, Any]  # e.g. {"bp_check": "daily"}        