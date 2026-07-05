from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..audit import get_acting_user_id, log_action
from ..database import get_db

router = APIRouter(prefix="/agenda", tags=["agenda"])


def _serialize(r: models.RendezVous) -> dict:
    return {
        "id": r.id,
        "titre": r.titre,
        "typeRdv": r.type_rdv,
        "dateDebut": r.date_debut.isoformat(),
        "dateFin": r.date_fin.isoformat() if r.date_fin else None,
        "lieu": r.lieu,
        "participants": r.participants,
        "statut": r.statut,
        "classification": r.classification,
        "notes": r.notes,
    }


@router.get("")
def list_agenda(db: Session = Depends(get_db)):
    rdvs = db.query(models.RendezVous).order_by(models.RendezVous.date_debut.asc()).all()
    return [_serialize(r) for r in rdvs]


class RendezVousPayload(BaseModel):
    titre: str
    type_rdv: str = "reunion"
    date_debut: datetime
    date_fin: datetime | None = None
    lieu: str = ""
    participants: str = ""
    classification: str = "confidentiel"
    notes: str | None = None


@router.post("")
def creer_rendez_vous(payload: RendezVousPayload, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    rdv = models.RendezVous(**payload.model_dump())
    db.add(rdv)
    db.commit()
    log_action(db, user_id=user_id, action="create", table_cible="rendez_vous", enregistrement_id=rdv.id)
    return _serialize(rdv)


@router.post("/{rdv_id}/confirmer")
def confirmer(rdv_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    rdv = db.get(models.RendezVous, rdv_id)
    if rdv is None:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    rdv.statut = "confirme"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="rendez_vous", enregistrement_id=rdv.id)
    return _serialize(rdv)


@router.post("/{rdv_id}/annuler")
def annuler(rdv_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    rdv = db.get(models.RendezVous, rdv_id)
    if rdv is None:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    rdv.statut = "annule"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="rendez_vous", enregistrement_id=rdv.id)
    return _serialize(rdv)
