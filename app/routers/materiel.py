from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/materiels", tags=["materiel"])

ARMEES = ("terre", "air", "mer")


def _serialize(m: models.Materiel) -> dict:
    return {
        "id": m.id,
        "nom": m.nom,
        "categorie": m.categorie,
        "typeMateriel": m.type_materiel,
        "armee": m.armee,
        "formationAffectation": m.formation_affectation,
        "fonction": m.fonction,
        "caracteristiques": m.caracteristiques,
        "statutDotation": m.statut_dotation,
        "etat": m.etat,
        "quantite": m.quantite,
        "seuilAlerte": m.seuil_alerte,
        "dotationTed": m.dotation_ted,
        "ecart": m.quantite - m.dotation_ted,
        "classification": m.classification,
        "enAlerte": m.quantite < m.seuil_alerte,
    }


@router.get("")
def list_materiels(db: Session = Depends(get_db)):
    items = db.query(models.Materiel).order_by(models.Materiel.armee, models.Materiel.categorie, models.Materiel.nom).all()
    return [_serialize(m) for m in items]


@router.get("/indicateurs")
def indicateurs(db: Session = Depends(get_db)):
    items = db.query(models.Materiel).all()

    total_dotation = sum(m.quantite for m in items if m.statut_dotation == "en_dotation")
    total_reserve = sum(m.quantite for m in items if m.statut_dotation == "en_reserve")
    en_alerte = [m for m in items if m.quantite < m.seuil_alerte]
    hors_service = [m for m in items if m.etat == "hors_service"]

    par_armee = {armee: sum(m.quantite for m in items if m.armee == armee) for armee in ARMEES}

    return {
        "totalDotation": total_dotation,
        "totalReserve": total_reserve,
        "nombreAlertes": len(en_alerte),
        "nombreHorsService": len(hors_service),
        "parArmee": par_armee,
    }
