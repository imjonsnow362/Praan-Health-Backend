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

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    # In a real app, password updates require specific endpoints/hashing

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    relation_type: Optional[str] = None

class ProgramUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None # e.g., "PAUSED", "COMPLETED"
    phase: Optional[int] = None    