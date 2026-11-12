"""Plan: cuánto podés gastar hoy y cómo viene la plata en los próximos días.

Ciclo = de cobro a cobro.
  para gastar = lo que cobrás − fijos − cuotas de tarjeta − cuotas de préstamos − ahorro
  hoy podés   = (lo que queda + lo que ya gastaste hoy) / días que faltan − lo de hoy
Así el número de hoy no se mueve en el día salvo por lo que gastás, y lo que te
sobra hoy se reparte entre los días que quedan.

Gasto variable = todo gasto en pesos (confirmado o en la bandeja) que no sea fijo,
ni compra en cuotas (cuenta por cuota, al pagar el resumen), ni pago de deudas.
"""
import calendar
from collections import defaultdict
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Ajuste,
    Cuenta,
    Deuda,
    EstadoMovimiento,
    EstadoResumen,
    Moneda,
    Movimiento,
    PlanCuotas,
    ResumenTarjeta,
    TipoCuenta,
    TipoDeuda,
    TipoMovimiento,
)
from app.services import deudas as svc_deudas
from app.services import tarjetas as svc_t
from app.services.detectores import clave_desc, recurrentes
from app.services.saldos import saldos_por_cuenta

CERO = Decimal("0")
CLAVES = ("dia_cobro", "ingreso_mensual", "ahorro_mensual")


def _q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("1"))


def dia_en(anio: int, mes: int, dia: int) -> date:
    return date(anio, mes, min(dia, calendar.monthrange(anio, mes)[1]))


def _mes(anio: int, mes: int, n: int) -> tuple[int, int]:
    t = anio * 12 + mes - 1 + n
    return t // 12, t % 12 + 1


# ───────────────────────── ajustes ─────────────────────────
def ajustes(db: Session) -> dict[str, str]:
    return {a.clave: a.valor for a in db.scalars(select(Ajuste))}


def guardar_ajustes(db: Session, valores: dict[str, str | None]) -> None:
    for k, v in valores.items():
        if k not in CLAVES:
            continue
        a = db.get(Ajuste, k)
        if v in (None, ""):
            if a:
                db.delete(a)
        elif a:
            a.valor = str(v)
        else:
            db.add(Ajuste(clave=k, valor=str(v)))


# ───────────────────────── cobro y ciclo ─────────────────────────
@dataclass
class Cobro:
    dia: int | None
    monto: Decimal | None
    detectado: bool  # salió de tus ingresos (no lo configuraste)


def _ingresos(db: Session, desde: date, hasta: date) -> list[Movimiento]:
    return list(db.scalars(
        select(Movimiento).options(selectinload(Movimiento.categoria))
        .where(Movimiento.tipo == TipoMovimiento.ingreso, Movimiento.estado == EstadoMovimiento.confirmado,
               Movimiento.moneda == Moneda.ARS, Movimiento.deuda_id.is_(None),
               Movimiento.fecha.between(desde, hasta))
        .order_by(Movimiento.fecha)
    ))


def cobro(db: Session, hoy: date) -> Cobro:
    cfg = ajustes(db)
    dia = int(cfg["dia_cobro"]) if cfg.get("dia_cobro") else None
    monto = Decimal(cfg["ingreso_mensual"]) if cfg.get("ingreso_mensual") else None
    if dia and monto:
        return Cobro(dia, monto, False)
    # Detectar: el último sueldo (o el ingreso más grande) de los últimos ~3 meses
    ings = _ingresos(db, hoy - timedelta(days=100), hoy)
    sueldos = [m for m in ings if m.categoria and m.categoria.nombre == "Sueldo"] or (
        [max(ings, key=lambda m: m.monto)] if ings else [])
    if not sueldos:
        return Cobro(dia, monto, False)
    ult = sueldos[-1]
    return Cobro(dia or ult.fecha.day, monto or ult.monto, True)


def ciclo(dia: int, hoy: date) -> tuple[date, date, date]:
    """(desde, hasta, próximo cobro)."""
    este = dia_en(hoy.year, hoy.month, dia)
    if hoy >= este:
        desde, sig = este, dia_en(*_mes(hoy.year, hoy.month, 1), dia)
    else:
        desde, sig = dia_en(*_mes(hoy.year, hoy.month, -1), dia), este
    return desde, sig - timedelta(days=1), sig


# ───────────────────────── tarjetas ─────────────────────────
def vencimiento(c: Cuenta, p: str) -> date:
    """Cuándo se paga el resumen que cierra en el periodo p."""
    a, m = map(int, p.split("-"))
    cierre = dia_en(a, m, svc_t.dia_cierre(c))
    if not c.dia_vencimiento:
        return cierre + timedelta(days=10)
    v = dia_en(a, m, c.dia_vencimiento)
    return v if v > cierre else dia_en(*_mes(a, m, 1), c.dia_vencimiento)


def _tarjetas(db: Session) -> list[Cuenta]:
    return list(db.scalars(select(Cuenta).where(
        Cuenta.tipo == TipoCuenta.tarjeta_credito, Cuenta.archivada.is_(False), Cuenta.moneda == Moneda.ARS)))


def _planes(db: Session, c: Cuenta) -> list[PlanCuotas]:
    return list(db.scalars(select(PlanCuotas).where(PlanCuotas.cuenta_id == c.id)))


def cuotas_del_periodo(planes: list[PlanCuotas], p: str) -> Decimal:
    return sum((pl.monto_cuota for pl in planes if pl.moneda == Moneda.ARS and svc_t.cuota_en(pl, p)), CERO)


def resumen_estimado(db: Session, c: Cuenta, p: str, planes: list[PlanCuotas]) -> tuple[Decimal, bool]:
    """Lo que vas a pagar del resumen p: el total del PDF si lo cargaste; si no, lo que sumaste."""
    r = db.scalar(select(ResumenTarjeta).where(
        ResumenTarjeta.cuenta_id == c.id, ResumenTarjeta.periodo == p, ResumenTarjeta.estado == EstadoResumen.confirmado))
    if r and r.total_ars is not None:
        return r.total_ars, False
    a, m = map(int, p.split("-"))
    desde = dia_en(*_mes(a, m, -1), svc_t.dia_cierre(c)) + timedelta(days=1)
    hasta = dia_en(a, m, svc_t.dia_cierre(c))
    compras = db.scalars(select(Movimiento).where(
        Movimiento.cuenta_id == c.id, Movimiento.tipo == TipoMovimiento.gasto, Movimiento.moneda == Moneda.ARS,
        Movimiento.estado == EstadoMovimiento.confirmado, Movimiento.fecha.between(desde, hasta)))
    total = sum((m.monto for m in compras if not (m.cuotas and m.cuotas > 1)), CERO)
    return total + cuotas_del_periodo(planes, p), True


# ───────────────────────── hoy podés gastar ─────────────────────────
@dataclass
class Plan:
    configurado: bool
    cobro: Cobro
    ahorro: Decimal
    desde: date | None = None
    hasta: date | None = None
    proximo_cobro: date | None = None
    dias_restantes: int = 0
    dias_total: int = 0
    ingreso: Decimal = CERO
    fijos: Decimal = CERO
    cuotas_tarjetas: Decimal = CERO
    cuotas_prestamos: Decimal = CERO
    metas: Decimal = CERO             # lo que tus metas de ahorro piden por mes
    para_gastar: Decimal = CERO
    gastado: Decimal = CERO
    gastado_hoy: Decimal = CERO
    restante: Decimal = CERO
    por_dia: Decimal = CERO          # lo que te toca por día (hoy incluido)
    hoy: Decimal = CERO              # lo que te queda para hoy
    manana: Decimal | None = None    # si hoy no gastás más
    proyeccion_fin: Decimal | None = None  # a este ritmo, cuánto gastarías en el ciclo
    estado: str = "sin_datos"        # bien | justo | pasado | sin_datos
    detalle_fijos: list[tuple[str, Decimal]] = field(default_factory=list)
    detalle_cuotas: list[tuple[str, Decimal]] = field(default_factory=list)
    detalle_metas: list[tuple[str, Decimal]] = field(default_factory=list)


def _variables(db: Session, desde: date, hasta: date, fijas: set[str]) -> list[Movimiento]:
    movs = db.scalars(select(Movimiento).where(
        Movimiento.tipo == TipoMovimiento.gasto, Movimiento.moneda == Moneda.ARS,
        Movimiento.deuda_id.is_(None), Movimiento.fecha.between(desde, hasta)))
    return [m for m in movs if not (m.cuotas and m.cuotas > 1) and m.fijo_id is None and clave_desc(m.descripcion) not in fijas]


def calcular(db: Session, hoy: date | None = None) -> Plan:
    hoy = hoy or date.today()
    cb = cobro(db, hoy)
    cfg = ajustes(db)
    ahorro = Decimal(cfg["ahorro_mensual"]) if cfg.get("ahorro_mensual") else CERO
    plan = Plan(configurado=False, cobro=cb, ahorro=ahorro)
    if not cb.dia:
        return plan

    desde, hasta, sig = ciclo(cb.dia, hoy)
    rec = recurrentes(db, hoy)
    fijas = {r.clave for r in rec}
    plan.desde, plan.hasta, plan.proximo_cobro = desde, hasta, sig
    plan.dias_total = (hasta - desde).days + 1
    plan.dias_restantes = (hasta - hoy).days + 1

    real = sum((m.monto for m in _ingresos(db, desde, hasta)), CERO)
    plan.ingreso = max(cb.monto or CERO, real)
    plan.detalle_fijos = [(r.nombre if r.cada_meses == 1 else f"{r.nombre} (apartado)", r.ultimo) for r in rec]
    plan.fijos = sum((v for _, v in plan.detalle_fijos), CERO)

    # Cuotas de los resúmenes que vencen dentro del ciclo
    for c in _tarjetas(db):
        planes = _planes(db, c)
        p0 = svc_t.periodo(desde.year, desde.month)
        for k in range(-1, 3):
            p = svc_t.sumar_meses(p0, k)
            if desde <= vencimiento(c, p) <= hasta:
                v = cuotas_del_periodo(planes, p)
                if v > 0:
                    plan.detalle_cuotas.append((f"Cuotas {c.nombre}", v))
    for d in db.scalars(select(Deuda).where(Deuda.cerrada.is_(False), Deuda.tipo == TipoDeuda.prestamo)):
        cuota = svc_deudas.cuota_sugerida(d, svc_deudas.estado(db, d, hoy))
        if cuota:
            plan.detalle_cuotas.append((f"Cuota {d.nombre}", cuota))
    plan.cuotas_tarjetas = sum((v for n, v in plan.detalle_cuotas if n.startswith("Cuotas ")), CERO)
    plan.cuotas_prestamos = sum((v for n, v in plan.detalle_cuotas if n.startswith("Cuota ")), CERO)

    # Metas de ahorro: lo que cada una pide por mes
    from app.services import cotizacion as svc_cot, metas as svc_metas
    cot = svc_cot.obtener(db) if svc_metas.hay_en_dolares(db) else None
    for m in svc_metas.activas(db):
        e = svc_metas.estado(db, m, hoy, cot)
        if e.por_mes_ars:
            plan.detalle_metas.append((f"{m.emoji} {m.nombre}".strip(), e.por_mes_ars))
    plan.metas = sum((v for _, v in plan.detalle_metas), CERO)

    if plan.ingreso <= 0:
        return plan
    plan.configurado = True
    plan.para_gastar = plan.ingreso - plan.fijos - plan.cuotas_tarjetas - plan.cuotas_prestamos - plan.metas - ahorro

    vars_ = _variables(db, desde, hoy, fijas)
    plan.gastado = sum((m.monto for m in vars_), CERO)
    plan.gastado_hoy = sum((m.monto for m in vars_ if m.fecha == hoy), CERO)
    plan.restante = plan.para_gastar - plan.gastado
    plan.por_dia = _q((plan.restante + plan.gastado_hoy) / plan.dias_restantes)
    plan.hoy = plan.por_dia - plan.gastado_hoy
    if plan.dias_restantes > 1:
        plan.manana = _q(plan.restante / (plan.dias_restantes - 1))
    transcurridos = (hoy - desde).days + 1
    if transcurridos >= 3:
        plan.proyeccion_fin = _q(plan.gastado / transcurridos * plan.dias_total)

    normal = plan.para_gastar / plan.dias_total if plan.para_gastar > 0 else CERO
    if plan.restante < 0 or plan.para_gastar <= 0:
        plan.estado = "pasado"
    elif plan.por_dia < normal * Decimal("0.6"):
        plan.estado = "justo"
    else:
        plan.estado = "bien"
    plan.restante, plan.para_gastar = _q(plan.restante), _q(plan.para_gastar)
    plan.hoy = _q(plan.hoy)
    return plan


# ───────────────────────── calendario ─────────────────────────
@dataclass
class Evento:
    fecha: date
    tipo: str        # cobro | tarjeta | prestamo | fijo
    titulo: str
    monto: Decimal   # con signo: + entra, − sale
    estimado: bool = False


@dataclass
class Calendario:
    saldo_hoy: Decimal
    gasto_diario: Decimal
    eventos: list[Evento]
    serie: list[tuple[date, Decimal]]
    rojo: tuple[date, Decimal] | None   # primer día en negativo
    minimo: tuple[date, Decimal]


def calendario(db: Session, hoy: date | None = None, dias: int = 60) -> Calendario:
    hoy = hoy or date.today()
    fin = hoy + timedelta(days=dias)
    saldos = saldos_por_cuenta(db)
    liquido = sum((saldos.get(c.id, CERO) for c in db.scalars(select(Cuenta).where(
        Cuenta.archivada.is_(False), Cuenta.moneda == Moneda.ARS, Cuenta.tipo != TipoCuenta.tarjeta_credito))), CERO)
    plan = calcular(db, hoy)
    ev: list[Evento] = []

    # Cobros
    if plan.configurado and plan.cobro.dia:
        if sum((m.monto for m in _ingresos(db, plan.desde, hoy)), CERO) == 0 and (hoy - plan.desde).days <= 5:
            ev.append(Evento(hoy, "cobro", "Cobro de este mes (todavía no lo cargaste)", plan.cobro.monto or CERO, True))
        f = plan.proximo_cobro
        while f and f <= fin:
            ev.append(Evento(f, "cobro", "Cobro", plan.cobro.monto or plan.ingreso, plan.cobro.detectado))
            f = dia_en(*_mes(f.year, f.month, 1), plan.cobro.dia)

    # Resúmenes de tarjeta
    for c in _tarjetas(db):
        planes = _planes(db, c)
        deuda = max(-saldos.get(c.id, CERO), CERO)
        abierto = svc_t.proximo_periodo(c, hoy)
        p = svc_t.sumar_meses(abierto, -2)
        while True:
            v = vencimiento(c, p)
            if v > fin:
                break
            if v >= hoy:
                if svc_t.distancia(p, abierto) >= 0:  # ya tiene compras (cerrado o abierto)
                    monto, estimado = resumen_estimado(db, c, p, planes)
                    if p != abierto:
                        monto = min(monto, deuda)  # si ya pagaste, no hay nada que pagar
                else:
                    monto, estimado = cuotas_del_periodo(planes, p), True
                if monto > 0:
                    ev.append(Evento(v, "tarjeta", f"Resumen {c.nombre}", -monto, estimado))
            p = svc_t.sumar_meses(p, 1)

    # Cuotas de préstamos
    for d in db.scalars(select(Deuda).where(Deuda.cerrada.is_(False), Deuda.tipo == TipoDeuda.prestamo)):
        e = svc_deudas.estado(db, d, hoy)
        cuota = svc_deudas.cuota_sugerida(d, e)
        if not (cuota and e.proximo_vencimiento):
            continue
        f, quedan = e.proximo_vencimiento, e.cuotas_restantes if e.cuotas_restantes is not None else 999
        # Si ya pagaste la cuota de este mes, la próxima es la del mes que viene
        if any(svc_deudas.efecto(d, m) < 0 and (f - m.fecha).days <= 25 for m in e.movimientos):
            f = dia_en(*_mes(f.year, f.month, 1), d.dia_vencimiento or f.day)
        while f <= fin and quedan > 0:
            ev.append(Evento(f, "prestamo", f"Cuota {d.nombre}", -cuota))
            f, quedan = dia_en(*_mes(f.year, f.month, 1), d.dia_vencimiento or f.day), quedan - 1

    # Fijos (alquiler, servicios, suscripciones): un mes después del último pago
    from app.models import GastoFijo
    from app.services import fijos as svc_fijos
    for r in recurrentes(db, hoy):
        if r.cada_meses > 1 and r.fijo_id:
            f = db.get(GastoFijo, uuid.UUID(r.fijo_id))
            for d in svc_fijos.ocurrencias(f, hoy, fin):
                if d > hoy or f.ultimo_periodo != svc_fijos.periodo(hoy):
                    ev.append(Evento(d, "fijo", f.nombre, -f.monto, True))
            continue
        if not r.ultima:
            continue
        f = dia_en(*_mes(r.ultima.year, r.ultima.month, 1), r.ultima.day)
        while f <= fin:
            ev.append(Evento(max(f, hoy), "fijo", r.nombre, -r.ultimo, True))
            f = dia_en(*_mes(f.year, f.month, 1), r.ultima.day)

    ev.sort(key=lambda e: (e.fecha, e.monto < 0))

    # Gasto del día a día: el que te propone el plan; sin plan, tu promedio del último mes
    if plan.configurado:
        diario = max(plan.por_dia, CERO)
        diario_sig = max(_q(plan.para_gastar / plan.dias_total), CERO)
    else:
        movs = _variables(db, hoy - timedelta(days=30), hoy, {r.clave for r in recurrentes(db, hoy)})
        diario = diario_sig = _q(sum((m.monto for m in movs), CERO) / 30)

    por_dia: dict[date, Decimal] = defaultdict(lambda: CERO)
    for e in ev:
        por_dia[e.fecha] += e.monto
    serie, saldo = [], liquido
    rojo, minimo = None, (hoy, liquido)
    for i in range(dias + 1):
        f = hoy + timedelta(days=i)
        gasto = max(plan.hoy, CERO) if (i == 0 and plan.configurado) else (
            diario if (not plan.hasta or f <= plan.hasta) else diario_sig)
        saldo += por_dia[f] - gasto
        serie.append((f, _q(saldo)))
        if saldo < minimo[1]:
            minimo = (f, _q(saldo))
        if rojo is None and saldo < 0:
            rojo = (f, _q(saldo))
    return Calendario(_q(liquido), diario, ev, serie, rojo, minimo)


# ───────────────────────── próximos meses ─────────────────────────
@dataclass
class Mes:
    desde: date
    hasta: date
    para_gastar: Decimal | None   # None si no sabemos cuánto cobrás
    cuotas_tarjetas: Decimal
    cuotas_prestamos: Decimal


def meses(db: Session, hoy: date | None = None, n: int = 6) -> list[Mes]:
    """Lo que te queda para gastar en cada uno de los próximos ciclos (fijos, metas y ahorro como hoy)."""
    hoy = hoy or date.today()
    p = calcular(db, hoy)
    if p.desde:
        desde0, dia = p.desde, p.cobro.dia
    else:  # sin cobro: meses calendario
        desde0, dia = hoy.replace(day=1), 1
    tarjetas = [(c, _planes(db, c)) for c in _tarjetas(db)]
    prestamos = []
    for d in db.scalars(select(Deuda).where(Deuda.cerrada.is_(False), Deuda.tipo == TipoDeuda.prestamo)):
        e = svc_deudas.estado(db, d, hoy)
        cuota = svc_deudas.cuota_sugerida(d, e)
        if cuota:
            prestamos.append((cuota, e.cuotas_restantes if e.cuotas_restantes is not None else 10_000))
    out = []
    for k in range(n):
        desde = dia_en(*_mes(desde0.year, desde0.month, k), dia)
        hasta = dia_en(*_mes(desde0.year, desde0.month, k + 1), dia) - timedelta(days=1)
        ct = CERO
        for c, planes in tarjetas:
            p0 = svc_t.periodo(desde.year, desde.month)
            for j in range(-1, 3):
                per = svc_t.sumar_meses(p0, j)
                if desde <= vencimiento(c, per) <= hasta:
                    ct += cuotas_del_periodo(planes, per)
        cp = sum((cuota for cuota, quedan in prestamos if k < quedan), CERO)
        para = None
        if p.configurado:
            ingreso = p.ingreso if k == 0 else (p.cobro.monto or p.ingreso)
            para = _q(ingreso - p.fijos - ct - cp - p.metas - p.ahorro)
        out.append(Mes(desde, hasta, para, ct, cp))
    return out
