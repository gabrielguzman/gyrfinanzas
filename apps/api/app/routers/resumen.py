"""Resumen del mes para el Inicio: en qué se fue la plata y a qué ritmo."""
import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Deuda, EstadoMovimiento, Moneda, Movimiento, TipoDeuda, TipoMovimiento
from app.schemas import CategoriaTotal, PuntoDiario, ResumenMes

router = APIRouter(prefix="/resumen", tags=["resumen"])
CERO = Decimal("0")


def _rango(anio: int, mes: int) -> tuple[date, date, int]:
    dias = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, dias), dias


def _acumulado(movs: list[Movimiento], dias: int, hasta: int) -> list[PuntoDiario]:
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
    del_mes = [x for x in del_mes if cuenta(x)]
    del_anterior = [x for x in del_anterior if cuenta(x)]
    gastos = [x for x in del_mes if x.tipo == TipoMovimiento.gasto]
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
