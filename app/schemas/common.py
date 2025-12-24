from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class EnrollmentRequest(BaseModel):
    """
    Combines Program Metadata + Configurable Goals.
    Used in POST /programs/{member_id}/enroll
    """
    # [cite_start]Metadata [cite: 19]
    title: str = "90-Day Wellness Journey"
    description: Optional[str] = None
    
    # [cite_start]Configurable Expectations [cite: 20]
    nutrition_goals: Dict[str, Any] # e.g. {"calories": 1500, "protein_g": 90}
    strength_goals: Dict[str, Any]  # e.g. {"sessions_per_week": 4}
    clinical_goals: Dict[str, Any]  # e.g. {"check_in": "daily"}
    
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

class UserBase(BaseModel):
    email: str
    full_name: Optional[str] = None

class UserResponse(UserBase):
    id: int
    # This magic line nests the members inside the user
    members: List[MemberResponse] = [] 
    
    class Config:
        from_attributes = True        


class ProgramConfigCreate(BaseModel):
    nutrition_goals: Dict[str, Any] # e.g. {"calories": 1500, "protein_g": 80}
    strength_goals: Dict[str, Any]  # e.g. {"sessions_per_week": 4}
    clinical_goals: Dict[str, Any]  # e.g. {"bp_check": "daily"}        