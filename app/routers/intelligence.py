from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import IntelligenceReportOut

router = APIRouter(prefix="/intelligence-reports", tags=["intelligence"])


@router.get("", response_model=list[IntelligenceReportOut])
def list_reports(db: Session = Depends(get_db)):
    return db.query(models.IntelligenceReport).order_by(models.IntelligenceReport.date_rapport.desc()).all()
