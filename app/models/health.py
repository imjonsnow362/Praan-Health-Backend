from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base

class DailyLog(Base):
    """
    Unified table for all health events.
    """
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("care_programs.id"))
    log_type = Column(String) # NUTRITION, WORKOUT, CLINICAL
    payload = Column(JSON)
    is_verified = Column(Boolean, default=False)
    
    # --- THIS WAS MISSING ---
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    program = relationship("CareProgram", back_populates="logs")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer)
    target_member_id = Column(Integer)
    action = Column(String)
    resource = Column(String)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())