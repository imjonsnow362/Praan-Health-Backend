from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Float
from sqlalchemy.orm import relationship
from app.db.base import Base
import datetime

class CareProgram(Base):
    __tablename__ = "care_programs"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"))
    start_date = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="ACTIVE")
    
    member = relationship("Member", back_populates="programs")
    config = relationship("ProgramConfig", uselist=False, back_populates="program")
    logs = relationship("DailyLog", back_populates="program")
    adherence = relationship("AdherenceMetric", back_populates="program")

class ProgramConfig(Base):
    __tablename__ = "program_configs"
    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("care_programs.id"))
    nutrition_goals = Column(JSON)
    program = relationship("CareProgram", back_populates="config")

class AdherenceMetric(Base):
    __tablename__ = "adherence_metrics"
    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("care_programs.id"))
    date = Column(String)
    total_score = Column(Float)
    program = relationship("CareProgram", back_populates="adherence")