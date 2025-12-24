from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db

async def get_current_user(x_user_id: int = Header(..., alias="X-User-ID")):
    """
    Simulates Authentication. 
    It forces the client to send a header 'X-User-ID: 1'.
    If missing, returns 422/400.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing Authentication Header")
    return x_user_id