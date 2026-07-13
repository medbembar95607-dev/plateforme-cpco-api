"""Peuple la base de dev avec les mêmes données que src/data/mockData.ts du frontend
(livrables/plateforme-cpco-app/), pour que le passage du mock au vrai backend soit invisible
à l'écran. Idempotent : ne fait rien si des unités existent déjà."""

import json
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models
from .database import Base, SessionLocal, engine


def migrer_colonnes_manquantes() -> None:
    """Base.metadata.create_all ne crée que les tables absentes, pas les colonnes ajoutées à une
    table existante. Le disque étant persistant sur Render, une colonne ajoutée au modèle après
    coup doit être migrée explicitement, sinon l'ORM interroge une colonne qui n'existe pas."""
    colonnes_a_ajouter = {
        "garnisons": [
            ("sante_pct", "INTEGER DEFAULT 80"),
            ("vehicule_pct", "INTEGER DEFAULT 80"),
        ],
    }
    with engine.connect() as conn:
        for table, colonnes in colonnes_a_ajouter.items():
            existantes = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            for nom_colonne, definition_sql in colonnes:
                if nom_colonne not in existantes:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {nom_colonne} {definition_sql}"))
        conn.commit()


def seed(db: Session) -> None:
    if db.query(models.Unit).count() > 0:
        return

    pc = models.Unit(code_unite="PC-CPCO", nom_unite="PC COP", type_unite="pc", echelon="groupement", effectif=25, commandant="Col. Ba", statut="disponible", communication="stable")
    u1 = models.Unit(code_unite="BAT-1", nom_unite="Bataillon 1", type_unite="infanterie", echelon="bataillon", effectif=520, statut="en_mission", communication="stable")
    u2 = models.Unit(code_unite="CIE-ALPHA", nom_unite="Compagnie Alpha", type_unite="infanterie", echelon="compagnie", effectif=140, statut="en_progression", communication="stable")
    u3 = models.Unit(code_unite="PA-NORD", nom_unite="Poste Avancé Nord", type_unite="pc", echelon="section", effectif=48, statut="disponible", communication="stable")
    u4 = models.Unit(code_unite="CONVOI-LIMA", nom_unite="Convoi", type_unite="logistique", echelon="section", effectif=36, statut="communication_degradee", communication="degradee")
    u5 = models.Unit(code_unite="POSTE-LOG-NORD", nom_unite="Poste logistique Nord", type_unite="logistique", echelon="section", effectif=20, statut="disponible", communication="stable")
    db.add_all([pc, u1, u2, u3, u4, u5])
    db.flush()

    # Positions réparties sur le territoire mauritanien (+ Léré au Mali pour la menace),
    # sur demande de Bardas le 2026-07-03 — coordonnées approximatives des localités citées.
    positions = [
        (u1, -7.25, 16.62, "12:33"),    # Bataillon 1 -> Néma
        (u2, -7.025414608093178, 15.705384312755095, "12:24"),    # Compagnie Alpha
        (u3, -11.60, 20.93, "12:08"),   # Poste Avancé Nord -> Ouadâne
        (u4, -5.774114140770708, 15.707085189958388, "11:51"),    # Convoi
        (u5, -13.05, 20.52, "11:58"),   # Poste logistique Nord -> Atar
        (pc, -15.99, 18.18, "12:00"),   # PC COP -> inchangé (secteur Nouakchott)
    ]
    for unit, lon, lat, _heure in positions:
        db.add(models.UnitPosition(unit_id=unit.id, lon=lon, lat=lat, source="manuel"))

    db.add(models.Threat(
        nom="Groupe hostile détecté", type_menace="groupe_hostile", niveau_menace="critique",
        statut="confirmee", classification="confidentiel", lon=-7.289557424909501, lat=15.186463905597305,  # Nara (Mali)
    ))

    db.add(models.Checkpoint(
        nom="Checkpoint Bravo", ordre_passage=1, statut="prevu",
        dernier_rapport="RAS", lon=-5.512285501482432, lat=15.526512758109305,
    ))

    db.add(models.OperationalArea(
        nom="Zone menace A3", type_zone="zone_menace", niveau_risque=4, classification="confidentiel",
        # Décalée vers la frontière mauritanienne (ouest de Nara) pour ne pas se superposer au marqueur de menace
        geom_json=json.dumps([[-8.05, 15.2], [-7.75, 15.2], [-7.75, 15.5], [-8.05, 15.5], [-8.05, 15.2]]),
    ))
    db.add(models.OperationalArea(
        nom="Zone OPS", type_zone="zone_ops", niveau_risque=2, classification="confidentiel",
        geom_json=json.dumps([[-6.534, 16.601], [-6.234, 16.601], [-6.234, 16.901], [-6.534, 16.901], [-6.534, 16.601]]),
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
        u1: {"carburant": 80, "munitions": 65, "vivres": 78, "maintenance": 71, "armement": 90},
        u2: {"carburant": 45, "munitions": 90, "vivres": 54, "maintenance": 68, "armement": 82},
        u4: {"carburant": 28, "munitions": 38, "vivres": 62, "maintenance": 41, "armement": 55},
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
    o2 = models.Order(numero_ordre="FRAGO-2026-031", type_ordre="FRAGO", classification="confidentiel", objet="Ravitaillement prioritaire Convoi", contenu="Organiser un ravitaillement en carburant et munitions pour le Convoi dès rétablissement de la liaison.", statut="signe", emetteur="Cdt Sy, Officier opérations", operation_id=op2.id, date_emission=datetime(2026, 7, 3, 9, 15))
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
        models.Incident(type_incident="communication", niveau_gravite="moyenne", localite="Axe Nord-Ouest", description="Perte de liaison radio prolongée avec le Convoi.", statut="nouveau", declarant="PC COP", date_incident=datetime(2026, 7, 3, 11, 51)),
        models.Incident(type_incident="logistique", niveau_gravite="faible", localite="Poste logistique Nord", description="Retard de livraison de pièces de maintenance.", statut="traite", declarant="Officier logistique", date_incident=datetime(2026, 7, 2, 16, 20)),
    ])

    db.add_all([
        models.Alert(type_alerte="menace", niveau="critique", message="Menace confirmée en Zone A3 — mouvement suspect observé.", statut="active", date_creation=datetime(2026, 7, 3, 12, 38)),
        models.Alert(type_alerte="logistique", niveau="attention", message="Compagnie Alpha sous seuil carburant (45%).", statut="active", date_creation=datetime(2026, 7, 3, 12, 12)),
        models.Alert(type_alerte="communication", niveau="attention", message="Communication dégradée avec Convoi.", statut="active", date_creation=datetime(2026, 7, 3, 11, 51)),
        models.Alert(type_alerte="logistique", niveau="info", message="Ravitaillement disponible au Poste logistique Nord pour deux unités.", statut="resolue", date_creation=datetime(2026, 7, 3, 11, 58)),
    ])

    col_ba = models.User(username="col.ba", nom_complet="Col. Ba", grade="Colonel", unit_id=pc.id, role="commandement", clearance_level="tres_secret")
    db.add_all([
        col_ba,
        models.User(username="cdt.sy", nom_complet="Cdt Sy", grade="Commandant", unit_id=pc.id, role="officier_operations", clearance_level="secret"),
        models.User(username="cne.diop", nom_complet="Cne Diop", grade="Capitaine", unit_id=pc.id, role="officier_renseignement", clearance_level="secret"),
        models.User(username="lt.kane", nom_complet="Lt Kane", grade="Lieutenant", unit_id=pc.id, role="officier_logistique", clearance_level="confidentiel"),
        models.User(username="adj.fall", nom_complet="Adj. Fall", grade="Adjudant", unit_id=pc.id, role="administrateur", clearance_level="secret"),
    ])
    db.flush()

    # Courrier du chef d'état-major : triage des correspondances remontant des subordonnés,
    # du ministère et d'institutions externes (2026-07-03).
    db.add_all([
        models.Courrier(
            numero_enregistrement="COUR-2026-0041", type_document="rapport", origine="subordonne",
            expediteur="Cdt Sy, Officier opérations", objet="Compte rendu hebdomadaire des opérations",
            resume="Bilan des opérations en cours : Sable Nord à 64%, aucune perte, ravitaillement Convoi en attente.",
            contenu="Compte rendu détaillé de la semaine écoulée pour l'ensemble des opérations en cours dans le secteur Hodh Ech Chargui...",
            classification="confidentiel", priorite="normal", statut="nouveau",
            date_reception=datetime(2026, 7, 3, 8, 15), date_limite_reponse=datetime(2026, 7, 5, 18, 0),
        ),
        models.Courrier(
            numero_enregistrement="COUR-2026-0042", type_document="lettre", origine="ministere_defense",
            expediteur="Ministère de la Défense — Cabinet", objet="Demande de point de situation avant Conseil des ministres",
            resume="Le cabinet du ministre demande un point de situation consolidé sur la Zone A3 avant le prochain Conseil des ministres.",
            contenu="Le Ministre souhaite disposer d'un point de situation actualisé sur les opérations en cours dans la Zone A3 avant le Conseil des ministres de vendredi...",
            classification="secret", priorite="tres_urgent", statut="nouveau",
            date_reception=datetime(2026, 7, 3, 9, 0), date_limite_reponse=datetime(2026, 7, 3, 17, 0),
        ),
        models.Courrier(
            numero_enregistrement="COUR-2026-0043", type_document="note", origine="institution_externe",
            expediteur="Gendarmerie nationale — État-major", objet="Coordination zone frontalière Hodh Ech Chargui",
            resume="La Gendarmerie signale une recrudescence de mouvements suspects côté malien et propose une réunion de coordination.",
            contenu="Suite à plusieurs signalements de mouvements suspects dans la zone frontalière, l'État-major de la Gendarmerie nationale propose d'organiser une réunion de coordination inter-forces...",
            classification="confidentiel", priorite="urgent", statut="nouveau",
            date_reception=datetime(2026, 7, 3, 10, 30), date_limite_reponse=datetime(2026, 7, 4, 12, 0),
        ),
        models.Courrier(
            numero_enregistrement="COUR-2026-0038", type_document="fiche", origine="subordonne",
            expediteur="Cne Diop, Officier renseignement", objet="Fiche de synthèse — activité suspecte Nara",
            resume="Synthèse renseignement confirmant la présence d'un groupe hostile dans le secteur de Nara.",
            contenu="Fiche de synthèse renseignement établie à partir de plusieurs sources HUMINT et SIGINT convergentes sur la présence d'un groupe armé non identifié...",
            classification="secret", priorite="urgent", statut="annote",
            date_reception=datetime(2026, 7, 2, 14, 0), date_limite_reponse=datetime(2026, 7, 3, 12, 0),
            annotation="Vu. Renforcer la surveillance et me tenir informé toutes les 6h. Voir avec DOP pour un dispositif complémentaire.",
            annote_par=col_ba.id, date_annotation=datetime(2026, 7, 2, 16, 30),
        ),
        models.Courrier(
            numero_enregistrement="COUR-2026-0035", type_document="compte_rendu", origine="institution_externe",
            expediteur="Préfecture du Hodh Ech Chargui", objet="Situation sécuritaire zone civile",
            resume="La préfecture confirme une situation calme dans les localités civiles, aucune action requise.",
            contenu="Compte rendu de situation transmis par la préfecture confirmant l'absence d'incident notable dans les zones civiles du Hodh Ech Chargui...",
            classification="diffusion_libre", priorite="normal", statut="classe_sans_suite",
            date_reception=datetime(2026, 7, 1, 9, 0), date_limite_reponse=None,
        ),
    ])

    db.add_all([
        # Armée de Terre
        models.Materiel(
            nom="VAB", categorie="vehicule", type_materiel="Véhicule blindé de transport de troupes", armee="terre",
            formation_affectation="Bataillon 1", fonction="Transport de troupes protégé",
            caracteristiques="4x4, blindage niveau 1, capacité 10 hommes",
            statut_dotation="en_dotation", etat="operationnel", quantite=8, seuil_alerte=5, dotation_ted=10, classification="confidentiel",
        ),
        models.Materiel(
            nom="FAMAS", categorie="arme", type_materiel="Fusil d'assaut", armee="terre",
            formation_affectation="Compagnie Alpha", fonction="Armement individuel",
            caracteristiques="Calibre 5.56mm, cadence 900 coups/min",
            statut_dotation="en_dotation", etat="operationnel", quantite=140, seuil_alerte=100, dotation_ted=150, classification="confidentiel",
        ),
        models.Materiel(
            nom="Munitions 7.62mm", categorie="munition", type_materiel="Cartouches mitrailleuse", armee="terre",
            formation_affectation="Dépôt central Nouakchott", fonction="Approvisionnement munitions",
            caracteristiques="Conditionnement caisses de 500",
            statut_dotation="en_reserve", etat="operationnel", quantite=1200, seuil_alerte=5000, dotation_ted=1000, classification="secret",
        ),
        models.Materiel(
            nom="Poste radio PR4G", categorie="communication", type_materiel="Radio tactique VHF", armee="terre",
            formation_affectation="Bataillon 1", fonction="Transmission tactique",
            caracteristiques="Portée 30km, chiffrement intégré",
            statut_dotation="en_dotation", etat="operationnel", quantite=12, seuil_alerte=10, dotation_ted=12, classification="confidentiel",
        ),
        models.Materiel(
            nom="Camion GBC 180", categorie="vehicule", type_materiel="Camion logistique tout-terrain", armee="terre",
            formation_affectation="Dépôt central Nouakchott", fonction="Ravitaillement des unités",
            caracteristiques="Charge utile 5 tonnes, 6x6",
            statut_dotation="en_reserve", etat="operationnel", quantite=4, seuil_alerte=3, dotation_ted=6, classification="confidentiel",
        ),
        models.Materiel(
            nom="Pistolet PAMAS G1", categorie="arme", type_materiel="Arme de poing", armee="terre",
            formation_affectation="Dépôt central Nouakchott", fonction="Armement individuel officiers",
            caracteristiques="Calibre 9mm, chargeur 15 coups",
            statut_dotation="en_reserve", etat="operationnel", quantite=30, seuil_alerte=20, dotation_ted=25, classification="confidentiel",
        ),
        models.Materiel(
            nom="Munitions 5.56mm", categorie="munition", type_materiel="Cartouches fusil d'assaut", armee="terre",
            formation_affectation="Compagnie Alpha", fonction="Approvisionnement munitions",
            caracteristiques="Conditionnement caisses de 1000",
            statut_dotation="en_dotation", etat="operationnel", quantite=8000, seuil_alerte=5000, dotation_ted=8000, classification="secret",
        ),
        models.Materiel(
            nom="Groupe électrogène", categorie="equipement", type_materiel="Générateur de campagne", armee="terre",
            formation_affectation="Bataillon 1", fonction="Alimentation électrique de campagne",
            caracteristiques="Puissance 20kVA",
            statut_dotation="en_reserve", etat="operationnel", quantite=3, seuil_alerte=2, dotation_ted=4, classification="confidentiel",
        ),
        # Armée de l'Air
        models.Materiel(
            nom="Gazelle SA342", categorie="aeronef", type_materiel="Hélicoptère de reconnaissance", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Reconnaissance et appui",
            caracteristiques="Autonomie 3h30, équipage 2",
            statut_dotation="en_dotation", etat="operationnel", quantite=3, seuil_alerte=2, dotation_ted=4, classification="secret",
        ),
        models.Materiel(
            nom="Pièces détachées moteur Astazou", categorie="equipement", type_materiel="Pièces de rechange aéronautiques", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Maintenance aéronefs",
            caracteristiques="Lot de rechange moteur turbine",
            statut_dotation="en_reserve", etat="operationnel", quantite=2, seuil_alerte=4, dotation_ted=5, classification="confidentiel",
        ),
        models.Materiel(
            nom="Jumelles de vision nocturne", categorie="optique", type_materiel="Optique de vision nocturne", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Observation nocturne",
            caracteristiques="Portée 300m, autonomie 8h",
            statut_dotation="en_dotation", etat="operationnel", quantite=15, seuil_alerte=10, dotation_ted=12, classification="confidentiel",
        ),
        models.Materiel(
            nom="Roquettes SNEB", categorie="munition", type_materiel="Roquettes air-sol", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Armement d'appui hélicoptère",
            caracteristiques="Calibre 68mm, conditionnement nacelle de 6",
            statut_dotation="en_dotation", etat="operationnel", quantite=24, seuil_alerte=10, dotation_ted=20, classification="secret",
        ),
        models.Materiel(
            nom="Drone de reconnaissance", categorie="aeronef", type_materiel="Aéronef sans pilote", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Reconnaissance longue durée",
            caracteristiques="Autonomie 8h, altitude 4000m",
            statut_dotation="en_reserve", etat="operationnel", quantite=1, seuil_alerte=2, dotation_ted=2, classification="secret",
        ),
        models.Materiel(
            nom="Véhicule de piste", categorie="vehicule", type_materiel="Tracteur de piste aéronautique", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Manutention aéronefs au sol",
            caracteristiques="Traction 4x4, treuil intégré",
            statut_dotation="en_dotation", etat="operationnel", quantite=2, seuil_alerte=1, dotation_ted=3, classification="confidentiel",
        ),
        models.Materiel(
            nom="Véhicule de piste (rechange)", categorie="vehicule", type_materiel="Tracteur de piste aéronautique", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Manutention aéronefs au sol",
            caracteristiques="Traction 4x4, treuil intégré",
            statut_dotation="en_reserve", etat="operationnel", quantite=1, seuil_alerte=1, dotation_ted=1, classification="confidentiel",
        ),
        models.Materiel(
            nom="Mitrailleuse de sabord", categorie="arme", type_materiel="Mitrailleuse d'hélicoptère", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Autodéfense en vol",
            caracteristiques="Calibre 7.62mm, cadence 600 coups/min",
            statut_dotation="en_dotation", etat="operationnel", quantite=2, seuil_alerte=2, dotation_ted=3, classification="secret",
        ),
        models.Materiel(
            nom="Mitrailleuse de sabord (réserve)", categorie="arme", type_materiel="Mitrailleuse d'hélicoptère", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Autodéfense en vol",
            caracteristiques="Calibre 7.62mm, cadence 600 coups/min",
            statut_dotation="en_reserve", etat="operationnel", quantite=1, seuil_alerte=1, dotation_ted=1, classification="secret",
        ),
        models.Materiel(
            nom="Munitions 7.62mm (aviation)", categorie="munition", type_materiel="Cartouches mitrailleuse de bord", armee="air",
            formation_affectation="Base aérienne Nouakchott", fonction="Approvisionnement armement de bord",
            caracteristiques="Conditionnement bandes de 200",
            statut_dotation="en_reserve", etat="operationnel", quantite=600, seuil_alerte=500, dotation_ted=500, classification="secret",
        ),
        # Marine
        models.Materiel(
            nom="Patrouilleur côtier", categorie="navire", type_materiel="Navire de surveillance côtière", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Surveillance des eaux territoriales",
            caracteristiques="Longueur 35m, vitesse max 22 nœuds",
            statut_dotation="en_dotation", etat="maintenance", quantite=2, seuil_alerte=2, dotation_ted=3, classification="secret",
        ),
        models.Materiel(
            nom="Moteur hors-bord", categorie="equipement", type_materiel="Moteur d'embarcation rapide", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Propulsion embarcations légères",
            caracteristiques="Puissance 150cv",
            statut_dotation="en_reserve", etat="operationnel", quantite=1, seuil_alerte=3, dotation_ted=2, classification="confidentiel",
        ),
        models.Materiel(
            nom="Gilets de sauvetage", categorie="equipement", type_materiel="Équipement de sécurité maritime", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Sécurité individuelle en mer",
            caracteristiques="Homologation SOLAS",
            statut_dotation="en_dotation", etat="operationnel", quantite=80, seuil_alerte=50, dotation_ted=80, classification="diffusion_libre",
        ),
        models.Materiel(
            nom="Munitions 12.7mm", categorie="munition", type_materiel="Cartouches mitrailleuse navale", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Armement de bord patrouilleur",
            caracteristiques="Conditionnement caisses de 200",
            statut_dotation="en_reserve", etat="operationnel", quantite=500, seuil_alerte=800, dotation_ted=600, classification="secret",
        ),
        models.Materiel(
            nom="Embarcation pneumatique rapide", categorie="navire", type_materiel="Embarcation d'intervention", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Intervention rapide et visite de navires",
            caracteristiques="Longueur 7m, vitesse max 35 nœuds",
            statut_dotation="en_reserve", etat="operationnel", quantite=1, seuil_alerte=2, dotation_ted=2, classification="confidentiel",
        ),
        models.Materiel(
            nom="Véhicule de servitude portuaire", categorie="vehicule", type_materiel="Véhicule utilitaire de quai", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Manutention portuaire",
            caracteristiques="Charge utile 2 tonnes",
            statut_dotation="en_dotation", etat="operationnel", quantite=2, seuil_alerte=1, dotation_ted=2, classification="confidentiel",
        ),
        models.Materiel(
            nom="Véhicule de servitude portuaire (rechange)", categorie="vehicule", type_materiel="Véhicule utilitaire de quai", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Manutention portuaire",
            caracteristiques="Charge utile 2 tonnes",
            statut_dotation="en_reserve", etat="operationnel", quantite=1, seuil_alerte=1, dotation_ted=1, classification="confidentiel",
        ),
        models.Materiel(
            nom="Mitrailleuse navale 12.7mm", categorie="arme", type_materiel="Mitrailleuse de pont", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Armement de bord",
            caracteristiques="Calibre 12.7mm, montage sur affût",
            statut_dotation="en_dotation", etat="operationnel", quantite=2, seuil_alerte=2, dotation_ted=2, classification="secret",
        ),
        models.Materiel(
            nom="Mitrailleuse navale 12.7mm (réserve)", categorie="arme", type_materiel="Mitrailleuse de pont", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Armement de bord",
            caracteristiques="Calibre 12.7mm, montage sur affût",
            statut_dotation="en_reserve", etat="operationnel", quantite=1, seuil_alerte=1, dotation_ted=1, classification="secret",
        ),
        models.Materiel(
            nom="Munitions 20mm", categorie="munition", type_materiel="Obus canon naval", armee="mer",
            formation_affectation="Base navale Nouadhibou", fonction="Armement de bord patrouilleur",
            caracteristiques="Conditionnement caisses de 100",
            statut_dotation="en_dotation", etat="operationnel", quantite=400, seuil_alerte=300, dotation_ted=400, classification="secret",
        ),
    ])

    db.add_all([
        # Fonctionnement
        models.LigneBudgetaire(
            libelle="Solde et primes du personnel", type_budget="fonctionnement",
            formation_beneficiaire="Toutes unités", periode="2026",
            montant_alloue=500_000_000, montant_consomme=310_000_000, seuil_alerte_pct=80, classification="confidentiel",
        ),
        models.LigneBudgetaire(
            libelle="Carburant et lubrifiants", type_budget="fonctionnement",
            formation_beneficiaire="Toutes unités", periode="2026",
            montant_alloue=80_000_000, montant_consomme=68_000_000, seuil_alerte_pct=80, classification="confidentiel",
        ),
        models.LigneBudgetaire(
            libelle="Entretien véhicules et matériel", type_budget="fonctionnement",
            formation_beneficiaire="Bataillon 1", periode="2026",
            montant_alloue=45_000_000, montant_consomme=30_000_000, seuil_alerte_pct=80, classification="confidentiel",
        ),
        models.LigneBudgetaire(
            libelle="Alimentation et vivres", type_budget="fonctionnement",
            formation_beneficiaire="Toutes unités", periode="2026",
            montant_alloue=60_000_000, montant_consomme=52_000_000, seuil_alerte_pct=85, classification="diffusion_libre",
        ),
        models.LigneBudgetaire(
            libelle="Formation et instruction", type_budget="fonctionnement",
            formation_beneficiaire="CSIC", periode="2026",
            montant_alloue=25_000_000, montant_consomme=9_000_000, seuil_alerte_pct=80, classification="confidentiel",
        ),
        # Investissement
        models.LigneBudgetaire(
            libelle="Acquisition véhicules blindés", type_budget="investissement",
            formation_beneficiaire="Bataillon 1", periode="2026",
            montant_alloue=200_000_000, montant_consomme=150_000_000, seuil_alerte_pct=90, classification="secret",
        ),
        models.LigneBudgetaire(
            libelle="Modernisation systèmes de communication", type_budget="investissement",
            formation_beneficiaire="CSIC", periode="2026",
            montant_alloue=90_000_000, montant_consomme=91_500_000, seuil_alerte_pct=90, classification="secret",
        ),
        models.LigneBudgetaire(
            libelle="Infrastructure — Base aérienne Nouakchott", type_budget="investissement",
            formation_beneficiaire="Base aérienne Nouakchott", periode="2026",
            montant_alloue=120_000_000, montant_consomme=40_000_000, seuil_alerte_pct=80, classification="confidentiel",
        ),
        models.LigneBudgetaire(
            libelle="Modernisation base navale Nouadhibou", type_budget="investissement",
            formation_beneficiaire="Base navale Nouadhibou", periode="2026",
            montant_alloue=70_000_000, montant_consomme=59_000_000, seuil_alerte_pct=80, classification="secret",
        ),
    ])

    col_ba_rh = models.Militaire(
        matricule="OFF-0012", nom_complet="Ba", grade="Colonel", categorie="officier", armee="terre",
        formation_affectation="PC COP", date_naissance=datetime(1970, 3, 12), date_entree_service=datetime(1992, 9, 1),
        date_prise_grade=datetime(2015, 1, 1), classification="confidentiel",
    )
    cdt_sy = models.Militaire(
        matricule="OFF-0045", nom_complet="Sy", grade="Commandant", categorie="officier", armee="terre",
        formation_affectation="Compagnie Alpha", date_naissance=datetime(1980, 5, 20), date_entree_service=datetime(2003, 9, 1),
        date_prise_grade=datetime(2018, 1, 1), classification="confidentiel",
    )
    cne_diop = models.Militaire(
        matricule="OFF-0078", nom_complet="Diop", grade="Capitaine", categorie="officier", armee="terre",
        formation_affectation="Bataillon 1", date_naissance=datetime(1985, 11, 3), date_entree_service=datetime(2008, 9, 1),
        date_prise_grade=datetime(2020, 1, 1), classification="confidentiel",
    )
    lt_fall = models.Militaire(
        matricule="OFF-0103", nom_complet="Fall", grade="Lieutenant", categorie="officier", armee="terre",
        formation_affectation="Compagnie Alpha", date_naissance=datetime(1992, 2, 14), date_entree_service=datetime(2015, 9, 1),
        date_prise_grade=datetime(2019, 1, 1), classification="confidentiel",
    )
    col_kane = models.Militaire(
        matricule="OFF-0005", nom_complet="Kane", grade="Colonel", categorie="officier", armee="air",
        formation_affectation="Base aérienne Nouakchott", date_naissance=datetime(1967, 6, 8), date_entree_service=datetime(1989, 9, 1),
        date_prise_grade=datetime(2008, 1, 1), classification="confidentiel",
    )
    adjc_sow = models.Militaire(
        matricule="SOF-0231", nom_complet="Sow", grade="Adjudant-chef", categorie="sous_officier", armee="terre",
        formation_affectation="Bataillon 1", date_naissance=datetime(1969, 9, 25), date_entree_service=datetime(1990, 3, 1),
        date_prise_grade=datetime(2012, 1, 1), classification="confidentiel",
    )
    sgc_ndiaye = models.Militaire(
        matricule="SOF-0344", nom_complet="Ndiaye", grade="Sergent-chef", categorie="sous_officier", armee="terre",
        formation_affectation="Compagnie Alpha", date_naissance=datetime(1988, 1, 17), date_entree_service=datetime(2010, 3, 1),
        date_prise_grade=datetime(2019, 1, 1), classification="confidentiel",
    )
    adj_traore = models.Militaire(
        matricule="SOF-0410", nom_complet="Traoré", grade="Adjudant", categorie="sous_officier", armee="air",
        formation_affectation="Base aérienne Nouakchott", date_naissance=datetime(1975, 7, 30), date_entree_service=datetime(1997, 3, 1),
        date_prise_grade=datetime(2009, 1, 1), classification="confidentiel",
    )
    sgt_camara = models.Militaire(
        matricule="SOF-0512", nom_complet="Camara", grade="Sergent", categorie="sous_officier", armee="mer",
        formation_affectation="Base navale Nouadhibou", date_naissance=datetime(1990, 4, 22), date_entree_service=datetime(2012, 3, 1),
        date_prise_grade=datetime(2020, 1, 1), classification="confidentiel",
    )
    capc_diallo = models.Militaire(
        matricule="TRP-0781", nom_complet="Diallo", grade="Caporal-chef", categorie="homme_du_rang", armee="terre",
        formation_affectation="Compagnie Alpha", date_naissance=datetime(1996, 8, 11), date_entree_service=datetime(2017, 1, 1),
        date_prise_grade=datetime(2022, 1, 1), classification="diffusion_libre",
    )
    sdt_barry = models.Militaire(
        matricule="TRP-0902", nom_complet="Barry", grade="Soldat de 1ère classe", categorie="homme_du_rang", armee="terre",
        formation_affectation="Bataillon 1", date_naissance=datetime(2000, 12, 5), date_entree_service=datetime(2021, 1, 1),
        date_prise_grade=datetime(2022, 1, 1), classification="diffusion_libre",
    )
    cap_sy = models.Militaire(
        matricule="TRP-0655", nom_complet="Sy", grade="Caporal", categorie="homme_du_rang", armee="air",
        formation_affectation="Base aérienne Nouakchott", date_naissance=datetime(1974, 10, 2), date_entree_service=datetime(1996, 1, 1),
        date_prise_grade=datetime(2003, 1, 1), classification="diffusion_libre",
    )
    sdt_wade = models.Militaire(
        matricule="TRP-1021", nom_complet="Wade", grade="Soldat de 2ème classe", categorie="homme_du_rang", armee="mer",
        formation_affectation="Base navale Nouadhibou", date_naissance=datetime(1998, 3, 19), date_entree_service=datetime(2019, 1, 1),
        date_prise_grade=datetime(2019, 1, 1), classification="diffusion_libre",
    )
    db.add_all([
        col_ba_rh, cdt_sy, cne_diop, lt_fall, col_kane,
        adjc_sow, sgc_ndiaye, adj_traore, sgt_camara,
        capc_diallo, sdt_barry, cap_sy, sdt_wade,
    ])
    db.flush()

    db.add_all([
        models.PropositionRH(
            militaire_id=cne_diop.id, type_proposition="avancement",
            motif="Ancienneté suffisante et notation excellente sur les deux dernières années.",
            proposition="Avancement au grade de Commandant", statut="en_cours", classification="confidentiel",
        ),
        models.PropositionRH(
            militaire_id=sgc_ndiaye.id, type_proposition="affectation",
            motif="Besoin en renfort à la cellule Renseignement suite à l'activité suspecte de la Zone A3.",
            proposition="Affectation à la cellule Renseignement (RENS)", statut="en_cours", classification="confidentiel",
        ),
        models.PropositionRH(
            militaire_id=lt_fall.id, type_proposition="avancement",
            motif="Réussite au stage supérieur d'état-major.",
            proposition="Avancement au grade de Capitaine", statut="validee", classification="confidentiel",
        ),
        models.PropositionRH(
            militaire_id=capc_diallo.id, type_proposition="affectation",
            motif="Réorganisation interne du Bataillon 1, poste déjà pourvu.",
            proposition="Affectation au Bataillon 1", statut="rejetee", classification="diffusion_libre",
        ),
    ])

    db.add_all([
        models.BesoinRecrutement(
            poste="Officier transmetteur", categorie="officier", armee="terre",
            formation_affectation="CSIC", nombre_postes=2, priorite="elevee", statut="ouvert", classification="confidentiel",
        ),
        models.BesoinRecrutement(
            poste="Mécanicien aéronautique", categorie="sous_officier", armee="air",
            formation_affectation="Base aérienne Nouakchott", nombre_postes=3, priorite="critique", statut="ouvert", classification="confidentiel",
        ),
        models.BesoinRecrutement(
            poste="Fusilier marin", categorie="homme_du_rang", armee="mer",
            formation_affectation="Base navale Nouadhibou", nombre_postes=10, priorite="normale", statut="ouvert", classification="diffusion_libre",
        ),
        models.BesoinRecrutement(
            poste="Officier logisticien", categorie="officier", armee="terre",
            formation_affectation="Dépôt central Nouakchott", nombre_postes=1, priorite="normale", statut="pourvu", classification="confidentiel",
        ),
    ])

    db.commit()


def reseeder_besoins_formation(db: Session) -> None:
    """Ajoute les besoins en formation de démo s'ils n'existent pas encore.

    Fonction séparée de seed() (idempotente sur sa propre table, pas sur Unit) : le disque de la
    base est persistant sur Render, donc seed() ne rejoue jamais une fois les unités déjà en
    place, et une nouvelle table ajoutée après coup ne serait sinon jamais peuplée.
    """
    if db.query(models.BesoinFormation).count() > 0:
        return

    db.add_all([
        models.BesoinFormation(
            intitule="Stage supérieur d'état-major", categorie="officier", armee="terre",
            formation_affectation="PC COP", nombre_places=4, priorite="elevee", statut="a_planifier", classification="confidentiel",
        ),
        models.BesoinFormation(
            intitule="Formation cybersécurité niveau 2", categorie="officier", armee="terre",
            formation_affectation="CSIC", nombre_places=6, priorite="critique", statut="a_planifier", classification="confidentiel",
        ),
        models.BesoinFormation(
            intitule="Perfectionnement maintenance aéronautique", categorie="sous_officier", armee="air",
            formation_affectation="Base aérienne Nouakchott", nombre_places=8, priorite="elevee", statut="planifie", classification="confidentiel",
        ),
        models.BesoinFormation(
            intitule="Stage de chefferie sous-officiers", categorie="sous_officier", armee="terre",
            formation_affectation="Bataillon 1", nombre_places=10, priorite="normale", statut="a_planifier", classification="confidentiel",
        ),
        models.BesoinFormation(
            intitule="Formation initiale fusilier marin", categorie="homme_du_rang", armee="mer",
            formation_affectation="Base navale Nouadhibou", nombre_places=15, priorite="normale", statut="realise", classification="diffusion_libre",
        ),
        models.BesoinFormation(
            intitule="Recyclage conduite et sécurité routière", categorie="homme_du_rang", armee="terre",
            formation_affectation="Compagnie Alpha", nombre_places=12, priorite="normale", statut="a_planifier", classification="diffusion_libre",
        ),
    ])
    db.commit()


def reseeder_agenda(db: Session) -> None:
    """Régénère les rendez-vous de démo avec des dates relatives à l'instant présent.

    Contrairement à seed(), tourne à chaque démarrage sans condition d'idempotence sur les
    autres tables : le disque de la base est persistant sur Render (pas éphémère comme supposé
    initialement), donc des dates de rendez-vous codées en dur finissent toujours par glisser
    dans le passé et faire disparaître le rappel de "prochain rendez-vous" sur l'écran Agenda.
    """
    db.query(models.RendezVous).delete()

    aujourdhui = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    db.add_all([
        models.RendezVous(
            titre="Point de situation hebdomadaire", type_rdv="briefing",
            date_debut=aujourdhui + timedelta(days=-3, hours=8), date_fin=aujourdhui + timedelta(days=-3, hours=9),
            lieu="PC CPCO — salle de crise", participants="État-major, officiers OPS/RENS/LOG",
            statut="confirme", classification="confidentiel",
        ),
        models.RendezVous(
            titre="Audience — Gouverneur du Hodh Ech Chargui", type_rdv="audience",
            date_debut=aujourdhui + timedelta(days=-3, hours=11), date_fin=aujourdhui + timedelta(days=-3, hours=12),
            lieu="Bureau du Chef d'état-major", participants="Gouverneur, Col. Ba",
            statut="a_confirmer", classification="confidentiel",
        ),
        models.RendezVous(
            titre="Conseil des ministres — point sécurité", type_rdv="reunion",
            date_debut=aujourdhui + timedelta(days=-1, hours=9), date_fin=aujourdhui + timedelta(days=-1, hours=11),
            lieu="Ministère de la Défense", participants="CEMGA, Ministre de la Défense",
            statut="confirme", classification="secret",
        ),
        models.RendezVous(
            titre="Déplacement — inspection Zone A3", type_rdv="deplacement",
            date_debut=aujourdhui + timedelta(days=1, hours=6), date_fin=aujourdhui + timedelta(days=1, hours=18),
            lieu="Zone A3", participants="Col. Ba, escorte Compagnie Alpha",
            statut="a_confirmer", classification="secret",
        ),
        models.RendezVous(
            titre="Cérémonie de passation — PC Avancé Nord", type_rdv="ceremonie",
            date_debut=aujourdhui + timedelta(days=-5, hours=10), date_fin=aujourdhui + timedelta(days=-5, hours=11, minutes=30),
            lieu="Poste Avancé Nord", participants="État-major, unités du secteur Nord",
            statut="annule", classification="diffusion_libre",
            notes="Reporté en raison des conditions météo.",
        ),
    ])
    db.commit()


def reseeder_garnisons(db: Session) -> None:
    """Déploiement permanent (carte Déploiement Armée) : une formation niveau bataillon (armée
    de terre ou force spéciale) dans chaque chef-lieu de wilaya, plus les bases aériennes
    (Nouakchott, Atar, Néma), bases navales (Nouakchott, Nouadhibou) et postes frontaliers.

    Idempotence par nom (pas par comptage global de la table) : contrairement à reseeder_agenda,
    cette liste est amenée à grandir au fil des demandes. Un simple "if count() > 0: return"
    empêcherait tout nouvel ajout de fonctionner après le premier déploiement, puisque le disque
    de la base est persistant sur Render (pas réinitialisé à chaque redémarrage).
    """
    garnisons_attendues = [
        # --- Bataillons Armée de Terre / Forces spéciales, un par chef-lieu de wilaya ---
        models.Garnison(
            nom="Bataillon des Forces Spéciales — Néma", type_unite="force_speciale", echelon="bataillon",
            wilaya="Hodh Ech Chargui", localite="Néma", armee="terre", effectif=420, statut="disponible",
            lon=-7.2700, lat=16.6000, carburant_pct=82, munitions_pct=88, armement_pct=90, vivres_pct=85, sante_pct=88, vehicule_pct=85,
            classification="secret",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Aïoun el Atrouss", type_unite="infanterie", echelon="bataillon",
            wilaya="Hodh El Gharbi", localite="Aïoun el Atrouss", armee="terre", effectif=480, statut="disponible",
            lon=-9.6165, lat=16.6650, carburant_pct=76, munitions_pct=80, armement_pct=85, vivres_pct=79, sante_pct=82, vehicule_pct=78,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Kiffa", type_unite="infanterie", echelon="bataillon",
            wilaya="Assaba", localite="Kiffa", armee="terre", effectif=510, statut="disponible",
            lon=-11.4000, lat=16.6167, carburant_pct=88, munitions_pct=83, armement_pct=87, vivres_pct=90, sante_pct=88, vehicule_pct=86,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Kaédi", type_unite="infanterie", echelon="bataillon",
            wilaya="Gorgol", localite="Kaédi", armee="terre", effectif=460, statut="disponible",
            lon=-13.5050, lat=16.1500, carburant_pct=71, munitions_pct=75, armement_pct=80, vivres_pct=74, sante_pct=77, vehicule_pct=73,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Aleg", type_unite="infanterie", echelon="bataillon",
            wilaya="Brakna", localite="Aleg", armee="terre", effectif=440, statut="disponible",
            lon=-13.9167, lat=17.0500, carburant_pct=80, munitions_pct=78, armement_pct=82, vivres_pct=81, sante_pct=82, vehicule_pct=79,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Rosso", type_unite="infanterie", echelon="bataillon",
            wilaya="Trarza", localite="Rosso", armee="terre", effectif=500, statut="communication_degradee",
            lon=-15.8058, lat=16.5136, carburant_pct=65, munitions_pct=70, armement_pct=76, vivres_pct=68, sante_pct=72, vehicule_pct=68,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Atar", type_unite="infanterie", echelon="bataillon",
            wilaya="Adrar", localite="Atar", armee="terre", effectif=470, statut="disponible",
            lon=-13.0700, lat=20.5000, carburant_pct=84, munitions_pct=86, armement_pct=88, vivres_pct=83, sante_pct=86, vehicule_pct=85,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Nouadhibou", type_unite="infanterie", echelon="bataillon",
            wilaya="Dakhlet Nouadhibou", localite="Nouadhibou", armee="terre", effectif=490, statut="disponible",
            lon=-17.0550, lat=20.9150, carburant_pct=79, munitions_pct=81, armement_pct=84, vivres_pct=80, sante_pct=82, vehicule_pct=80,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Tidjikja", type_unite="infanterie", echelon="bataillon",
            wilaya="Tagant", localite="Tidjikja", armee="terre", effectif=380, statut="disponible",
            lon=-11.4260, lat=18.5550, carburant_pct=73, munitions_pct=77, armement_pct=79, vivres_pct=75, sante_pct=77, vehicule_pct=75,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon des Forces Spéciales — Sélibaby", type_unite="force_speciale", echelon="bataillon",
            wilaya="Guidimaka", localite="Sélibaby", armee="terre", effectif=400, statut="en_mission",
            lon=-12.1841, lat=15.1706, carburant_pct=68, munitions_pct=85, armement_pct=91, vivres_pct=72, sante_pct=82, vehicule_pct=76,
            classification="secret",
        ),
        models.Garnison(
            nom="Bataillon des Forces Spéciales — Zouérat", type_unite="force_speciale", echelon="bataillon",
            wilaya="Tiris Zemmour", localite="Zouérat", armee="terre", effectif=410, statut="disponible",
            lon=-12.4672, lat=22.7354, carburant_pct=77, munitions_pct=84, armement_pct=89, vivres_pct=78, sante_pct=84, vehicule_pct=80,
            classification="secret",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Akjoujt", type_unite="infanterie", echelon="bataillon",
            wilaya="Inchiri", localite="Akjoujt", armee="terre", effectif=360, statut="disponible",
            lon=-14.3800, lat=19.7461, carburant_pct=81, munitions_pct=79, armement_pct=83, vivres_pct=80, sante_pct=82, vehicule_pct=80,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Garde de Nouakchott", type_unite="infanterie", echelon="bataillon",
            wilaya="Nouakchott", localite="Nouakchott", armee="terre", effectif=580, statut="disponible",
            lon=-15.9785, lat=18.0858, carburant_pct=90, munitions_pct=92, armement_pct=93, vivres_pct=91, sante_pct=92, vehicule_pct=91,
            classification="confidentiel",
        ),
        # --- Bases aériennes : Nouakchott, Atar, Néma ---
        models.Garnison(
            nom="Base Aérienne — Nouakchott", type_unite="aerien", echelon="base",
            wilaya="Nouakchott", localite="Nouakchott", armee="air", effectif=280, statut="disponible",
            lon=-15.9450, lat=18.1050, carburant_pct=85, munitions_pct=80, armement_pct=87, vivres_pct=82, sante_pct=84, vehicule_pct=82,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Base Aérienne — Atar", type_unite="aerien", echelon="base",
            wilaya="Adrar", localite="Atar", armee="air", effectif=190, statut="disponible",
            lon=-13.0250, lat=20.5350, carburant_pct=78, munitions_pct=74, armement_pct=80, vivres_pct=76, sante_pct=78, vehicule_pct=76,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Base Aérienne — Néma", type_unite="aerien", echelon="base",
            wilaya="Hodh Ech Chargui", localite="Néma", armee="air", effectif=160, statut="disponible",
            lon=-7.2350, lat=16.6300, carburant_pct=72, munitions_pct=70, armement_pct=75, vivres_pct=71, sante_pct=73, vehicule_pct=71,
            classification="confidentiel",
        ),
        # --- Bases navales : Nouadhibou, Nouakchott ---
        models.Garnison(
            nom="Base Navale — Nouadhibou", type_unite="marine", echelon="base",
            wilaya="Dakhlet Nouadhibou", localite="Nouadhibou", armee="mer", effectif=320, statut="disponible",
            lon=-17.0150, lat=20.9450, carburant_pct=83, munitions_pct=79, armement_pct=85, vivres_pct=81, sante_pct=83, vehicule_pct=81,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Base Navale — Nouakchott", type_unite="marine", echelon="base",
            wilaya="Nouakchott", localite="Nouakchott", armee="mer", effectif=260, statut="disponible",
            lon=-16.0150, lat=18.0450, carburant_pct=87, munitions_pct=82, armement_pct=86, vivres_pct=84, sante_pct=85, vehicule_pct=84,
            classification="confidentiel",
        ),
        # --- Postes frontaliers Nord-Est (Tiris Zemmour, frontière Algérie/Sahara occidental) ---
        models.Garnison(
            nom="Bataillon d'Infanterie — Poste Frontière Sud-Est", type_unite="infanterie", echelon="bataillon",
            wilaya="Tiris Zemmour", localite="Poste Frontière Sud-Est", armee="terre", effectif=390, statut="disponible",
            lon=-7.948722, lat=21.285806, carburant_pct=74, munitions_pct=78, armement_pct=81, vivres_pct=76, sante_pct=78, vehicule_pct=76,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Poste Frontière Est", type_unite="infanterie", echelon="bataillon",
            wilaya="Tiris Zemmour", localite="Poste Frontière Est", armee="terre", effectif=400, statut="disponible",
            lon=-7.858889, lat=23.509000, carburant_pct=72, munitions_pct=76, armement_pct=80, vivres_pct=74, sante_pct=77, vehicule_pct=74,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Poste Frontière Nord-Est", type_unite="infanterie", echelon="bataillon",
            wilaya="Tiris Zemmour", localite="Poste Frontière Nord-Est", armee="terre", effectif=380, statut="disponible",
            lon=-6.762083, lat=25.352583, carburant_pct=70, munitions_pct=75, armement_pct=79, vivres_pct=72, sante_pct=76, vehicule_pct=72,
            classification="confidentiel",
        ),
        models.Garnison(
            nom="Bataillon d'Infanterie — Bir Moghrein", type_unite="infanterie", echelon="bataillon",
            wilaya="Tiris Zemmour", localite="Bir Moghrein", armee="terre", effectif=420, statut="disponible",
            lon=-11.543556, lat=25.213250, carburant_pct=76, munitions_pct=80, armement_pct=83, vivres_pct=78, sante_pct=80, vehicule_pct=78,
            classification="confidentiel",
        ),
    ]

    # Upsert par nom : insère les formations manquantes et resynchronise les autres champs
    # (position, effectif, statut...) de celles qui existent déjà, pour que les ajustements faits
    # ici (ex. repositionnement d'un poste) s'appliquent aussi au redémarrage suivant, pas
    # seulement les toutes nouvelles formations.
    existantes = {g.nom: g for g in db.query(models.Garnison).all()}
    for attendue in garnisons_attendues:
        existante = existantes.get(attendue.nom)
        if existante is None:
            db.add(attendue)
            continue
        existante.type_unite = attendue.type_unite
        existante.echelon = attendue.echelon
        existante.wilaya = attendue.wilaya
        existante.localite = attendue.localite
        existante.armee = attendue.armee
        existante.effectif = attendue.effectif
        existante.statut = attendue.statut
        existante.lon = attendue.lon
        existante.lat = attendue.lat
        existante.carburant_pct = attendue.carburant_pct
        existante.munitions_pct = attendue.munitions_pct
        existante.armement_pct = attendue.armement_pct
        existante.vivres_pct = attendue.vivres_pct
        existante.sante_pct = attendue.sante_pct
        existante.vehicule_pct = attendue.vehicule_pct
        existante.classification = attendue.classification
    db.commit()


def reseeder_veille(db: Session) -> None:
    """Veille stratégique : signaux géopolitiques et sécuritaires régionaux de démo.

    Même pattern d'upsert par titre que reseeder_garnisons (disque persistant sur Render) :
    insère les signaux manquants et resynchronise les autres au redémarrage.
    """
    signaux_attendus = [
        models.SignalStrategique(
            categorie="securite_regionale",
            titre="Recrudescence d'activité JNIM/AQMI en zone frontalière malienne",
            zone="Frontière Mali — Hodh Ech Chargui / Hodh El Gharbi",
            niveau_risque="critique", tendance="hausse", probabilite_crise_pct=78, horizon="court_terme",
            analyse="Multiplication des signalements de mouvements armés et d'engins explosifs improvisés côté malien, à proximité immédiate de la frontière. Risque direct de débordement vers le territoire national et de ciblage des postes avancés.",
            source="Cellule Renseignement CPCO / coopération G5 Sahel", classification="secret",
        ),
        models.SignalStrategique(
            categorie="securite_regionale",
            titre="Contagion potentielle depuis le triangle Liptako-Gourma",
            zone="Zone tri-frontalière Mali–Niger–Burkina Faso",
            niveau_risque="modere", tendance="hausse", probabilite_crise_pct=45, horizon="moyen_terme",
            analyse="L'intensification des opérations dans le Liptako-Gourma pousse des groupes armés à chercher de nouvelles zones de repli, avec un risque de report progressif de l'activité vers l'Est mauritanien.",
            source="Analyse open source / partenaires régionaux", classification="confidentiel",
        ),
        models.SignalStrategique(
            categorie="securite_regionale",
            titre="Afflux de déplacés maliens vers le camp de Mbera",
            zone="Bassikounou — Hodh Ech Chargui",
            niveau_risque="eleve", tendance="hausse", probabilite_crise_pct=58, horizon="court_terme",
            analyse="La pression humanitaire croissante sur le camp de Mbera fragilise le tissu sécuritaire local et complique le contrôle des flux transfrontaliers, avec un risque d'infiltration parmi les populations déplacées.",
            source="HCR / rapports de terrain CPCO", classification="confidentiel",
        ),
        models.SignalStrategique(
            categorie="diplomatique",
            titre="Durcissement des contrôles frontaliers avec le Mali",
            zone="Frontière Mali — ensemble du tracé Est",
            niveau_risque="eleve", tendance="hausse", probabilite_crise_pct=55, horizon="court_terme",
            analyse="Multiplication des incidents mineurs lors des patrouilles conjointes et durcissement unilatéral des points de passage côté malien. Risque d'escalade diplomatique en cas d'incident armé.",
            source="Ministère des Affaires étrangères / DRSM", classification="secret",
        ),
        models.SignalStrategique(
            categorie="diplomatique",
            titre="Dossier du Sahara occidental et posture au Nord",
            zone="Frontière Nord — Sahara occidental / Algérie",
            niveau_risque="modere", tendance="stable", probabilite_crise_pct=25, horizon="long_terme",
            analyse="Le statu quo relatif sur le dossier du Sahara occidental limite le risque immédiat, mais toute évolution du conflit Maroc-Polisario aurait un impact direct sur la posture de sécurité des postes frontaliers du Tiris Zemmour.",
            source="Veille diplomatique régionale", classification="confidentiel",
        ),
        models.SignalStrategique(
            categorie="influence_etrangere",
            titre="Expansion de l'Africa Corps (ex-Wagner) au Mali",
            zone="Mali — bases arrière proches de la frontière",
            niveau_risque="eleve", tendance="hausse", probabilite_crise_pct=60, horizon="moyen_terme",
            analyse="Le renforcement de la présence de l'Africa Corps dans le centre et l'est du Mali modifie l'équilibre régional et pourrait accroître la pression sécuritaire aux abords de la frontière mauritanienne.",
            source="Analyse open source / renseignement extérieur", classification="secret",
        ),
        models.SignalStrategique(
            categorie="influence_etrangere",
            titre="Recul des partenariats militaires occidentaux dans la région",
            zone="Sahel élargi",
            niveau_risque="faible", tendance="baisse", probabilite_crise_pct=15, horizon="long_terme",
            analyse="La réduction des exercices conjoints (type Flintlock) et des programmes de coopération occidentaux limite les capacités de formation et de partage de renseignement à moyen terme, sans constituer un risque immédiat.",
            source="Coopération bilatérale / DRSM", classification="confidentiel",
        ),
        models.SignalStrategique(
            categorie="economique",
            titre="Volatilité du cours du fer et recettes d'exportation",
            zone="National — filière SNIM",
            niveau_risque="modere", tendance="hausse", probabilite_crise_pct=40, horizon="moyen_terme",
            analyse="Le fer représente une part majeure des recettes d'exportation. Une baisse durable des cours mondiaux fragiliserait le budget de l'État et, indirectement, les capacités d'investissement en matière de défense.",
            source="Ministère des Finances / veille économique", classification="confidentiel",
        ),
        models.SignalStrategique(
            categorie="economique",
            titre="Retards de décaissement des programmes de développement",
            zone="National",
            niveau_risque="faible", tendance="stable", probabilite_crise_pct=20, horizon="long_terme",
            analyse="Des retards dans les décaissements des bailleurs internationaux ralentissent des projets d'infrastructure sensibles dans les régions périphériques, avec un risque limité de frustration locale à surveiller.",
            source="Coopération internationale", classification="diffusion_libre",
        ),
        models.SignalStrategique(
            categorie="climat_ressources",
            titre="Stress hydrique sur le fleuve Sénégal",
            zone="Vallée du fleuve Sénégal — Trarza / Brakna / Gorgol",
            niveau_risque="modere", tendance="hausse", probabilite_crise_pct=35, horizon="moyen_terme",
            analyse="La baisse du débit du fleuve Sénégal ravive les tensions autour du partage de la ressource en eau avec les pays riverains et fragilise l'agriculture irriguée dans trois wilayas frontalières.",
            source="OMVS / veille climatique", classification="diffusion_libre",
        ),
        models.SignalStrategique(
            categorie="climat_ressources",
            titre="Sécheresse et insécurité alimentaire dans les zones pastorales de l'Est",
            zone="Hodh Ech Chargui / Hodh El Gharbi / Assaba",
            niveau_risque="eleve", tendance="hausse", probabilite_crise_pct=50, horizon="court_terme",
            analyse="Le déficit pluviométrique cumulé fragilise les moyens de subsistance pastoraux dans l'Est du pays, un facteur historiquement corrélé à une plus grande porosité aux réseaux armés transfrontaliers.",
            source="Système d'alerte précoce / PAM", classification="diffusion_libre",
        ),
        models.SignalStrategique(
            categorie="cyber",
            titre="Recrudescence de tentatives d'intrusion sur les systèmes étatiques",
            zone="National — infrastructures critiques",
            niveau_risque="modere", tendance="hausse", probabilite_crise_pct=38, horizon="court_terme",
            analyse="Augmentation des tentatives d'intrusion détectées sur les systèmes d'information gouvernementaux, cohérente avec l'absence d'agence nationale de cybersécurité pleinement opérationnelle.",
            source="CSIC / veille cyber", classification="secret",
        ),
    ]

    existants = {s.titre: s for s in db.query(models.SignalStrategique).all()}
    for attendu in signaux_attendus:
        existant = existants.get(attendu.titre)
        if existant is None:
            db.add(attendu)
            continue
        existant.categorie = attendu.categorie
        existant.zone = attendu.zone
        existant.niveau_risque = attendu.niveau_risque
        existant.tendance = attendu.tendance
        existant.probabilite_crise_pct = attendu.probabilite_crise_pct
        existant.horizon = attendu.horizon
        existant.analyse = attendu.analyse
        existant.source = attendu.source
        existant.classification = attendu.classification
    db.commit()


def reseeder_execution(db: Session) -> None:
    """Suivi d'exécution des ordres/instructions par unité, avec délais relatifs à l'instant
    présent (même raison que reseeder_agenda : sinon tout finit par apparaître "en retard" une
    fois la date de seed dépassée). Upsert par (reference, unité), même logique de résilience au
    disque persistant Render que les autres reseeders.
    """
    unites = {u.code_unite: u for u in db.query(models.Unit).all()}
    bat1, alpha, pa_nord, convoi, poste_log, pc = (
        unites.get("BAT-1"), unites.get("CIE-ALPHA"), unites.get("PA-NORD"),
        unites.get("CONVOI-LIMA"), unites.get("POSTE-LOG-NORD"), unites.get("PC-CPCO"),
    )
    if not all([bat1, alpha, pa_nord, convoi, poste_log, pc]):
        return  # seed() de base pas encore passé (unités absentes) : rien à faire pour l'instant

    maintenant = datetime.now()

    def j(offset_jours: float, heure: int, minute: int = 0) -> datetime:
        return (maintenant + timedelta(days=offset_jours)).replace(hour=heure, minute=minute, second=0, microsecond=0)

    suivis_attendus = [
        models.SuiviExecution(
            reference="OPORD-2026-014", type_ordre="OPORD", objet="Sécurisation de l'axe nord",
            instruction="Sécuriser l'axe de progression nord et tenir les checkpoints Bravo et Charlie.",
            emetteur="Col. Ba, Commandement CPCO", unite_id=bat1.id,
            date_emission=j(-6, 8), date_limite=j(-4, 18),
            statut="execute", date_execution=j(-5, 14),
            compte_rendu="Axe sécurisé, checkpoints Bravo et Charlie tenus, aucune activité hostile constatée.",
            classification="secret",
        ),
        models.SuiviExecution(
            reference="OPORD-2026-014", type_ordre="OPORD", objet="Sécurisation de l'axe nord — appui",
            instruction="Appuyer le Bataillon 1 sur le flanc est de l'axe nord.",
            emetteur="Col. Ba, Commandement CPCO", unite_id=alpha.id,
            date_emission=j(-6, 8), date_limite=j(-4, 18),
            statut="en_cours", date_execution=None, compte_rendu=None,
            classification="secret",
        ),
        models.SuiviExecution(
            reference="FRAGO-2026-031", type_ordre="FRAGO", objet="Ravitaillement prioritaire Convoi",
            instruction="Organiser un ravitaillement en carburant et munitions dès rétablissement de la liaison.",
            emetteur="Cdt Sy, Officier opérations", unite_id=convoi.id,
            date_emission=j(-4, 9, 15), date_limite=j(-1, 17),
            statut="en_attente", date_execution=None, compte_rendu=None,
            classification="confidentiel",
        ),
        models.SuiviExecution(
            reference="WARNO-2026-009", type_ordre="WARNO", objet="Renforcement surveillance Zone A3",
            instruction="Renforcer le dispositif de surveillance sur la Zone A3 suite à confirmation de menace.",
            emetteur="Cne Diop, Officier renseignement", unite_id=pa_nord.id,
            date_emission=j(-2, 10), date_limite=j(1, 12),
            statut="en_cours", date_execution=None, compte_rendu=None,
            classification="secret",
        ),
        models.SuiviExecution(
            reference="INSTRUCTION-2026-042", type_ordre="INSTRUCTION", objet="Inventaire hebdomadaire des stocks",
            instruction="Transmettre l'inventaire complet des stocks de la semaine.",
            emetteur="Cdt Sy, Officier opérations", unite_id=poste_log.id,
            date_emission=j(-1, 8), date_limite=j(2, 18),
            statut="en_attente", date_execution=None, compte_rendu=None,
            classification="diffusion_libre",
        ),
        models.SuiviExecution(
            reference="INSTRUCTION-2026-038", type_ordre="INSTRUCTION", objet="Compte-rendu effectifs mensuel",
            instruction="Transmettre le compte-rendu des effectifs disponibles pour le mois en cours.",
            emetteur="Col. Ba, Commandement CPCO", unite_id=bat1.id,
            date_emission=j(-10, 8), date_limite=j(-8, 18),
            statut="execute", date_execution=j(-9, 10),
            compte_rendu="Effectifs transmis : 520 personnels, 4 postes à pourvoir signalés.",
            classification="confidentiel",
        ),
        models.SuiviExecution(
            reference="FRAGO-2026-028", type_ordre="FRAGO", objet="Reconnaissance itinéraire alternatif Nord",
            instruction="Reconnaître un itinéraire alternatif pour contourner la Zone A3 en cas de nécessité.",
            emetteur="Cdt Sy, Officier opérations", unite_id=alpha.id,
            date_emission=j(-3, 7), date_limite=j(-1, 18),
            statut="execute", date_execution=j(-1, 16, 30),
            compte_rendu="Itinéraire alternatif reconnu et validé, praticable pour véhicules légers et poids lourds.",
            classification="confidentiel",
        ),
        models.SuiviExecution(
            reference="INSTRUCTION-2026-045", type_ordre="INSTRUCTION", objet="Rétablir la liaison radio principale",
            instruction="Diagnostiquer et rétablir la liaison radio principale avec le PC COP.",
            emetteur="Col. Ba, Commandement CPCO", unite_id=convoi.id,
            date_emission=j(-2, 9), date_limite=j(0, 18),
            statut="en_cours", date_execution=None, compte_rendu=None,
            classification="confidentiel",
        ),
        models.SuiviExecution(
            reference="INSTRUCTION-2026-040", type_ordre="INSTRUCTION", objet="Préparer le briefing hebdomadaire état-major",
            instruction="Préparer les éléments de situation pour le briefing hebdomadaire de l'état-major.",
            emetteur="Col. Ba, Commandement CPCO", unite_id=pc.id,
            date_emission=j(-1, 8), date_limite=j(3, 9),
            statut="en_attente", date_execution=None, compte_rendu=None,
            classification="confidentiel",
        ),
        models.SuiviExecution(
            reference="FRAGO-2026-025", type_ordre="FRAGO", objet="Rapport de reconnaissance Zone A3",
            instruction="Transmettre un rapport détaillé de reconnaissance sur la Zone A3.",
            emetteur="Cne Diop, Officier renseignement", unite_id=pa_nord.id,
            date_emission=j(-5, 8), date_limite=j(-3, 18),
            statut="execute", date_execution=j(-2, 9),
            compte_rendu="Rapport transmis avec retard suite à une panne de transmission temporaire. Aucun mouvement hostile confirmé depuis 48h.",
            classification="secret",
        ),
        models.SuiviExecution(
            reference="WARNO-2026-011", type_ordre="WARNO", objet="Préparation relève Compagnie Alpha",
            instruction="Préparer la relève de la Compagnie Alpha par une unité fraîche sous 5 jours.",
            emetteur="Col. Ba, Commandement CPCO", unite_id=bat1.id,
            date_emission=j(-1, 15), date_limite=j(5, 18),
            statut="en_attente", date_execution=None, compte_rendu=None,
            classification="confidentiel",
        ),
        models.SuiviExecution(
            reference="FRAGO-2026-033", type_ordre="FRAGO", objet="Constitution d'un stock d'urgence carburant",
            instruction="Constituer un stock d'urgence de carburant équivalent à 5 jours d'autonomie.",
            emetteur="Cdt Sy, Officier opérations", unite_id=poste_log.id,
            date_emission=j(-7, 8), date_limite=j(-5, 18),
            statut="execute", date_execution=j(-6, 12),
            compte_rendu="Stock d'urgence constitué et vérifié, autonomie de 5,5 jours atteinte.",
            classification="diffusion_libre",
        ),
    ]

    existants = {(s.reference, s.unite_id): s for s in db.query(models.SuiviExecution).all()}
    for attendu in suivis_attendus:
        cle = (attendu.reference, attendu.unite_id)
        existant = existants.get(cle)
        if existant is None:
            db.add(attendu)
            continue
        existant.type_ordre = attendu.type_ordre
        existant.objet = attendu.objet
        existant.instruction = attendu.instruction
        existant.emetteur = attendu.emetteur
        existant.date_emission = attendu.date_emission
        existant.date_limite = attendu.date_limite
        existant.statut = attendu.statut
        existant.date_execution = attendu.date_execution
        existant.compte_rendu = attendu.compte_rendu
        existant.classification = attendu.classification
    db.commit()


def reseeder_logistique_etendue(db: Session) -> None:
    """Ajoute les domaines Santé et Véhicules (mobilité) aux unités qui ont déjà un suivi
    logistique, sans rejouer tout `seed()` (idempotent par unité + type_stock, pas par comptage
    global, pour la même raison que les autres reseeders)."""
    unites = {u.code_unite: u for u in db.query(models.Unit).all()}
    valeurs_par_unite = {
        "BAT-1": {"sante": 85, "vehicule": 88},
        "CIE-ALPHA": {"sante": 60, "vehicule": 50},
        "CONVOI-LIMA": {"sante": 45, "vehicule": 35},
    }
    for code_unite, valeurs in valeurs_par_unite.items():
        unite = unites.get(code_unite)
        if unite is None:
            continue
        types_existants = {
            s.type_stock for s in db.query(models.Stock).filter(models.Stock.unit_id == unite.id).all()
        }
        for type_stock, pct in valeurs.items():
            if type_stock in types_existants:
                continue
            stock = models.Stock(unit_id=unite.id, type_stock=type_stock)
            db.add(stock)
            db.flush()
            db.add(models.StockLevel(stock_id=stock.id, pct=pct))
    db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    migrer_colonnes_manquantes()
    db = SessionLocal()
    try:
        seed(db)
        reseeder_agenda(db)
        reseeder_besoins_formation(db)
        reseeder_garnisons(db)
        reseeder_veille(db)
        reseeder_execution(db)
        reseeder_logistique_etendue(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Base initialisée et peuplée (ou déjà existante).")
