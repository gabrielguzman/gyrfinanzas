"""Patrimonio neto: todo lo que tenés menos todo lo que debés, en pesos y en dólares.

Evolución: fotos diarias reales (se guarda una cada vez que lo mirás) y, para los meses
anteriores a la primera foto, una estimación con los saldos de las cuentas a fin de mes.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Cuenta,
    Deuda,
    EstadoMovimiento,
    FotoPatrimonio,
    Inversion,
    Moneda,
    Movimiento,
    TipoCuenta,
    TipoDeuda,
    TipoInversion,
    TipoMovimiento,
)
from app.services import deudas as svc_deudas
from app.services.cotizacion import Cotizacion, a_pesos
from app.services.saldos import saldos_por_cuenta

CERO = Decimal("0")
LIQUIDAS = {TipoInversion.fci, TipoInversion.cripto, TipoInversion.acciones, TipoInversion.bonos}


def valor_inversion(i: Inversion, hoy: date) -> Decimal:
    if i.valor_actual is not None:
        return i.valor_actual
    if i.tna and i.fecha_inicio:
        hasta = min(hoy, i.vence) if i.vence else hoy
        dias = max(0, (hasta - i.fecha_inicio).days)
        return (i.capital * (1 + i.tna / 100 * Decimal(dias) / 365)).quantize(Decimal("0.01"))
    return i.capital


@dataclass
class Item:
    grupo: str           # Pesos | Dólares | Inversiones | Te deben | Tarjetas | Préstamos | Le debés
    nombre: str
    moneda: str
    monto: Decimal       # en su moneda, siempre positivo
    ars: Decimal | None  # en pesos (None si es en dólares y no hay cotización)
    activo: bool
    ref: str             # a dónde ir para verlo


@dataclass
class Patrimonio:
    items: list[Item]
    activos: Decimal
    pasivos: Decimal
    neto: Decimal
    neto_usd: Decimal | None
    cotizacion: Cotizacion | None
    sin_convertir: bool
    liquido: Decimal
    gasto_esencial: Decimal
    gasto_mensual: Decimal
    meses_esencial: Decimal | None
    meses_total: Decimal | None
    serie: list[tuple[date, Decimal, bool]] = field(default_factory=list)  # fecha, neto, estimado


def _items(db: Session, hoy: date, cot: Cotizacion | None, saldos: dict) -> list[Item]:
    out: list[Item] = []
    for c in db.scalars(select(Cuenta).where(Cuenta.archivada.is_(False)).order_by(Cuenta.nombre)):
        s = saldos.get(c.id, CERO)
        mon = c.moneda.value
        if c.tipo == TipoCuenta.tarjeta_credito:
            if s < 0:
                out.append(Item("Tarjetas", c.nombre, mon, -s, a_pesos(-s, mon, cot), False, f"/tarjetas/{c.id}"))
        elif s != 0:
            out.append(Item("Pesos" if mon == "ARS" else "Dólares", c.nombre, mon, s, a_pesos(s, mon, cot), True, "/cuentas"))
    for i in db.scalars(select(Inversion).where(Inversion.cerrada.is_(False)).order_by(Inversion.nombre)):
        v = valor_inversion(i, hoy)
        out.append(Item("Inversiones", i.nombre, i.moneda.value, v, a_pesos(v, i.moneda.value, cot), True, "/patrimonio"))
    for d in db.scalars(select(Deuda).where(Deuda.cerrada.is_(False))):
        e = svc_deudas.estado(db, d, hoy)
        if e.saldo <= 0:
            continue
        mon = d.moneda.value
        if d.tipo == TipoDeuda.me_deben:
            out.append(Item("Te deben", d.nombre, mon, e.saldo, a_pesos(e.saldo, mon, cot), True, "/deudas"))
        else:
            grupo = "Préstamos" if d.tipo == TipoDeuda.prestamo else "Le debés"
            out.append(Item(grupo, d.nombre, mon, e.saldo, a_pesos(e.saldo, mon, cot), False, "/deudas"))
    return out


def deuda_tarjetas_corriente(db: Session, hoy: date, saldos: dict) -> Decimal:
    """Lo que debés en tarjetas sin las cuotas que vencen en resúmenes futuros (eso no sale ahora)."""
    from app.services import tarjetas as svc_t
    return sum((svc_t.deuda_corriente(db, c, saldos.get(c.id, CERO), hoy)[0]
                for c in db.scalars(select(Cuenta).where(Cuenta.tipo == TipoCuenta.tarjeta_credito,
                                                         Cuenta.archivada.is_(False), Cuenta.moneda == Moneda.ARS))), CERO)


def gasto_mensual_promedio(db: Session, hoy: date) -> Decimal:
    movs = db.scalars(select(Movimiento.monto).where(
        Movimiento.tipo == TipoMovimiento.gasto, Movimiento.estado == EstadoMovimiento.confirmado,
        Movimiento.moneda == Moneda.ARS, Movimiento.deuda_id.is_(None),
        (Movimiento.cuotas.is_(None)) | (Movimiento.cuotas <= 1),  # las compras en cuotas van por cuota
        Movimiento.fecha.between(hoy - timedelta(days=90), hoy)))
    return (sum(movs, CERO) / 90 * Decimal("30.4")).quantize(Decimal("1"))


def calcular(db: Session, hoy: date | None, cot: Cotizacion | None, guardar_foto: bool = True) -> Patrimonio:
    from app.services import plan as svc_plan  # evita import circular

    hoy = hoy or date.today()
    saldos = saldos_por_cuenta(db)
    items = _items(db, hoy, cot, saldos)
    activos = sum((i.ars for i in items if i.activo and i.ars is not None), CERO)
    pasivos = sum((i.ars for i in items if not i.activo and i.ars is not None), CERO)
    neto = activos - pasivos
    neto_usd = (neto / cot.valor).quantize(Decimal("1")) if cot and cot.valor else None

    # Fondo de emergencia: lo que podrías usar ya (cuentas + inversiones líquidas − tarjetas)
    liquidas = {i.nombre for i in db.scalars(select(Inversion).where(
        Inversion.cerrada.is_(False), Inversion.tipo.in_(LIQUIDAS)))}
    liquido = sum((i.ars or CERO for i in items if i.grupo in ("Pesos", "Dólares")
                   or (i.grupo == "Inversiones" and i.nombre in liquidas)), CERO)
    liquido -= deuda_tarjetas_corriente(db, hoy, saldos)
    p = svc_plan.calcular(db, hoy)
    esencial = p.fijos + p.cuotas_tarjetas + p.cuotas_prestamos
    mensual = gasto_mensual_promedio(db, hoy)
    meses_e = (liquido / esencial).quantize(Decimal("0.1")) if esencial > 0 else None
    meses_t = (liquido / mensual).quantize(Decimal("0.1")) if mensual > 0 else None

    pat = Patrimonio(items, activos, pasivos, neto, neto_usd, cot,
                     any(i.ars is None for i in items), liquido, esencial, mensual, meses_e, meses_t)

    if guardar_foto:
        foto = db.get(FotoPatrimonio, hoy)
        if foto is None:
            foto = FotoPatrimonio(fecha=hoy)
            db.add(foto)
        foto.neto_ars, foto.neto_usd, foto.cotizacion = neto, neto_usd, cot.valor if cot else None
        db.commit()
    pat.serie = serie(db, hoy, cot, neto, items)
    return pat


def serie(db: Session, hoy: date, cot: Cotizacion | None, neto_hoy: Decimal, items_hoy: list[Item], meses: int = 6):
    """Fin de cada uno de los últimos meses + hoy. Foto real si hay; si no, estimación."""
    fotos = {f.fecha: f for f in db.scalars(select(FotoPatrimonio).order_by(FotoPatrimonio.fecha))}
    # Lo que no son cuentas (inversiones, deudas) se toma como hoy: solo se estima con los saldos
    resto = sum((i.ars or CERO) * (1 if i.activo else -1) for i in items_hoy if i.grupo not in ("Pesos", "Dólares", "Tarjetas"))
    cuentas = {c.id: c for c in db.scalars(select(Cuenta).where(Cuenta.archivada.is_(False)))}
    # Solo se estima desde que tus cuentas están en la app: antes, el saldo inicial no dice nada
    creadas = [c.creado.date() for c in cuentas.values() if c.creado]
    desde = max(filter(None, [db.scalar(select(Movimiento.fecha).order_by(Movimiento.fecha).limit(1)),
                              min(creadas) if creadas else None]), default=None)
    puntos = []
    for k in range(meses, 0, -1):
        a, m = hoy.year, hoy.month - k + 1
        while m < 1:
            a, m = a - 1, m + 12
        fin = date(a, m, 1) - timedelta(days=1)
        del_mes = [f for f in fotos if f.year == fin.year and f.month == fin.month]
        if del_mes:
            f = fotos[max(del_mes)]
            puntos.append((fin, f.neto_ars, False))
            continue
        if desde is None or fin < desde:
            continue
        saldos = saldos_por_cuenta(db, fin)
        total = CERO
        for cid, c in cuentas.items():
            v = a_pesos(saldos.get(cid, CERO), c.moneda.value, cot) or CERO
            if c.tipo == TipoCuenta.tarjeta_credito:
                total += min(v, CERO)
            else:
                total += v
        puntos.append((fin, (total + resto).quantize(Decimal("1")), True))
    puntos.append((hoy, neto_hoy.quantize(Decimal("1")), False))
    return puntos
