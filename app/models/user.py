from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship  # <--- This function was getting overwritten!
from sqlalchemy.sql import func
from app.db.base import Base

class User(Base):
    """
    The Account Holder.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    members = relationship("Member", back_populates="guardian")

class Member(Base):
    """
    The Patient/Family Member.
    """
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    age = Column(Integer)
    gender = Column(String)
    
    # RENAMED to avoid conflict with sqlalchemy.orm.relationship
    relation_type = Column(String)  # e.g., "Mother", "Father"
    
    guardian = relationship("User", back_populates="members")
    programs = relationship("CareProgram", back_populates="member")