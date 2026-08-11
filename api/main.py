from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin import init_admin
from api.routers import auth, backend, entreprise, paiement

app = FastAPI(title="E-Assis API")

# CORS_ALLOW_ALL_ORIGINS=True cote Django d'origine - le JWT passe par l'en-tete Authorization
# (pas de cookies), pas besoin d'allow_credentials.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(entreprise.router)
app.include_router(backend.router)
app.include_router(paiement.router)

init_admin(app)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
