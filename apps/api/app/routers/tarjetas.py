import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import SessionLocal, get_db
from app.models import (
    AccionLinea,
    Archivo,
    Cuenta,
    EstadoResumen,
    Movimiento,
    PlanCuotas,
    ResumenTarjeta,
    RolAdjunto,
    TipoCuenta,
    TipoLinea,
)
from app.routers.util import obtener
from app.schemas import (
    CompromisoOut,
    LiberacionOut,
    LineaOut,
    LineaPatch,
    PlanIn,
    PlanOut,
    ResumenCorto,
    ResumenOut,
    ResumenPatch,
    TarjetaOut,
)
from app.services import archivos as svc_archivos
from app.services import conciliacion
from app.services import tarjetas as svc
from app.services.registro import vincular
from app.services.resumen_pdf import ErrorLectura, extraer
from app.services.saldos import saldos_por_cuenta

router = APIRouter(tags=["tarjetas"])
log = logging.getLogger("gyr.tarjetas")


def _tarjeta(db: Session, cuenta_id: uuid.UUID) -> Cuenta:
    c = obtener(db, Cuenta, cuenta_id, "Tarjeta")
    if c.tipo != TipoCuenta.tarjeta_credito:
        raise HTTPException(422, "Esa cuenta no es una tarjeta de crédito")
    return c


def _plan_out(p: PlanCuotas, prox: str) -> PlanOut:
    pagadas = svc.distancia(p.primer_periodo, prox)  # cuotas que ya cayeron antes del próximo resumen
    return PlanOut(
        id=p.id, cuenta_id=p.cuenta_id, descripcion=p.descripcion, monto_cuota=p.monto_cuota,
        cuotas_total=p.cuotas_total, primer_periodo=p.primer_periodo, moneda=p.moneda,
        cuota_actual=svc.cuota_en(p, prox), restantes=max(0, min(p.cuotas_total, p.cuotas_total - pagadas)),
        ultimo_periodo=svc.ultimo_periodo(p), movimiento_id=p.movimiento_id,
    )


def _interes_minimo(r: ResumenTarjeta) -> Decimal | None:
    """Interés aproximado de un mes si pagás el mínimo (TNA / 12 sobre lo que queda)."""
    if r.tna and r.total_ars and r.pago_minimo and r.total_ars > r.pago_minimo:
        return ((r.total_ars - r.pago_minimo) * r.tna / Decimal(1200)).quantize(Decimal("1"))
    return None


def _corto(r: ResumenTarjeta) -> ResumenCorto:
    return ResumenCorto(
        id=r.id, periodo=r.periodo, estado=r.estado.value, fecha_cierre=r.fecha_cierre,
        fecha_vencimiento=r.fecha_vencimiento, total_ars=r.total_ars, total_usd=r.total_usd,
        pago_minimo=r.pago_minimo, tna=r.tna, interes_si_minimo=_interes_minimo(r),
    )


def _tarjeta_out(db: Session, c: Cuenta, saldos: dict) -> TarjetaOut:
    prox = svc.proximo_periodo(c)
    planes = list(db.scalars(select(PlanCuotas).where(PlanCuotas.cuenta_id == c.id)))
    activos = [p for p in planes if svc.ultimo_periodo(p) >= prox]
    confirmados = select(ResumenTarjeta).where(ResumenTarjeta.cuenta_id == c.id)
    ultimo = db.scalar(
        confirmados.where(ResumenTarjeta.estado == EstadoResumen.confirmado)
        .order_by(ResumenTarjeta.periodo.desc(), ResumenTarjeta.creado.desc()).limit(1)
    )
    pendiente = db.scalar(
        confirmados.where(ResumenTarjeta.estado.in_([EstadoResumen.revision, EstadoResumen.procesando]))
        .order_by(ResumenTarjeta.creado.desc()).limit(1)
    )
    lib = svc.mayor_liberacion(activos, prox)
    return TarjetaOut(
        cuenta_id=c.id, nombre=c.nombre, deuda=max(-saldos.get(c.id, Decimal(0)), Decimal(0)),
        dia_cierre=c.dia_cierre, dia_vencimiento=c.dia_vencimiento, proximo_periodo=prox,
        mejor_dia_compra=svc.mejor_dia_de_compra(c),
        ultimo_resumen=_corto(ultimo) if ultimo else None,
        pendiente_revision=pendiente.id if pendiente else None,
        planes=sorted((_plan_out(p, prox) for p in activos), key=lambda p: (p.ultimo_periodo, p.descripcion)),
        compromisos=[CompromisoOut(periodo=x.periodo, total=x.total, planes=x.planes) for x in svc.compromisos(activos, prox)],
        liberacion=LiberacionOut(periodo=lib[0], monto=lib[1], planes_que_terminan=lib[2]) if lib else None,
    )


@router.get("/tarjetas", response_model=list[TarjetaOut])
def listar(db: Session = Depends(get_db)):
    saldos = saldos_por_cuenta(db)
    cuentas = db.scalars(select(Cuenta).where(
        Cuenta.tipo == TipoCuenta.tarjeta_credito, Cuenta.archivada.is_(False)).order_by(Cuenta.creado))
    return [_tarjeta_out(db, c, saldos) for c in cuentas]


@router.get("/tarjetas/{cuenta_id}", response_model=TarjetaOut)
def detalle(cuenta_id: uuid.UUID, db: Session = Depends(get_db)):
    return _tarjeta_out(db, _tarjeta(db, cuenta_id), saldos_por_cuenta(db))


# ---------- planes ----------
@router.post("/tarjetas/{cuenta_id}/planes", response_model=PlanOut, status_code=201)
def crear_plan(cuenta_id: uuid.UUID, datos: PlanIn, db: Session = Depends(get_db)):
    """Para cargar a mano un plan que ya venías pagando."""
    c = _tarjeta(db, cuenta_id)
    if datos.cuota_actual > datos.cuotas_total:
        raise HTTPException(422, "La cuota actual no puede ser mayor que el total")
    prox = svc.proximo_periodo(c)
    p = PlanCuotas(cuenta_id=c.id, descripcion=datos.descripcion, monto_cuota=datos.monto_cuota,
                   cuotas_total=datos.cuotas_total, moneda=datos.moneda,
                   primer_periodo=svc.sumar_meses(prox, -(datos.cuota_actual - 1)))
    db.add(p)
    db.commit()
    return _plan_out(p, prox)


@router.delete("/planes/{plan_id}", status_code=204)
def borrar_plan(plan_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(obtener(db, PlanCuotas, plan_id, "Plan"))
    db.commit()


# ---------- resúmenes ----------
def _procesar(resumen_id: uuid.UUID, contenido: bytes, bind=None) -> None:
    """Corre en segundo plano: lee el PDF y deja el resumen listo para revisar."""
    with (Session(bind=bind, expire_on_commit=False) if bind is not None else SessionLocal()) as db:
        r = db.get(ResumenTarjeta, resumen_id)
        if r is None:
            return
        try:
            conciliacion.cargar_extraccion(db, r, extraer(contenido))
            r.estado = EstadoResumen.revision
        except ErrorLectura as e:
            db.rollback()
            r = db.get(ResumenTarjeta, resumen_id)
            r.estado, r.error = EstadoResumen.error, str(e)
        except Exception:
            log.exception("Error leyendo resumen")
            db.rollback()
            r = db.get(ResumenTarjeta, resumen_id)
            r.estado, r.error = EstadoResumen.error, "Algo falló leyendo el PDF."
        db.commit()


def _cargar_resumen(db: Session, rid: uuid.UUID) -> ResumenTarjeta:
    db.expire_all()
    r = db.scalar(select(ResumenTarjeta)
                  .options(selectinload(ResumenTarjeta.lineas), selectinload(ResumenTarjeta.cuenta))
                  .where(ResumenTarjeta.id == rid))
    if r is None:
        raise HTTPException(404, "Resumen no encontrado")
    return r


def _out(db: Session, r: ResumenTarjeta) -> ResumenOut:
    ids = [l.movimiento_id for l in r.lineas if l.movimiento_id]
    movs = {m.id: m for m in db.scalars(select(Movimiento).where(Movimiento.id.in_(ids)))} if ids else {}
    return ResumenOut(
        **_corto(r).model_dump(), cuenta_id=r.cuenta_id, cuenta=r.cuenta.nombre, metodo=r.metodo, error=r.error,
        saldo_anterior=r.saldo_anterior, archivo_id=r.archivo_id,
        verificacion=conciliacion.verificar(r) if r.estado != EstadoResumen.procesando and r.lineas else None,
        lineas=[LineaOut(
            id=l.id, fecha=l.fecha, descripcion=l.descripcion, monto=l.monto, moneda=l.moneda, tipo=l.tipo.value,
            cuota_n=l.cuota_n, cuota_total=l.cuota_total, accion=l.accion.value, movimiento_id=l.movimiento_id,
            movimiento=(f"{movs[l.movimiento_id].descripcion} del {movs[l.movimiento_id].fecha:%d/%m}"
                        if l.movimiento_id in movs else None),
            plan_id=l.plan_id,
        ) for l in r.lineas],
    )


@router.post("/tarjetas/{cuenta_id}/resumenes", response_model=ResumenOut, status_code=201)
def subir_resumen(cuenta_id: uuid.UUID, tareas: BackgroundTasks, archivo: UploadFile = File(...),
                  db: Session = Depends(get_db)):
    c = _tarjeta(db, cuenta_id)
    if (archivo.content_type or "") != "application/pdf":
        raise HTTPException(415, "Subí el resumen en PDF, como lo descargás del banco.")
    guardado = svc_archivos.guardar(db, archivo)
    contenido = svc_archivos.ruta_absoluta(guardado).read_bytes()
    r = ResumenTarjeta(cuenta_id=c.id, archivo_id=guardado.id, estado=EstadoResumen.procesando)
    db.add(r)
    db.commit()
    tareas.add_task(_procesar, r.id, contenido, db.get_bind())
    return _out(db, _cargar_resumen(db, r.id))


@router.get("/resumenes/{rid}", response_model=ResumenOut)
def ver_resumen(rid: uuid.UUID, db: Session = Depends(get_db)):
    return _out(db, _cargar_resumen(db, rid))


@router.get("/tarjetas/{cuenta_id}/resumenes", response_model=list[ResumenCorto])
def resumenes_de(cuenta_id: uuid.UUID, db: Session = Depends(get_db)):
    _tarjeta(db, cuenta_id)
    rs = db.scalars(select(ResumenTarjeta).where(ResumenTarjeta.cuenta_id == cuenta_id)
                    .order_by(ResumenTarjeta.creado.desc()))
    return [_corto(r) for r in rs]


def _editable(r: ResumenTarjeta) -> None:
    if r.estado != EstadoResumen.revision:
        raise HTTPException(409, "Este resumen ya no se puede editar")


@router.patch("/resumenes/{rid}", response_model=ResumenOut)
def editar_resumen(rid: uuid.UUID, datos: ResumenPatch, db: Session = Depends(get_db)):
    r = _cargar_resumen(db, rid)
    _editable(r)
    for k, v in datos.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    if datos.fecha_cierre:
        r.periodo = None  # se recalcula al confirmar
    db.commit()
    return _out(db, _cargar_resumen(db, rid))


@router.patch("/resumenes/{rid}/lineas/{lid}", response_model=ResumenOut)
def editar_linea(rid: uuid.UUID, lid: uuid.UUID, datos: LineaPatch, db: Session = Depends(get_db)):
    r = _cargar_resumen(db, rid)
    _editable(r)
    l = next((x for x in r.lineas if x.id == lid), None)
    if l is None:
        raise HTTPException(404, "Línea no encontrada")
    try:
        if datos.tipo:
            l.tipo = TipoLinea(datos.tipo)
        if datos.moneda:
            l.moneda = datos.moneda
        if datos.accion:
            accion = AccionLinea(datos.accion)
            if accion == AccionLinea.vincular and not (l.movimiento_id or l.plan_id):
                raise HTTPException(422, "No hay nada cargado para vincular esta línea")
            l.accion = accion
    except ValueError:
        raise HTTPException(422, "Valor inválido")
    db.commit()
    return _out(db, _cargar_resumen(db, rid))


@router.post("/resumenes/{rid}/confirmar", response_model=ResumenOut)
def confirmar_resumen(rid: uuid.UUID, db: Session = Depends(get_db)):
    r = _cargar_resumen(db, rid)
    _editable(r)
    if not r.fecha_cierre:
        raise HTTPException(422, "Falta la fecha de cierre del resumen")
    p = svc.periodo(r.fecha_cierre.year, r.fecha_cierre.month)
    if db.scalar(select(ResumenTarjeta.id).where(
            ResumenTarjeta.cuenta_id == r.cuenta_id, ResumenTarjeta.periodo == p, ResumenTarjeta.id != r.id)):
        raise HTTPException(409, "Ya cargaste el resumen de ese mes para esta tarjeta")
    r.periodo = p
    conciliacion.confirmar(db, r)
    archivo = db.get(Archivo, r.archivo_id) if r.archivo_id else None
    if archivo:
        for l in r.lineas:
            if l.movimiento_id and l.accion != AccionLinea.ignorar:
                mov = db.get(Movimiento, l.movimiento_id)
                if mov:
                    vincular(db, mov, archivo, RolAdjunto.resumen)
    r.estado = EstadoResumen.confirmado
    db.commit()
    return _out(db, _cargar_resumen(db, rid))


@router.delete("/resumenes/{rid}", status_code=204)
def descartar(rid: uuid.UUID, db: Session = Depends(get_db)):
    r = _cargar_resumen(db, rid)
    if r.estado == EstadoResumen.confirmado:
        raise HTTPException(409, "Un resumen confirmado no se puede descartar")
    db.delete(r)
    db.commit()
