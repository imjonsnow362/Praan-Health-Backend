import logging
import shutil
import os
import uuid
import asyncio
from datetime import datetime
from typing import List

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from cachetools import TTLCache # pip install cachetools

from app.db.session import get_db
from app.models.health import DailyLog
from app.models.program import CareProgram, AdherenceMetric
from app.schemas.health import LogResponse, MealExtractionResponse, LogCreate

# --- SETUP ---
router = APIRouter()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CACHING STRATEGY:
# In-memory cache that holds up to 100 adherence records for 60 seconds.
# In production, this would be replaced by Redis.
adherence_cache = TTLCache(maxsize=100, ttl=60)

# Local storage for images
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- 1. MOCK AI / IMAGE UPLOAD ENDPOINT ---
@router.post("/meals/analyze", response_model=MealExtractionResponse)
async def analyze_meal_photo(file: UploadFile = File(...)):
    """
    1. Receives image and saves it locally (Document Production Approach).
    2. Returns FIXED Mock Data immediately (Mock AI).
    """
    # Generate unique filename
    file_path = f"{UPLOAD_DIR}/{uuid.uuid4()}_{file.filename}"
    
    # Save file to disk
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    logger.info(f"Image saved to {file_path}. Returning Mock Data.")

    # Simulate AI Latency
    await asyncio.sleep(1)

    # RETURN FIXED MOCK DATA
    return {
        "food_items": ["Grilled Chicken", "Brown Rice", "Broccoli"],
        "calories": 450,
        "macros": {
            "protein_g": 35,  # High protein to trigger adherence
            "carbs_g": 40,
            "fats_g": 10
        },
        "confidence": 0.98
    }

# --- 2. CREATE LOG & CALCULATE ADHERENCE ---
@router.post("/logs", response_model=LogResponse)
def create_log(
    log_data: LogCreate, 
    db: Session = Depends(get_db)
):
    """
    Saves the log and triggers the adherence engine.
    """
    logger.info(f"Creating log for Program {log_data.program_id}")

    # A. Create the Log Object
    new_log = DailyLog(
        program_id=log_data.program_id,
        log_type=log_data.log_type,
        payload=log_data.payload,
        is_verified=True,
        timestamp=datetime.now() # Manually set timestamp to fix validation error
    )
    
    # B. Save to DB
    db.add(new_log)
    db.commit()
    # Note: We do NOT db.refresh() to avoid SQLite timestamp issues in this prototype
    
    # C. CACHE INVALIDATION
    # Since new data arrived, the cached adherence score is now STALE.
    cache_key = f"adherence_{log_data.program_id}"
    if cache_key in adherence_cache:
        del adherence_cache[cache_key]
        logger.info(f"INVALIDATED Cache for {cache_key}")
    
    # D. Trigger Logic Engine
    calculate_adherence(db, log_data.program_id, log_data.payload)
    
    return new_log

# --- 3. ADHERENCE LOGIC ENGINE ---
def calculate_adherence(db: Session, program_id: int, latest_payload: dict):
    """
    Calculates score based on latest log and saves to DB.
    """
    # 1. Fetch Program Configuration
    program = db.query(CareProgram).filter(CareProgram.id == program_id).first()
    if not program or not program.config:
        return

    # 2. Calculate Score (Simplified Rule: 1g Protein = 3 points, max 100)
    protein = latest_payload.get("macros", {}).get("protein_g", 0)
    score = min(100, protein * 3) 
    
    # 3. Update or Create Today's Metric
    today = datetime.now().strftime("%Y-%m-%d")
    
    metric = db.query(AdherenceMetric).filter(
        AdherenceMetric.program_id == program_id, 
        AdherenceMetric.date == today
    ).first()
    
    if not metric:
        metric = AdherenceMetric(program_id=program_id, date=today)
    
    metric.nutrition_score = score
    metric.total_score = score 
    metric.details = {"last_protein": protein, "status": "calculated_live"}
    
    db.add(metric)
    db.commit()

# --- 4. GET ADHERENCE (WITH CACHING) ---
@router.get("/adherence/{program_id}")
def get_adherence(program_id: int, db: Session = Depends(get_db)):
    """
    Demonstrates Caching Strategy:
    1. Check Cache
    2. If miss, Check DB
    3. Save to Cache
    """
    cache_key = f"adherence_{program_id}"
    
    # STEP 1: Check Cache
    if cache_key in adherence_cache:
        logger.info(f"🟢 Serving adherence from CACHE for {program_id}")
        return adherence_cache[cache_key]
    
    # STEP 2: DB Miss -> Query DB
    logger.info(f"🔴 Serving adherence from DB for {program_id}")
    today = datetime.now().strftime("%Y-%m-%d")
    metric = db.query(AdherenceMetric).filter(
        AdherenceMetric.program_id == program_id,
        AdherenceMetric.date == today
    ).first()
    
    # STEP 3: Save to Cache
    if metric:
        adherence_cache[cache_key] = metric
        
    return metric

# --- 5. VIEW HISTORY ---
@router.get("/{program_id}/history")
def get_log_history(program_id: int, db: Session = Depends(get_db)):
    """Fetch all logs for a program"""
    return db.query(DailyLog)\
        .filter(DailyLog.program_id == program_id)\
        .order_by(DailyLog.timestamp.desc())\
        .all()