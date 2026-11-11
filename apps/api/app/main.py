import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth, accounts
from app.config import settings
from app.routers import archivos, captura, categorias, cuentas, inicio, medios_pago, movimientos, resumen, semana, tarjetas, deudas, garantias, plan, metas, patrimonio, compra, fijos, reglas, exportar, avisos

def _pasada() -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.db import SessionLocal, engine
    from app.accounts_models import Usuario
    from app.services import avisos as svc_avisos
    if settings.usuarios_habilitados:
        with SessionLocal() as identities:
            schemas = list(identities.scalars(select(Usuario.esquema).where(Usuario.activo.is_(True))))
    else:
        schemas = [None]
    for schema in schemas:
        try:
            bind = engine.execution_options(schema_translate_map={None: schema}) if schema else engine
            with Session(bind=bind, expire_on_commit=False) as db:
                svc_avisos.tick(db)
        except Exception:
            logging.getLogger("gyr.avisos").exception("Falló la pasada de avisos de una cuenta")



async def _programador() -> None:
    """Cada 10 minutos: fijos del día a la bandeja y notificaciones que correspondan."""
    await asyncio.sleep(20)
    while True:
        try:
            await asyncio.to_thread(_pasada)
        except Exception:
            logging.getLogger("gyr.avisos").exception("Falló la pasada de avisos")
        await asyncio.sleep(600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    tarea = asyncio.create_task(_programador()) if settings.avisos_activos else None
    yield
    if tarea:
        tarea.cancel()


# Con login activo, la documentación interactiva no queda pública
app = FastAPI(title="gyrfinanzas API", version="0.1.0", lifespan=lifespan,
              docs_url=None if settings.app_password_hash or settings.usuarios_habilitados else "/docs", redoc_url=None, openapi_url=None if settings.app_password_hash or settings.usuarios_habilitados else "/openapi.json")
app.middleware("http")(auth.middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
for r in (inicio, resumen, captura, movimientos, cuentas, medios_pago, categorias, archivos, tarjetas, deudas, semana, garantias, plan, metas, patrimonio, compra, fijos, reglas, exportar, avisos):
    app.include_router(r.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"ok": True}
