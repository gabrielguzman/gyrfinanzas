import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Etiqueta
from app.routers.util import obtener
from app.services import etiquetas as svc

router = APIRouter(prefix="/etiquetas", tags=["etiquetas"])


class CatTotal(BaseModel):
    nombre: str
    icono: str
    color: str
    total: Decimal


class EtiquetaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    total: Decimal
    total_usd: Decimal
    cantidad: int
    desde: date | None
    hasta: date | None
    activa: bool
    por_categoria: list[CatTotal]


class EtiquetasOut(BaseModel):
    activa: str | None
    etiquetas: list[EtiquetaOut]


class ActivaIn(BaseModel):
    nombre: str | None = Field(default=None, max_length=60)


class RenombrarIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)


def _out(r: svc.Resumen, activa: str | None) -> EtiquetaOut:
    return EtiquetaOut(id=r.id, nombre=r.nombre, total=r.total, total_usd=r.total_usd, cantidad=r.cantidad,
                       desde=r.desde, hasta=r.hasta, activa=r.nombre == activa,
                       por_categoria=[CatTotal(nombre=n, icono=i, color=c, total=t) for n, i, c, t in r.por_categoria])


@router.get("", response_model=EtiquetasOut)
def listar(db: Session = Depends(get_db)):
    activa = svc.activa(db)
    return EtiquetasOut(activa=activa, etiquetas=[_out(r, activa) for r in svc.resumenes(db)])


@router.put("/activa", response_model=EtiquetasOut)
def poner_activa(datos: ActivaIn, db: Session = Depends(get_db)):
    """Prende (o apaga, con nombre vacío) la etiqueta que se pone sola a todo lo que cargás."""
    svc.set_activa(db, datos.nombre)
    db.commit()
    return listar(db)


@router.get("/{nombre}", response_model=EtiquetaOut)
def detalle(nombre: str, db: Session = Depends(get_db)):
    e = db.scalar(select(Etiqueta).where(Etiqueta.nombre == svc.limpiar(nombre)))
    if e is None:
        raise HTTPException(404, "Etiqueta no encontrada")
    r, _ = svc.resumen(db, e)
    return _out(r, svc.activa(db))


@router.patch("/{etiqueta_id}", response_model=EtiquetaOut)
def renombrar(etiqueta_id: uuid.UUID, datos: RenombrarIn, db: Session = Depends(get_db)):
    e = obtener(db, Etiqueta, etiqueta_id, "Etiqueta")
    nuevo = svc.limpiar(datos.nombre)
    if not nuevo:
        raise HTTPException(422, "Usá letras o números.")
    if db.scalar(select(Etiqueta).where(Etiqueta.nombre == nuevo, Etiqueta.id != e.id)):
        raise HTTPException(409, f"Ya existe #{nuevo}.")
    era_activa = svc.activa(db) == e.nombre
    e.nombre = nuevo
    if era_activa:
        svc.set_activa(db, nuevo)
    db.commit()
    r, _ = svc.resumen(db, e)
    return _out(r, svc.activa(db))


@router.delete("/{etiqueta_id}", status_code=204)
def borrar(etiqueta_id: uuid.UUID, db: Session = Depends(get_db)):
    """Saca la etiqueta de todos los movimientos (los movimientos quedan)."""
    e = obtener(db, Etiqueta, etiqueta_id, "Etiqueta")
    if svc.activa(db) == e.nombre:
        svc.set_activa(db, None)
    db.delete(e)
    db.commit()
