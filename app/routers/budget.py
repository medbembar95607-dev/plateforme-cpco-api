from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/budget", tags=["budget"])

TYPES_BUDGET = ("fonctionnement", "investissement")


def _taux(consomme: float, alloue: float) -> float:
    return round((consomme / alloue) * 100, 1) if alloue else 0.0


def _statut(taux: float, seuil: float) -> str:
    if taux > 100:
        return "depassement"
    if taux >= seuil:
        return "attention"
    return "normal"


def _serialize(l: models.LigneBudgetaire) -> dict:
    taux = _taux(l.montant_consomme, l.montant_alloue)
    return {
        "id": l.id,
        "libelle": l.libelle,
        "typeBudget": l.type_budget,
        "formationBeneficiaire": l.formation_beneficiaire,
        "periode": l.periode,
        "montantAlloue": l.montant_alloue,
        "montantConsomme": l.montant_consomme,
        "seuilAlertePct": l.seuil_alerte_pct,
        "tauxConsommationPct": taux,
        "statut": _statut(taux, l.seuil_alerte_pct),
        "classification": l.classification,
    }


@router.get("")
def list_budget(db: Session = Depends(get_db)):
    lignes = db.query(models.LigneBudgetaire).order_by(models.LigneBudgetaire.type_budget, models.LigneBudgetaire.libelle).all()
    return [_serialize(l) for l in lignes]


@router.get("/indicateurs")
def indicateurs(db: Session = Depends(get_db)):
    lignes = db.query(models.LigneBudgetaire).all()

    total_alloue = sum(l.montant_alloue for l in lignes)
    total_consomme = sum(l.montant_consomme for l in lignes)

    par_type = {}
    for type_budget in TYPES_BUDGET:
        du_type = [l for l in lignes if l.type_budget == type_budget]
        alloue = sum(l.montant_alloue for l in du_type)
        consomme = sum(l.montant_consomme for l in du_type)
        par_type[type_budget] = {
            "montantAlloue": alloue,
            "montantConsomme": consomme,
            "tauxConsommationPct": _taux(consomme, alloue),
        }

    nombre_depassements = sum(1 for l in lignes if _statut(_taux(l.montant_consomme, l.montant_alloue), l.seuil_alerte_pct) == "depassement")
    nombre_attentions = sum(1 for l in lignes if _statut(_taux(l.montant_consomme, l.montant_alloue), l.seuil_alerte_pct) == "attention")

    return {
        "budgetGlobalAlloue": total_alloue,
        "budgetGlobalConsomme": total_consomme,
        "tauxConsommationGlobalPct": _taux(total_consomme, total_alloue),
        "parType": par_type,
        "nombreDepassements": nombre_depassements,
        "nombreAttentions": nombre_attentions,
    }
