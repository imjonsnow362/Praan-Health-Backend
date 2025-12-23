from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import Member
from app.schemas.common import MemberCreate, MemberResponse

router = APIRouter()

@router.post("/", response_model=MemberResponse)
def create_member(member: MemberCreate, db: Session = Depends(get_db)):
    db_member = Member(**member.model_dump())
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member

@router.get("/{user_id}", response_model=list[MemberResponse])
def list_members(user_id: int, db: Session = Depends(get_db)):
    return db.query(Member).filter(Member.user_id == user_id).all()