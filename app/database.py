from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Dev : SQLite local (décision Bardas du 2026-07-03, faute de PostgreSQL/Docker sur la machine de dev).
# Cible retenue dans le cadrage (02-architecture/decisions.md) : PostgreSQL + PostGIS self-hosted.
# Migration : remplacer cette URL par "postgresql+psycopg://user:pass@host/dbname" et les colonnes
# lon/lat ci-dessous par de vraies colonnes GEOGRAPHY(POINT, 4326) via GeoAlchemy2.
DATABASE_URL = "sqlite:///./cpco_dev.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
