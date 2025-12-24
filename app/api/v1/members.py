from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import Member, User
from app.schemas.common import MemberCreate, MemberResponse, UserResponse
from pydantic import BaseModel
from app.api.deps import get_current_user

router = APIRouter()

# --- 1. User Registration Schema ---
class UserCreate(BaseModel):
    email: str
    full_name: str
    password: str

# --- 2. The Register Endpoint (Fixes your issue) ---
@router.post("/register", tags=["Auth"])
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new Account Holder (User).
    This enables POST /api/v1/members/register
    """
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user.email, 
        full_name=user.full_name, 
        hashed_password=user.password  # In production, hash this!
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"id": new_user.id, "email": new_user.email}

# --- 3. Member Management Endpoints ---

@router.post("/", response_model=MemberResponse)
def create_member(member: MemberCreate, user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    # Validation: Ensure User ID in body matches Auth Header
    print(f"Debug: member.user_id = {member.user_id}, user_id = {user_id}")
    if member.user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot create member for another user")

    db_member = Member(**member.model_dump())
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member

@router.get("/{user_id}", response_model=list[MemberResponse])
def list_members(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all family members for a specific User"""
    return db.query(Member).filter(Member.user_id == user_id).all()



@router.get("/{user_id}", response_model=list[MemberResponse])
def list_members(user_id: int, db: Session = Depends(get_db)):
    return db.query(Member).filter(Member.user_id == user_id).all()

# --- NEW: Get All Users & Families (For Admin View) ---
@router.get("/users/all", response_model=list[UserResponse])
def get_all_users_with_families(db: Session = Depends(get_db)):
    """
    Fetches every user and nests their family members in the response.
    """
    # SQLAlchemy automatically handles the join via the 'members' relationship
    users = db.query(User).all() 
    return users    