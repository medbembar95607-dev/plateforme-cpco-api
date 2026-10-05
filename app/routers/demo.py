"""Écran de démonstration (2026-10-05) : saisie d'une note d'information, d'un message ou d'une
note de service, analyse par règles (mots-clés, lieux, unités) en impacts proposés, puis application
de ces impacts aux écrans concernés (incidents, alertes, renseignement, logistique).

Analyse déterministe, sans IA : elle repère des thèmes et des lieux connus. Elle sert à montrer la
chaîne « information entrante -> mise à jour de la situation », pas à remplacer l'analyste : chaque
impact est proposé, puis validé ou écarté avant application."""

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models
from ..audit import get_acting_user_id, log_action
from ..database import get_db
from .intelligence import _prochaine_reference

router = APIRouter(prefix="/demo", tags=["demo"])

# Lieux reconnus dans le texte (forme normalisée, sans accents) -> libellé et position.
LIEUX = {
    "bassikounou": ("Bassikounou", -5.92, 15.87),
    "fassala": ("Fassala", -5.52, 15.55),
    "mbera": ("Camp de Mbera", -5.75, 15.95),
    "nema": ("Néma", -7.26, 16.62),
    "adel bagrou": ("Adel Bagrou", -7.03, 15.55),
    "timbedra": ("Timbédra", -8.17, 16.24),
    "oualata": ("Oualata", -7.03, 17.30),
    "zone a3": ("Zone A3", -7.90, 15.35),
    "kiffa": ("Kiffa", -11.40, 16.62),
    "aioun": ("Aïoun el Atrous", -9.60, 16.66),
    "tidjikja": ("Tidjikja", -11.43, 18.56),
    "atar": ("Atar", -13.05, 20.52),
    "ouadane": ("Ouadâne", -11.62, 20.93),
    "zouerate": ("Zouérate", -12.48, 22.73),
    "chegga": ("Chegga", -5.78, 25.37),
    "nouadhibou": ("Nouadhibou", -17.03, 20.94),
    "nouakchott": ("Nouakchott", -15.98, 18.08),
    "rosso": ("Rosso", -15.81, 16.51),
}

# « armé » seul correspondrait aussi à « armée » : on ne retient que des formes sans ambiguïté.
MENACE = ["attaque", "hommes armes", "groupe arme", "individus armes", "elements armes", "hostile", "terroris", "jihad", "jnim", "aqmi", "embuscade", "tirs", "coups de feu", "ied",
          "engin explosif", "incursion", "enlevement", "enleve", "assaillant"]
GRAVE = ["attaque", "tirs", "coups de feu", "embuscade", "ied", "engin explosif", "explosion", "enlevement", "tue", "morts", "blesse"]
URGENCE = ["urgent", "immediat", "critique", "sans delai", "priorite absolue", "au plus vite"]
INCERTAIN = ["non confirme", "rumeur", "a verifier", "selon des habitants", "non verifie"]
CONFIRME = ["confirme", "constate", "observe par", "identifie"]
BESOIN = ["manque", "penurie", "besoin", "ravitaillement", "rupture", "sous seuil", "epuise", "a court", "reapprovisionnement"]
RESSOURCES = [
    (["carburant", "gasoil", "essence", "gazole"], "carburant", "Carburant"),
    (["munition"], "munitions", "Munitions"),
    (["vivres", "nourriture", "rations", "eau potable"], "vivres", "Vivres"),
    (["medicament", "sanitaire", "soins"], "sante", "Santé"),
    (["piece", "maintenance", "reparation"], "maintenance", "Maintenance"),
    (["vehicule", "camion", "pick-up", "blinde"], "vehicule", "Véhicules"),
]
COMMUNICATION = ["perte de liaison", "liaison radio", "liaison rompue", "radio", "perte de contact", "injoignable", "brouillage",
                 "communication degradee", "communications coupees"]
MEDICAL = ["blesse", "evacuation", "medevac", "malade"]
MIGRATION = ["pirogue", "migrant", "passeur", "clandestin"]
REFUGIES = ["refugie", "deplace", "mbera"]

# --- Écrans du chef (2026-10-05) : parapheur, suivi d'exécution, agenda, matériel, finances, RH ---
CONSIGNE = ["doivent", "devront", "doit ", "sont charges", "est charge", "rendre compte", "rendent compte", "a compter de",
            "il est ordonne", "il est demande", "veilleront", "renforcent", "executer", "mettre en place"]
REUNION = [("briefing", "briefing"), ("reunion", "reunion"), ("audience", "audience"), ("visite", "deplacement"),
           ("deplacement", "deplacement"), ("ceremonie", "ceremonie"), ("rendez-vous", "reunion"), ("point de situation", "briefing")]
DEGATS = ["detruit", "endommage", "hors service", "en panne", "panne", "immobilise", "perdu", "vole", "incendie"]
CATEGORIES_MATERIEL = [  # mots-clés, catégorie, libellé singulier, libellé pluriel
    (["vehicule", "camion", "pick-up", "blinde", "vab"], "vehicule", "véhicule", "véhicules"),
    (["fusil", "mitrailleuse", "famas", "armement"], "arme", "arme", "armes"),
    (["poste radio", "pr4g"], "communication", "poste radio", "postes radio"),
    (["drone", "helicoptere", "gazelle"], "aeronef", "aéronef", "aéronefs"),
    (["jumelles", "optique"], "optique", "optique", "optiques"),
]
LIGNES_BUDGET = [  # mot-clé du texte -> début du libellé de la ligne budgétaire
    (["carburant", "gasoil", "lubrifiant"], "Carburant"),
    (["vivres", "alimentation", "rations"], "Alimentation"),
    (["reparation", "remise en etat", "entretien", "pieces", "maintenance"], "Entretien"),
    (["formation", "stage", "instruction"], "Formation"),
    (["radio", "transmission", "communication"], "Modernisation systèmes de communication"),
    (["acquisition", "achat"], "Acquisition"),
    (["solde", "prime"], "Solde"),
]
PERTES = ["blesse", "tue", "morts", "decede", "disparu"]
RENFORT = ["renfort", "effectif insuffisant", "manque de personnel", "sous-effectif"]
FORMATION = ["formation", "stage", "recyclage", "entrainement", "cours de"]
NOMBRES = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
           "dix": 10, "douze": 12, "quinze": 15, "vingt": 20, "trente": 30}
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def _nombre_devant(texte: str, mots: list[str]) -> int | None:
    """Nombre (chiffres ou lettres) placé jusqu'à deux mots avant l'un des mots cherchés."""
    for mot in mots:
        m = re.search(r"(\d+|" + "|".join(NOMBRES) + r")\s+(?:\S+\s+){0,2}?" + re.escape(mot), texte)
        if m:
            brut = m.group(1)
            return int(brut) if brut.isdigit() else NOMBRES[brut]
    return None


def _phrases(texte: str) -> list[str]:
    return [ph for ph in re.split(r"[.;!?\n]", texte) if ph.strip()]


def _phrase_avec(texte: str, mots_a: list[str], mots_b: list[str]) -> str | None:
    """Première phrase contenant à la fois un mot de mots_a et un mot de mots_b (ex. matériel + avarie)."""
    return next((ph for ph in _phrases(texte) if _contient(ph, mots_a) and _contient(ph, mots_b)), None)


def _montant(texte: str) -> int | None:
    """« 4 millions MRU », « 2,5 millions d'ouguiyas », « 800 000 MRU » -> montant en MRU."""
    m = re.search(r"(\d+(?:[.,]\d+)?(?:\s\d{3})*)\s*(milliards?|millions?)?\s*(?:d'|de\s+)?(mru|ouguiyas?|um)\b", texte)
    if not m:
        return None
    valeur = float(m.group(1).replace(" ", "").replace(",", "."))
    facteur = {"milliard": 1e9, "milliards": 1e9, "million": 1e6, "millions": 1e6}.get(m.group(2) or "", 1)
    return int(valeur * facteur)


def _date_rendez_vous(texte: str) -> datetime:
    """« demain à 10 h », « jeudi à 8h30 », « aujourd'hui à 16 h » ; à défaut, demain 9 h."""
    maintenant = datetime.now()
    jour = maintenant + timedelta(days=1)
    if "apres-demain" in texte or "apres demain" in texte:
        jour = maintenant + timedelta(days=2)
    elif "aujourd'hui" in texte or "ce soir" in texte:
        jour = maintenant
    else:
        for i, nom in enumerate(JOURS):
            if nom in texte:
                ecart = (i - maintenant.weekday()) % 7 or 7
                jour = maintenant + timedelta(days=ecart)
                break
    # Heure introduite par « à » en priorité (« jeudi à 10 h »), pour ne pas lire un délai (« sous 48 h »).
    heure = re.search(r"\ba\s*(\d{1,2})\s*h\s*(\d{2})?", texte)
    if heure is None:
        heure = next((m for m in re.finditer(r"\b(\d{1,2})\s*h\s*(\d{2})?", texte) if int(m.group(1)) < 24), None)
    h, mn = (int(heure.group(1)), int(heure.group(2) or 0)) if heure and int(heure.group(1)) < 24 else (9, 0)
    debut = jour.replace(hour=h, minute=mn, second=0, microsecond=0)
    return debut if debut > maintenant else maintenant + timedelta(hours=1)


def _delai(texte: str, urgent: bool) -> timedelta:
    """Délai d'exécution d'une consigne : « sous 48 h », « dans les 3 jours » ; à défaut 72 h (24 h si urgent)."""
    heures = re.search(r"(\d+)\s*(?:h|heures)\b", texte)
    jours = re.search(r"(\d+)\s*jours?", texte)
    if heures:
        return timedelta(hours=int(heures.group(1)))
    if jours:
        return timedelta(days=int(jours.group(1)))
    return timedelta(hours=24 if urgent else 72)


TYPES_DOCUMENT = {"note_information": "Note d'information", "message": "Message", "note_service": "Note de service"}
SOURCE_RENS = {"note_information": "HUMINT", "message": "SIGINT", "note_service": "OSINT"}


def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in sans_accents if unicodedata.category(c) != "Mn")


def _contient(texte: str, mots: list[str]) -> bool:
    return any(m in texte for m in mots)


class DocumentDemo(BaseModel):
    type_document: str
    emetteur: str = Field(min_length=1, max_length=150)
    classification: str = "confidentiel"
    objet: str = Field(min_length=1, max_length=200)
    texte: str = Field(min_length=1, max_length=4000)


def _unites_citees(db: Session, texte: str) -> list[tuple[models.Unit, models.UnitPosition | None]]:
    out = []
    for unite in db.query(models.Unit).all():
        if _normaliser(unite.nom_unite) in texte or _normaliser(unite.code_unite) in texte:
            pos = (
                db.query(models.UnitPosition)
                .filter(models.UnitPosition.unit_id == unite.id)
                .order_by(models.UnitPosition.position_time.desc())
                .first()
            )
            out.append((unite, pos))
    return out


def analyser_document(db: Session, doc: DocumentDemo) -> dict:
    texte = _normaliser(f"{doc.objet} {doc.texte}")
    unites = _unites_citees(db, texte)
    lieu = next((LIEUX[cle] for cle in LIEUX if cle in texte), None)
    # Localisation : lieu cité en priorité, sinon position de la première unité citée.
    if lieu is not None:
        localite, lon, lat = lieu
    elif unites and unites[0][1] is not None:
        localite, lon, lat = f"Secteur {unites[0][0].nom_unite}", unites[0][1].lon, unites[0][1].lat
    else:
        localite, lon, lat = "Non localisé", None, None

    urgent = _contient(texte, URGENCE)
    fiabilite = "B" if unites or doc.type_document == "message" else "C"
    credibilite = 4 if _contient(texte, INCERTAIN) else 2 if _contient(texte, CONFIRME) else 3
    origine = f"{TYPES_DOCUMENT.get(doc.type_document, 'Document')} de {doc.emetteur}"
    impacts: list[dict] = []

    def ajouter(type_impact: str, ecran: str, titre: str, resume: str, payload: dict, en_tete: bool = False) -> None:
        impact = {"cle": f"{type_impact}-{len(impacts)}", "type": type_impact, "ecran": ecran, "titre": titre, "resume": resume,
                  "localite": localite if payload.get("lon") is not None or type_impact == "incident" else None, "payload": payload}
        if en_tete:
            impacts.insert(0, impact)
        else:
            impacts.append(impact)

    if _contient(texte, MENACE):
        critique = _contient(texte, GRAVE) or urgent
        gravite = "critique" if critique else "elevee"
        ajouter("incident", "incidents", f"Incident sécurité ({'critique' if critique else 'élevé'}) : {localite}",
                f"Incident de sécurité créé à partir de : {doc.objet}.",
                {"type_incident": "securite", "niveau_gravite": gravite, "localite": localite,
                 "description": f"{doc.objet}. {doc.texte}", "declarant": doc.emetteur, "lon": lon, "lat": lat})
        ajouter("alerte", "alertes", f"Alerte menace ({'critique' if critique else 'attention'})",
                "Alerte active à acquitter par le PC.",
                {"type_alerte": "menace", "niveau": "critique" if critique else "attention",
                 "message": f"{doc.objet} ({localite}).", "lon": lon, "lat": lat})
        ajouter("rapport_rens", "renseignement", f"Rapport de renseignement coté {fiabilite}{credibilite}",
                f"Rapport {SOURCE_RENS.get(doc.type_document, 'HUMINT')} évalué « {'menace' if critique else 'observation'} ».",
                {"type_renseignement": SOURCE_RENS.get(doc.type_document, "HUMINT"), "classification": doc.classification,
                 "titre": doc.objet[:200], "resume": f"{doc.texte} (Source : {origine}.)",
                 "fiabilite_source": fiabilite, "credibilite_info": credibilite,
                 "statut": "menace" if critique else "observation", "lon": lon, "lat": lat})

    ressources_citees = [(cle, label) for mots, cle, label in RESSOURCES if _contient(texte, mots)]
    if ressources_citees and _contient(texte, BESOIN):
        if unites:
            unite = unites[0][0]
            for cle, label in ressources_citees:
                ajouter("demande_ravitaillement", "logistique", f"Demande de ravitaillement {label.lower()} : {unite.nom_unite}",
                        f"Demande {'urgente' if urgent else 'routine'} de +{50 if urgent else 30} points, à traiter par la logistique.",
                        {"unit_id": unite.id, "unite_nom": unite.nom_unite, "type_stock": cle, "points_pct": 50 if urgent else 30,
                         "priorite": "urgent" if urgent else "routine", "commentaire": f"Suite à : {doc.objet} ({origine})."})
        ajouter("alerte", "alertes", "Alerte logistique (attention)", "Besoin logistique signalé.",
                {"type_alerte": "logistique", "niveau": "attention",
                 "message": f"{doc.objet}" + (f" — {unites[0][0].nom_unite}." if unites else "."), "lon": lon, "lat": lat})

    if _contient(texte, COMMUNICATION):
        ajouter("incident", "incidents", f"Incident communication : {localite}", "Perte ou dégradation de liaison signalée.",
                {"type_incident": "communication", "niveau_gravite": "elevee" if urgent else "moyenne", "localite": localite,
                 "description": f"{doc.objet}. {doc.texte}", "declarant": doc.emetteur, "lon": lon, "lat": lat})
        ajouter("alerte", "alertes", "Alerte communication (attention)", "Liaison à rétablir.",
                {"type_alerte": "communication", "niveau": "attention", "message": f"{doc.objet}.", "lon": lon, "lat": lat})

    if _contient(texte, MEDICAL):
        ajouter("incident", "incidents", f"Incident médical : {localite}", "Prise en charge sanitaire à organiser.",
                {"type_incident": "medical", "niveau_gravite": "critique" if urgent else "elevee", "localite": localite,
                 "description": f"{doc.objet}. {doc.texte}", "declarant": doc.emetteur, "lon": lon, "lat": lat})

    if _contient(texte, MIGRATION):
        ajouter("rapport_rens", "renseignement", "Rapport de renseignement : migration irrégulière",
                "Observation à corréler avec les services compétents.",
                {"type_renseignement": "OSINT" if doc.type_document == "note_service" else "HUMINT", "classification": doc.classification,
                 "titre": doc.objet[:200], "resume": f"{doc.texte} (Source : {origine}.)", "fiabilite_source": fiabilite,
                 "credibilite_info": credibilite, "statut": "observation", "lon": lon, "lat": lat})

    if _contient(texte, REFUGIES) and not _contient(texte, MENACE):
        ajouter("rapport_rens", "renseignement", "Rapport de renseignement : déplacés et réfugiés",
                "Suivi de la situation humanitaire et des tensions éventuelles.",
                {"type_renseignement": SOURCE_RENS.get(doc.type_document, "HUMINT"), "classification": doc.classification,
                 "titre": doc.objet[:200], "resume": f"{doc.texte} (Source : {origine}.)", "fiabilite_source": fiabilite,
                 "credibilite_info": credibilite, "statut": "observation", "lon": lon, "lat": lat})

    impacts_chef(db, doc, texte, unites, localite, urgent, origine, ajouter)

    # Une note de service est toujours diffusée comme alerte d'information ; un document dont seul
    # l'enregistrement au parapheur a été retenu l'est aussi, pour rester visible du dispositif.
    if doc.type_document == "note_service" or all(i["type"] == "courrier" for i in impacts):
        ajouter("alerte", "alertes", "Alerte d'information (diffusion)", "Information diffusée à l'ensemble du dispositif.",
                {"type_alerte": "operationnelle", "niveau": "info",
                 "message": f"{TYPES_DOCUMENT.get(doc.type_document, 'Document')} : {doc.objet}.", "lon": lon, "lat": lat})

    return {
        "localite": localite,
        "unitesCitees": [u.nom_unite for u, _ in unites],
        "urgent": urgent,
        "impacts": impacts,
    }


def impacts_chef(db: Session, doc: DocumentDemo, texte: str, unites: list, localite: str, urgent: bool, origine: str, ajouter) -> None:
    """Impacts sur les écrans du chef : suivi d'exécution, agenda, matériel, finances, RH, parapheur."""
    maintenant = datetime.now()

    # Suivi d'exécution : une consigne adressée à des unités devient une instruction à suivre.
    if _contient(texte, CONSIGNE):
        cibles = db.query(models.Unit).all() if "toutes les unites" in texte else [u for u, _ in unites]
        if cibles:
            limite = maintenant + _delai(texte, urgent)
            ajouter("suivi_execution", "suivi_execution", f"Instruction à suivre pour {len(cibles)} unité(s)",
                    f"Échéance le {limite.strftime('%d/%m à %H:%M')} : {', '.join(u.nom_unite for u in cibles[:4])}{'…' if len(cibles) > 4 else ''}.",
                    {"unites": [{"id": u.id, "nom": u.nom_unite} for u in cibles], "type_ordre": "INSTRUCTION",
                     "objet": doc.objet[:250], "instruction": doc.texte, "emetteur": doc.emetteur, "date_limite": limite.isoformat()})

    # Agenda : réunion annoncée, ou briefing de crise proposé pour une menace critique.
    type_rdv = next((t for mot, t in REUNION if mot in texte), None)
    if type_rdv:
        debut = _date_rendez_vous(texte)
        ajouter("rendez_vous", "calendrier", f"Rendez-vous : {doc.objet[:80]}", f"Le {debut.strftime('%d/%m à %H:%M')}, à confirmer.",
                {"titre": doc.objet[:200], "type_rdv": type_rdv, "date_debut": debut.isoformat(),
                 "date_fin": (debut + timedelta(hours=1)).isoformat(), "lieu": localite if localite != "Non localisé" else "PC COP",
                 "participants": doc.emetteur, "notes": f"Créé à partir de : {origine}."})
    elif _contient(texte, MENACE) and (_contient(texte, GRAVE) or urgent):
        debut = (maintenant + timedelta(hours=1)).replace(second=0, microsecond=0)
        ajouter("rendez_vous", "calendrier", "Briefing de crise dans l'heure", f"Le {debut.strftime('%d/%m à %H:%M')}, au PC COP.",
                {"titre": f"Briefing de crise : {doc.objet[:150]}", "type_rdv": "briefing", "date_debut": debut.isoformat(),
                 "date_fin": (debut + timedelta(minutes=45)).isoformat(), "lieu": "PC COP",
                 "participants": "CEMGA, Cdt Sy, Cne Diop, Lt Kane", "notes": f"Proposé automatiquement suite à : {origine}."})

    # Matériel : perte ou indisponibilité signalée, l'avarie devant être citée dans la même phrase que
    # le matériel (« perte de liaison radio » ne met pas un poste radio en panne).
    if _contient(texte, DEGATS):
        unite = unites[0][0] if unites else None
        for mots, categorie, singulier, pluriel in CATEGORIES_MATERIEL:
            phrase = _phrase_avec(texte, mots, DEGATS)
            if phrase is None:
                continue
            nombre = _nombre_devant(phrase, mots) or 1
            label = singulier if nombre == 1 else pluriel
            existant = (
                db.query(models.Materiel)
                .filter(models.Materiel.categorie == categorie, models.Materiel.formation_affectation == unite.nom_unite)
                .first()
                if unite else None
            )
            etat = "hors_service" if _contient(phrase, ["detruit", "perdu", "vole", "incendie", "hors service"]) else "maintenance"
            if existant:
                ajouter("materiel", "materiel", f"Matériel : {existant.nom} −{nombre} ({unite.nom_unite})",
                        f"Quantité disponible ramenée de {existant.quantite} à {max(0, existant.quantite - nombre)}.",
                        {"mode": "decompte", "materiel_id": existant.id, "nombre": nombre})
            else:
                affectation = unite.nom_unite if unite else doc.emetteur
                ajouter("materiel", "materiel", f"Matériel : {nombre} {label} {'hors service' if etat == 'hors_service' else 'en maintenance'} ({affectation})",
                        "Ligne ajoutée à la situation matériel de l'unité.",
                        {"mode": "creation", "nom": f"{pluriel.capitalize()} — {affectation}", "categorie": categorie, "nombre": nombre,
                         "etat": etat, "formation_affectation": affectation, "fonction": f"Signalé par : {origine}"})

    # Finances : un montant cité s'impute sur la ligne budgétaire correspondante.
    montant = _montant(texte)
    if montant:
        # Ligne choisie d'après la phrase qui cite le montant (« coût de la remise en état : 4 millions MRU »).
        phrase = next((ph for ph in _phrases(texte) if _montant(ph)), texte)
        prefixe = next((libelle for mots, libelle in LIGNES_BUDGET if _contient(phrase, mots)), None) or next(
            (libelle for mots, libelle in LIGNES_BUDGET if _contient(texte, mots)), None)
        ligne = db.query(models.LigneBudgetaire).filter(models.LigneBudgetaire.libelle.like(f"{prefixe}%")).first() if prefixe else None
        if ligne:
            ajouter("budget", "budget", f"Dépense de {montant:,} MRU : {ligne.libelle}".replace(",", " "),
                    f"Consommé porté de {int(ligne.montant_consomme):,} à {int(ligne.montant_consomme + montant):,} MRU sur {int(ligne.montant_alloue):,}.".replace(",", " "),
                    {"ligne_id": ligne.id, "montant": montant})

    # RH : pertes ou besoin de renfort -> besoin en recrutement ; formation demandée -> besoin en formation.
    affectation = "Toutes unités" if "toutes les unites" in texte else unites[0][0].nom_unite if unites else doc.emetteur
    categorie = "officier" if "officier" in texte and "sous-officier" not in texte else "sous_officier" if "sous-officier" in texte else "homme_du_rang"
    pertes = _contient(texte, PERTES)
    if pertes or _contient(texte, RENFORT):
        nombre = _nombre_devant(texte, PERTES + ["hommes", "militaires", "personnels", "soldats"]) or 1
        ajouter("recrutement", "rh", f"Besoin en recrutement : {nombre} poste(s), {affectation}",
                "Remplacement des personnels indisponibles." if pertes else "Renfort demandé.",
                {"poste": f"{'Remplacement' if pertes else 'Renfort'} — {affectation}", "categorie": categorie, "nombre_postes": nombre,
                 "priorite": "critique" if _contient(texte, ["tue", "morts", "decede"]) or urgent else "elevee",
                 "formation_affectation": affectation})
    if _contient(texte, FORMATION):
        places = _nombre_devant(texte, ["places", "stagiaires", "personnels", "militaires", "hommes"]) or 10
        ajouter("formation", "rh", f"Besoin en formation : {doc.objet[:70]}", f"{places} place(s) pour {affectation}.",
                {"intitule": doc.objet[:150], "categorie": categorie, "nombre_places": places,
                 "priorite": "elevee" if urgent else "normale", "formation_affectation": affectation})

    # Parapheur : tout document reçu est enregistré au courrier arrivé du chef, en tête de liste.
    origine_courrier = ("ministere_defense" if "ministere" in _normaliser(doc.emetteur)
                        else "subordonne" if unites or doc.emetteur in ("CEMGA", "PC COP") else "institution_externe")
    ajouter("courrier", "courrier", f"Courrier arrivé : {doc.objet[:80]}",
            f"Enregistré au parapheur, priorité {'très urgent' if urgent else 'normale'}.",
            {"type_document": {"note_information": "note", "message": "message", "note_service": "note"}.get(doc.type_document, "note"),
             "origine": origine_courrier, "expediteur": doc.emetteur, "objet": doc.objet[:250], "resume": doc.texte[:300],
             "contenu": doc.texte, "priorite": "tres_urgent" if urgent else "normal"}, en_tete=True)


@router.post("/analyser")
def analyser(doc: DocumentDemo, db: Session = Depends(get_db)):
    if doc.type_document not in TYPES_DOCUMENT:
        raise HTTPException(status_code=422, detail="Type de document inconnu")
    return analyser_document(db, doc)


class ApplicationDemo(BaseModel):
    document: DocumentDemo
    impacts: list[dict]


def _dernier_numero(references: list[str], prefixe: str) -> int:
    """Plus grand numéro existant pour un préfixe (« COUR-2026-0043 » -> 43), pour continuer la série."""
    numeros = [int(r[len(prefixe):]) for r in references if r.startswith(prefixe) and r[len(prefixe):].isdigit()]
    return max(numeros, default=0)


def _creer(db: Session, impact: dict, document: DocumentDemo, user_id: str | None) -> dict:
    p = impact["payload"]
    if impact["type"] == "incident":
        objet = models.Incident(type_incident=p["type_incident"], niveau_gravite=p["niveau_gravite"], localite=p["localite"],
                                description=p["description"], declarant=p["declarant"], lon=p.get("lon"), lat=p.get("lat"),
                                classification=document.classification)
        table = "incidents"
    elif impact["type"] == "alerte":
        objet = models.Alert(type_alerte=p["type_alerte"], niveau=p["niveau"], message=p["message"], statut="active",
                             classification=document.classification, lon=p.get("lon"), lat=p.get("lat"))
        table = "alerts"
    elif impact["type"] == "rapport_rens":
        objet = models.IntelligenceReport(reference=_prochaine_reference(db, p["type_renseignement"]),
                                          type_renseignement=p["type_renseignement"], classification=p["classification"],
                                          titre=p["titre"], resume=p["resume"], fiabilite_source=p["fiabilite_source"],
                                          credibilite_info=p["credibilite_info"], statut=p["statut"],
                                          lon=p.get("lon"), lat=p.get("lat"), redige_par=user_id)
        table = "intelligence_reports"
    elif impact["type"] == "demande_ravitaillement":
        objet = models.DemandeRavitaillement(unit_id=p["unit_id"], type_stock=p["type_stock"], points_pct=p["points_pct"],
                                             priorite=p["priorite"], commentaire=p["commentaire"], demandeur_id=user_id)
        table = "demandes_ravitaillement"
    elif impact["type"] == "courrier":
        prefixe = f"COUR-{datetime.now().year}-"
        numero = _dernier_numero([n for (n,) in db.query(models.Courrier.numero_enregistrement).all()], prefixe) + 1
        objet = models.Courrier(numero_enregistrement=f"{prefixe}{numero:04d}", type_document=p["type_document"], origine=p["origine"],
                                expediteur=p["expediteur"], objet=p["objet"], resume=p["resume"], contenu=p["contenu"],
                                classification=document.classification, priorite=p["priorite"], statut="nouveau",
                                date_reception=datetime.now(),
                                date_limite_reponse=datetime.now() + timedelta(hours=48) if p["priorite"] != "normal" else None)
        table = "courriers"
    elif impact["type"] == "suivi_execution":
        prefixe = f"INSTRUCTION-{datetime.now().year}-"
        base = _dernier_numero([r for (r,) in db.query(models.SuiviExecution.reference).all()], prefixe)
        crees = []
        for i, u in enumerate(p["unites"]):
            ligne = models.SuiviExecution(reference=f"{prefixe}{base + i + 1:03d}", type_ordre=p["type_ordre"], objet=p["objet"],
                                          instruction=p["instruction"], emetteur=p["emetteur"], unite_id=u["id"],
                                          date_emission=datetime.now(), date_limite=datetime.fromisoformat(p["date_limite"]),
                                          statut="en_attente", classification=document.classification)
            db.add(ligne)
            db.flush()
            crees.append(ligne)
        objet = crees[0]
        table = "suivi_execution"
    elif impact["type"] == "rendez_vous":
        objet = models.RendezVous(titre=p["titre"], type_rdv=p["type_rdv"], date_debut=datetime.fromisoformat(p["date_debut"]),
                                  date_fin=datetime.fromisoformat(p["date_fin"]), lieu=p["lieu"], participants=p["participants"],
                                  statut="a_confirmer", classification=document.classification, notes=p["notes"])
        table = "rendez_vous"
    elif impact["type"] == "materiel":
        if p["mode"] == "decompte":
            objet = db.get(models.Materiel, p["materiel_id"])
            if objet is None:
                raise HTTPException(status_code=404, detail="Matériel introuvable")
            objet.quantite = max(0, objet.quantite - p["nombre"])
        else:
            objet = models.Materiel(nom=p["nom"], categorie=p["categorie"], type_materiel="Signalement opérationnel", armee="terre",
                                    formation_affectation=p["formation_affectation"], fonction=p["fonction"], statut_dotation="en_dotation",
                                    etat=p["etat"], quantite=p["nombre"], seuil_alerte=0, dotation_ted=p["nombre"],
                                    classification=document.classification)
        table = "materiels"
    elif impact["type"] == "budget":
        objet = db.get(models.LigneBudgetaire, p["ligne_id"])
        if objet is None:
            raise HTTPException(status_code=404, detail="Ligne budgétaire introuvable")
        objet.montant_consomme += p["montant"]
        table = "lignes_budgetaires"
    elif impact["type"] == "recrutement":
        objet = models.BesoinRecrutement(poste=p["poste"], categorie=p["categorie"], armee="terre", formation_affectation=p["formation_affectation"],
                                         nombre_postes=p["nombre_postes"], priorite=p["priorite"], statut="ouvert",
                                         classification=document.classification)
        table = "besoins_recrutement"
    elif impact["type"] == "formation":
        objet = models.BesoinFormation(intitule=p["intitule"], categorie=p["categorie"], armee="terre", formation_affectation=p["formation_affectation"],
                                       nombre_places=p["nombre_places"], priorite=p["priorite"], statut="a_planifier",
                                       classification=document.classification)
        table = "besoins_formation"
    else:
        raise HTTPException(status_code=422, detail=f"Type d'impact inconnu : {impact['type']}")
    db.add(objet)
    db.flush()
    log_action(db, user_id=user_id, action="create", table_cible=table, enregistrement_id=objet.id)
    # Pour la logistique, l'écran sélectionne l'unité concernée sur sa carte.
    focus = p["unit_id"] if impact["type"] == "demande_ravitaillement" else objet.id
    return {"cle": impact["cle"], "type": impact["type"], "ecran": impact["ecran"], "titre": impact["titre"], "id": objet.id, "focusId": focus}


@router.post("/appliquer")
def appliquer(demande: ApplicationDemo, db: Session = Depends(get_db), user_id: str | None = Depends(get_acting_user_id)):
    if not demande.impacts:
        raise HTTPException(status_code=422, detail="Aucun impact sélectionné")
    resultats = [_creer(db, impact, demande.document, user_id) for impact in demande.impacts]
    note = models.NoteDemo(
        type_document=demande.document.type_document, emetteur=demande.document.emetteur,
        classification=demande.document.classification, objet=demande.document.objet, texte=demande.document.texte,
        impacts_json=json.dumps(resultats, ensure_ascii=False), saisi_par=user_id, date_saisie=datetime.now(timezone.utc),
    )
    db.add(note)
    db.commit()
    return {"resultats": resultats, "noteId": note.id}


@router.get("/historique")
def historique(db: Session = Depends(get_db)):
    notes = db.query(models.NoteDemo).order_by(models.NoteDemo.date_saisie.desc()).limit(20).all()
    return [
        {
            "id": n.id,
            "typeDocument": n.type_document,
            "emetteur": n.emetteur,
            "objet": n.objet,
            "dateSaisie": n.date_saisie.isoformat(),
            "impacts": json.loads(n.impacts_json),
        }
        for n in notes
    ]
