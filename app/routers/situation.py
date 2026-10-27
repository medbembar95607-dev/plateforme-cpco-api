import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from .logistics import list_logistics

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

    # Niveaux moyens par domaine : dernier niveau de stock de chaque unité suivie, puis moyenne.
    lignes = list_logistics(db)

    def moyenne(cle: str) -> int:
        return round(sum(l[cle] for l in lignes) / len(lignes)) if lignes else 0

    # Personnel : effectif présent / effectif théorique, sur les unités dont le TED est connu.
    avec_ted = [u for u in units if u.effectif_theorique]
    theorique = sum(u.effectif_theorique for u in avec_ted)
    personnel = round(100 * sum(u.effectif for u in avec_ted) / theorique) if theorique else 0

    niveaux = {
        "personnel": personnel,
        "armement": moyenne("armementPct"),
        "munitions": moyenne("munitionsPct"),
        "vivres": moyenne("vivresPct"),
        "carburant": moyenne("carburantPct"),
        "auto": moyenne("vehiculePct"),
    }
    niveau_logistique_moyen = round(sum(niveaux.values()) / len(niveaux))

    kpis = {
        "operationsActives": operations_actives,
        "unitesEngagees": len(units),
        "effectifsEngages": effectifs_engages,
        "menacesDetectees": db.query(models.Threat).count(),
        "menacesConfirmees": menaces_confirmees,
        "niveauLogistiquePct": niveau_logistique_moyen,
        "niveauxLogistiques": niveaux,
    }

    return {"unites": unites_out, "menaces": menaces, "checkpoints": checkpoints, "zones": zones, "axes": axes, "kpis": kpis}
