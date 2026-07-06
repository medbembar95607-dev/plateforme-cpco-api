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
        models.RendezVous(
            titre="Point de situation hebdomadaire", type_rdv="briefing",
            date_debut=datetime(2026, 7, 6, 8, 0), date_fin=datetime(2026, 7, 6, 9, 0),
            lieu="PC CPCO — salle de crise", participants="État-major, officiers OPS/RENS/LOG",
            statut="confirme", classification="confidentiel",
        ),
        models.RendezVous(
            titre="Audience — Gouverneur du Hodh Ech Chargui", type_rdv="audience",
            date_debut=datetime(2026, 7, 6, 11, 0), date_fin=datetime(2026, 7, 6, 12, 0),
            lieu="Bureau du Chef d'état-major", participants="Gouverneur, Col. Ba",
            statut="a_confirmer", classification="confidentiel",
        ),
        models.RendezVous(
            titre="Conseil des ministres — point sécurité", type_rdv="reunion",
            date_debut=datetime(2026, 7, 8, 9, 0), date_fin=datetime(2026, 7, 8, 11, 0),
            lieu="Ministère de la Défense", participants="CEMGA, Ministre de la Défense",
            statut="confirme", classification="secret",
        ),
        models.RendezVous(
            titre="Déplacement — inspection Zone A3", type_rdv="deplacement",
            date_debut=datetime(2026, 7, 9, 6, 0), date_fin=datetime(2026, 7, 9, 18, 0),
            lieu="Zone A3", participants="Col. Ba, escorte Compagnie Alpha",
            statut="a_confirmer", classification="secret",
        ),
        models.RendezVous(
            titre="Cérémonie de passation — PC Avancé Nord", type_rdv="ceremonie",
            date_debut=datetime(2026, 7, 4, 10, 0), date_fin=datetime(2026, 7, 4, 11, 30),
            lieu="Poste Avancé Nord", participants="État-major, unités du secteur Nord",
            statut="annule", classification="diffusion_libre",
            notes="Reporté en raison des conditions météo.",
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
