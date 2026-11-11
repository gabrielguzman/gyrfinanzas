import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria, EstadoMovimiento, GastoFijo, MedioPago, Movimiento, OrigenMovimiento
from app.routers.util import obtener
from app.schemas import FijoDecision, FijoIn, FijoOut, FijoPatch, FijosOut, FijoSugerido
from app.services import fijos as svc

router = APIRouter(prefix="/fijos", tags=["fijos"])


def _out(db: Session, f: GastoFijo, hoy: date) -> FijoOut:
    mov = svc.del_mes(db, f, hoy)
    if mov is not None:
        este_mes = "pagado" if mov.estado == EstadoMovimiento.confirmado else "en_bandeja"
    else:
        este_mes = "por_venir"
    c = f.categoria
    return FijoOut(
        id=f.id, nombre=f.nombre, clave=f.clave, monto=f.monto, dia=f.dia, activo=f.activo,
        categoria_id=f.categoria_id, categoria=c.nombre if c else None,
        categoria_icono=c.icono if c else None, categoria_color=c.color if c else None,
        medio_pago_id=f.medio_pago_id, medio_pago=f.medio_pago.nombre if f.medio_pago else None,
        proxima=svc.proxima(f, hoy), este_mes=este_mes, movimiento_id=mov.id if mov else None,
    )


@router.get("", response_model=FijosOut)
def listar(db: Session = Depends(get_db)):
    hoy = date.today()
    svc.generar(db, hoy)
    fijos = [_out(db, f, hoy) for f in svc.todos(db)]
    activos = [f for f in fijos if f.activo]
    return FijosOut(
        fijos=fijos,
        sugeridos=[FijoSugerido(**s.__dict__) for s in svc.sugeridos(db, hoy)],
        total_mensual=sum((f.monto for f in activos), Decimal("0")),
        pagado_mes=sum((f.monto for f in activos if f.este_mes == "pagado"), Decimal("0")),
    )


def _validar(db: Session, categoria_id, medio_pago_id):
    if categoria_id:
        obtener(db, Categoria, categoria_id, "Categoría")
    if medio_pago_id:
        obtener(db, MedioPago, medio_pago_id, "Medio de pago")


@router.post("", response_model=FijoOut, status_code=201)
def crear(datos: FijoIn, db: Session = Depends(get_db)):
    _validar(db, datos.categoria_id, datos.medio_pago_id)
    f = svc.nuevo(db, **datos.model_dump())
    db.commit()
    svc.generar(db)
    return _out(db, f, date.today())


@router.post("/decidir", response_model=FijoOut)
def decidir(datos: FijoDecision, db: Session = Depends(get_db)):
    """Activa un fijo sugerido (o lo marca como «no es fijo»)."""
    f = svc.desde_detectado(db, datos.clave, datos.activo)
    db.commit()
    if f.activo:
        svc.generar(db)
    return _out(db, f, date.today())


@router.patch("/{fijo_id}", response_model=FijoOut)
def editar(fijo_id: uuid.UUID, datos: FijoPatch, db: Session = Depends(get_db)):
    f = obtener(db, GastoFijo, fijo_id, "Gasto fijo")
    cambios = datos.model_dump(exclude_unset=True)
    _validar(db, cambios.get("categoria_id"), cambios.get("medio_pago_id"))
    for k, v in cambios.items():
        setattr(f, k, v.strip() if k == "nombre" else v)
    db.commit()
    if f.activo:
        svc.generar(db)
    return _out(db, f, date.today())


@router.delete("/{fijo_id}", status_code=204)
def borrar(fijo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Deja de ser fijo. Los pagos ya cargados quedan; el generado sin confirmar se va."""
    f = obtener(db, GastoFijo, fijo_id, "Gasto fijo")
    for m in db.query(Movimiento).filter(Movimiento.fijo_id == f.id, Movimiento.estado == EstadoMovimiento.pendiente,
                                         Movimiento.origen == OrigenMovimiento.fijo):
        db.delete(m)
    # Queda como «no es fijo» para que no vuelva a sugerirse
    f.activo = False
    db.commit()


@router.post("/{fijo_id}/saltear", response_model=FijoOut)
def saltear(fijo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Este mes no va (vacaciones, lo pausaste): saca el generado y no lo vuelve a poner."""
    f = obtener(db, GastoFijo, fijo_id, "Gasto fijo")
    hoy = date.today()
    mov = svc.del_mes(db, f, hoy)
    if mov is not None and mov.estado == EstadoMovimiento.confirmado:
        raise HTTPException(409, "Este mes ya está pagado.")
    if mov is not None:
        db.delete(mov)
    f.ultimo_periodo = svc.periodo(hoy)
    db.commit()
    return _out(db, f, hoy)
