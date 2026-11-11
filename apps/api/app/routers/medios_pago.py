import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Cuenta, MedioPago
from app.routers.util import obtener
from app.schemas import MedioPagoIn, MedioPagoOut, MedioPagoPatch

router = APIRouter(prefix="/medios-pago", tags=["medios de pago"])


@router.get("", response_model=list[MedioPagoOut])
def listar(incluir_archivados: bool = False, db: Session = Depends(get_db)):
    q = select(MedioPago).order_by(MedioPago.nombre)
    if not incluir_archivados:
        q = q.where(MedioPago.archivado.is_(False))
    return db.scalars(q).all()


@router.post("", response_model=MedioPagoOut, status_code=201)
def crear(datos: MedioPagoIn, db: Session = Depends(get_db)):
    obtener(db, Cuenta, datos.cuenta_id, "Cuenta")
    medio = MedioPago(**datos.model_dump())
    db.add(medio)
    db.commit()
    return medio


@router.patch("/{medio_id}", response_model=MedioPagoOut)
def editar(medio_id: uuid.UUID, datos: MedioPagoPatch, db: Session = Depends(get_db)):
    medio = obtener(db, MedioPago, medio_id, "Medio de pago")
    cambios = datos.model_dump(exclude_unset=True)
    if "cuenta_id" in cambios:
        obtener(db, Cuenta, cambios["cuenta_id"], "Cuenta")
    for k, v in cambios.items():
        setattr(medio, k, v)
    db.commit()
    return medio
