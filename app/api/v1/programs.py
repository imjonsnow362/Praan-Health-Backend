from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.program import CareProgram, ProgramConfig

router = APIRouter()

@router.post("/{member_id}/enroll")
def enroll_member(member_id: int, db: Session = Depends(get_db)):
    # Create Program
    program = CareProgram(member_id=member_id)
    db.add(program)
    db.commit()
    
    # Create Default Config (Nutrition: 2000 cal, 60g protein)
    config = ProgramConfig(
        program_id=program.id,
        nutrition_goals={"calories": 2000, "protein_g": 60},
        strength_goals={"sessions": 3},
        clinical_goals={"bp_check": "weekly"}
    )
    db.add(config)
    db.commit()
    return {"status": "enrolled", "program_id": program.id}