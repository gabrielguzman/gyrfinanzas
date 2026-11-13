import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria, TipoCategoria
from app.routers.util import obtener
from app.services import topes as svc

router = APIRouter(prefix="/topes", tags=["topes"])


class TopeOut(BaseModel):
    categoria_id: uuid.UUID
    categoria: str
    icono: str
    color: str
    tope: Decimal | None
    gastado: Decimal
    porcentaje: int
    queda: Decimal
    proyeccion: Decimal
    promedio: Decimal
    sugerido: Decimal | None
    estado: str


class TopeIn(BaseModel):
    monto: Decimal | None = Field(default=None, ge=0)


def _out(e: svc.Estado) -> TopeOut:
    c = e.categoria
    return TopeOut(categoria_id=c.id, categoria=c.nombre, icono=c.icono, color=c.color, tope=e.tope, gastado=e.gastado,
                   porcentaje=e.porcentaje, queda=e.queda, proyeccion=e.proyeccion, promedio=e.promedio,
                   sugerido=svc.sugerido(e.promedio if e.promedio > 0 else e.proyeccion), estado=e.estado)


@router.get("", response_model=list[TopeOut])
def listar(todas: bool = False, db: Session = Depends(get_db)):
    """Los topes del mes (con `todas=true`, también las categorías sin tope, con lo que solés gastar)."""
    orden = {"pasado": 0, "cerca": 1, "ok": 2, "sin_tope": 3}
    es = svc.estados(db, solo_con_tope=not todas)
    return [_out(e) for e in sorted(es, key=lambda e: (orden[e.estado], -(e.porcentaje or 0), -e.gastado))]


@router.put("/{categoria_id}", response_model=list[TopeOut])
def poner(categoria_id: uuid.UUID, datos: TopeIn, db: Session = Depends(get_db)):
    """Pone (o saca, con monto vacío o 0) el tope de una categoría."""
    c = obtener(db, Categoria, categoria_id, "Categoría")
    if c.tipo != TipoCategoria.gasto:
        raise HTTPException(422, "Los topes son para categorías de gastos.")
    svc.poner(db, c.id, datos.monto)
    db.commit()
    return listar(False, db)
