from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/veille", tags=["veille"])

NIVEAU_POIDS = {"faible": 1, "modere": 2, "eleve": 3, "critique": 4}


def _serialize(s: models.SignalStrategique) -> dict:
    return {
        "id": s.id,
        "categorie": s.categorie,
        "titre": s.titre,
        "zone": s.zone,
        "niveauRisque": s.niveau_risque,
        "tendance": s.tendance,
        "probabiliteCrisePct": s.probabilite_crise_pct,
        "horizon": s.horizon,
        "analyse": s.analyse,
        "source": s.source,
        "dateMaj": s.date_maj.isoformat(),
        "classification": s.classification,
    }


@router.get("")
def list_signaux(db: Session = Depends(get_db)):
    signaux = db.query(models.SignalStrategique).order_by(models.SignalStrategique.probabilite_crise_pct.desc()).all()
    return [_serialize(s) for s in signaux]


@router.get("/indicateurs")
def indicateurs(db: Session = Depends(get_db)):
    signaux = db.query(models.SignalStrategique).all()
    if not signaux:
        return {
            "indiceRisqueRegionalPct": 0,
            "signauxCritiques": 0,
            "signauxEnHausse": 0,
            "zonesSurveillees": 0,
            "probabiliteMaxPct": 0,
        }

    # Indice pondéré par le niveau de risque plutôt qu'une simple moyenne : un signal critique
    # doit peser davantage sur l'indice global qu'un signal faible, même à probabilité égale.
    poids_total = sum(NIVEAU_POIDS[s.niveau_risque] for s in signaux)
    indice = sum(s.probabilite_crise_pct * NIVEAU_POIDS[s.niveau_risque] for s in signaux) / poids_total

    return {
        "indiceRisqueRegionalPct": round(indice),
        "signauxCritiques": sum(1 for s in signaux if s.niveau_risque == "critique"),
        "signauxEnHausse": sum(1 for s in signaux if s.tendance == "hausse"),
        "zonesSurveillees": len({s.zone for s in signaux}),
        "probabiliteMaxPct": max(s.probabilite_crise_pct for s in signaux),
    }
