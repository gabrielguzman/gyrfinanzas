import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Cuenta
from app.routers.util import obtener
from app.schemas import CuentaIn, CuentaOut, CuentaPatch
from app.services.saldos import saldos_por_cuenta

router = APIRouter(prefix="/cuentas", tags=["cuentas"])


def _out(cuenta: Cuenta, saldos: dict) -> CuentaOut:
    out = CuentaOut.model_validate(cuenta)
    out.saldo = saldos.get(cuenta.id, cuenta.saldo_inicial)
    return out


@router.get("", response_model=list[CuentaOut])
def listar(incluir_archivadas: bool = False, db: Session = Depends(get_db)):
    q = select(Cuenta).order_by(Cuenta.creado)
    if not incluir_archivadas:
        q = q.where(Cuenta.archivada.is_(False))
    saldos = saldos_por_cuenta(db)
    return [_out(c, saldos) for c in db.scalars(q)]


@router.post("", response_model=CuentaOut, status_code=201)
def crear(datos: CuentaIn, db: Session = Depends(get_db)):
    cuenta = Cuenta(**datos.model_dump())
    db.add(cuenta)
    db.commit()
    return _out(cuenta, saldos_por_cuenta(db))


@router.get("/{cuenta_id}", response_model=CuentaOut)
def detalle(cuenta_id: uuid.UUID, db: Session = Depends(get_db)):
    return _out(obtener(db, Cuenta, cuenta_id, "Cuenta"), saldos_por_cuenta(db))


@router.patch("/{cuenta_id}", response_model=CuentaOut)
def editar(cuenta_id: uuid.UUID, datos: CuentaPatch, db: Session = Depends(get_db)):
    cuenta = obtener(db, Cuenta, cuenta_id, "Cuenta")
    for k, v in datos.model_dump(exclude_unset=True).items():
        setattr(cuenta, k, v)
    db.commit()
    return _out(cuenta, saldos_por_cuenta(db))
