from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/deploiement", tags=["deploiement"])


def _serialize(g: models.Garnison) -> dict:
    return {
        "id": g.id,
        "nom": g.nom,
        "typeUnite": g.type_unite,
        "echelon": g.echelon,
        "wilaya": g.wilaya,
        "localite": g.localite,
        "armee": g.armee,
        "effectif": g.effectif,
        "statut": g.statut,
        "lon": g.lon,
        "lat": g.lat,
        "carburantPct": g.carburant_pct,
        "munitionsPct": g.munitions_pct,
        "armementPct": g.armement_pct,
        "vivresPct": g.vivres_pct,
        "classification": g.classification,
    }


@router.get("")
def list_garnisons(db: Session = Depends(get_db)):
    garnisons = db.query(models.Garnison).order_by(models.Garnison.wilaya).all()
    return [_serialize(g) for g in garnisons]
