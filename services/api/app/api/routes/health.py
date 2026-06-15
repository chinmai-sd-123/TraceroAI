from fastapi import APIRouter, Depends
from sqlalchemy import text 
from sqlalchemy.orm import Session
from app.db.session import get_db

router= APIRouter(prefix="/health", tags=["health"])

@router.get("")
def health_check() ->dict[str, str]:
    return{"status":"ok"}

@router.get("/db")
def health_check_db(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "details": str(e)}