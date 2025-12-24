from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.models.program import CareProgram, ProgramConfig
from app.models.user import Member
from app.schemas.common import ProgramConfigCreate

router = APIRouter()

# In a real app, you'd get 'current_user_id' from the Auth Token.
# For this prototype, we will pass 'user_id' as a header or query param for simplicity.
@router.post("/{member_id}/enroll")
def enroll_member(
    member_id: int, 
    user_id: int,
    config_data: ProgramConfigCreate, # <--- We now expect JSON body with goals
    db: Session = Depends(get_db)
):
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
        "status": program.status,
        "start_date": program.start_date,
        "goals": {
            "nutrition": nutrition,
            "strength": strength,
            "clinical": clinical
        }
    }