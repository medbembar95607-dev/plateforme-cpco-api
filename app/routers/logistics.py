from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..audit import exiger_role, get_acting_user_id, log_action
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
        armement = valeurs.get("armement", 0)
        sante = valeurs.get("sante", 0)
        vehicule = valeurs.get("vehicule", 0)

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
                "armementPct": armement,
                "santePct": sante,
                "vehiculePct": vehicule,
                "alerte": alerte,
            }
        )
    return out


@router.get("/thresholds")
def get_thresholds(db: Session = Depends(get_db)):
    return {t.type_stock: t.seuil_pct for t in db.query(models.AlertThreshold).all()}


# --- Demandes de ravitaillement (2026-10-04) -------------------------------------------

# Toute la cellule peut demander pour une unité ; seuls la logistique et le commandement traitent.
ROLES_TRAITEMENT = {"officier_logistique", "commandement", "administrateur"}
TYPES_STOCK = {"carburant", "munitions", "vivres", "maintenance", "armement", "sante", "vehicule"}
PRIORITES = {"routine", "urgent", "vital"}


def _serialize_demande(d: models.DemandeRavitaillement, db: Session) -> dict:
    unite = db.get(models.Unit, d.unit_id)
    demandeur = db.get(models.User, d.demandeur_id) if d.demandeur_id else None
    traitant = db.get(models.User, d.traite_par) if d.traite_par else None
    return {
        "id": d.id,
        "uniteId": d.unit_id,
        "uniteNom": unite.nom_unite if unite else "—",
        "typeStock": d.type_stock,
        "pointsPct": d.points_pct,
        "priorite": d.priorite,
        "statut": d.statut,
        "commentaire": d.commentaire,
        "demandeur": demandeur.nom_complet if demandeur else None,
        "traitePar": traitant.nom_complet if traitant else None,
        "dateDemande": d.date_demande.isoformat(),
        "dateTraitement": d.date_traitement.isoformat() if d.date_traitement else None,
    }


@router.get("/demandes")
def list_demandes(db: Session = Depends(get_db)):
    demandes = db.query(models.DemandeRavitaillement).order_by(models.DemandeRavitaillement.date_demande.desc()).all()
    return [_serialize_demande(d, db) for d in demandes]


class DemandeCreate(BaseModel):
    unit_id: str
    type_stock: str
    points_pct: float = Field(gt=0, le=100)
    priorite: str = "routine"
    commentaire: str = ""


@router.post("/demandes")
def create_demande(payload: DemandeCreate, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    if user_id is None or db.get(models.User, user_id) is None:
        raise HTTPException(status_code=403, detail="Utilisateur non identifié")
    if payload.type_stock not in TYPES_STOCK or payload.priorite not in PRIORITES:
        raise HTTPException(status_code=422, detail="Ressource ou priorité invalide")
    if db.get(models.Unit, payload.unit_id) is None:
        raise HTTPException(status_code=404, detail="Unité introuvable")
    demande = models.DemandeRavitaillement(
        unit_id=payload.unit_id,
        type_stock=payload.type_stock,
        points_pct=payload.points_pct,
        priorite=payload.priorite,
        commentaire=payload.commentaire.strip(),
        demandeur_id=user_id,
    )
    db.add(demande)
    db.commit()
    db.refresh(demande)
    log_action(db, user_id=user_id, action="create", table_cible="demandes_ravitaillement", enregistrement_id=demande.id)
    return _serialize_demande(demande, db)


def _demande_ouverte(db: Session, demande_id: str) -> models.DemandeRavitaillement:
    demande = db.get(models.DemandeRavitaillement, demande_id)
    if demande is None:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    if demande.statut not in ("demandee", "en_cours"):
        raise HTTPException(status_code=409, detail=f"Demande déjà clôturée ({demande.statut})")
    return demande


def _cloturer(db: Session, demande: models.DemandeRavitaillement, statut: str, user_id: str | None) -> dict:
    demande.statut = statut
    demande.traite_par = user_id
    demande.date_traitement = datetime.now(timezone.utc)
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible="demandes_ravitaillement", enregistrement_id=demande.id)
    return _serialize_demande(demande, db)


@router.post("/demandes/{demande_id}/prendre-en-charge")
def prendre_en_charge(demande_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    exiger_role(db, user_id, ROLES_TRAITEMENT, "traitement des demandes par la logistique")
    demande = _demande_ouverte(db, demande_id)
    if demande.statut != "demandee":
        raise HTTPException(status_code=409, detail="Demande déjà prise en charge")
    return _cloturer(db, demande, "en_cours", user_id)


@router.post("/demandes/{demande_id}/refuser")
def refuser(demande_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    exiger_role(db, user_id, ROLES_TRAITEMENT, "traitement des demandes par la logistique")
    return _cloturer(db, _demande_ouverte(db, demande_id), "refusee", user_id)


@router.post("/demandes/{demande_id}/livrer")
def livrer(demande_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    """Clôt la demande et relève le niveau du stock concerné (nouvelle ligne d'historique
    StockLevel, plafonnée à 100 %), dans la même transaction."""
    exiger_role(db, user_id, ROLES_TRAITEMENT, "traitement des demandes par la logistique")
    demande = _demande_ouverte(db, demande_id)
    stock = (
        db.query(models.Stock)
        .filter(models.Stock.unit_id == demande.unit_id, models.Stock.type_stock == demande.type_stock)
        .first()
    )
    if stock is None:
        stock = models.Stock(unit_id=demande.unit_id, type_stock=demande.type_stock)
        db.add(stock)
        db.flush()
    niveau_actuel = _last_level(db, stock.id) or 0
    db.add(models.StockLevel(stock_id=stock.id, pct=min(100, niveau_actuel + demande.points_pct)))
    return _cloturer(db, demande, "livree", user_id)
