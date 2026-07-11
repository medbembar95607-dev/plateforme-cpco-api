from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..audit import get_acting_user_id, log_action
from ..database import get_db

router = APIRouter(prefix="/rh", tags=["rh"])

CATEGORIES = ("officier", "sous_officier", "homme_du_rang")
ARMEES = ("terre", "air", "mer")

# Âge de départ à la retraite par catégorie (règle simplifiée pour la démo)
AGE_RETRAITE = {"officier": 60, "sous_officier": 57, "homme_du_rang": 52}


def _age(date_naissance: datetime) -> float:
    return (datetime.now(timezone.utc) - date_naissance.replace(tzinfo=timezone.utc)).days / 365.25


def _anciennete(date_entree: datetime) -> float:
    return (datetime.now(timezone.utc) - date_entree.replace(tzinfo=timezone.utc)).days / 365.25


def _annees_avant_retraite(m: models.Militaire) -> float:
    age_retraite = AGE_RETRAITE.get(m.categorie, 60)
    return round(age_retraite - _age(m.date_naissance), 1)


def _serialize_militaire(m: models.Militaire) -> dict:
    return {
        "id": m.id,
        "matricule": m.matricule,
        "nomComplet": m.nom_complet,
        "grade": m.grade,
        "categorie": m.categorie,
        "armee": m.armee,
        "formationAffectation": m.formation_affectation,
        "age": round(_age(m.date_naissance)),
        "anciennete": round(_anciennete(m.date_entree_service)),
        "ancienneteGrade": round(_anciennete(m.date_prise_grade)),
        "anneesAvantRetraite": _annees_avant_retraite(m),
        "procheRetraite": _annees_avant_retraite(m) <= 2,
        "classification": m.classification,
    }


@router.get("/personnel")
def list_personnel(db: Session = Depends(get_db)):
    militaires = db.query(models.Militaire).order_by(models.Militaire.categorie, models.Militaire.grade).all()
    return [_serialize_militaire(m) for m in militaires]


@router.get("/indicateurs")
def indicateurs(db: Session = Depends(get_db)):
    militaires = db.query(models.Militaire).all()
    propositions_en_cours = db.query(models.PropositionRH).filter(models.PropositionRH.statut == "en_cours").count()
    besoins_ouverts = db.query(models.BesoinRecrutement).filter(models.BesoinRecrutement.statut == "ouvert").count()

    par_categorie = {c: sum(1 for m in militaires if m.categorie == c) for c in CATEGORIES}
    par_armee = {a: sum(1 for m in militaires if m.armee == a) for a in ARMEES}
    proche_retraite = sum(1 for m in militaires if _annees_avant_retraite(m) <= 2)

    return {
        "effectifTotal": len(militaires),
        "parCategorie": par_categorie,
        "parArmee": par_armee,
        "procheRetraite": proche_retraite,
        "propositionsEnCours": propositions_en_cours,
        "besoinsOuverts": besoins_ouverts,
    }


def _serialize_proposition(p: models.PropositionRH, db: Session) -> dict:
    militaire = db.get(models.Militaire, p.militaire_id)
    return {
        "id": p.id,
        "militaireId": p.militaire_id,
        "militaireNom": militaire.nom_complet if militaire else "—",
        "militaireGrade": militaire.grade if militaire else "",
        "typeProposition": p.type_proposition,
        "motif": p.motif,
        "proposition": p.proposition,
        "statut": p.statut,
        "dateCreation": p.date_creation.isoformat(),
        "classification": p.classification,
    }


@router.get("/propositions")
def list_propositions(db: Session = Depends(get_db)):
    propositions = db.query(models.PropositionRH).order_by(models.PropositionRH.date_creation.desc()).all()
    return [_serialize_proposition(p, db) for p in propositions]


class PropositionPayload(BaseModel):
    militaire_id: str
    type_proposition: str
    motif: str
    proposition: str
    classification: str = "confidentiel"


@router.post("/propositions")
def creer_proposition(payload: PropositionPayload, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    proposition = models.PropositionRH(**payload.model_dump())
    db.add(proposition)
    db.commit()
    log_action(db, user_id=user_id, action="create", table_cible="propositions_rh", enregistrement_id=proposition.id)
    return _serialize_proposition(proposition, db)


@router.post("/propositions/{proposition_id}/valider")
def valider_proposition(proposition_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    proposition = db.get(models.PropositionRH, proposition_id)
    if proposition is None:
        raise HTTPException(status_code=404, detail="Proposition introuvable")
    proposition.statut = "validee"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="propositions_rh", enregistrement_id=proposition.id)
    return _serialize_proposition(proposition, db)


@router.post("/propositions/{proposition_id}/rejeter")
def rejeter_proposition(proposition_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    proposition = db.get(models.PropositionRH, proposition_id)
    if proposition is None:
        raise HTTPException(status_code=404, detail="Proposition introuvable")
    proposition.statut = "rejetee"
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="propositions_rh", enregistrement_id=proposition.id)
    return _serialize_proposition(proposition, db)


def _serialize_besoin(b: models.BesoinRecrutement) -> dict:
    return {
        "id": b.id,
        "poste": b.poste,
        "categorie": b.categorie,
        "armee": b.armee,
        "formationAffectation": b.formation_affectation,
        "nombrePostes": b.nombre_postes,
        "priorite": b.priorite,
        "statut": b.statut,
        "classification": b.classification,
    }


@router.get("/besoins-recrutement")
def list_besoins(db: Session = Depends(get_db)):
    besoins = db.query(models.BesoinRecrutement).order_by(models.BesoinRecrutement.priorite).all()
    return [_serialize_besoin(b) for b in besoins]


def _serialize_besoin_formation(b: models.BesoinFormation) -> dict:
    return {
        "id": b.id,
        "intitule": b.intitule,
        "categorie": b.categorie,
        "armee": b.armee,
        "formationAffectation": b.formation_affectation,
        "nombrePlaces": b.nombre_places,
        "priorite": b.priorite,
        "statut": b.statut,
        "classification": b.classification,
    }


@router.get("/besoins-formation")
def list_besoins_formation(db: Session = Depends(get_db)):
    besoins = db.query(models.BesoinFormation).order_by(models.BesoinFormation.priorite).all()
    return [_serialize_besoin_formation(b) for b in besoins]
