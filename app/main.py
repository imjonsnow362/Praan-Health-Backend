from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.db.session import engine
from app.db.base import Base
from app.api.v1 import members, programs, logs

# Auto-create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Praan Family Health OS")

# Mount 'uploads' folder so Frontend can view images (e.g. localhost:8000/uploads/xyz.jpg)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include Routers
app.include_router(members.router, prefix="/api/v1/members", tags=["Members"])
app.include_router(programs.router, prefix="/api/v1/programs", tags=["Programs"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["Logs & AI"])

@app.get("/")
def root():
    return {"message": "System Operational"}