from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from . import models


def get_acting_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str | None:
    """Pas d'authentification pour l'instant (voir README) : le frontend envoie l'utilisateur
    sélectionné dans le sélecteur de démonstration via cet en-tête. À remplacer par un vrai
    utilisateur authentifié (JWT) quand l'auth sera construite."""
    return x_user_id


def exiger_role(db: Session, user_id: str | None, roles: set[str], action: str) -> models.User:
    """Contrôle d'accès par rôle, sur l'utilisateur du sélecteur de démonstration (en-tête non
    vérifié tant qu'il n'y a pas d'authentification réelle : la règle est en place, pas la preuve
    d'identité)."""
    user = db.get(models.User, user_id) if user_id else None
    if user is None or user.role not in roles:
        raise HTTPException(status_code=403, detail=f"Action réservée : {action}")
    return user


def log_action(db: Session, *, user_id: str | None, action: str, table_cible: str, enregistrement_id: str) -> None:
    db.add(models.AuditLog(user_id=user_id, action=action, table_cible=table_cible, enregistrement_id=enregistrement_id))
    db.commit()
