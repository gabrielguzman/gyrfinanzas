from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import exportar as svc

router = APIRouter(prefix="/exportar", tags=["exportar"])

TIPOS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
}


@router.get("")
def exportar(formato: Literal["xlsx", "csv"] = "xlsx", desde: date | None = None, hasta: date | None = None,
             db: Session = Depends(get_db)):
    contenido = svc.excel(db, desde, hasta) if formato == "xlsx" else svc.csv_movimientos(db, desde, hasta)
    nombre = svc.nombre_archivo(formato, desde, hasta)
    return Response(contenido, media_type=TIPOS[formato],
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"', "Cache-Control": "no-store"})
