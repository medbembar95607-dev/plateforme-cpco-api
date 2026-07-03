from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/units", tags=["units"])


@router.get("")
def list_units(db: Session = Depends(get_db)):
    units = db.query(models.Unit).all()
    out = []
    for u in units:
        pos = (
            db.query(models.UnitPosition)
            .filter(models.UnitPosition.unit_id == u.id)
            .order_by(models.UnitPosition.position_time.desc())
            .first()
        )
        out.append(
            {
                "id": u.id,
                "nom": u.nom_unite,
                "typeUnite": u.type_unite,
                "echelon": u.echelon,
                "statut": u.statut,
                "effectif": u.effectif,
                "communication": u.communication,
                "dernierRapport": pos.position_time.strftime("%H:%M") if pos else None,
            }
        )
    return out
