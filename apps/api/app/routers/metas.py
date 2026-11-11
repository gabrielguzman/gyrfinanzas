import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import AporteMeta, Cuenta, Meta
from app.routers.util import obtener
from app.schemas import AporteIn, AporteOut, MetaIn, MetaOut, MetaPatch
from app.services import cotizacion as svc_cot
from app.services import metas as svc
from app.services.saldos import saldos_por_cuenta

router = APIRouter(prefix="/metas", tags=["metas"])


def _cargar(db: Session, mid: uuid.UUID) -> Meta:
    m = db.scalar(select(Meta).options(selectinload(Meta.aportes)).where(Meta.id == mid))
    if m is None:
        raise HTTPException(404, "Meta no encontrada")
    return m


def _out(db: Session, m: Meta, cot, saldos=None, con_aportes=False) -> MetaOut:
    e = svc.estado(db, m, date.today(), cot, saldos)
    cuenta = db.get(Cuenta, m.cuenta_id) if m.cuenta_id else None
    return MetaOut(
        id=m.id, nombre=m.nombre, emoji=m.emoji, objetivo=m.objetivo, moneda=m.moneda,
        fecha_objetivo=m.fecha_objetivo, aporte_mensual=m.aporte_mensual, cuenta_id=m.cuenta_id,
        cuenta=cuenta.nombre if cuenta else None, **e.__dict__,
        aportes=[AporteOut(id=a.id, fecha=a.fecha, monto=a.monto, nota=a.nota) for a in reversed(m.aportes)] if con_aportes else [],
    )


def _cot(db: Session):
    return svc_cot.obtener(db) if svc.hay_en_dolares(db) else None


def _validar_cuenta(db: Session, cuenta_id, moneda) -> None:
    if cuenta_id:
        c = obtener(db, Cuenta, cuenta_id, "Cuenta")
        if c.moneda != moneda:
            raise HTTPException(422, f"La cuenta {c.nombre} es en {c.moneda.value} y la meta en {moneda.value}.")


@router.get("", response_model=list[MetaOut])
def listar(incluir_archivadas: bool = False, db: Session = Depends(get_db)):
    q = select(Meta).options(selectinload(Meta.aportes)).order_by(Meta.creado)
    if not incluir_archivadas:
        q = q.where(Meta.archivada.is_(False))
    cot, saldos = _cot(db), saldos_por_cuenta(db)
    return [_out(db, m, cot, saldos) for m in db.scalars(q)]


@router.get("/{mid}", response_model=MetaOut)
def detalle(mid: uuid.UUID, db: Session = Depends(get_db)):
    return _out(db, _cargar(db, mid), _cot(db), con_aportes=True)


@router.post("", response_model=MetaOut, status_code=201)
def crear(datos: MetaIn, db: Session = Depends(get_db)):
    _validar_cuenta(db, datos.cuenta_id, datos.moneda)
    if datos.fecha_objetivo and datos.fecha_objetivo < date.today():
        raise HTTPException(422, "La fecha de la meta ya pasó")
    m = Meta(**datos.model_dump(exclude={"ya_tengo"}))
    db.add(m)
    db.flush()
    if datos.ya_tengo and not datos.cuenta_id:
        db.add(AporteMeta(meta_id=m.id, fecha=date.today(), monto=datos.ya_tengo, nota="Lo que ya tenía"))
    db.commit()
    return _out(db, _cargar(db, m.id), _cot(db), con_aportes=True)


@router.patch("/{mid}", response_model=MetaOut)
def editar(mid: uuid.UUID, datos: MetaPatch, db: Session = Depends(get_db)):
    m = _cargar(db, mid)
    cambios = datos.model_dump(exclude_unset=True)
    if "cuenta_id" in cambios:
        _validar_cuenta(db, cambios["cuenta_id"], m.moneda)
    for k, v in cambios.items():
        if v is not None or k in ("fecha_objetivo", "aporte_mensual", "cuenta_id"):
            setattr(m, k, v)
    db.commit()
    return _out(db, _cargar(db, mid), _cot(db), con_aportes=True)


@router.delete("/{mid}", status_code=204)
def borrar(mid: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(_cargar(db, mid))
    db.commit()


@router.post("/{mid}/aportes", response_model=MetaOut, status_code=201)
def aportar(mid: uuid.UUID, datos: AporteIn, db: Session = Depends(get_db)):
    m = _cargar(db, mid)
    if m.cuenta_id:
        raise HTTPException(422, "Esta meta sigue el saldo de una cuenta: transferí a esa cuenta y se actualiza sola.")
    if datos.monto == 0:
        raise HTTPException(422, "El monto no puede ser cero")
    db.add(AporteMeta(meta_id=m.id, fecha=datos.fecha or date.today(), monto=datos.monto, nota=datos.nota))
    db.commit()
    db.expire_all()
    return _out(db, _cargar(db, mid), _cot(db), con_aportes=True)


@router.delete("/{mid}/aportes/{aid}", response_model=MetaOut)
def borrar_aporte(mid: uuid.UUID, aid: uuid.UUID, db: Session = Depends(get_db)):
    a = db.get(AporteMeta, aid)
    if a is None or a.meta_id != mid:
        raise HTTPException(404, "Aporte no encontrado")
    db.delete(a)
    db.commit()
    db.expire_all()
    return _out(db, _cargar(db, mid), _cot(db), con_aportes=True)
