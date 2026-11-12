from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import racha as svc

router = APIRouter(prefix="/racha", tags=["racha"])


class Dia(BaseModel):
    fecha: date
    estado: str


class RachaOut(BaseModel):
    actual: int
    mejor: int
    hoy: str
    dias: list[Dia]


class SinGastosIn(BaseModel):
    fecha: date | None = None
    sin_gastos: bool = True


def _out(r: svc.Racha) -> RachaOut:
    return RachaOut(actual=r.actual, mejor=r.mejor, hoy=r.hoy, dias=[Dia(fecha=f, estado=e) for f, e in r.dias])


@router.get("", response_model=RachaOut)
def ver(db: Session = Depends(get_db)):
    return _out(svc.calcular(db))


@router.post("/sin-gastos", response_model=RachaOut)
def sin_gastos(datos: SinGastosIn, db: Session = Depends(get_db)):
    """«Hoy no gasté nada» (o un día anterior que te olvidaste de marcar)."""
    f = datos.fecha or date.today()
    if f > date.today():
        raise HTTPException(422, "No se puede marcar un día que todavía no pasó.")
    svc.marcar_sin_gastos(db, f, datos.sin_gastos)
    db.commit()
    return _out(svc.calcular(db))
