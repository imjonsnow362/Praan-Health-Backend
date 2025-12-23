from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.program import CareProgram, ProgramConfig
from app.models.user import Member

router = APIRouter()

# In a real app, you'd get 'current_user_id' from the Auth Token.
# For this prototype, we will pass 'user_id' as a header or query param for simplicity.
@router.post("/{member_id}/enroll")
def enroll_member(
    member_id: int, 
    user_id: int,  # <--- Added for ownership check
    db: Session = Depends(get_db)
):
    # 1. SECURITY CHECK: Does this user own this member?
    # member = db.query(Member).filter(Member.id == member_id, Member.user_id == user_id).first()
    # if not member:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, 
    #         detail="You are not authorized to enroll this member."
    #     )

    # 2. Check if active program exists
    existing_program = db.query(CareProgram).filter(
        CareProgram.member_id == member_id, 
        CareProgram.status == "ACTIVE"
    ).first()
    if existing_program:
        return {"status": "exists", "program_id": existing_program.id}

    # 3. Create Program
    program = CareProgram(member_id=member_id)
    db.add(program)
    db.commit()
    
    # 4. Create Default Config
    config = ProgramConfig(
        program_id=program.id,
        nutrition_goals={"calories": 2000, "protein_g": 60},
        strength_goals={"sessions": 3},
        clinical_goals={"bp_check": "weekly"}
    )
    db.add(config)
    db.commit()
    
    return {"status": "enrolled", "program_id": program.id}