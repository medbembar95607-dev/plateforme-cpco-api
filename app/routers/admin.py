from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..schemas import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])

# Statique pour l'instant : reflète le RBAC documenté dans le cadrage
# (03-donnees/modele-donnees.md), pas encore de tables roles/permissions/role_permissions
# en base (à ajouter quand la gestion des permissions deviendra dynamique).
PERMISSIONS_PAR_ROLE = {
    "commandement": ["*.read", "orders.validate", "orders.sign", "intelligence.read_secret"],
    "officier_operations": ["orders.create", "orders.diffuse", "operations.write", "incidents.write"],
    "officier_renseignement": ["intelligence.write", "intelligence.read_secret", "threats.write"],
    "officier_logistique": ["logistics.write", "alert_thresholds.write"],
    "administrateur": ["users.write", "roles.write", "audit_log.read"],
}


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()


@router.get("/roles")
def list_roles():
    return PERMISSIONS_PAR_ROLE


@router.get("/audit-log")
def list_audit_log(db: Session = Depends(get_db)):
    entries = db.query(models.AuditLog).order_by(models.AuditLog.horodatage.desc()).limit(50).all()
    return [
        {"horodatage": e.horodatage.isoformat(), "userId": e.user_id, "action": e.action, "tableCible": e.table_cible}
        for e in entries
    ]
