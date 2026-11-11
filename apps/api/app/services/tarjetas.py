"""Tarjetas de crédito: periodos de resumen, planes de cuotas y compromisos."""
import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cuenta, Moneda, Movimiento, PlanCuotas, TipoCuenta

DIA_CIERRE_POR_DEFECTO = 25
CERO = Decimal("0")


# ---------- periodos ("YYYY-MM" del mes en que cierra el resumen) ----------
def periodo(anio: int, mes: int) -> str:
    return f"{anio:04d}-{mes:02d}"


def sumar_meses(p: str, n: int) -> str:
    a, m = map(int, p.split("-"))
    total = a * 12 + (m - 1) + n
    return periodo(total // 12, total % 12 + 1)


def distancia(desde: str, hasta: str) -> int:
    a1, m1 = map(int, desde.split("-"))
    a2, m2 = map(int, hasta.split("-"))
    return (a2 * 12 + m2) - (a1 * 12 + m1)


def dia_cierre(cuenta: Cuenta) -> int:
    return cuenta.dia_cierre or DIA_CIERRE_POR_DEFECTO


def periodo_de_compra(cuenta: Cuenta, fecha: date) -> str:
    """En qué resumen entra una compra hecha en esa fecha."""
    p = periodo(fecha.year, fecha.month)
    return p if fecha.day <= dia_cierre(cuenta) else sumar_meses(p, 1)


def proximo_periodo(cuenta: Cuenta, hoy: date | None = None) -> str:
    return periodo_de_compra(cuenta, hoy or date.today())


def mejor_dia_de_compra(cuenta: Cuenta, hoy: date | None = None) -> date:
    """El día siguiente al cierre: lo que compres ahí se paga casi dos meses después."""
    hoy = hoy or date.today()
    dc = dia_cierre(cuenta)
    anio, mes = hoy.year, hoy.month
    if hoy.day > dc:
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    ultimo = calendar.monthrange(anio, mes)[1]
    d = min(dc, ultimo) + 1
    if d > ultimo:
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        d = 1
    return date(anio, mes, d)


# ---------- planes ----------
def cuota_en(plan: PlanCuotas, p: str) -> int | None:
    k = distancia(plan.primer_periodo, p) + 1
    return k if 1 <= k <= plan.cuotas_total else None


def ultimo_periodo(plan: PlanCuotas) -> str:
    return sumar_meses(plan.primer_periodo, plan.cuotas_total - 1)


def plan_desde_movimiento(db: Session, mov: Movimiento) -> PlanCuotas | None:
    """Si el movimiento es una compra en cuotas con tarjeta, crea su plan (una sola vez)."""
    if not mov.cuotas or mov.cuotas < 2 or mov.cuenta_id is None:
        return None
    cuenta = db.get(Cuenta, mov.cuenta_id)
    if cuenta is None or cuenta.tipo != TipoCuenta.tarjeta_credito:
        return None
    db.flush()
    if db.scalar(select(PlanCuotas).where(PlanCuotas.movimiento_id == mov.id)):
        return None
    plan = PlanCuotas(
        cuenta_id=cuenta.id,
        descripcion=mov.descripcion.split(" (")[0],
        monto_cuota=(mov.monto / mov.cuotas).quantize(Decimal("0.01")),
        cuotas_total=mov.cuotas,
        primer_periodo=periodo_de_compra(cuenta, mov.fecha),
        moneda=mov.moneda,
        movimiento_id=mov.id,
    )
    db.add(plan)
    return plan


@dataclass
class Compromiso:
    periodo: str
    total: Decimal
    planes: int


def compromisos(planes: list[PlanCuotas], desde: str, meses: int = 6) -> list[Compromiso]:
    salida = []
    for i in range(meses):
        p = sumar_meses(desde, i)
        activos = [pl for pl in planes if pl.moneda == Moneda.ARS and cuota_en(pl, p)]
        salida.append(Compromiso(p, sum((pl.monto_cuota for pl in activos), CERO), len(activos)))
    return salida


def mayor_liberacion(planes: list[PlanCuotas], desde: str, meses: int = 6) -> tuple[str, Decimal, int] | None:
    """El mes (dentro de los próximos) en que más baja lo comprometido."""
    serie = compromisos(planes, desde, meses + 1)
    mejor = None
    for prev, act in zip(serie, serie[1:]):
        baja = prev.total - act.total
        if baja > 0 and (mejor is None or baja > mejor[1]):
            terminan = sum(1 for pl in planes if pl.moneda == Moneda.ARS and ultimo_periodo(pl) == prev.periodo)
            mejor = (act.periodo, baja, terminan)
    return mejor
