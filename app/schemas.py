from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code_unite: str
    nom_unite: str
    type_unite: str
    echelon: str
    effectif: int
    commandant: str | None
    statut: str
    communication: str


class UnitWithPositionOut(UnitOut):
    lon: float | None = None
    lat: float | None = None
    dernier_rapport: str | None = None
    carburant_pct: float | None = None
    munitions_pct: float | None = None


class ThreatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    nom: str
    type_menace: str
    niveau_menace: str
    statut: str
    classification: str
    lon: float
    lat: float


class CheckpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    nom: str
    statut: str
    dernier_rapport: str | None
    lon: float
    lat: float


class IntelligenceReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    reference: str
    type_renseignement: str
    classification: str
    titre: str
    resume: str
    fiabilite_source: str
    statut: str


class StockLevelRow(BaseModel):
    unite_id: str
    unite_nom: str
    carburant_pct: float
    munitions_pct: float
    vivres_pct: float
    maintenance_pct: float
    alerte: str


class OperationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code_operation: str
    nom_operation: str
    objectif: str
    statut: str
    priorite: str
    progression: int


class OrderRecipientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    unit_id: str
    unit_nom: str
    statut: str


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    numero_ordre: str
    type_ordre: str
    classification: str
    objet: str
    contenu: str
    statut: str
    emetteur: str
    operation_id: str | None
    date_emission: datetime | None
    destinataires: list[OrderRecipientOut] = []


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type_incident: str
    niveau_gravite: str
    localite: str
    description: str
    statut: str
    declarant: str
    date_incident: datetime


class IncidentCreate(BaseModel):
    type_incident: str
    niveau_gravite: str
    localite: str
    description: str
    declarant: str
    lon: float | None = None
    lat: float | None = None


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type_alerte: str
    niveau: str
    message: str
    statut: str
    date_creation: datetime


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    nom_complet: str
    grade: str
    role: str
    clearance_level: str
    actif: bool
