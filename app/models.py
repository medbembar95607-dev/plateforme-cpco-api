import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


# --- SECURITY -----------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    nom_complet: Mapped[str] = mapped_column(String(150))
    grade: Mapped[str] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("units.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(50))  # commandement, officier_operations, officier_renseignement, officier_logistique, administrateur
    clearance_level: Mapped[str] = mapped_column(String(20), default="confidentiel")
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


# --- OPS ------------------------------------------------------------------------

class Unit(Base):
    __tablename__ = "units"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code_unite: Mapped[str] = mapped_column(String(50))
    nom_unite: Mapped[str] = mapped_column(String(150))
    type_unite: Mapped[str] = mapped_column(String(50))  # pc, infanterie, artillerie, genie, logistique
    echelon: Mapped[str] = mapped_column(String(30))
    effectif: Mapped[int] = mapped_column(Integer, default=0)
    commandant: Mapped[str | None] = mapped_column(String(150), nullable=True)
    parent_unit_id: Mapped[str | None] = mapped_column(ForeignKey("units.id"), nullable=True)
    # Statut opérationnel (en_mission, en_progression, disponible, communication_degradee) — pas le statut
    # administratif (actif/en_reserve/dissous) du cahier des charges initial, celui-ci reste à ajouter
    # séparément si besoin (ex. colonne `statut_administratif`).
    statut: Mapped[str] = mapped_column(String(40), default="disponible")
    communication: Mapped[str] = mapped_column(String(20), default="stable")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)

    positions: Mapped[list["UnitPosition"]] = relationship(back_populates="unit", order_by="UnitPosition.position_time.desc()")


class UnitPosition(Base):
    __tablename__ = "unit_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    unit_id: Mapped[str] = mapped_column(ForeignKey("units.id"))
    position_time: Mapped[datetime] = mapped_column(DateTime, default=now)
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="manuel")
    saisi_par: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    unit: Mapped["Unit"] = relationship(back_populates="positions")


class OperationalArea(Base):
    __tablename__ = "operational_areas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    nom: Mapped[str] = mapped_column(String(200))
    type_zone: Mapped[str] = mapped_column(String(30))  # zone_ops, zone_interdite, zone_menace, zone_securisee
    niveau_risque: Mapped[int] = mapped_column(Integer, default=0)
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"), nullable=True)
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    # Polygone simplifié : liste de [lon, lat] sérialisée en JSON texte (remplacé par GEOGRAPHY(POLYGON) en prod)
    geom_json: Mapped[str] = mapped_column(Text)


class ProgressAxis(Base):
    __tablename__ = "progress_axes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    nom: Mapped[str] = mapped_column(String(150))
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"), nullable=True)
    geom_json: Mapped[str] = mapped_column(Text)  # liste de [lon, lat]


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    nom: Mapped[str] = mapped_column(String(150))
    ordre_passage: Mapped[int] = mapped_column(Integer, default=0)
    statut: Mapped[str] = mapped_column(String(30), default="prevu")
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"), nullable=True)
    dernier_rapport: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    code_operation: Mapped[str] = mapped_column(String(50))
    nom_operation: Mapped[str] = mapped_column(String(200))
    objectif: Mapped[str] = mapped_column(Text)
    commandant_operation: Mapped[str | None] = mapped_column(String(150), nullable=True)
    statut: Mapped[str] = mapped_column(String(30), default="planifiee")
    priorite: Mapped[str] = mapped_column(String(20), default="moyenne")
    progression: Mapped[int] = mapped_column(Integer, default=0)
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    date_lancement: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_fin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    numero_ordre: Mapped[str] = mapped_column(String(50))
    type_ordre: Mapped[str] = mapped_column(String(20))  # OPORD, FRAGO, WARNO
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    objet: Mapped[str] = mapped_column(String(250))
    contenu: Mapped[str] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(String(20), default="brouillon")  # brouillon, signe, diffuse, annule
    emetteur: Mapped[str] = mapped_column(String(150))
    operation_id: Mapped[str | None] = mapped_column(ForeignKey("operations.id"), nullable=True)
    date_emission: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    destinataires: Mapped[list["OrderRecipient"]] = relationship(back_populates="order")


class OrderRecipient(Base):
    __tablename__ = "order_recipients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    unit_id: Mapped[str] = mapped_column(ForeignKey("units.id"))
    statut: Mapped[str] = mapped_column(String(20), default="envoye")  # envoye, recu, accuse, execute

    order: Mapped["Order"] = relationship(back_populates="destinataires")
    unit: Mapped["Unit"] = relationship()


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    type_incident: Mapped[str] = mapped_column(String(30))  # securite, logistique, renseignement, medical, communication
    niveau_gravite: Mapped[str] = mapped_column(String(20))  # faible, moyenne, elevee, critique
    localite: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(String(20), default="nouveau")  # nouveau, en_cours, traite
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    declarant: Mapped[str] = mapped_column(String(150))
    date_incident: Mapped[datetime] = mapped_column(DateTime, default=now)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)


# --- RENS -------------------------------------------------------------------------

class IntelligenceReport(Base):
    __tablename__ = "intelligence_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reference: Mapped[str] = mapped_column(String(50))
    type_renseignement: Mapped[str] = mapped_column(String(20))  # HUMINT, SIGINT, OSINT, IMINT
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    titre: Mapped[str] = mapped_column(String(200))
    resume: Mapped[str] = mapped_column(Text)
    fiabilite_source: Mapped[str] = mapped_column(String(5), default="B")
    statut: Mapped[str] = mapped_column(String(20), default="observation")  # menace, observation, stabilise
    date_rapport: Mapped[datetime] = mapped_column(DateTime, default=now)


class Threat(Base):
    __tablename__ = "threats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    nom: Mapped[str] = mapped_column(String(200))
    type_menace: Mapped[str] = mapped_column(String(50), default="groupe_hostile")
    niveau_menace: Mapped[str] = mapped_column(String(20), default="moyenne")  # faible, moyenne, elevee, critique
    statut: Mapped[str] = mapped_column(String(20), default="a_verifier")  # confirmee, a_verifier, neutralisee
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    lon: Mapped[float] = mapped_column(Float)
    lat: Mapped[float] = mapped_column(Float)


# --- LOG --------------------------------------------------------------------------

class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    unit_id: Mapped[str] = mapped_column(ForeignKey("units.id"))
    type_stock: Mapped[str] = mapped_column(String(30))  # carburant, munitions, vivres, maintenance

    niveaux: Mapped[list["StockLevel"]] = relationship(back_populates="stock", order_by="StockLevel.horodatage.desc()")


class StockLevel(Base):
    __tablename__ = "stock_levels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    stock_id: Mapped[str] = mapped_column(ForeignKey("stocks.id"))
    pct: Mapped[float] = mapped_column(Float)
    horodatage: Mapped[datetime] = mapped_column(DateTime, default=now)

    stock: Mapped["Stock"] = relationship(back_populates="niveaux")


class AlertThreshold(Base):
    __tablename__ = "alert_thresholds"

    type_stock: Mapped[str] = mapped_column(String(30), primary_key=True)
    seuil_pct: Mapped[float] = mapped_column(Float)


# --- SYSTEM -------------------------------------------------------------------------

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    type_alerte: Mapped[str] = mapped_column(String(30))  # logistique, menace, communication, operationnelle
    niveau: Mapped[str] = mapped_column(String(20))  # info, attention, critique
    message: Mapped[str] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    statut: Mapped[str] = mapped_column(String(20), default="active")  # active, acquittee, resolue
    date_creation: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(20))  # create, update, delete
    table_cible: Mapped[str] = mapped_column(String(50))
    enregistrement_id: Mapped[str] = mapped_column(String(36))
    horodatage: Mapped[datetime] = mapped_column(DateTime, default=now)


# --- COURRIER (triage du chef d'état-major, 2026-07-03) -----------------------------

class Courrier(Base):
    __tablename__ = "courriers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    numero_enregistrement: Mapped[str] = mapped_column(String(50))
    type_document: Mapped[str] = mapped_column(String(30))  # note, message, fiche, rapport, compte_rendu, lettre
    origine: Mapped[str] = mapped_column(String(30))  # subordonne, ministere_defense, institution_externe
    expediteur: Mapped[str] = mapped_column(String(200))
    objet: Mapped[str] = mapped_column(String(250))
    resume: Mapped[str] = mapped_column(Text)
    contenu: Mapped[str] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    priorite: Mapped[str] = mapped_column(String(20), default="normal")  # normal, urgent, tres_urgent
    statut: Mapped[str] = mapped_column(String(20), default="nouveau")  # nouveau, annote, oriente, classe_sans_suite, traite
    date_reception: Mapped[datetime] = mapped_column(DateTime, default=now)
    date_limite_reponse: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    annotation: Mapped[str | None] = mapped_column(Text, nullable=True)
    annote_par: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    date_annotation: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    oriente_vers: Mapped[str | None] = mapped_column(String(150), nullable=True)
    ordre_genere_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), nullable=True)


# --- AGENDA (calendrier des rendez-vous du chef, 2026-07-05) -----------------------

class RendezVous(Base):
    __tablename__ = "rendez_vous"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    titre: Mapped[str] = mapped_column(String(200))
    type_rdv: Mapped[str] = mapped_column(String(30), default="reunion")  # reunion, audience, deplacement, ceremonie, briefing, autre
    date_debut: Mapped[datetime] = mapped_column(DateTime)
    date_fin: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lieu: Mapped[str] = mapped_column(String(200), default="")
    participants: Mapped[str] = mapped_column(String(300), default="")
    statut: Mapped[str] = mapped_column(String(20), default="a_confirmer")  # a_confirmer, confirme, annule
    classification: Mapped[str] = mapped_column(String(20), default="confidentiel")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
