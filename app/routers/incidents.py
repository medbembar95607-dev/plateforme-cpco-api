from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import IncidentCreate, IncidentOut

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    return db.query(models.Incident).order_by(models.Incident.date_incident.desc()).all()


@router.post("", response_model=IncidentOut)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)):
    incident = models.Incident(
        type_incident=payload.type_incident,
        niveau_gravite=payload.niveau_gravite,
        localite=payload.localite,
        description=payload.description,
        declarant=payload.declarant,
        lon=payload.lon,
        lat=payload.lat,
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident
