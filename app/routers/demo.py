"""Écran de démonstration (2026-10-05) : saisie d'une note d'information, d'un message ou d'une
note de service, analyse par règles (mots-clés, lieux, unités) en impacts proposés, puis application
de ces impacts aux écrans concernés (incidents, alertes, renseignement, logistique).

Analyse déterministe, sans IA : elle repère des thèmes et des lieux connus. Elle sert à montrer la
chaîne « information entrante -> mise à jour de la situation », pas à remplacer l'analyste : chaque
impact est proposé, puis validé ou écarté avant application."""

import json
import unicodedata
from datetime import datetime, timezone

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
MENACE = ["attaque", "hommes armes", "groupe arme", "individus armes", "elements armes", "hostile", "terroris", "jihad", "jnim", "aqmi", "embuscade", "tirs", "tir ", "ied",
          "engin explosif", "incursion", "enlevement", "enleve", "assaillant"]
GRAVE = ["attaque", "tirs", "embuscade", "ied", "engin explosif", "explosion", "enlevement", "tue", "morts", "blesse"]
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

    def ajouter(type_impact: str, ecran: str, titre: str, resume: str, payload: dict) -> None:
        impacts.append({"cle": f"{type_impact}-{len(impacts)}", "type": type_impact, "ecran": ecran, "titre": titre,
                        "resume": resume, "localite": localite if payload.get("lon") is not None or type_impact == "incident" else None,
                        "payload": payload})

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

    # Une note de service est toujours diffusée comme alerte d'information ; un document sans thème
    # reconnu l'est aussi, pour qu'aucune saisie ne reste sans trace.
    if doc.type_document == "note_service" or not impacts:
        ajouter("alerte", "alertes", "Alerte d'information (diffusion)", "Information diffusée à l'ensemble du dispositif.",
                {"type_alerte": "operationnelle", "niveau": "info",
                 "message": f"{TYPES_DOCUMENT.get(doc.type_document, 'Document')} : {doc.objet}.", "lon": lon, "lat": lat})

    return {
        "localite": localite,
        "unitesCitees": [u.nom_unite for u, _ in unites],
        "urgent": urgent,
        "impacts": impacts,
    }


@router.post("/analyser")
def analyser(doc: DocumentDemo, db: Session = Depends(get_db)):
    if doc.type_document not in TYPES_DOCUMENT:
        raise HTTPException(status_code=422, detail="Type de document inconnu")
    return analyser_document(db, doc)


class ApplicationDemo(BaseModel):
    document: DocumentDemo
    impacts: list[dict]


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
