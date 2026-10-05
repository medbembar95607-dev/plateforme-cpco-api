"""Saisie manuelle pour l'écran de démonstration (2026-10-05).

1. GET /demo/schema : description des formulaires de chaque type d'impact (correction d'un impact
   proposé, ajout d'un impact à la main) et listes de référence (unités, lieux, lignes budgétaires,
   matériels). Le frontend génère ses formulaires à partir de cette description.
2. /demo/donnees : modification et suppression d'éléments existants, par catégorie, sur une liste
   blanche de champs. Chaque écriture est tracée dans le journal d'audit."""

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..audit import get_acting_user_id, log_action
from ..database import get_db
from .demo import LIEUX

router = APIRouter(prefix="/demo", tags=["demo"])


def _options(*paires: tuple[str, str]) -> list[dict]:
    return [{"valeur": v, "libelle": l} for v, l in paires]


GRAVITES = _options(("faible", "Faible"), ("moyenne", "Moyenne"), ("elevee", "Élevée"), ("critique", "Critique"))
TYPES_INCIDENT = _options(("securite", "Sécurité"), ("logistique", "Logistique"), ("renseignement", "Renseignement"),
                          ("medical", "Médical"), ("communication", "Communication"))
STATUTS_INCIDENT = _options(("nouveau", "Nouveau"), ("en_cours", "En cours"), ("traite", "Traité"))
NIVEAUX_ALERTE = _options(("info", "Info"), ("attention", "Attention"), ("critique", "Critique"))
TYPES_ALERTE = _options(("menace", "Menace"), ("logistique", "Logistique"), ("communication", "Communication"),
                        ("operationnelle", "Opérationnelle"))
STATUTS_ALERTE = _options(("active", "Active"), ("acquittee", "Acquittée"), ("resolue", "Résolue"))
TYPES_RENS = _options(("HUMINT", "HUMINT"), ("SIGINT", "SIGINT"), ("OSINT", "OSINT"), ("IMINT", "IMINT"))
CLASSIFICATIONS = _options(("diffusion_libre", "Diffusion libre"), ("confidentiel", "Confidentiel"), ("secret", "Secret"),
                           ("tres_secret", "Très Secret"))
FIABILITES = _options(*[(l, l) for l in "ABCDEF"])
CREDIBILITES = _options(*[(str(i), str(i)) for i in range(1, 7)])
STATUTS_RENS = _options(("menace", "Menace"), ("observation", "Observation"), ("stabilise", "Stabilisé"))
TYPES_STOCK = _options(("carburant", "Carburant"), ("munitions", "Munitions"), ("vivres", "Vivres"), ("maintenance", "Maintenance"),
                       ("armement", "Armement"), ("sante", "Santé"), ("vehicule", "Véhicules"))
PRIORITES_DEMANDE = _options(("routine", "Routine"), ("urgent", "Urgent"), ("vital", "Vital"))
STATUTS_DEMANDE = _options(("demandee", "Demandée"), ("en_cours", "En cours"), ("livree", "Livrée"), ("refusee", "Refusée"))
TYPES_COURRIER = _options(("note", "Note"), ("message", "Message"), ("fiche", "Fiche"), ("rapport", "Rapport"),
                          ("compte_rendu", "Compte rendu"), ("lettre", "Lettre"))
ORIGINES_COURRIER = _options(("subordonne", "Subordonné"), ("ministere_defense", "Ministère de la Défense"),
                             ("institution_externe", "Institution externe"))
PRIORITES_COURRIER = _options(("normal", "Normal"), ("urgent", "Urgent"), ("tres_urgent", "Très urgent"))
STATUTS_COURRIER = _options(("nouveau", "Nouveau"), ("annote", "Annoté"), ("oriente", "Orienté"),
                            ("classe_sans_suite", "Classé sans suite"), ("traite", "Traité"))
TYPES_ORDRE = _options(("INSTRUCTION", "Instruction"), ("OPORD", "OPORD"), ("FRAGO", "FRAGO"), ("WARNO", "WARNO"))
STATUTS_SUIVI = _options(("en_attente", "En attente"), ("en_cours", "En cours"), ("execute", "Exécuté"))
TYPES_RDV = _options(("reunion", "Réunion"), ("briefing", "Briefing"), ("audience", "Audience"), ("deplacement", "Déplacement"),
                     ("ceremonie", "Cérémonie"), ("autre", "Autre"))
STATUTS_RDV = _options(("a_confirmer", "À confirmer"), ("confirme", "Confirmé"), ("annule", "Annulé"))
CATEGORIES_MATERIEL = _options(("vehicule", "Véhicule"), ("arme", "Armement"), ("communication", "Communication"),
                               ("aeronef", "Aéronef"), ("optique", "Optique"), ("munition", "Munition"), ("equipement", "Équipement"))
ETATS_MATERIEL = _options(("operationnel", "Opérationnel"), ("maintenance", "En maintenance"), ("hors_service", "Hors service"))
CATEGORIES_PERSONNEL = _options(("officier", "Officier"), ("sous_officier", "Sous-officier"), ("homme_du_rang", "Homme du rang"))
PRIORITES_RH = _options(("normale", "Normale"), ("elevee", "Élevée"), ("critique", "Critique"))
STATUTS_UNITE = _options(("disponible", "Disponible"), ("en_mission", "En mission"), ("en_progression", "En progression"),
                         ("communication_degradee", "Communication dégradée"))
COMMUNICATIONS = _options(("stable", "Stable"), ("degradee", "Dégradée"))


def champ(cle: str, libelle: str, type_champ: str, options: list[dict] | None = None, obligatoire: bool = True) -> dict:
    """Types : texte, texte_long, nombre, choix, dateheure, position (lieu + lon/lat), unite, unites,
    ligne_budget, materiel."""
    return {"cle": cle, "libelle": libelle, "type": type_champ, "options": options or [], "obligatoire": obligatoire}


# --- 1. Formulaires d'impacts (variante = type, ou type_mode pour le matériel) --------------
SCHEMA_IMPACTS = {
    "incident": {"libelle": "Incident", "ecran": "incidents", "champs": [
        champ("type_incident", "Type", "choix", TYPES_INCIDENT), champ("niveau_gravite", "Gravité", "choix", GRAVITES),
        champ("position", "Lieu", "position", obligatoire=False), champ("description", "Description", "texte_long"),
        champ("declarant", "Déclarant", "texte")]},
    "alerte": {"libelle": "Alerte", "ecran": "alertes", "champs": [
        champ("type_alerte", "Type", "choix", TYPES_ALERTE), champ("niveau", "Niveau", "choix", NIVEAUX_ALERTE),
        champ("message", "Message", "texte_long"), champ("position", "Lieu", "position", obligatoire=False)]},
    "rapport_rens": {"libelle": "Rapport de renseignement", "ecran": "renseignement", "champs": [
        champ("titre", "Titre", "texte"), champ("type_renseignement", "Source", "choix", TYPES_RENS),
        champ("classification", "Classification", "choix", CLASSIFICATIONS),
        champ("fiabilite_source", "Fiabilité (A-F)", "choix", FIABILITES), champ("credibilite_info", "Crédibilité (1-6)", "choix", CREDIBILITES),
        champ("statut", "Évaluation", "choix", STATUTS_RENS), champ("resume", "Résumé", "texte_long"),
        champ("position", "Lieu", "position", obligatoire=False)]},
    "demande_ravitaillement": {"libelle": "Demande de ravitaillement", "ecran": "logistique", "champs": [
        champ("unit_id", "Unité", "unite"), champ("type_stock", "Ressource", "choix", TYPES_STOCK),
        champ("points_pct", "Complément (points de %)", "nombre"), champ("priorite", "Priorité", "choix", PRIORITES_DEMANDE),
        champ("commentaire", "Commentaire", "texte", obligatoire=False)]},
    "courrier": {"libelle": "Courrier arrivé", "ecran": "courrier", "champs": [
        champ("objet", "Objet", "texte"), champ("expediteur", "Expéditeur", "texte"),
        champ("type_document", "Type", "choix", TYPES_COURRIER), champ("origine", "Origine", "choix", ORIGINES_COURRIER),
        champ("priorite", "Priorité", "choix", PRIORITES_COURRIER), champ("resume", "Résumé", "texte_long"),
        champ("contenu", "Contenu", "texte_long")]},
    "suivi_execution": {"libelle": "Instruction à suivre", "ecran": "suivi_execution", "champs": [
        champ("objet", "Objet", "texte"), champ("unites", "Unités destinataires", "unites"),
        champ("type_ordre", "Type", "choix", TYPES_ORDRE), champ("date_limite", "Échéance", "dateheure"),
        champ("instruction", "Instruction", "texte_long"), champ("emetteur", "Émetteur", "texte")]},
    "rendez_vous": {"libelle": "Rendez-vous", "ecran": "calendrier", "champs": [
        champ("titre", "Titre", "texte"), champ("type_rdv", "Type", "choix", TYPES_RDV),
        champ("date_debut", "Début", "dateheure"), champ("date_fin", "Fin", "dateheure"),
        champ("lieu", "Lieu", "texte"), champ("participants", "Participants", "texte", obligatoire=False),
        champ("notes", "Notes", "texte_long", obligatoire=False)]},
    "materiel_creation": {"libelle": "Matériel indisponible (nouvelle ligne)", "ecran": "materiel", "type": "materiel", "mode": "creation", "champs": [
        champ("nom", "Désignation", "texte"), champ("categorie", "Catégorie", "choix", CATEGORIES_MATERIEL),
        champ("nombre", "Nombre", "nombre"), champ("etat", "État", "choix", ETATS_MATERIEL),
        champ("formation_affectation", "Formation d'affectation", "texte"), champ("fonction", "Observation", "texte", obligatoire=False)]},
    "materiel_decompte": {"libelle": "Matériel retiré d'un stock existant", "ecran": "materiel", "type": "materiel", "mode": "decompte", "champs": [
        champ("materiel_id", "Matériel", "materiel"), champ("nombre", "Nombre retiré", "nombre")]},
    "budget": {"libelle": "Dépense budgétaire", "ecran": "budget", "champs": [
        champ("ligne_id", "Ligne budgétaire", "ligne_budget"), champ("montant", "Montant (MRU)", "nombre")]},
    "recrutement": {"libelle": "Besoin en recrutement", "ecran": "rh", "champs": [
        champ("poste", "Poste", "texte"), champ("categorie", "Catégorie", "choix", CATEGORIES_PERSONNEL),
        champ("nombre_postes", "Nombre de postes", "nombre"), champ("priorite", "Priorité", "choix", PRIORITES_RH),
        champ("formation_affectation", "Affectation", "texte")]},
    "formation": {"libelle": "Besoin en formation", "ecran": "rh", "champs": [
        champ("intitule", "Intitulé", "texte"), champ("categorie", "Catégorie", "choix", CATEGORIES_PERSONNEL),
        champ("nombre_places", "Nombre de places", "nombre"), champ("priorite", "Priorité", "choix", PRIORITES_RH),
        champ("formation_affectation", "Affectation", "texte")]},
}


def _references(db: Session) -> dict:
    return {
        "unites": [{"id": u.id, "nom": u.nom_unite} for u in db.query(models.Unit).order_by(models.Unit.nom_unite).all()],
        "lieux": [{"cle": c, "libelle": l, "lon": lon, "lat": lat} for c, (l, lon, lat) in LIEUX.items()],
        "lignes": [{"id": l.id, "libelle": l.libelle} for l in db.query(models.LigneBudgetaire).order_by(models.LigneBudgetaire.libelle).all()],
        "materiels": [{"id": m.id, "nom": f"{m.nom} ({m.formation_affectation}, {m.quantite})"}
                      for m in db.query(models.Materiel).order_by(models.Materiel.nom).all()],
    }


@router.get("/schema")
def schema(db: Session = Depends(get_db)):
    return {"impacts": SCHEMA_IMPACTS, "references": _references(db)}


# --- 2. Éditeur de données existantes ------------------------------------------------------
def _derniere_position(db: Session, unit_id: str) -> models.UnitPosition | None:
    return db.query(models.UnitPosition).filter(models.UnitPosition.unit_id == unit_id).order_by(models.UnitPosition.position_time.desc()).first()


def _dernier_niveau(db: Session, stock_id: str) -> float | None:
    niveau = db.query(models.StockLevel).filter(models.StockLevel.stock_id == stock_id).order_by(models.StockLevel.horodatage.desc()).first()
    return niveau.pct if niveau else None


# Ressources génériques : modèle, champs modifiables, libellé d'une ligne, suppression autorisée.
RESSOURCES = {
    "incidents": {"libelle": "Incidents", "ecran": "incidents", "modele": models.Incident, "suppression": True,
                  "titre": lambda o: f"{o.localite} — {o.type_incident}", "tri": lambda: models.Incident.date_incident.desc(),
                  "champs": [champ("type_incident", "Type", "choix", TYPES_INCIDENT), champ("niveau_gravite", "Gravité", "choix", GRAVITES),
                             champ("statut", "Statut", "choix", STATUTS_INCIDENT), champ("localite", "Localité", "texte"),
                             champ("position", "Position", "position", obligatoire=False), champ("description", "Description", "texte_long")]},
    "alertes": {"libelle": "Alertes", "ecran": "alertes", "modele": models.Alert, "suppression": True,
                "titre": lambda o: o.message, "tri": lambda: models.Alert.date_creation.desc(),
                "champs": [champ("niveau", "Niveau", "choix", NIVEAUX_ALERTE), champ("statut", "Statut", "choix", STATUTS_ALERTE),
                           champ("type_alerte", "Type", "choix", TYPES_ALERTE), champ("message", "Message", "texte_long"),
                           champ("position", "Position", "position", obligatoire=False)]},
    "renseignement": {"libelle": "Rapports de renseignement", "ecran": "renseignement", "modele": models.IntelligenceReport, "suppression": True,
                      "titre": lambda o: f"{o.reference} — {o.titre}", "tri": lambda: models.IntelligenceReport.date_rapport.desc(),
                      "champs": [champ("titre", "Titre", "texte"), champ("statut", "Évaluation", "choix", STATUTS_RENS),
                                 champ("fiabilite_source", "Fiabilité", "choix", FIABILITES), champ("credibilite_info", "Crédibilité", "choix", CREDIBILITES),
                                 champ("classification", "Classification", "choix", CLASSIFICATIONS), champ("resume", "Résumé", "texte_long"),
                                 champ("position", "Position", "position", obligatoire=False)]},
    "demandes": {"libelle": "Demandes de ravitaillement", "ecran": "logistique", "modele": models.DemandeRavitaillement, "suppression": True,
                 "titre": lambda o: f"{o.type_stock} +{o.points_pct:g} pts", "tri": lambda: models.DemandeRavitaillement.date_demande.desc(),
                 "champs": [champ("priorite", "Priorité", "choix", PRIORITES_DEMANDE), champ("statut", "Statut", "choix", STATUTS_DEMANDE),
                            champ("points_pct", "Complément (points)", "nombre"), champ("commentaire", "Commentaire", "texte", obligatoire=False)]},
    "materiel": {"libelle": "Matériel", "ecran": "materiel", "modele": models.Materiel, "suppression": True,
                 "titre": lambda o: f"{o.nom} — {o.formation_affectation}", "tri": lambda: models.Materiel.nom,
                 "champs": [champ("quantite", "Quantité", "nombre"), champ("etat", "État", "choix", ETATS_MATERIEL),
                            champ("seuil_alerte", "Seuil d'alerte", "nombre"), champ("dotation_ted", "Dotation TED", "nombre"),
                            champ("formation_affectation", "Affectation", "texte")]},
    "budget": {"libelle": "Lignes budgétaires", "ecran": "budget", "modele": models.LigneBudgetaire, "suppression": False,
               "titre": lambda o: o.libelle, "tri": lambda: models.LigneBudgetaire.libelle,
               "champs": [champ("montant_alloue", "Alloué (MRU)", "nombre"), champ("montant_consomme", "Consommé (MRU)", "nombre"),
                          champ("seuil_alerte_pct", "Seuil d'alerte (%)", "nombre")]},
    "recrutement": {"libelle": "Besoins en recrutement", "ecran": "rh", "modele": models.BesoinRecrutement, "suppression": True,
                    "titre": lambda o: f"{o.poste} ({o.nombre_postes})", "tri": lambda: models.BesoinRecrutement.poste,
                    "champs": [champ("poste", "Poste", "texte"), champ("nombre_postes", "Nombre de postes", "nombre"),
                               champ("priorite", "Priorité", "choix", PRIORITES_RH), champ("categorie", "Catégorie", "choix", CATEGORIES_PERSONNEL),
                               champ("statut", "Statut", "choix", _options(("ouvert", "Ouvert"), ("pourvu", "Pourvu")))]},
    "formation": {"libelle": "Besoins en formation", "ecran": "rh", "modele": models.BesoinFormation, "suppression": True,
                  "titre": lambda o: f"{o.intitule} ({o.nombre_places})", "tri": lambda: models.BesoinFormation.intitule,
                  "champs": [champ("intitule", "Intitulé", "texte"), champ("nombre_places", "Nombre de places", "nombre"),
                             champ("priorite", "Priorité", "choix", PRIORITES_RH), champ("categorie", "Catégorie", "choix", CATEGORIES_PERSONNEL),
                             champ("statut", "Statut", "choix", _options(("a_planifier", "À planifier"), ("planifie", "Planifié"), ("realise", "Réalisé")))]},
    "agenda": {"libelle": "Agenda du chef", "ecran": "calendrier", "modele": models.RendezVous, "suppression": True,
               "titre": lambda o: f"{o.titre} — {o.date_debut:%d/%m %H:%M}", "tri": lambda: models.RendezVous.date_debut,
               "champs": [champ("titre", "Titre", "texte"), champ("type_rdv", "Type", "choix", TYPES_RDV),
                          champ("date_debut", "Début", "dateheure"), champ("date_fin", "Fin", "dateheure", obligatoire=False),
                          champ("lieu", "Lieu", "texte"), champ("statut", "Statut", "choix", STATUTS_RDV)]},
    "courrier": {"libelle": "Courrier (parapheur)", "ecran": "courrier", "modele": models.Courrier, "suppression": True,
                 "titre": lambda o: f"{o.numero_enregistrement} — {o.objet}", "tri": lambda: models.Courrier.date_reception.desc(),
                 "champs": [champ("objet", "Objet", "texte"), champ("priorite", "Priorité", "choix", PRIORITES_COURRIER),
                            champ("statut", "Statut", "choix", STATUTS_COURRIER), champ("resume", "Résumé", "texte_long")]},
    "instructions": {"libelle": "Instructions (suivi d'exécution)", "ecran": "suivi_execution", "modele": models.SuiviExecution, "suppression": True,
                     "titre": lambda o: f"{o.reference} — {o.objet}", "tri": lambda: models.SuiviExecution.date_limite.desc(),
                     "champs": [champ("objet", "Objet", "texte"), champ("statut", "Statut", "choix", STATUTS_SUIVI),
                                champ("date_limite", "Échéance", "dateheure"), champ("compte_rendu", "Compte rendu", "texte_long", obligatoire=False)]},
}

# Ressources calculées : position/statut des unités (historique de positions), niveaux logistiques (%).
RESSOURCE_UNITES = {"libelle": "Unités (position et statut)", "ecran": "unites", "suppression": False,
                    "champs": [champ("statut", "Statut", "choix", STATUTS_UNITE), champ("communication", "Liaison", "choix", COMMUNICATIONS),
                               champ("effectif", "Effectif", "nombre"), champ("position", "Position", "position")]}
RESSOURCE_STOCKS = {"libelle": "Niveaux logistiques (%)", "ecran": "logistique", "suppression": False,
                    "champs": [champ("pct", "Niveau (%)", "nombre")]}


def _valeur(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _ligne(spec: dict, objet) -> dict:
    valeurs = {}
    for c in spec["champs"]:
        if c["type"] == "position":
            valeurs["position"] = {"lon": objet.lon, "lat": objet.lat}
        else:
            v = getattr(objet, c["cle"])
            valeurs[c["cle"]] = str(v) if c["cle"] == "credibilite_info" else _valeur(v)
    return {"id": objet.id, "titre": spec["titre"](objet), "valeurs": valeurs}


@router.get("/donnees")
def liste_ressources():
    ressources = {"unites": RESSOURCE_UNITES, "stocks": RESSOURCE_STOCKS, **RESSOURCES}
    return [{"cle": cle, "libelle": spec["libelle"], "ecran": spec["ecran"], "suppression": spec["suppression"], "champs": spec["champs"]}
            for cle, spec in ressources.items()]


@router.get("/donnees/{ressource}")
def lire_ressource(ressource: str, db: Session = Depends(get_db)):
    if ressource == "unites":
        out = []
        for u in db.query(models.Unit).order_by(models.Unit.nom_unite).all():
            pos = _derniere_position(db, u.id)
            out.append({"id": u.id, "titre": u.nom_unite, "valeurs": {
                "statut": u.statut, "communication": u.communication, "effectif": u.effectif,
                "position": {"lon": pos.lon if pos else None, "lat": pos.lat if pos else None}}})
        return out
    if ressource == "stocks":
        out = []
        for s in db.query(models.Stock).all():
            unite = db.get(models.Unit, s.unit_id)
            out.append({"id": s.id, "titre": f"{unite.nom_unite if unite else '—'} — {s.type_stock}", "valeurs": {"pct": _dernier_niveau(db, s.id)}})
        return sorted(out, key=lambda x: x["titre"])
    spec = RESSOURCES.get(ressource)
    if spec is None:
        raise HTTPException(status_code=404, detail="Catégorie inconnue")
    return [_ligne(spec, o) for o in db.query(spec["modele"]).order_by(spec["tri"]()).all()]


def _convertir(c: dict, v):
    """Contrôle et conversion d'une valeur saisie selon le type de champ."""
    if v in (None, "") and not c["obligatoire"]:
        return None
    if v in (None, ""):
        raise HTTPException(status_code=422, detail=f"Champ obligatoire : {c['libelle']}")
    if c["type"] == "nombre":
        try:
            n = float(v)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"Nombre attendu : {c['libelle']}")
        if n < 0:
            raise HTTPException(status_code=422, detail=f"Valeur négative refusée : {c['libelle']}")
        return n
    if c["type"] == "choix":
        valeurs = [o["valeur"] for o in c["options"]]
        if str(v) not in valeurs:
            raise HTTPException(status_code=422, detail=f"Valeur non autorisée pour {c['libelle']}")
        return int(v) if c["cle"] == "credibilite_info" else str(v)
    if c["type"] == "dateheure":
        try:
            return datetime.fromisoformat(str(v))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Date invalide : {c['libelle']}")
    return str(v).strip()


def _position(v) -> tuple[float | None, float | None]:
    if not isinstance(v, dict) or v.get("lon") in (None, "") or v.get("lat") in (None, ""):
        return None, None
    lon, lat = float(v["lon"]), float(v["lat"])
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise HTTPException(status_code=422, detail="Coordonnées hors limites")
    return lon, lat


def _element_calcule(db: Session, ressource: str, element_id: str) -> dict:
    """Élément d'une ressource calculée (unités, stocks) relu après modification, au format de la liste."""
    return next(x for x in lire_ressource(ressource, db) if x["id"] == element_id)


@router.patch("/donnees/{ressource}/{element_id}")
def modifier(ressource: str, element_id: str, valeurs: dict = Body(...), db: Session = Depends(get_db),
             user_id: str | None = Depends(get_acting_user_id)):
    if ressource == "unites":
        unite = db.get(models.Unit, element_id)
        if unite is None:
            raise HTTPException(status_code=404, detail="Unité introuvable")
        for c in RESSOURCE_UNITES["champs"]:
            if c["cle"] not in valeurs:
                continue
            if c["type"] == "position":
                lon, lat = _position(valeurs["position"])
                pos = _derniere_position(db, unite.id)
                # Les positions sont un historique : un déplacement ajoute une position, il ne réécrit pas l'ancienne.
                if lon is not None and (pos is None or (pos.lon, pos.lat) != (lon, lat)):
                    db.add(models.UnitPosition(unit_id=unite.id, lon=lon, lat=lat, source="manuel", saisi_par=user_id))
            else:
                v = _convertir(c, valeurs[c["cle"]])
                setattr(unite, c["cle"], int(v) if c["cle"] == "effectif" else v)
        db.commit()
        log_action(db, user_id=user_id, action="update", table_cible="units", enregistrement_id=unite.id)
        return _element_calcule(db, ressource, element_id)
    if ressource == "stocks":
        stock = db.get(models.Stock, element_id)
        if stock is None:
            raise HTTPException(status_code=404, detail="Stock introuvable")
        pct = _convertir(RESSOURCE_STOCKS["champs"][0], valeurs.get("pct"))
        # Historique également : un nouveau niveau relevé, plafonné à 100 %.
        db.add(models.StockLevel(stock_id=stock.id, pct=min(100, pct)))
        db.commit()
        log_action(db, user_id=user_id, action="update", table_cible="stock_levels", enregistrement_id=stock.id)
        return _element_calcule(db, ressource, element_id)
    spec = RESSOURCES.get(ressource)
    if spec is None:
        raise HTTPException(status_code=404, detail="Catégorie inconnue")
    objet = db.get(spec["modele"], element_id)
    if objet is None:
        raise HTTPException(status_code=404, detail="Élément introuvable")
    for c in spec["champs"]:
        if c["cle"] not in valeurs:
            continue
        if c["type"] == "position":
            objet.lon, objet.lat = _position(valeurs["position"])
            continue
        v = _convertir(c, valeurs[c["cle"]])
        colonne = spec["modele"].__table__.columns.get(c["cle"])
        if v is not None and colonne is not None and colonne.type.python_type is int:
            v = int(v)
        setattr(objet, c["cle"], v)
    db.commit()
    log_action(db, user_id=user_id, action="update", table_cible=spec["modele"].__tablename__, enregistrement_id=objet.id)
    return _ligne(spec, objet)


@router.delete("/donnees/{ressource}/{element_id}")
def supprimer(ressource: str, element_id: str, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    spec = RESSOURCES.get(ressource)
    if spec is None or not spec["suppression"]:
        raise HTTPException(status_code=403, detail="Suppression non autorisée pour cette catégorie")
    objet = db.get(spec["modele"], element_id)
    if objet is None:
        raise HTTPException(status_code=404, detail="Élément introuvable")
    db.delete(objet)
    db.commit()
    log_action(db, user_id=user_id, action="delete", table_cible=spec["modele"].__tablename__, enregistrement_id=element_id)
    return {"ok": True}
