import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(tags=["situation"])


def _last_position(db: Session, unit_id: str) -> models.UnitPosition | None:
    return (
        db.query(models.UnitPosition)
        .filter(models.UnitPosition.unit_id == unit_id)
        .order_by(models.UnitPosition.position_time.desc())
        .first()
    )


@router.get("/situation")
def get_situation(db: Session = Depends(get_db)):
    units = db.query(models.Unit).all()
    unites_out = []
    for u in units:
        pos = _last_position(db, u.id)
        unites_out.append(
            {
                "id": u.id,
                "nom": u.nom_unite,
                "typeUnite": u.type_unite,
                "echelon": u.echelon,
                "statut": u.statut,
                "effectif": u.effectif,
                "communication": u.communication,
                "lon": pos.lon if pos else None,
                "lat": pos.lat if pos else None,
            }
        )

    menaces = [
        {"id": m.id, "nom": m.nom, "niveau": m.niveau_menace, "statut": m.statut, "classification": m.classification, "lon": m.lon, "lat": m.lat}
        for m in db.query(models.Threat).all()
    ]
    checkpoints = [
        {"id": c.id, "nom": c.nom, "statut": c.statut, "dernierRapport": c.dernier_rapport, "lon": c.lon, "lat": c.lat}
        for c in db.query(models.Checkpoint).all()
    ]
    zones = [
        {"id": z.id, "nom": z.nom, "typeZone": z.type_zone, "coordinates": json.loads(z.geom_json)}
        for z in db.query(models.OperationalArea).all()
    ]
    axes = [
        {"id": a.id, "nom": a.nom, "coordinates": json.loads(a.geom_json)}
        for a in db.query(models.ProgressAxis).all()
    ]

    operations_actives = db.query(models.Operation).filter(models.Operation.statut.in_(["en_cours", "sous_tension"])).count()
    effectifs_engages = db.query(func.sum(models.Unit.effectif)).scalar() or 0
    menaces_confirmees = db.query(models.Threat).filter(models.Threat.statut == "confirmee").count()

    dernier_niveau_carburant = (
        db.query(models.StockLevel)
        .join(models.Stock)
        .filter(models.Stock.type_stock == "carburant")
        .order_by(models.StockLevel.horodatage.desc())
        .all()
    )
    niveau_logistique_moyen = round(sum(sl.pct for sl in dernier_niveau_carburant) / len(dernier_niveau_carburant)) if dernier_niveau_carburant else 0

    kpis = {
        "operationsActives": operations_actives,
        "unitesEngagees": len(units),
        "effectifsEngages": effectifs_engages,
        "menacesDetectees": db.query(models.Threat).count(),
        "menacesConfirmees": menaces_confirmees,
        "niveauLogistiquePct": niveau_logistique_moyen,
    }

    return {"unites": unites_out, "menaces": menaces, "checkpoints": checkpoints, "zones": zones, "axes": axes, "kpis": kpis}
