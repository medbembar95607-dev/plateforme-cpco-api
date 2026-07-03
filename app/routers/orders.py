from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/orders", tags=["orders"])

NEXT_STATUT = {"brouillon": "signe", "signe": "diffuse"}


def _serialize(order: models.Order) -> dict:
    return {
        "id": order.id,
        "numero": order.numero_ordre,
        "type": order.type_ordre,
        "classification": order.classification,
        "objet": order.objet,
        "contenu": order.contenu,
        "statut": order.statut,
        "emetteur": order.emetteur,
        "operationId": order.operation_id,
        "dateEmission": order.date_emission.isoformat() if order.date_emission else None,
        "destinataires": [
            {"uniteId": d.unit_id, "uniteNom": d.unit.nom_unite, "statut": d.statut} for d in order.destinataires
        ],
    }


@router.get("")
def list_orders(db: Session = Depends(get_db)):
    return [_serialize(o) for o in db.query(models.Order).all()]


@router.post("/{order_id}/advance")
def advance_order(order_id: str, db: Session = Depends(get_db)):
    """Fait passer un ordre à l'étape suivante du workflow (brouillon -> signé -> diffusé)."""
    order = db.get(models.Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Ordre introuvable")
    if order.statut not in NEXT_STATUT:
        raise HTTPException(status_code=400, detail=f"Aucune action possible depuis le statut '{order.statut}'")
    order.statut = NEXT_STATUT[order.statut]
    db.commit()
    db.refresh(order)
    return _serialize(order)
