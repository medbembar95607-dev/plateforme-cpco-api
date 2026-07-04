from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..audit import get_acting_user_id, log_action
from ..database import get_db

router = APIRouter(prefix="/courriers", tags=["courrier"])


def _serialize(c: models.Courrier, db: Session) -> dict:
    annotateur = db.get(models.User, c.annote_par) if c.annote_par else None
    return {
        "id": c.id,
        "numero": c.numero_enregistrement,
        "typeDocument": c.type_document,
        "origine": c.origine,
        "expediteur": c.expediteur,
        "objet": c.objet,
        "resume": c.resume,
        "contenu": c.contenu,
        "classification": c.classification,
        "priorite": c.priorite,
        "statut": c.statut,
        "dateReception": c.date_reception.isoformat(),
        "dateLimiteReponse": c.date_limite_reponse.isoformat() if c.date_limite_reponse else None,
        "annotation": c.annotation,
        "annotePar": annotateur.nom_complet if annotateur else None,
        "dateAnnotation": c.date_annotation.isoformat() if c.date_annotation else None,
        "orienteVers": c.oriente_vers,
        "ordreGenereId": c.ordre_genere_id,
    }


@router.get("")
def list_courriers(db: Session = Depends(get_db)):
    courriers = db.query(models.Courrier).order_by(models.Courrier.date_reception.desc()).all()
    return [_serialize(c, db) for c in courriers]


class AnnotationPayload(BaseModel):
    annotation: str


@router.post("/{courrier_id}/annoter")
def annoter(courrier_id: str, payload: AnnotationPayload, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    courrier = db.get(models.Courrier, courrier_id)
    if courrier is None:
        raise HTTPException(status_code=404, detail="Courrier introuvable")
    courrier.annotation = payload.annotation
    courrier.annote_par = user_id
    courrier.date_annotation = datetime.now(timezone.utc)
    if courrier.statut == "nouveau":
        courrier.statut = "annote"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="courriers", enregistrement_id=courrier.id)
    return _serialize(courrier, db)


class OrientationPayload(BaseModel):
    destination: str


@router.post("/{courrier_id}/orienter")
def orienter(courrier_id: str, payload: OrientationPayload, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    courrier = db.get(models.Courrier, courrier_id)
    if courrier is None:
        raise HTTPException(status_code=404, detail="Courrier introuvable")
    courrier.oriente_vers = payload.destination
    courrier.statut = "oriente"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="courriers", enregistrement_id=courrier.id)
    return _serialize(courrier, db)


@router.post("/{courrier_id}/classer")
def classer(courrier_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    courrier = db.get(models.Courrier, courrier_id)
    if courrier is None:
        raise HTTPException(status_code=404, detail="Courrier introuvable")
    courrier.statut = "classe_sans_suite"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="courriers", enregistrement_id=courrier.id)
    return _serialize(courrier, db)


@router.post("/{courrier_id}/traiter")
def traiter(courrier_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    courrier = db.get(models.Courrier, courrier_id)
    if courrier is None:
        raise HTTPException(status_code=404, detail="Courrier introuvable")
    courrier.statut = "traite"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="courriers", enregistrement_id=courrier.id)
    return _serialize(courrier, db)


@router.post("/{courrier_id}/generer-ordre")
def generer_ordre(courrier_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    courrier = db.get(models.Courrier, courrier_id)
    if courrier is None:
        raise HTTPException(status_code=404, detail="Courrier introuvable")
    if courrier.ordre_genere_id:
        raise HTTPException(status_code=400, detail="Un ordre a déjà été généré pour ce courrier")

    ordre = models.Order(
        numero_ordre=f"ORD-{courrier.numero_enregistrement}",
        type_ordre="FRAGO",
        classification=courrier.classification,
        objet=courrier.objet,
        contenu=f"Ordre généré à partir du courrier {courrier.numero_enregistrement} ({courrier.expediteur}).\n\n{courrier.resume}",
        statut="brouillon",
        emetteur="Chef d'état-major",
    )
    db.add(ordre)
    db.flush()
    courrier.ordre_genere_id = ordre.id
    courrier.statut = "oriente"
    db.commit()
    log_action(db, user_id=user_id, action="create", table_cible="orders", enregistrement_id=ordre.id)
    log_action(db, user_id=user_id, action="update", table_cible="courriers", enregistrement_id=courrier.id)
    return _serialize(courrier, db)
