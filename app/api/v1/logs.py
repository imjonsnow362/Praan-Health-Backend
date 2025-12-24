from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.health import DailyLog
from app.models.program import CareProgram, AdherenceMetric
from app.services.ai_service import MockAIService
from app.schemas.health import LogResponse, MealExtractionResponse, LogCreate
import shutil
import os
import uuid
from datetime import datetime
import json

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/meals/analyze", response_model=MealExtractionResponse)
async def analyze_meal_photo(file: UploadFile = File(...)):
    """
    1. Receives image.
    2. Calls (Mock) AI Service.
    3. Returns extraction for user verification.
    """
    file_path = f"{UPLOAD_DIR}/{uuid.uuid4()}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    extraction = await MockAIService.analyze_meal_image(file_path)
    return extraction

@router.post("/logs", response_model=LogResponse)
def create_log(
    log_data: LogCreate, 
    db: Session = Depends(get_db)
):
    """
    Saves the verified data to the DB and triggers adherence calc.
    """
    # 1. Create the Log Object
    new_log = DailyLog(
        program_id=log_data.program_id,
        log_type=log_data.log_type,
        payload=log_data.payload,
        is_verified=True,
        timestamp=datetime.now() # Manually set timestamp
    )
    
    # 2. Save to DB
    db.add(new_log)
    db.commit()
    
    # REMOVED db.refresh(new_log) to prevent SQLite from clearing the timestamp
    
    # 3. Trigger Adherence Calculation
    calculate_adherence(db, log_data.program_id, log_data.payload)
    
    return new_log

def calculate_adherence(db: Session, program_id: int, latest_payload: dict):
    """
    The 'Logic' Engine: Compares Actual vs Config
    """
    program = db.query(CareProgram).filter(CareProgram.id == program_id).first()
    if not program or not program.config:
        return

    # Simple Logic: If protein > 20g, give points.
    protein = latest_payload.get("macros", {}).get("protein_g", 0)
    score = min(100, protein * 3) 
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    metric = db.query(AdherenceMetric).filter(
        AdherenceMetric.program_id == program_id, 
        AdherenceMetric.date == today
    ).first()
    
    if not metric:
        metric = AdherenceMetric(program_id=program_id, date=today)
    
    metric.nutrition_score = score
    metric.total_score = score 
    metric.details = {"last_protein": protein, "status": "calculated"}
    
    db.add(metric)
    db.commit()

@router.get("/adherence/{program_id}")
def get_adherence(program_id: int, db: Session = Depends(get_db)):
    today = datetime.now().strftime("%Y-%m-%d")
    metric = db.query(AdherenceMetric).filter(
        AdherenceMetric.program_id == program_id,
        AdherenceMetric.date == today
    ).first()
    return metric


@router.get("/{program_id}/history")
def get_log_history(program_id: int, db: Session = Depends(get_db)):
    """
    Fetch all logs (Meals, Workouts) for a specific program.
    """
    logs = db.query(DailyLog).filter(DailyLog.program_id == program_id).order_by(DailyLog.timestamp.desc()).all()
    return logs