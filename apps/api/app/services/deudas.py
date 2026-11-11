"""Deudas: saldo al vuelo, próximas cuotas y simulador de estrategias de pago."""
import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Deuda, EstadoMovimiento, Movimiento, TipoDeuda, TipoMovimiento

CERO = Decimal("0")
CENT = Decimal("0.01")


def _q(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def tasa_mensual(d: Deuda) -> Decimal:
    return (d.tna or CERO) / Decimal(1200)


def efecto(d: Deuda, m: Movimiento) -> int:
    """+1 si el movimiento agranda la deuda, -1 si la achica."""
    if d.tipo == TipoDeuda.me_deben:
        return 1 if m.tipo == TipoMovimiento.gasto else -1   # le presté más / me devolvió
    return -1 if m.tipo == TipoMovimiento.gasto else 1       # pagué / me prestaron más


@dataclass
class Estado:
    saldo: Decimal
    pagado: Decimal
    intereses_pagados: Decimal
    pagos: int
    cuotas_pagadas: int | None
    cuotas_restantes: int | None
    proximo_vencimiento: date | None
    movimientos: list[Movimiento] = field(default_factory=list)


def movimientos_de(db: Session, d: Deuda) -> list[Movimiento]:
    return list(db.scalars(
        select(Movimiento)
        .where(Movimiento.deuda_id == d.id, Movimiento.estado == EstadoMovimiento.confirmado)
        .order_by(Movimiento.fecha, Movimiento.creado)
    ))


def _proximo_dia(dia: int | None, hoy: date) -> date | None:
    if not dia:
        return None
    anio, mes = hoy.year, hoy.month
    d = min(dia, calendar.monthrange(anio, mes)[1])
    if d < hoy.day:
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        d = min(dia, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, d)


def estado(db: Session, d: Deuda, hoy: date | None = None) -> Estado:
    hoy = hoy or date.today()
    movs = movimientos_de(db, d)
    saldo, pagado, intereses, pagos = d.monto_inicial, CERO, CERO, 0
    i = tasa_mensual(d) if d.tipo == TipoDeuda.prestamo else CERO
    for m in movs:
        if efecto(d, m) < 0:
            pagos += 1
            pagado += m.monto
            # Sistema francés: cada pago cubre primero el interés del mes
            interes = _q(saldo * i) if saldo > 0 else CERO
            intereses += min(interes, m.monto)
            saldo -= max(CERO, m.monto - interes)
        else:
            saldo += m.monto
    saldo = max(CERO, _q(saldo))

    cuotas_pagadas = cuotas_restantes = None
    if d.tipo == TipoDeuda.prestamo and d.cuotas_total:
        cuotas_pagadas = min(d.cuotas_total, d.cuotas_pagadas + pagos)
        cuotas_restantes = d.cuotas_total - cuotas_pagadas
        if cuotas_restantes == 0:
            saldo = CERO
    vence = _proximo_dia(d.dia_vencimiento, hoy) if saldo > 0 else None
    return Estado(saldo, pagado, intereses, pagos, cuotas_pagadas, cuotas_restantes, vence, movs)


def cuota_sugerida(d: Deuda, e: Estado) -> Decimal | None:
    if d.cuota:
        return min(d.cuota, e.saldo + _q(e.saldo * tasa_mensual(d))) if e.saldo > 0 else None
    return None


# ───────────────────────── simulador ─────────────────────────
@dataclass
class DeudaSim:
    id: str
    nombre: str
    saldo: Decimal
    tasa_mensual: Decimal       # nominal
    minimo: Decimal             # lo que pagás sí o sí cada mes
    tasa_real: Decimal | None = None  # si hay inflación esperada


@dataclass
class Resultado:
    estrategia: str
    meses: int | None           # None = no termina con estos pagos
    intereses: Decimal
    orden: list[str]            # ids en el orden en que se terminan
    fin_por_deuda: dict[str, int]
    serie: list[Decimal]        # saldo total al final de cada mes


def simular(deudas: list[DeudaSim], extra: Decimal, estrategia: str, max_meses: int = 360) -> Resultado:
    saldos = {d.id: d.saldo for d in deudas if d.saldo > 0}
    por_id = {d.id: d for d in deudas}
    presupuesto = sum((d.minimo for d in deudas if d.id in saldos), CERO) + extra
    intereses, fin, orden, serie = CERO, {}, [], []

    def prioridad(d: DeudaSim):
        if estrategia == "bola_de_nieve":
            return (saldos[d.id], -d.tasa_mensual)
        t = d.tasa_real if d.tasa_real is not None else d.tasa_mensual
        return (-t, saldos[d.id])

    mes = 0
    while saldos and mes < max_meses:
        mes += 1
        for k in saldos:
            interes = _q(saldos[k] * por_id[k].tasa_mensual)
            saldos[k] += interes
            intereses += interes
        disponible = presupuesto
        # 1) mínimos
        for k in list(saldos):
            pago = min(por_id[k].minimo, saldos[k], disponible)
            saldos[k] -= pago
            disponible -= pago
        # 2) el resto a la deuda prioritaria (y si se termina, a la siguiente)
        for d in sorted((por_id[k] for k in saldos), key=prioridad):
            if disponible <= 0:
                break
            pago = min(saldos[d.id], disponible)
            saldos[d.id] -= pago
            disponible -= pago
        for k in [k for k, v in saldos.items() if v <= Decimal("0.5")]:
            del saldos[k]
            fin[k] = mes
            orden.append(k)
        serie.append(_q(sum(saldos.values(), CERO)))
        # Si el saldo total no baja, con estos pagos no se termina nunca
        if len(serie) >= 13 and serie[-1] >= serie[-13] and serie[-1] > 0:
            return Resultado(estrategia, None, _q(intereses), orden, fin, serie)
    return Resultado(estrategia, mes if not saldos else None, _q(intereses), orden, fin, serie)
