from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import admin, agenda, alerts, budget, communication, courrier, deploiement, execution, incidents, intelligence, logistics, materiel, operations, orders, rh, situation, units, veille
from .seed import init_db
from .storage import UPLOAD_DIR

app = FastAPI(title="Plateforme CPCO — API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://medbembar95607-dev.github.io",
        "https://tbcomd.netlify.app",
    ],
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


app.include_router(situation.router, prefix="/api")
app.include_router(units.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
app.include_router(logistics.router, prefix="/api")
app.include_router(operations.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(courrier.router, prefix="/api")
app.include_router(agenda.router, prefix="/api")
app.include_router(materiel.router, prefix="/api")
app.include_router(budget.router, prefix="/api")
app.include_router(rh.router, prefix="/api")
app.include_router(deploiement.router, prefix="/api")
app.include_router(veille.router, prefix="/api")
app.include_router(execution.router, prefix="/api")
app.include_router(communication.router, prefix="/api")

# Pièces jointes du chat (documents, messages vocaux) — voir app/storage.py
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}
