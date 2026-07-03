from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/logistics", tags=["logistics"])


def _last_level(db: Session, stock_id: str) -> float | None:
    row = (
        db.query(models.StockLevel)
        .filter(models.StockLevel.stock_id == stock_id)
        .order_by(models.StockLevel.horodatage.desc())
        .first()
    )
    return row.pct if row else None


@router.get("")
def list_logistics(db: Session = Depends(get_db)):
    thresholds = {t.type_stock: t.seuil_pct for t in db.query(models.AlertThreshold).all()}
    units_with_stocks = (
        db.query(models.Unit)
        .join(models.Stock, models.Stock.unit_id == models.Unit.id)
        .distinct()
        .all()
    )

    out = []
    for unit in units_with_stocks:
        stocks = db.query(models.Stock).filter(models.Stock.unit_id == unit.id).all()
        valeurs = {s.type_stock: _last_level(db, s.id) or 0 for s in stocks}
        carburant = valeurs.get("carburant", 0)
        munitions = valeurs.get("munitions", 0)
        vivres = valeurs.get("vivres", 0)
        maintenance = valeurs.get("maintenance", 0)

        seuil_carburant = thresholds.get("carburant", 40)
        seuil_vivres = thresholds.get("vivres", 30)
        seuil_munitions = thresholds.get("munitions", 50)
        marge_attention = 10  # bande d'alerte "attention" au-dessus du seuil critique

        if carburant < seuil_carburant or munitions < seuil_munitions or vivres < seuil_vivres:
            alerte = "critique"
        elif carburant < seuil_carburant + marge_attention or munitions < seuil_munitions + marge_attention or vivres < seuil_vivres + marge_attention:
            alerte = "attention"
        else:
            alerte = "normal"

        out.append(
            {
                "uniteId": unit.id,
                "uniteNom": unit.nom_unite,
                "carburantPct": carburant,
                "munitionsPct": munitions,
                "vivresPct": vivres,
                "maintenancePct": maintenance,
                "alerte": alerte,
            }
        )
    return out


@router.get("/thresholds")
def get_thresholds(db: Session = Depends(get_db)):
    return {t.type_stock: t.seuil_pct for t in db.query(models.AlertThreshold).all()}
