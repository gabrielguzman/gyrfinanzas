"""Resumen del mes para el Inicio: en qué se fue la plata y a qué ritmo."""
import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Categoria, Deuda, EstadoMovimiento, Moneda, Movimiento, PlanCuotas, TipoDeuda, TipoMovimiento
from app.services.tarjetas import cuota_en, periodo
from app.schemas import CategoriaTotal, PuntoDiario, ResumenMes

router = APIRouter(prefix="/resumen", tags=["resumen"])
CERO = Decimal("0")


def _rango(anio: int, mes: int) -> tuple[date, date, int]:
    dias = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, dias), dias


@dataclass
class Gasto:
    """Un gasto del mes: un movimiento, o la cuota del mes de una compra en cuotas."""
    fecha: date
    monto: Decimal
    categoria: Categoria | None


def _cuotas_del_mes(db: Session, anio: int, mes: int) -> list[Gasto]:
    """Las cuotas que caen en el resumen de ese mes (se cuentan el día 1: son un cargo del mes)."""
    per = periodo(anio, mes)
    out = []
    for pl in db.scalars(select(PlanCuotas).where(PlanCuotas.moneda == Moneda.ARS)):
        if cuota_en(pl, per):
            mov = db.get(Movimiento, pl.movimiento_id) if pl.movimiento_id else None
            out.append(Gasto(date(anio, mes, 1), pl.monto_cuota, mov.categoria if mov else None))
    return out


def gastos_del_mes(db: Session, anio: int, mes: int) -> list[Gasto]:
    """Los gastos del mes como se cuentan en el resumen: sin préstamos a personas y con las
    compras en cuotas por su cuota del mes."""
    inicio, fin, _ = _rango(anio, mes)
    me_deben = set(db.scalars(select(Deuda.id).where(Deuda.tipo == TipoDeuda.me_deben)))
    movs = db.scalars(select(Movimiento).options(selectinload(Movimiento.categoria)).where(
        Movimiento.estado == EstadoMovimiento.confirmado, Movimiento.moneda == Moneda.ARS,
        Movimiento.tipo == TipoMovimiento.gasto, Movimiento.fecha.between(inicio, fin)))
    out = [Gasto(x.fecha, x.monto, x.categoria) for x in movs
           if (not x.deuda_id or x.deuda_id not in me_deben) and not (x.cuotas and x.cuotas > 1)]
    return out + _cuotas_del_mes(db, anio, mes)


def _acumulado(movs: list, dias: int, hasta: int) -> list[PuntoDiario]:
    por_dia: dict[int, Decimal] = defaultdict(lambda: CERO)
    for m in movs:
        por_dia[m.fecha.day] += m.monto
    total, puntos = CERO, []
    for d in range(1, min(hasta, dias) + 1):
        total += por_dia[d]
        puntos.append(PuntoDiario(dia=d, acumulado=total))
    return puntos


@router.get("", response_model=ResumenMes)
def resumen(mes: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"), db: Session = Depends(get_db)):
    hoy = date.today()
    anio, m = (int(x) for x in mes.split("-")) if mes else (hoy.year, hoy.month)
    if not 1 <= m <= 12:
        raise HTTPException(422, "Mes inválido")
    inicio, fin, dias = _rango(anio, m)
    anio_ant, mes_ant = (anio - 1, 12) if m == 1 else (anio, m - 1)
    inicio_ant, fin_ant, dias_ant = _rango(anio_ant, mes_ant)

    base = (
        select(Movimiento)
        .options(selectinload(Movimiento.categoria))
        .where(Movimiento.estado == EstadoMovimiento.confirmado, Movimiento.moneda == Moneda.ARS)
    )
    del_mes = db.scalars(base.where(Movimiento.fecha.between(inicio, fin))).all()
    del_anterior = db.scalars(base.where(
        Movimiento.fecha.between(inicio_ant, fin_ant), Movimiento.tipo == TipoMovimiento.gasto)).all()

    # Prestar plata o recibir un préstamo no es gastar ni ganar: se deja afuera.
    me_deben = set(db.scalars(select(Deuda.id).where(Deuda.tipo == TipoDeuda.me_deben)))
    cuenta = lambda x: not x.deuda_id or (x.tipo == TipoMovimiento.gasto and x.deuda_id not in me_deben)
    # Una compra en cuotas no es gasto del mes por el total: cuenta su cuota en cada mes.
    en_cuotas = lambda x: bool(x.cuotas and x.cuotas > 1)  # noqa: E731
    del_mes = [x for x in del_mes if cuenta(x)]
    del_anterior = [Gasto(x.fecha, x.monto, x.categoria) for x in del_anterior if cuenta(x) and not en_cuotas(x)]
    del_anterior += _cuotas_del_mes(db, anio_ant, mes_ant)
    gastos = [Gasto(x.fecha, x.monto, x.categoria) for x in del_mes if x.tipo == TipoMovimiento.gasto and not en_cuotas(x)]
    gastos += _cuotas_del_mes(db, anio, m)
    ingresos = sum((x.monto for x in del_mes if x.tipo == TipoMovimiento.ingreso), CERO)

    es_actual = (anio, m) == (hoy.year, hoy.month)
    dia_hoy = hoy.day if es_actual else None
    corte = dia_hoy or dias

    grupos: dict = {}
    for x in gastos:
        c = x.categoria
        clave = c.id if c else None
        g = grupos.setdefault(clave, {
            "categoria_id": clave, "nombre": c.nombre if c else "Sin categoría",
            "icono": (c.icono if c else "") or "otros", "color": (c.color if c else "") or "slate",
            "total": CERO, "cantidad": 0,
        })
        g["total"] += x.monto
        g["cantidad"] += 1
    por_categoria = sorted((CategoriaTotal(**g) for g in grupos.values()), key=lambda g: -g.total)

    anterior_a_la_fecha = sum((x.monto for x in del_anterior if x.fecha.day <= min(corte, dias_ant)), CERO)
    return ResumenMes(
        mes=f"{anio:04d}-{m:02d}", dias_mes=dias, dia_hoy=dia_hoy,
        gastos=sum((x.monto for x in gastos), CERO), ingresos=ingresos,
        gastos_anterior_a_la_fecha=anterior_a_la_fecha,
        gastos_anterior_total=sum((x.monto for x in del_anterior), CERO),
        por_categoria=por_categoria,
        diario=_acumulado(gastos, dias, corte),
        diario_anterior=_acumulado(list(del_anterior), dias_ant, dias_ant),
    )
