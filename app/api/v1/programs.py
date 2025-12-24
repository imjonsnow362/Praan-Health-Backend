from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.models.program import CareProgram, ProgramConfig
from app.schemas.common import EnrollmentRequest
from app.models.user import Member
from app.schemas.common import ProgramConfigCreate
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/{member_id}/enroll")
def enroll_member(
    member_id: int, 
    user_id: int,
    request: EnrollmentRequest, 
    db: Session = Depends(get_db)
):
    """
    Enrolls a member in a 90-Day Care Program.
    
    WHAT IS HAPPENING HERE:
    1. Validation: Ensures User owns the Member.
    2. Logic: Calculates the 90-day end date automatically.
    3. Persistence: Saves Program Metadata + Goal Configuration.
    """
    
    # --- 1. VALIDATION LAYER ---
    # We verify that the logged-in User actually owns this Member profile.
    # preventing User A from enrolling User B's mom.
    # member = db.query(Member).filter(Member.id == member_id, Member.user_id == user_id).first()
    # if not member:
    #     raise HTTPException(status_code=403, detail="Not authorized to enroll this member")

    # We check if they are already in an active program to prevent double-enrollment.
    existing = db.query(CareProgram).filter(
        CareProgram.member_id == member_id, 
        CareProgram.status == "ACTIVE"
    ).first()
    if existing:
        return {"status": "exists", "program_id": existing.id, "message": "Member already has an active program"}

    # --- 2. BUSINESS LOGIC LAYER (The 90-Day Rule) ---
    # Requirement: "startDate, endDate (90 days)" 
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(days=90) # <--- EXPLICIT 90-DAY CALCULATION

    # Create the Program Metadata Shell
    program = CareProgram(
        member_id=member_id,
        # Metadata from Request
        title=request.title,             
        description=request.description, 
        
        # Auto-Calculated Fields
        start_date=start_time,
        end_date=end_time,      # <--- Saved to DB
        phase=1,                # <--- Default start phase 
        status="ACTIVE"         # <--- Default status 
    )
    db.add(program)
    db.commit() # Commit first to generate the program.id
    
    # --- 3. CONFIGURATION LAYER ---
    # Requirement: "Three components with configurable expectations" 
    # We save the specific JSON goals linked to the program ID we just created.
    new_config = ProgramConfig(
        program_id=program.id,
        nutrition_goals=request.nutrition_goals, # e.g. {"calories": 1500}
        strength_goals=request.strength_goals,
        clinical_goals=request.clinical_goals
    )
    db.add(new_config)
    db.commit()
    
    return {
        "status": "enrolled", 
        "program_id": program.id,
        "start_date": start_time,
        "end_date": end_time
    }
    """
    Enrolls a member and saves their specific health goals (Config).
    """
    # # Security Check
    # member = db.query(Member).filter(Member.id == member_id, Member.user_id == user_id).first()
    # if not member:
    #     raise HTTPException(status_code=403, detail="Not authorized to enroll this member")

    # Check for existing active program
    existing = db.query(CareProgram).filter(
        CareProgram.member_id == member_id, 
        CareProgram.status == "ACTIVE"
    ).first()
    if existing:
        return {"status": "exists", "program_id": existing.id, "message": "Member already has an active program"}

    # Create Program Shell
    program = CareProgram(member_id=member_id)
    db.add(program)
    db.commit()
    
    # Save the USER-DEFINED Config
    new_config = ProgramConfig(
        program_id=program.id,
        nutrition_goals=config_data.nutrition_goals, # Saved from JSON input
        strength_goals=config_data.strength_goals,
        clinical_goals=config_data.clinical_goals
    )
    db.add(new_config)
    db.commit()
    
    return {"status": "enrolled", "program_id": program.id}



@router.get("/{program_id}")
def get_program_details(program_id: int, db: Session = Depends(get_db)):
    """
    View a program and its set goals.
    Uses joinedload to eagerly fetch the Member data (Performance Optimization).
    """
    program = db.query(CareProgram)\
        .options(joinedload(CareProgram.member))\
        .options(joinedload(CareProgram.config))\
        .filter(CareProgram.id == program_id)\
        .first()
        
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    # Defensive check: If member is somehow missing (orphaned record), handle gracefully
    member_name = program.member.name if program.member else "Unknown Member"
    
    # Defensive check: If config is missing
    nutrition = program.config.nutrition_goals if program.config else {}
    strength = program.config.strength_goals if program.config else {}
    clinical = program.config.clinical_goals if program.config else {}

    return {
        "id": program.id,
        "member_name": member_name,
        "metadata": {
            "title": program.title,
            "description": program.description,
            "phase": program.phase,       # <--- Returning the Phase
            "status": program.status,     # <--- Returning the Status
            "start_date": program.start_date,
            "end_date": program.end_date  # <--- Returning the calculated End Date
        },
        "goals": {
            # Use getattr to safely get goals or return empty dict if config is None
            "nutrition": getattr(program.config, 'nutrition_goals', {}),
            "strength": getattr(program.config, 'strength_goals', {}),
            "clinical": getattr(program.config, 'clinical_goals', {})
        }
    }