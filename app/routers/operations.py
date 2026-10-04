import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import OperationOut

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=list[OperationOut])
def list_operations(db: Session = Depends(get_db)):
    return db.query(models.Operation).all()


def _derniere_position(db: Session, unit_id: str) -> models.UnitPosition | None:
    return (
        db.query(models.UnitPosition)
        .filter(models.UnitPosition.unit_id == unit_id)
        .order_by(models.UnitPosition.position_time.desc())
        .first()
    )


@router.get("/carte")
def carte_operations(db: Session = Depends(get_db)):
    """Géographie de chaque opération : point de référence, zones, axes, checkpoints rattachés,
    et unités engagées (destinataires des ordres de l'opération) avec leur dernière position."""
    out = []
    for op in db.query(models.Operation).all():
        zones = db.query(models.OperationalArea).filter(models.OperationalArea.operation_id == op.id).all()
        axes = db.query(models.ProgressAxis).filter(models.ProgressAxis.operation_id == op.id).all()
        checkpoints = db.query(models.Checkpoint).filter(models.Checkpoint.operation_id == op.id).all()
        unit_ids = {
            r.unit_id
            for r in db.query(models.OrderRecipient).join(models.Order).filter(models.Order.operation_id == op.id).all()
        }
        unites = []
        for unit_id in unit_ids:
            unite = db.get(models.Unit, unit_id)
            pos = _derniere_position(db, unit_id)
            if unite is not None and pos is not None:
                unites.append({"id": unite.id, "nom": unite.nom_unite, "typeUnite": unite.type_unite, "lon": pos.lon, "lat": pos.lat})
        out.append({
            "operationId": op.id,
            "lon": op.lon,
            "lat": op.lat,
            "zones": [{"id": z.id, "nom": z.nom, "typeZone": z.type_zone, "coordinates": json.loads(z.geom_json)} for z in zones],
            "axes": [{"id": a.id, "nom": a.nom, "coordinates": json.loads(a.geom_json)} for a in axes],
            "checkpoints": [{"id": c.id, "nom": c.nom, "statut": c.statut, "lon": c.lon, "lat": c.lat} for c in checkpoints],
            "unites": sorted(unites, key=lambda u: u["nom"]),
        })
    return out
