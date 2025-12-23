from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Float
from sqlalchemy.orm import relationship
from app.db.base import Base
import datetime

class CareProgram(Base):
    """
    The 90-Day Care Program Container.
    """
    __tablename__ = "care_programs"

    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"))
    title = Column(String, default="90-Day Wellness Journey")
    start_date = Column(DateTime, default=datetime.datetime.utcnow)
    end_date = Column(DateTime)
    status = Column(String, default="ACTIVE")
    phase = Column(Integer, default=1)
    
    member = relationship("Member", back_populates="programs")
    config = relationship("ProgramConfig", uselist=False, back_populates="program")
    logs = relationship("DailyLog", back_populates="program")
    adherence = relationship("AdherenceMetric", back_populates="program")

class ProgramConfig(Base):
    """
    Stores the "Configurable Expectations".
    """
    __tablename__ = "program_configs"

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("care_programs.id"))
    
    # --- THESE WERE MISSING ---
    nutrition_goals = Column(JSON, default={})
    strength_goals = Column(JSON, default={})
    clinical_goals = Column(JSON, default={})

    program = relationship("CareProgram", back_populates="config")

class AdherenceMetric(Base):
    __tablename__ = "adherence_metrics"

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("care_programs.id"))
    date = Column(String)
    
    nutrition_score = Column(Float, default=0.0)
    strength_score = Column(Float, default=0.0)
    clinical_score = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)
    
    details = Column(JSON)

    program = relationship("CareProgram", back_populates="adherence")