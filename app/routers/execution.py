from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..audit import get_acting_user_id, log_action
from ..database import get_db

router = APIRouter(prefix="/execution", tags=["execution"])


def _en_retard(s: models.SuiviExecution) -> bool:
    maintenant = datetime.now(timezone.utc)
    limite = s.date_limite.replace(tzinfo=timezone.utc)
    if s.statut == "execute":
        return s.date_execution is not None and s.date_execution.replace(tzinfo=timezone.utc) > limite
    return limite < maintenant


def _serialize(s: models.SuiviExecution) -> dict:
    return {
        "id": s.id,
        "reference": s.reference,
        "typeOrdre": s.type_ordre,
        "objet": s.objet,
        "instruction": s.instruction,
        "emetteur": s.emetteur,
        "uniteId": s.unite_id,
        "uniteNom": s.unite.nom_unite if s.unite else "—",
        "dateEmission": s.date_emission.isoformat(),
        "dateLimite": s.date_limite.isoformat(),
        "statut": s.statut,
        "dateExecution": s.date_execution.isoformat() if s.date_execution else None,
        "compteRendu": s.compte_rendu,
        "enRetard": _en_retard(s),
        "classification": s.classification,
    }


@router.get("")
def list_suivi(db: Session = Depends(get_db)):
    suivi = db.query(models.SuiviExecution).order_by(models.SuiviExecution.date_limite).all()
    return [_serialize(s) for s in suivi]


@router.get("/indicateurs")
def indicateurs(db: Session = Depends(get_db)):
    suivi = db.query(models.SuiviExecution).all()
    if not suivi:
        return {"tauxExecutionPct": 0, "enRetard": 0, "enCours": 0, "enAttente": 0, "executesATemps": 0, "total": 0}

    en_retard = sum(1 for s in suivi if _en_retard(s))
    executes = [s for s in suivi if s.statut == "execute"]
    executes_a_temps = sum(1 for s in executes if not _en_retard(s))

    return {
        "tauxExecutionPct": round(len(executes) / len(suivi) * 100),
        "enRetard": en_retard,
        "enCours": sum(1 for s in suivi if s.statut == "en_cours"),
        "enAttente": sum(1 for s in suivi if s.statut == "en_attente"),
        "executesATemps": executes_a_temps,
        "total": len(suivi),
    }


@router.post("/{suivi_id}/demarrer")
def demarrer(suivi_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    s = db.get(models.SuiviExecution, suivi_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Suivi introuvable")
    s.statut = "en_cours"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="suivi_execution", enregistrement_id=s.id)
    return _serialize(s)


class ExecuterPayload(BaseModel):
    compte_rendu: str


@router.post("/{suivi_id}/executer")
def executer(suivi_id: str, payload: ExecuterPayload, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    s = db.get(models.SuiviExecution, suivi_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Suivi introuvable")
    s.statut = "execute"
    s.date_execution = datetime.now(timezone.utc)
    s.compte_rendu = payload.compte_rendu
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="suivi_execution", enregistrement_id=s.id)
    return _serialize(s)
