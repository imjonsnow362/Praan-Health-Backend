from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class DailyLog(Base):
    __tablename__ = "daily_logs"
    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("care_programs.id"))
    log_type = Column(String) # NUTRITION, WORKOUT
    payload = Column(JSON)
    is_verified = Column(Boolean, default=False)
    program = relationship("CareProgram", back_populates="logs")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String)
    resource = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())