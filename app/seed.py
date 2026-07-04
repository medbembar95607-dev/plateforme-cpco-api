"""Peuple la base de dev avec les mêmes données que src/data/mockData.ts du frontend
(livrables/plateforme-cpco-app/), pour que le passage du mock au vrai backend soit invisible
à l'écran. Idempotent : ne fait rien si des unités existent déjà."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from . import models
from .database import Base, SessionLocal, engine


def seed(db: Session) -> None:
    if db.query(models.Unit).count() > 0:
        return

    pc = models.Unit(code_unite="PC-CPCO", nom_unite="PC CPCO", type_unite="pc", echelon="groupement", effectif=25, commandant="Col. Ba", statut="disponible", communication="stable")
    u1 = models.Unit(code_unite="BAT-1", nom_unite="Bataillon 1", type_unite="infanterie", echelon="bataillon", effectif=520, statut="en_mission", communication="stable")
    u2 = models.Unit(code_unite="CIE-ALPHA", nom_unite="Compagnie Alpha", type_unite="infanterie", echelon="compagnie", effectif=140, statut="en_progression", communication="stable")
    u3 = models.Unit(code_unite="PA-NORD", nom_unite="Poste Avancé Nord", type_unite="pc", echelon="section", effectif=48, statut="disponible", communication="stable")
    u4 = models.Unit(code_unite="CONVOI-LIMA", nom_unite="Convoi Lima", type_unite="logistique", echelon="section", effectif=36, statut="communication_degradee", communication="degradee")
    u5 = models.Unit(code_unite="POSTE-LOG-NORD", nom_unite="Poste logistique Nord", type_unite="logistique", echelon="section", effectif=20, statut="disponible", communication="stable")
    db.add_all([pc, u1, u2, u3, u4, u5])
    db.flush()

    # Positions réparties sur le territoire mauritanien (+ Léré au Mali pour la menace),
    # sur demande de Bardas le 2026-07-03 — coordonnées approximatives des localités citées.
    positions = [
        (u1, -7.25, 16.62, "12:33"),    # Bataillon 1 -> Néma
        (u2, -7.42, 15.68, "12:24"),    # Compagnie Alpha -> Fassala
        (u3, -11.60, 20.93, "12:08"),   # Poste Avancé Nord -> Ouadâne
        (u4, -5.93, 15.43, "11:51"),    # Convoi Lima -> Bassiknou
        (u5, -13.05, 20.52, "11:58"),   # Poste logistique Nord -> Atar
        (pc, -15.99, 18.18, "12:00"),   # PC CPCO -> inchangé (secteur Nouakchott)
    ]
    for unit, lon, lat, _heure in positions:
        db.add(models.UnitPosition(unit_id=unit.id, lon=lon, lat=lat, source="manuel"))

    db.add(models.Threat(
        nom="Groupe hostile détecté", type_menace="groupe_hostile", niveau_menace="critique",
        statut="confirmee", classification="confidentiel", lon=-7.289557424909501, lat=15.186463905597305,  # Nara (Mali)
    ))

    db.add(models.Checkpoint(
        nom="Checkpoint Bravo", ordre_passage=1, statut="prevu",
        dernier_rapport="RAS", lon=-6.15, lat=15.32,  # Adel Bagrou
    ))

    db.add(models.OperationalArea(
        nom="Zone menace A3", type_zone="zone_menace", niveau_risque=4, classification="confidentiel",
        # Nara (Mali) — agrandie pour rester visible à l'échelle nationale
        geom_json=json.dumps([[-7.433, 15.017], [-7.133, 15.017], [-7.133, 15.317], [-7.433, 15.317], [-7.433, 15.017]]),
    ))
    db.add(models.OperationalArea(
        nom="Zone OPS Sable", type_zone="zone_ops", niveau_risque=2, classification="confidentiel",
        # Kaédi (Mauritanie) — agrandie pour rester visible à l'échelle nationale
        geom_json=json.dumps([[-13.65, 16.0], [-13.35, 16.0], [-13.35, 16.3], [-13.65, 16.3], [-13.65, 16.0]]),
    ))
    db.add(models.ProgressAxis(nom="Axe de progression", geom_json=json.dumps([[-16.03, 18.14], [-15.90, 18.24]])))

    db.add_all([
        models.IntelligenceReport(
            reference="HUMINT-2026-0045", type_renseignement="HUMINT", classification="secret",
            titre="Mouvement suspect A3", resume="Observation consolidée par patrouille et source OSINT. Risque élevé sur l'axe nord.",
            fiabilite_source="A", statut="menace",
        ),
        models.IntelligenceReport(
            reference="SIGINT-2026-0112", type_renseignement="SIGINT", classification="confidentiel",
            titre="Activité radio irrégulière", resume="Signalement SIGINT à corréler avec les derniers mouvements terrain.",
            fiabilite_source="B", statut="observation",
        ),
        models.IntelligenceReport(
            reference="OSINT-2026-0033", type_renseignement="OSINT", classification="diffusion_libre",
            titre="Zone logistique N2", resume="Pas d'indice hostile récent autour du poste logistique principal.",
            fiabilite_source="C", statut="stabilise",
        ),
    ])

    db.add(models.AlertThreshold(type_stock="carburant", seuil_pct=40))
    db.add(models.AlertThreshold(type_stock="munitions", seuil_pct=50))
    db.add(models.AlertThreshold(type_stock="vivres", seuil_pct=30))

    logistique = {
        u1: {"carburant": 80, "munitions": 65, "vivres": 78, "maintenance": 71},
        u2: {"carburant": 45, "munitions": 90, "vivres": 54, "maintenance": 68},
        u4: {"carburant": 28, "munitions": 38, "vivres": 62, "maintenance": 41},
    }
    for unit, valeurs in logistique.items():
        for type_stock, pct in valeurs.items():
            stock = models.Stock(unit_id=unit.id, type_stock=type_stock)
            db.add(stock)
            db.flush()
            db.add(models.StockLevel(stock_id=stock.id, pct=pct))

    op1 = models.Operation(code_operation="OPS-2026-014", nom_operation="Opération Sable Nord", objectif="Sécurisation de l'axe nord et maintien des checkpoints prioritaires.", commandant_operation="Col. Ba", statut="en_cours", priorite="elevee", progression=64, classification="secret")
    op2 = models.Operation(code_operation="OPS-2026-015", nom_operation="Mission Ravitaillement N2", objectif="Ravitaillement carburant et pièces critiques pour les unités avancées.", statut="planifiee", priorite="moyenne", progression=22, classification="confidentiel")
    op3 = models.Operation(code_operation="OPS-2026-016", nom_operation="Surveillance Zone A3", objectif="Renforcement renseignement et suivi des mouvements suspects confirmés.", statut="sous_tension", priorite="elevee", progression=48, classification="secret")
    db.add_all([op1, op2, op3])
    db.flush()

    o1 = models.Order(numero_ordre="OPORD-2026-014", type_ordre="OPORD", classification="secret", objet="Sécurisation de l'axe nord", contenu="Sécuriser l'axe de progression nord et maintenir les checkpoints Bravo et Charlie sous contrôle jusqu'à nouvel ordre.", statut="diffuse", emetteur="Col. Ba, Commandement CPCO", operation_id=op1.id, date_emission=datetime(2026, 7, 1, 8, 0))
    o2 = models.Order(numero_ordre="FRAGO-2026-031", type_ordre="FRAGO", classification="confidentiel", objet="Ravitaillement prioritaire Convoi Lima", contenu="Organiser un ravitaillement en carburant et munitions pour le Convoi Lima dès rétablissement de la liaison.", statut="signe", emetteur="Cdt Sy, Officier opérations", operation_id=op2.id, date_emission=datetime(2026, 7, 3, 9, 15))
    o3 = models.Order(numero_ordre="WARNO-2026-009", type_ordre="WARNO", classification="secret", objet="Renforcement surveillance Zone A3", contenu="Préparer un renforcement du dispositif de surveillance sur la Zone A3 suite à confirmation de menace.", statut="brouillon", emetteur="Cne Diop, Officier renseignement", operation_id=op3.id, date_emission=None)
    db.add_all([o1, o2, o3])
    db.flush()

    db.add_all([
        models.OrderRecipient(order_id=o1.id, unit_id=u1.id, statut="execute"),
        models.OrderRecipient(order_id=o1.id, unit_id=u2.id, statut="accuse"),
        models.OrderRecipient(order_id=o2.id, unit_id=u4.id, statut="envoye"),
    ])

    db.add_all([
        models.Incident(type_incident="renseignement", niveau_gravite="critique", localite="Zone A3", description="Groupe hostile détecté par patrouille, confirmé par renseignement SIGINT.", statut="en_cours", declarant="Compagnie Alpha", date_incident=datetime(2026, 7, 3, 12, 38)),
        models.Incident(type_incident="communication", niveau_gravite="moyenne", localite="Axe Nord-Ouest", description="Perte de liaison radio prolongée avec le Convoi Lima.", statut="nouveau", declarant="PC CPCO", date_incident=datetime(2026, 7, 3, 11, 51)),
        models.Incident(type_incident="logistique", niveau_gravite="faible", localite="Poste logistique Nord", description="Retard de livraison de pièces de maintenance.", statut="traite", declarant="Officier logistique", date_incident=datetime(2026, 7, 2, 16, 20)),
    ])

    db.add_all([
        models.Alert(type_alerte="menace", niveau="critique", message="Menace confirmée en Zone A3 — mouvement suspect observé.", statut="active", date_creation=datetime(2026, 7, 3, 12, 38)),
        models.Alert(type_alerte="logistique", niveau="attention", message="Compagnie Alpha sous seuil carburant (45%).", statut="active", date_creation=datetime(2026, 7, 3, 12, 12)),
        models.Alert(type_alerte="communication", niveau="attention", message="Communication dégradée avec Convoi Lima.", statut="active", date_creation=datetime(2026, 7, 3, 11, 51)),
        models.Alert(type_alerte="logistique", niveau="info", message="Ravitaillement disponible au Poste logistique Nord pour deux unités.", statut="resolue", date_creation=datetime(2026, 7, 3, 11, 58)),
    ])

    db.add_all([
        models.User(username="col.ba", nom_complet="Col. Ba", grade="Colonel", unit_id=pc.id, role="commandement", clearance_level="tres_secret"),
        models.User(username="cdt.sy", nom_complet="Cdt Sy", grade="Commandant", unit_id=pc.id, role="officier_operations", clearance_level="secret"),
        models.User(username="cne.diop", nom_complet="Cne Diop", grade="Capitaine", unit_id=pc.id, role="officier_renseignement", clearance_level="secret"),
        models.User(username="lt.kane", nom_complet="Lt Kane", grade="Lieutenant", unit_id=pc.id, role="officier_logistique", clearance_level="confidentiel"),
        models.User(username="adj.fall", nom_complet="Adj. Fall", grade="Adjudant", unit_id=pc.id, role="administrateur", clearance_level="secret"),
    ])

    db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Base initialisée et peuplée (ou déjà existante).")
