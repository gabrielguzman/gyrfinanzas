from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import archivos, captura, categorias, cuentas, inicio, medios_pago, movimientos, resumen, semana, tarjetas, deudas, garantias, plan, metas, patrimonio, compra

app = FastAPI(title="gyrfinanzas API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (inicio, resumen, captura, movimientos, cuentas, medios_pago, categorias, archivos, tarjetas, deudas, semana, garantias, plan, metas, patrimonio, compra):
    app.include_router(r.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"ok": True}
