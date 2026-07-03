# Plateforme CPCO — API

Backend FastAPI + SQLAlchemy pour la Plateforme CPCO. Sert de source de données à [`../plateforme-cpco-app/`](../plateforme-cpco-app/) (React).

Le cadrage complet (modèle de données, décisions d'architecture) vit dans [`../plateforme-cpco/`](../plateforme-cpco/). Ce README couvre uniquement le code.

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2.x (ORM)
- **SQLite pour le développement** (`cpco_dev.db`, généré automatiquement, ignoré par git) — décision de Bardas du 2026-07-03 faute de PostgreSQL/Docker sur la machine de dev
- **Cible retenue dans le cadrage : PostgreSQL + PostGIS self-hosted** (voir `../plateforme-cpco/02-architecture/decisions.md`). Migration : remplacer `DATABASE_URL` dans `app/database.py`, ajouter `psycopg[binary]` + `geoalchemy2`, et remplacer les colonnes `lon`/`lat` (float) et `geom_json` (texte JSON) par de vraies colonnes `GEOGRAPHY(POINT/POLYGON/LINESTRING, 4326)`

## Démarrer en local

```bash
python -m venv .venv
./.venv/Scripts/pip install -r requirements.txt   # Windows ; sous Linux/macOS : .venv/bin/pip
./.venv/Scripts/python -m uvicorn app.main:app --port 8000 --reload
```

Au démarrage, la base est créée et peuplée automatiquement (`app/seed.py`) si elle est vide — mêmes données que celles utilisées pour valider visuellement le frontend. Documentation interactive : http://localhost:8000/docs

## Structure

```
app/
  main.py         point d'entrée FastAPI, CORS (autorise localhost:*), montage des routers
  database.py     connexion SQLAlchemy (SQLite pour l'instant)
  models.py       tables ORM, alignées sur ../plateforme-cpco/03-donnees/modele-donnees.md
  schemas.py      schémas Pydantic de réponse
  seed.py         données de démonstration (mêmes valeurs que le prototype de référence)
  routers/        un fichier par domaine (situation, units, intelligence, logistics, operations, orders, incidents, alerts, admin)
```

## Endpoints principaux

| Endpoint | Usage |
|---|---|
| `GET /api/situation` | Écran Situation : unités + positions, menaces, checkpoints, zones, axes, KPI |
| `GET /api/units` | Écran Unités |
| `GET /api/intelligence-reports` | Écran Renseignement |
| `GET /api/logistics` | Écran Logistique (niveaux + alerte calculée par rapport aux seuils) |
| `GET /api/operations` | Écran Opérations |
| `GET /api/orders`, `POST /api/orders/{id}/advance` | Écran Ordres (workflow brouillon → signé → diffusé) |
| `GET /api/incidents`, `POST /api/incidents` | Écran Incidents |
| `GET /api/alerts`, `POST /api/alerts/{id}/acknowledge` | Écran Alertes |
| `GET /api/admin/users`, `/admin/roles`, `/admin/audit-log` | Écran Administration |

## Journal d'audit (`audit_log`)

Alimenté par `app/audit.py` (`log_action`) à chaque écriture sensible (`orders.advance`, `alerts.acknowledge`, `incidents.create`). Pas de vraie authentification : l'"utilisateur actif" est choisi dans un sélecteur de démonstration côté frontend (`UserSwitcher.tsx`) et transmis via l'en-tête `X-User-Id` ; `get_acting_user_id` (dépendance FastAPI) le lit, sans le vérifier. Une action sans en-tête est journalisée avec `user_id = null` (affiché "Non identifié" côté écran Administration).

## Limitations connues

- Pas d'authentification : tous les endpoints sont ouverts, pas de vérification de rôle/permission côté backend (RBAC affiché à l'écran Administration mais pas encore appliqué). L'en-tête `X-User-Id` n'est pas vérifié, n'importe quel appelant peut prétendre être n'importe qui — acceptable en dev, à corriger avant tout déploiement réel
- Pas de tables `roles`/`permissions`/`role_permissions` en base : `/admin/roles` renvoie un dictionnaire statique en dur dans `routers/admin.py`
- `unit_id` de `users` non exploité par l'API (pas de filtrage par unité/chaîne de commandement, contrairement au RLS hiérarchique du MVP `cadrage-app-c2`)
- Géométries en `lon`/`lat` simples ou JSON, pas de vrais types PostGIS — voir la section Stack ci-dessus pour la migration prévue
