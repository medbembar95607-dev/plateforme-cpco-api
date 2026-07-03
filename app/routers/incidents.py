from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..audit import get_acting_user_id, log_action
from ..database import get_db
from ..schemas import IncidentCreate, IncidentOut

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
def list_incidents(db: Session = Depends(get_db)):
    return db.query(models.Incident).order_by(models.Incident.date_incident.desc()).all()


@router.post("", response_model=IncidentOut)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
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
    log_action(db, user_id=user_id, action="create", table_cible="incidents", enregistrement_id=incident.id)
    return incident
