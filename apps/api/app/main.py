import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth
from app.config import settings
from app.routers import archivos, captura, categorias, cuentas, inicio, medios_pago, movimientos, resumen, semana, tarjetas, deudas, garantias, plan, metas, patrimonio, compra, fijos, reglas, exportar, avisos

def _pasada() -> None:
    from app.db import SessionLocal
    from app.services import avisos as svc_avisos
    with SessionLocal() as db:
        svc_avisos.tick(db)


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
              docs_url=None if settings.app_password_hash else "/docs", redoc_url=None, openapi_url=None if settings.app_password_hash else "/openapi.json")
app.middleware("http")(auth.middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
for r in (inicio, resumen, captura, movimientos, cuentas, medios_pago, categorias, archivos, tarjetas, deudas, semana, garantias, plan, metas, patrimonio, compra, fijos, reglas, exportar, avisos):
    app.include_router(r.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"ok": True}
