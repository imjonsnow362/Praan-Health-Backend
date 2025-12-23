# app/db/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Still using SQLite for the prototype
SQLALCHEMY_DATABASE_URL = "sqlite:///./praan_health.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()