import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    Categoria,
    Cuenta,
    Deuda,
    EstadoMovimiento,
    Indexacion,
    MedioPago,
    Moneda,
    Movimiento,
    OrigenMovimiento,
    ResumenTarjeta,
    TipoCuenta,
    TipoDeuda,
    TipoMovimiento,
    EstadoResumen,
)
from app.routers.movimientos import _cargar, serializar
from app.routers.util import obtener
from app.schemas import (
    DeudaDetalle,
    DeudaIn,
    DeudaMovimientoIn,
    DeudaOut,
    DeudaPatch,
    DeudaSimOut,
    EstrategiaOut,
    PasoOut,
    SimularIn,
    SimularOut,
)
from app.services import deudas as svc
from app.services.registro import confirmar
from app.services.saldos import saldos_por_cuenta
from app.services.tarjetas import sumar_meses

router = APIRouter(prefix="/deudas", tags=["deudas"])
CERO = Decimal("0")


def _out(db: Session, d: Deuda, con_movs: bool = False):
    e = svc.estado(db, d)
    datos = dict(
        id=d.id, tipo=d.tipo.value, nombre=d.nombre, moneda=d.moneda, monto_inicial=d.monto_inicial,
        fecha_alta=d.fecha_alta, tna=d.tna, indexacion=d.indexacion.value, cuota=d.cuota,
        cuotas_total=d.cuotas_total, dia_vencimiento=d.dia_vencimiento, cuenta_id=d.cuenta_id,
        cerrada=d.cerrada, notas=d.notas, saldo=e.saldo, pagado=e.pagado, intereses_pagados=e.intereses_pagados,
        pagos=e.pagos, cuotas_pagadas=e.cuotas_pagadas, cuotas_restantes=e.cuotas_restantes,
        proximo_vencimiento=e.proximo_vencimiento, cuota_sugerida=svc.cuota_sugerida(d, e),
    )
    if con_movs:
        movs = [serializar(_cargar(db, m.id)) for m in reversed(e.movimientos)]
        return DeudaDetalle(**datos, movimientos=movs)
    return DeudaOut(**datos)


@router.get("", response_model=list[DeudaOut])
def listar(incluir_cerradas: bool = False, db: Session = Depends(get_db)):
    q = select(Deuda).order_by(Deuda.creado)
    if not incluir_cerradas:
        q = q.where(Deuda.cerrada.is_(False))
    return [_out(db, d) for d in db.scalars(q)]


@router.post("", response_model=DeudaOut, status_code=201)
def crear(datos: DeudaIn, db: Session = Depends(get_db)):
    if datos.cuenta_id:
        obtener(db, Cuenta, datos.cuenta_id, "Cuenta")
    d = Deuda(**{**datos.model_dump(), "tipo": TipoDeuda(datos.tipo), "indexacion": Indexacion(datos.indexacion),
                 "fecha_alta": datos.fecha_alta or date.today()})
    if d.tipo == TipoDeuda.prestamo and d.cuotas_total and d.cuotas_pagadas > d.cuotas_total:
        raise HTTPException(422, "Las cuotas pagadas no pueden superar el total")
    db.add(d)
    db.commit()
    return _out(db, d)


@router.get("/{deuda_id}", response_model=DeudaDetalle)
def detalle(deuda_id: uuid.UUID, db: Session = Depends(get_db)):
    return _out(db, obtener(db, Deuda, deuda_id, "Deuda"), con_movs=True)


@router.patch("/{deuda_id}", response_model=DeudaOut)
def editar(deuda_id: uuid.UUID, datos: DeudaPatch, db: Session = Depends(get_db)):
    d = obtener(db, Deuda, deuda_id, "Deuda")
    cambios = datos.model_dump(exclude_unset=True)
    if "indexacion" in cambios:
        cambios["indexacion"] = Indexacion(cambios["indexacion"])
    for k, v in cambios.items():
        setattr(d, k, v)
    db.commit()
    return _out(db, d)


@router.delete("/{deuda_id}", status_code=204)
def borrar(deuda_id: uuid.UUID, db: Session = Depends(get_db)):
    d = obtener(db, Deuda, deuda_id, "Deuda")
    if db.scalar(select(Movimiento.id).where(Movimiento.deuda_id == d.id).limit(1)):
        raise HTTPException(409, "Tiene pagos registrados: en vez de borrarla, marcala como cerrada.")
    db.delete(d)
    db.commit()


def _categoria_deudas(db: Session) -> Categoria | None:
    return db.scalar(select(Categoria).where(Categoria.nombre == "Deudas y préstamos"))


@router.post("/{deuda_id}/movimientos", response_model=DeudaDetalle, status_code=201)
def registrar(deuda_id: uuid.UUID, datos: DeudaMovimientoIn, db: Session = Depends(get_db)):
    d = obtener(db, Deuda, deuda_id, "Deuda")
    e = svc.estado(db, d)
    monto = datos.monto
    if monto is None and datos.accion == "pago":
        monto = svc.cuota_sugerida(d, e) or (e.saldo if e.saldo > 0 else None)
    if not monto:
        raise HTTPException(422, "Falta el monto")

    medio = db.get(MedioPago, datos.medio_pago_id) if datos.medio_pago_id else None
    if datos.medio_pago_id and medio is None:
        raise HTTPException(404, "Medio de pago no encontrado")
    cuenta_id = medio.cuenta_id if medio else d.cuenta_id
    if cuenta_id is None:
        raise HTTPException(422, "Elegí de qué cuenta sale o entra la plata.")

    cobra = d.tipo == TipoDeuda.me_deben
    if datos.accion == "pago":
        tipo = TipoMovimiento.ingreso if cobra else TipoMovimiento.gasto
        if d.tipo == TipoDeuda.prestamo:
            n = (e.cuotas_pagadas or 0) + 1
            desc = f"Cuota {n}/{d.cuotas_total} {d.nombre}" if d.cuotas_total else f"Pago {d.nombre}"
        else:
            desc = f"{d.nombre} me devolvió" if cobra else f"Devolución a {d.nombre}"
    else:
        tipo = TipoMovimiento.gasto if cobra else TipoMovimiento.ingreso
        desc = f"Préstamo a {d.nombre}" if cobra else f"{d.nombre} me prestó"

    cat = _categoria_deudas(db) if (tipo == TipoMovimiento.gasto and not cobra) else None
    mov = Movimiento(
        tipo=tipo, estado=EstadoMovimiento.pendiente, origen=OrigenMovimiento.manual,
        fecha=datos.fecha or date.today(), monto=monto, moneda=d.moneda, descripcion=desc[:200],
        medio_pago_id=medio.id if medio else None, cuenta_id=cuenta_id, deuda_id=d.id,
        categoria_id=cat.id if cat else None,
    )
    db.add(mov)
    db.flush()
    confirmar(db, mov)
    db.flush()
    d.cerrada = svc.estado(db, d).saldo <= 0 and datos.accion == "pago"
    db.commit()
    return _out(db, d, con_movs=True)


# ---------- simulador ----------
def _fecha_mes(n: int) -> date:
    hoy = date.today()
    a, m = map(int, sumar_meses(f"{hoy.year:04d}-{hoy.month:02d}", n).split("-"))
    return date(a, m, 1)


def _real(tasa_mensual: Decimal, inflacion: Decimal | None, uva: bool) -> Decimal | None:
    if inflacion is None:
        return None
    if uva:  # la TNA de un UVA ya es por encima de la inflación
        return tasa_mensual
    pi = inflacion / 100
    return (1 + tasa_mensual) / (1 + pi) - 1


@router.post("/simular", response_model=SimularOut)
def simular(datos: SimularIn, db: Session = Depends(get_db)):
    sims: list[svc.DeudaSim] = []
    tipos: dict[str, str] = {}
    for d in db.scalars(select(Deuda).where(Deuda.cerrada.is_(False), Deuda.tipo != TipoDeuda.me_deben,
                                            Deuda.moneda == Moneda.ARS)):
        e = svc.estado(db, d)
        if e.saldo <= 0:
            continue
        i = svc.tasa_mensual(d)
        minimo = d.cuota or CERO
        sims.append(svc.DeudaSim(str(d.id), d.nombre, e.saldo, i, minimo,
                                 _real(i, datos.inflacion_mensual, d.indexacion == Indexacion.uva)))
        tipos[str(d.id)] = d.tipo.value
    saldos = saldos_por_cuenta(db)
    for tid in datos.tarjetas:
        c = db.get(Cuenta, tid)
        if c is None or c.tipo != TipoCuenta.tarjeta_credito:
            continue
        deuda = max(-saldos.get(c.id, CERO), CERO)
        if deuda <= 0:
            continue
        r = db.scalar(select(ResumenTarjeta).where(
            ResumenTarjeta.cuenta_id == c.id, ResumenTarjeta.estado == EstadoResumen.confirmado)
            .order_by(ResumenTarjeta.periodo.desc()).limit(1))
        i = (r.tna if r and r.tna else CERO) / Decimal(1200)
        minimo = r.pago_minimo if r and r.pago_minimo else (deuda * Decimal("0.05")).quantize(Decimal("1"))
        sims.append(svc.DeudaSim(str(c.id), c.nombre, deuda, i, minimo, _real(i, datos.inflacion_mensual, False)))
        tipos[str(c.id)] = "tarjeta"

    nombres = {s.id: s.nombre for s in sims}

    def salida(res: svc.Resultado) -> EstrategiaOut:
        return EstrategiaOut(
            estrategia=res.estrategia, meses=res.meses,
            fecha_fin=_fecha_mes(res.meses) if res.meses else None, intereses=res.intereses,
            orden=[PasoOut(id=k, nombre=nombres[k], mes=res.fin_por_deuda[k], fecha=_fecha_mes(res.fin_por_deuda[k]))
                   for k in res.orden],
            serie=res.serie,
        )

    return SimularOut(
        deudas=[DeudaSimOut(id=s.id, nombre=s.nombre, tipo=tipos[s.id], saldo=s.saldo,
                            tasa_anual=(s.tasa_mensual * 1200).quantize(Decimal("0.01")),
                            tasa_real_anual=None if s.tasa_real is None else (s.tasa_real * 1200).quantize(Decimal("0.01")),
                            minimo=s.minimo) for s in sims],
        presupuesto_mensual=sum((s.minimo for s in sims), CERO) + datos.extra_mensual,
        avalancha=salida(svc.simular(sims, datos.extra_mensual, "avalancha")),
        bola_de_nieve=salida(svc.simular(sims, datos.extra_mensual, "bola_de_nieve")),
    )
