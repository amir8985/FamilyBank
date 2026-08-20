from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_auth,
    routes_catalog,
    routes_debt,
    routes_family,
    routes_internal,
    routes_investing,
    routes_kids,
)
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title="FamilyBank API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_auth.router)
app.include_router(routes_kids.router)
app.include_router(routes_debt.router)
app.include_router(routes_investing.router)
app.include_router(routes_catalog.router)
app.include_router(routes_family.router)
app.include_router(routes_internal.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
