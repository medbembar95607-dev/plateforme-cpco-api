import uuid as uuid_module
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..audit import get_acting_user_id, log_action
from ..database import get_db
from ..storage import UPLOAD_DIR

router = APIRouter(prefix="/communication", tags=["communication"])


def _serialize_message(m: models.Message, db: Session) -> dict:
    expediteur = db.get(models.User, m.expediteur_id) if m.expediteur_id else None
    return {
        "id": m.id,
        "expediteurNom": expediteur.nom_complet if expediteur else "Inconnu",
        "typeMessage": m.type_message,
        "contenu": m.contenu,
        "fichierUrl": m.fichier_url,
        "fichierNom": m.fichier_nom,
        "dureeSecondes": m.duree_secondes,
        "diffusion": m.diffusion,
        "classification": m.classification,
        "dateEnvoi": m.date_envoi.isoformat(),
        "destinataires": [{"uniteId": d.unit_id, "uniteNom": d.unit.nom_unite} for d in m.destinataires],
    }


def _serialize_reunion(r: models.Reunion, db: Session) -> dict:
    organisateur = db.get(models.User, r.organisateur_id) if r.organisateur_id else None
    return {
        "id": r.id,
        "titre": r.titre,
        "organisateurNom": organisateur.nom_complet if organisateur else "Inconnu",
        "dateConvocation": r.date_convocation.isoformat(),
        "statut": r.statut,
        "classification": r.classification,
        "notes": r.notes,
        "participants": [
            {"id": p.id, "uniteId": p.unit_id, "uniteNom": p.unit.nom_unite, "statut": p.statut} for p in r.participants
        ],
    }


def _toutes_les_unites(db: Session) -> list[str]:
    return [u.id for u in db.query(models.Unit).all()]


# --- Messages (chat) ---------------------------------------------------------------

@router.get("/messages")
def list_messages(db: Session = Depends(get_db)):
    messages = db.query(models.Message).order_by(models.Message.date_envoi.desc()).all()
    return [_serialize_message(m, db) for m in messages]


class MessageTextePayload(BaseModel):
    contenu: str
    destinataire_unit_ids: list[str] = []
    diffusion: bool = False
    classification: str = "confidentiel"


@router.post("/messages")
def envoyer_message_texte(payload: MessageTextePayload, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    if not payload.diffusion and not payload.destinataire_unit_ids:
        raise HTTPException(status_code=400, detail="Sélectionnez au moins un destinataire ou activez la diffusion.")

    message = models.Message(
        expediteur_id=user_id,
        type_message="texte",
        contenu=payload.contenu,
        diffusion=payload.diffusion,
        classification=payload.classification,
    )
    db.add(message)
    db.flush()
    unit_ids = _toutes_les_unites(db) if payload.diffusion else payload.destinataire_unit_ids
    for unit_id in unit_ids:
        db.add(models.MessageRecipient(message_id=message.id, unit_id=unit_id))
    db.commit()
    log_action(db, user_id=user_id, action="create", table_cible="messages", enregistrement_id=message.id)
    return _serialize_message(message, db)


@router.post("/messages/upload")
async def envoyer_message_media(
    type_message: str = Form(...),
    fichier: UploadFile = File(...),
    destinataire_unit_ids: str = Form(""),
    diffusion: bool = Form(False),
    duree_secondes: int | None = Form(None),
    contenu: str | None = Form(None),
    classification: str = Form("confidentiel"),
    db: Session = Depends(get_db),
    user_id: str | None = Depends(get_acting_user_id),
):
    if type_message not in ("vocal", "document"):
        raise HTTPException(status_code=400, detail="type_message doit être 'vocal' ou 'document'")
    ids = [i for i in destinataire_unit_ids.split(",") if i]
    if not diffusion and not ids:
        raise HTTPException(status_code=400, detail="Sélectionnez au moins un destinataire ou activez la diffusion.")

    extension = Path(fichier.filename or "").suffix
    nom_stocke = f"{uuid_module.uuid4()}{extension}"
    with open(Path(UPLOAD_DIR) / nom_stocke, "wb") as f:
        f.write(await fichier.read())

    message = models.Message(
        expediteur_id=user_id,
        type_message=type_message,
        contenu=contenu,
        fichier_url=f"/uploads/{nom_stocke}",
        fichier_nom=fichier.filename,
        duree_secondes=duree_secondes,
        diffusion=diffusion,
        classification=classification,
    )
    db.add(message)
    db.flush()
    unit_ids = _toutes_les_unites(db) if diffusion else ids
    for unit_id in unit_ids:
        db.add(models.MessageRecipient(message_id=message.id, unit_id=unit_id))
    db.commit()
    log_action(db, user_id=user_id, action="create", table_cible="messages", enregistrement_id=message.id)
    return _serialize_message(message, db)


# --- Réunions (VTC) ------------------------------------------------------------------

@router.get("/reunions")
def list_reunions(db: Session = Depends(get_db)):
    reunions = db.query(models.Reunion).order_by(models.Reunion.date_convocation.desc()).all()
    return [_serialize_reunion(r, db) for r in reunions]


class ReunionPayload(BaseModel):
    titre: str
    participant_unit_ids: list[str]
    classification: str = "confidentiel"
    notes: str | None = None


@router.post("/reunions")
def convoquer_reunion(payload: ReunionPayload, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    if not payload.participant_unit_ids:
        raise HTTPException(status_code=400, detail="Sélectionnez au moins un participant à convoquer.")

    reunion = models.Reunion(titre=payload.titre, organisateur_id=user_id, classification=payload.classification, notes=payload.notes)
    db.add(reunion)
    db.flush()
    for unit_id in payload.participant_unit_ids:
        db.add(models.ReunionParticipant(reunion_id=reunion.id, unit_id=unit_id))
    db.commit()
    log_action(db, user_id=user_id, action="create", table_cible="reunions", enregistrement_id=reunion.id)
    return _serialize_reunion(reunion, db)


def _get_reunion_ou_404(reunion_id: str, db: Session) -> models.Reunion:
    reunion = db.get(models.Reunion, reunion_id)
    if reunion is None:
        raise HTTPException(status_code=404, detail="Réunion introuvable")
    return reunion


@router.post("/reunions/{reunion_id}/demarrer")
def demarrer_reunion(reunion_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    reunion = _get_reunion_ou_404(reunion_id, db)
    reunion.statut = "en_cours"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="reunions", enregistrement_id=reunion.id)
    return _serialize_reunion(reunion, db)


@router.post("/reunions/{reunion_id}/terminer")
def terminer_reunion(reunion_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    reunion = _get_reunion_ou_404(reunion_id, db)
    reunion.statut = "terminee"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="reunions", enregistrement_id=reunion.id)
    return _serialize_reunion(reunion, db)


@router.post("/reunions/{reunion_id}/annuler")
def annuler_reunion(reunion_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    reunion = _get_reunion_ou_404(reunion_id, db)
    reunion.statut = "annulee"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="reunions", enregistrement_id=reunion.id)
    return _serialize_reunion(reunion, db)


@router.post("/reunions/{reunion_id}/participants/{participant_id}/basculer")
def basculer_statut_participant(
    reunion_id: str, participant_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)
):
    """Fait avancer le statut d'un participant (convoqué -> rejoint -> absent -> convoqué), pour
    simuler la présence en salle sans vrai flux WebRTC (voir Reunion.__doc__)."""
    participant = db.get(models.ReunionParticipant, participant_id)
    if participant is None or participant.reunion_id != reunion_id:
        raise HTTPException(status_code=404, detail="Participant introuvable")
    suite = {"convoque": "rejoint", "rejoint": "absent", "absent": "convoque"}
    participant.statut = suite.get(participant.statut, "convoque")
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="reunion_participants", enregistrement_id=participant.id)
    return _serialize_reunion(_get_reunion_ou_404(reunion_id, db), db)
