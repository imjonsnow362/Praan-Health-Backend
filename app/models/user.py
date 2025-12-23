from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base  # We will create this next

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    members = relationship("Member", back_populates="guardian")

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    age = Column(Integer)
    # Relationships
    guardian = relationship("User", back_populates="members")
    programs = relationship("CareProgram", back_populates="member")