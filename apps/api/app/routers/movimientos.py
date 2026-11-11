import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import (
    Archivo,
    Categoria,
    Cuenta,
    EstadoMovimiento,
    MedioPago,
    Movimiento,
    MovimientoAdjunto,
    RolAdjunto,
    TipoMovimiento,
)
from app.routers.util import obtener
from app.schemas import AdjuntoIn, AdjuntoOut, GarantiaMini, MovimientoIn, MovimientoOut, MovimientoPatch
from app.services import garantias as svc_garantias
from app.services import archivos as svc_archivos
from app.services.tarjetas import plan_desde_movimiento
from app.services.registro import borrar as borrar_mov, confirmar as confirmar_mov, sincronizar_plan, resolver, vincular as _vincular

router = APIRouter(prefix="/movimientos", tags=["movimientos"])

_CARGAS = (
    selectinload(Movimiento.categoria),
    selectinload(Movimiento.medio_pago),
    selectinload(Movimiento.cuenta),
    selectinload(Movimiento.cuenta_destino),
    selectinload(Movimiento.adjuntos).selectinload(MovimientoAdjunto.archivo),
    selectinload(Movimiento.garantias),
)


def serializar(m: Movimiento) -> MovimientoOut:
    adjuntos = [
        AdjuntoOut(archivo_id=a.archivo_id, nombre=a.archivo.nombre_original, mime=a.archivo.mime, rol=a.rol)
        for a in m.adjuntos
    ]
    g = m.garantias[0] if m.garantias else None
    ge = svc_garantias.estado(g) if g else None
    return MovimientoOut(
        garantia=GarantiaMini(id=g.id, vence=ge.vence, estado=ge.estado, dias_restantes=ge.dias_restantes) if g else None,
        id=m.id, tipo=m.tipo, estado=m.estado, origen=m.origen, fecha=m.fecha, monto=m.monto,
        moneda=m.moneda, descripcion=m.descripcion, texto_original=m.texto_original,
        categoria_id=m.categoria_id, categoria=m.categoria.nombre if m.categoria else None,
        categoria_icono=m.categoria.icono if m.categoria else None,
        categoria_color=m.categoria.color if m.categoria else None,
        medio_pago_id=m.medio_pago_id, medio_pago=m.medio_pago.nombre if m.medio_pago else None,
        cuenta_id=m.cuenta_id, cuenta=m.cuenta.nombre if m.cuenta else None,
        cuenta_destino_id=m.cuenta_destino_id,
        cuenta_destino=m.cuenta_destino.nombre if m.cuenta_destino else None,
        adjuntos=adjuntos, tiene_comprobante=bool(adjuntos), valio=m.valio, deuda_id=m.deuda_id, creado=m.creado,
        cuotas=m.cuotas,
    )


def _cargar(db: Session, mov_id: uuid.UUID) -> Movimiento:
    mov = db.scalar(select(Movimiento).options(*_CARGAS).where(Movimiento.id == mov_id))
    if mov is None:
        raise HTTPException(404, "Movimiento no encontrado")
    return mov


@router.get("", response_model=list[MovimientoOut])
def listar(
    estado: EstadoMovimiento | None = None,
    tipo: TipoMovimiento | None = None,
    cuenta_id: uuid.UUID | None = None,
    categoria_id: uuid.UUID | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    sin_comprobante: bool = False,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    consulta = select(Movimiento).options(*_CARGAS)
    if estado:
        consulta = consulta.where(Movimiento.estado == estado)
    if tipo:
        consulta = consulta.where(Movimiento.tipo == tipo)
    if cuenta_id:
        consulta = consulta.where((Movimiento.cuenta_id == cuenta_id) | (Movimiento.cuenta_destino_id == cuenta_id))
    if categoria_id:
        consulta = consulta.where(Movimiento.categoria_id == categoria_id)
    if desde:
        consulta = consulta.where(Movimiento.fecha >= desde)
    if hasta:
        consulta = consulta.where(Movimiento.fecha <= hasta)
    if sin_comprobante:
        consulta = consulta.where(
            Movimiento.tipo != TipoMovimiento.transferencia,
            ~exists().where(MovimientoAdjunto.movimiento_id == Movimiento.id),
        )
    if q:
        consulta = consulta.where(Movimiento.descripcion.ilike(f"%{q}%"))
    consulta = consulta.order_by(Movimiento.fecha.desc(), Movimiento.creado.desc()).limit(limit).offset(offset)
    return [serializar(m) for m in db.scalars(consulta)]


@router.post("", response_model=MovimientoOut, status_code=201)
def crear(datos: MovimientoIn, db: Session = Depends(get_db)):
    mov = Movimiento(**datos.model_dump())
    if mov.cuotas == 1:
        mov.cuotas = None
    resolver(db, mov, confirmar=mov.estado == EstadoMovimiento.confirmado)
    db.add(mov)
    if mov.estado == EstadoMovimiento.confirmado:
        plan_desde_movimiento(db, mov)  # compra en cuotas con tarjeta → su plan
    db.commit()
    return serializar(_cargar(db, mov.id))


@router.get("/{mov_id}", response_model=MovimientoOut)
def detalle(mov_id: uuid.UUID, db: Session = Depends(get_db)):
    return serializar(_cargar(db, mov_id))


@router.patch("/{mov_id}", response_model=MovimientoOut)
def editar(mov_id: uuid.UUID, datos: MovimientoPatch, db: Session = Depends(get_db)):
    mov = _cargar(db, mov_id)
    for k, v in datos.model_dump(exclude_unset=True).items():
        setattr(mov, k, v)
    if mov.cuotas == 1:
        mov.cuotas = None
    resolver(db, mov, confirmar=mov.estado == EstadoMovimiento.confirmado)
    sincronizar_plan(db, mov)
    db.commit()
    db.expire_all()
    return serializar(_cargar(db, mov_id))


@router.post("/{mov_id}/confirmar", response_model=MovimientoOut)
def confirmar(mov_id: uuid.UUID, db: Session = Depends(get_db)):
    mov = _cargar(db, mov_id)
    confirmar_mov(db, mov)
    db.commit()
    return serializar(mov)


@router.post("/{mov_id}/desconfirmar", response_model=MovimientoOut)
def desconfirmar(mov_id: uuid.UUID, db: Session = Depends(get_db)):
    """Vuelve un movimiento a la bandeja (para «Deshacer» después de confirmar)."""
    mov = _cargar(db, mov_id)
    mov.estado = EstadoMovimiento.pendiente
    db.commit()
    return serializar(mov)


@router.delete("/{mov_id}", status_code=204)
def borrar(mov_id: uuid.UUID, db: Session = Depends(get_db)):
    mov = obtener(db, Movimiento, mov_id, "Movimiento")
    borrar_mov(db, mov)
    db.commit()


# ---------- Comprobantes ----------
@router.post("/{mov_id}/adjuntos", response_model=MovimientoOut)
def vincular(mov_id: uuid.UUID, datos: AdjuntoIn, db: Session = Depends(get_db)):
    mov = _cargar(db, mov_id)
    archivo = obtener(db, Archivo, datos.archivo_id, "Archivo")
    _vincular(db, mov, archivo, datos.rol)
    db.commit()
    db.expire_all()
    return serializar(_cargar(db, mov_id))


@router.post("/{mov_id}/adjuntos/subir", response_model=MovimientoOut)
def subir_y_vincular(
    mov_id: uuid.UUID,
    archivo: UploadFile = File(...),
    rol: RolAdjunto = Form(RolAdjunto.ticket),
    db: Session = Depends(get_db),
):
    mov = _cargar(db, mov_id)
    guardado = svc_archivos.guardar(db, archivo)
    _vincular(db, mov, guardado, rol)
    db.commit()
    db.expire_all()
    return serializar(_cargar(db, mov_id))


@router.delete("/{mov_id}/adjuntos/{archivo_id}", response_model=MovimientoOut)
def desvincular(mov_id: uuid.UUID, archivo_id: uuid.UUID, db: Session = Depends(get_db)):
    vinculo = db.get(MovimientoAdjunto, (mov_id, archivo_id))
    if vinculo is None:
        raise HTTPException(404, "Ese comprobante no está vinculado a este movimiento")
    db.delete(vinculo)  # solo se borra el vínculo; el archivo se conserva
    db.commit()
    db.expire_all()
    return serializar(_cargar(db, mov_id))
