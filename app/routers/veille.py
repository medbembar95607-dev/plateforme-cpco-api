from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

router = APIRouter(prefix="/veille", tags=["veille"])

NIVEAU_POIDS = {"faible": 1, "modere": 2, "eleve": 3, "critique": 4}


def _serialize(s: models.SignalStrategique) -> dict:
    return {
        "id": s.id,
        "categorie": s.categorie,
        "titre": s.titre,
        "zone": s.zone,
        "niveauRisque": s.niveau_risque,
        "tendance": s.tendance,
        "probabiliteCrisePct": s.probabilite_crise_pct,
        "horizon": s.horizon,
        "analyse": s.analyse,
        "source": s.source,
        "dateMaj": s.date_maj.isoformat(),
        "classification": s.classification,
    }


@router.get("")
def list_signaux(db: Session = Depends(get_db)):
    signaux = db.query(models.SignalStrategique).order_by(models.SignalStrategique.probabilite_crise_pct.desc()).all()
    return [_serialize(s) for s in signaux]


@router.get("/indicateurs")
def indicateurs(db: Session = Depends(get_db)):
    signaux = db.query(models.SignalStrategique).all()
    if not signaux:
        return {
            "indiceRisqueRegionalPct": 0,
            "signauxCritiques": 0,
            "signauxEnHausse": 0,
            "zonesSurveillees": 0,
            "probabiliteMaxPct": 0,
        }

    # Indice pondéré par le niveau de risque plutôt qu'une simple moyenne : un signal critique
    # doit peser davantage sur l'indice global qu'un signal faible, même à probabilité égale.
    poids_total = sum(NIVEAU_POIDS[s.niveau_risque] for s in signaux)
    indice = sum(s.probabilite_crise_pct * NIVEAU_POIDS[s.niveau_risque] for s in signaux) / poids_total

    return {
        "indiceRisqueRegionalPct": round(indice),
        "signauxCritiques": sum(1 for s in signaux if s.niveau_risque == "critique"),
        "signauxEnHausse": sum(1 for s in signaux if s.tendance == "hausse"),
        "zonesSurveillees": len({s.zone for s in signaux}),
        "probabiliteMaxPct": max(s.probabilite_crise_pct for s in signaux),
    }


# --- Réseaux sociaux (2026-10-05) ---------------------------------------------------------
# Données de démonstration : aucune collecte réelle. Une mise en production supposerait un outil
# d'écoute des réseaux sociaux ou les API des plateformes, avec un cadre juridique adapté.

def _serialize_tendance(t: models.TendanceSociale) -> dict:
    return {
        "id": t.id,
        "libelle": t.libelle,
        "plateformes": t.plateformes,
        "volumeMentions24h": t.volume_mentions_24h,
        "evolutionPct": t.evolution_pct,
        "domaineRisque": t.domaine_risque,
        "niveauRisque": t.niveau_risque,
        "langues": t.langues,
        "resume": t.resume,
        "dateMaj": t.date_maj.isoformat(),
    }


def _serialize_publication(p: models.PublicationSociale) -> dict:
    return {
        "id": p.id,
        "plateforme": p.plateforme,
        "typeAuteur": p.type_auteur,
        "abonnes": p.abonnes,
        "vues": p.vues,
        "partages": p.partages,
        "commentaires": p.commentaires,
        "resume": p.resume,
        "domaineRisque": p.domaine_risque,
        "niveauRisque": p.niveau_risque,
        "verification": p.verification,
        "langue": p.langue,
        "actionRecommandee": p.action_recommandee,
        "datePublication": p.date_publication.isoformat(),
    }


@router.get("/social-media")
def social_media(db: Session = Depends(get_db)):
    tendances = db.query(models.TendanceSociale).order_by(models.TendanceSociale.volume_mentions_24h.desc()).all()
    publications = db.query(models.PublicationSociale).order_by(models.PublicationSociale.vues.desc()).all()
    return {
        "donneesSimulees": True,
        "tendances": [_serialize_tendance(t) for t in tendances],
        "publications": [_serialize_publication(p) for p in publications],
        "indicateurs": {
            "mentions24h": sum(t.volume_mentions_24h for t in tendances),
            "tendancesEnHausse": sum(1 for t in tendances if t.evolution_pct > 0),
            "publicationsRisqueEleve": sum(1 for p in publications if p.niveau_risque in ("eleve", "critique")),
            "desinformationsAverees": sum(1 for p in publications if p.verification == "faux_avere"),
            "vuesCumulees": sum(p.vues for p in publications),
        },
    }


# --- Médias : presse publique et presse libre (2026-10-05) -------------------------------
# Données de démonstration : aucun média réel nommé, aucune collecte réelle.

@router.get("/medias")
def medias(db: Session = Depends(get_db)):
    sujets = db.query(models.SujetMedia).all()
    sujets.sort(key=lambda s: s.articles_presse_publique + s.articles_presse_libre, reverse=True)
    articles = db.query(models.ArticleMedia).order_by(models.ArticleMedia.audience.desc()).all()
    return {
        "donneesSimulees": True,
        "sujets": [
            {
                "id": s.id,
                "libelle": s.libelle,
                "articlesPressePublique": s.articles_presse_publique,
                "articlesPresseLibre": s.articles_presse_libre,
                "tonalitePublique": s.tonalite_publique,
                "tonaliteLibre": s.tonalite_libre,
                "domaineRisque": s.domaine_risque,
                "niveauRisque": s.niveau_risque,
                "evolutionPct": s.evolution_pct,
                "resume": s.resume,
            }
            for s in sujets
        ],
        "articles": [
            {
                "id": a.id,
                "secteur": a.secteur,
                "support": a.support,
                "typeOrgane": a.type_organe,
                "titre": a.titre,
                "audience": a.audience,
                "reprises": a.reprises,
                "tonalite": a.tonalite,
                "resume": a.resume,
                "domaineRisque": a.domaine_risque,
                "niveauRisque": a.niveau_risque,
                "langue": a.langue,
                "actionRecommandee": a.action_recommandee,
                "datePublication": a.date_publication.isoformat(),
            }
            for a in articles
        ],
        "indicateurs": {
            "articles24h": sum(s.articles_presse_publique + s.articles_presse_libre for s in sujets),
            "articlesPressePublique": sum(s.articles_presse_publique for s in sujets),
            "articlesPresseLibre": sum(s.articles_presse_libre for s in sujets),
            # Divergence : même sujet, tonalité officielle ou neutre côté public, critique côté libre (ou l'inverse).
            "sujetsDivergents": sum(1 for s in sujets if (s.tonalite_publique == "critique") != (s.tonalite_libre == "critique")),
            "contenusRisqueEleve": sum(1 for a in articles if a.niveau_risque in ("eleve", "critique")),
            "audienceCumulee": sum(a.audience for a in articles),
        },
    }
