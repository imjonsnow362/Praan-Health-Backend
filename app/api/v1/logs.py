from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.health import DailyLog
from app.models.program import CareProgram, AdherenceMetric, ProgramConfig
from app.services.ai_service import MockAIService
from app.schemas.health import LogResponse, MealExtractionResponse
import shutil
import os
import uuid
from datetime import datetime
import json

router = APIRouter()

# Just helper to save file locally
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/meals/analyze", response_model=MealExtractionResponse)
async def analyze_meal_photo(file: UploadFile = File(...)):
    """
    1. Receives image.
    2. Calls (Mock) AI Service.
    3. Returns extraction for user verification.
    """
    # 1. Save file locally (simulating S3/GCS upload)
    file_path = f"{UPLOAD_DIR}/{uuid.uuid4()}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Call AI Service (Simulates 1.5s delay)
    extraction = await MockAIService.analyze_meal_image(file_path)
    
    return extraction

@router.post("/logs", response_model=LogResponse)
def create_log(
    program_id: int,
    log_type: str, 
    payload: dict,
    db: Session = Depends(get_db)
):
    """
    Saves the verified data to the DB and triggers adherence calc.
    """
    # 1. Save Log
    new_log = DailyLog(
        program_id=program_id,
        log_type=log_type,
        payload=payload,
        is_verified=True
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    
    # 2. Trigger Adherence Calculation (Simplified for Prototype)
    # In production, this would be an async background task (Celery/PubSub)
    calculate_adherence(db, program_id, payload)
    
    return new_log

def calculate_adherence(db: Session, program_id: int, latest_payload: dict):
    """
    The 'Logic' Engine: Compares Actual vs Config
    """
    # Fetch Program Config
    program = db.query(CareProgram).filter(CareProgram.id == program_id).first()
    if not program or not program.config:
        return

    # Example Logic: Nutrition Protocol
    # Target: 2000 cal. Actual: Sum of today's logs.
    
    # Simple Logic for Assignment:
    # If the meal has protein > 20g, give 20 points.
    protein = latest_payload.get("macros", {}).get("protein_g", 0)
    score = min(100, protein * 3) # Dummy math for demo
    
    # Update/Create Adherence Metric
    today = datetime.now().strftime("%Y-%m-%d")
    metric = db.query(AdherenceMetric).filter(
        AdherenceMetric.program_id == program_id, 
        AdherenceMetric.date == today
    ).first()
    
    if not metric:
        metric = AdherenceMetric(program_id=program_id, date=today)
    
    metric.nutrition_score = score
    metric.total_score = score # Aggregate logic would go here
    metric.details = {"last_protein": protein, "status": "calculated"}
    
    db.add(metric)
    db.commit()