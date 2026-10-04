from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..audit import exiger_role, get_acting_user_id, log_action
from ..database import get_db
from ..schemas import IntelligenceReportOut

router = APIRouter(prefix="/intelligence-reports", tags=["intelligence"])

# Saisie et évolution du statut d'un rapport : cellule renseignement et commandement.
ROLES_RENSEIGNEMENT = {"officier_renseignement", "commandement", "administrateur"}
TYPES = {"HUMINT", "SIGINT", "OSINT", "IMINT"}
CLASSIFICATIONS = {"diffusion_libre", "confidentiel", "secret", "tres_secret"}
STATUTS = {"menace", "observation", "stabilise"}


@router.get("", response_model=list[IntelligenceReportOut])
def list_reports(db: Session = Depends(get_db)):
    return db.query(models.IntelligenceReport).order_by(models.IntelligenceReport.date_rapport.desc()).all()


class RapportCreate(BaseModel):
    type_renseignement: str
    classification: str
    titre: str = Field(min_length=1, max_length=200)
    resume: str = ""
    fiabilite_source: str = Field(pattern="^[A-F]$")
    credibilite_info: int = Field(ge=1, le=6)
    statut: str = "observation"
    lon: float | None = None
    lat: float | None = None


def _prochaine_reference(db: Session, type_renseignement: str) -> str:
    annee = datetime.now().year
    prefixe = f"{type_renseignement}-{annee}-"
    existantes = (
        db.query(models.IntelligenceReport.reference)
        .filter(models.IntelligenceReport.reference.like(f"{prefixe}%"))
        .all()
    )
    numeros = [int(r[0].rsplit("-", 1)[1]) for r in existantes if r[0].rsplit("-", 1)[1].isdigit()]
    return f"{prefixe}{(max(numeros, default=0) + 1):04d}"


@router.post("", response_model=IntelligenceReportOut)
def create_report(payload: RapportCreate, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    exiger_role(db, user_id, ROLES_RENSEIGNEMENT, "rédaction d'un rapport de renseignement")
    if payload.type_renseignement not in TYPES or payload.classification not in CLASSIFICATIONS or payload.statut not in STATUTS:
        raise HTTPException(status_code=422, detail="Type, classification ou statut invalide")
    if (payload.lon is None) != (payload.lat is None):
        raise HTTPException(status_code=422, detail="Position incomplète")

    rapport = models.IntelligenceReport(
        reference=_prochaine_reference(db, payload.type_renseignement),
        type_renseignement=payload.type_renseignement,
        classification=payload.classification,
        titre=payload.titre.strip(),
        resume=payload.resume.strip(),
        fiabilite_source=payload.fiabilite_source,
        credibilite_info=payload.credibilite_info,
        statut=payload.statut,
        lon=payload.lon,
        lat=payload.lat,
        redige_par=user_id,
    )
    db.add(rapport)
    db.commit()
    db.refresh(rapport)
    log_action(db, user_id=user_id, action="create", table_cible="intelligence_reports", enregistrement_id=rapport.id)
    return rapport


class StatutPayload(BaseModel):
    statut: str


@router.post("/{rapport_id}/statut", response_model=IntelligenceReportOut)
def changer_statut(rapport_id: str, payload: StatutPayload, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    exiger_role(db, user_id, ROLES_RENSEIGNEMENT, "évaluation d'un rapport de renseignement")
    if payload.statut not in STATUTS:
        raise HTTPException(status_code=422, detail="Statut invalide")
    rapport = db.get(models.IntelligenceReport, rapport_id)
    if rapport is None:
        raise HTTPException(status_code=404, detail="Rapport introuvable")
    rapport.statut = payload.statut
    db.commit()
    db.refresh(rapport)
    log_action(db, user_id=user_id, action="update", table_cible="intelligence_reports", enregistrement_id=rapport.id)
    return rapport
