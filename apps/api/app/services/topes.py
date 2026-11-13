"""Topes por categoría: cuánto querés gastar como mucho por mes en cada una."""
import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Categoria, TipoCategoria, TopeCategoria

CERO = Decimal("0")


@dataclass
class Estado:
    categoria: Categoria
    tope: Decimal | None
    gastado: Decimal
    proyeccion: Decimal          # a este ritmo, cómo cerrarías el mes
    promedio: Decimal            # lo que solés gastar (mediana de los 3 meses anteriores)
    estado: str                  # ok | cerca | pasado | sin_tope

    @property
    def porcentaje(self) -> int:
        return int(self.gastado / self.tope * 100) if self.tope else 0

    @property
    def queda(self) -> Decimal:
        return (self.tope - self.gastado) if self.tope else CERO


def _por_categoria(db: Session, anio: int, mes: int) -> dict:
    from app.routers.resumen import gastos_del_mes
    suma: dict = defaultdict(lambda: CERO)
    for g in gastos_del_mes(db, anio, mes):
        if g.categoria:
            suma[g.categoria.id] += g.monto
    return suma


def _mes_atras(anio: int, mes: int, k: int) -> tuple[int, int]:
    t = anio * 12 + (mes - 1) - k
    return t // 12, t % 12 + 1


def estados(db: Session, hoy: date | None = None, solo_con_tope: bool = False) -> list[Estado]:
    hoy = hoy or date.today()
    topes = {t.categoria_id: t.monto for t in db.scalars(select(TopeCategoria))}
    actual = _por_categoria(db, hoy.year, hoy.month)
    previos = [_por_categoria(db, *_mes_atras(hoy.year, hoy.month, k)) for k in (1, 2, 3)]
    dias = calendar.monthrange(hoy.year, hoy.month)[1]
    out = []
    for c in db.scalars(select(Categoria).where(Categoria.tipo == TipoCategoria.gasto).order_by(Categoria.nombre)):
        tope = topes.get(c.id)
        if solo_con_tope and tope is None:
            continue
        gastado = actual.get(c.id, CERO)
        prom = Decimal(str(median([p.get(c.id, CERO) for p in previos]))).quantize(Decimal("1"))
        proy = (gastado / hoy.day * dias).quantize(Decimal("1")) if hoy.day else gastado
        if tope is None:
            est = "sin_tope"
        elif gastado >= tope:
            est = "pasado"
        elif gastado >= tope * Decimal("0.8"):
            est = "cerca"
        else:
            est = "ok"
        out.append(Estado(c, tope, gastado, max(proy, gastado), prom, est))
    return out


def poner(db: Session, categoria_id, monto: Decimal | None) -> None:
    t = db.get(TopeCategoria, categoria_id)
    if not monto or monto <= 0:
        if t:
            db.delete(t)
        return
    if t is None:
        db.add(TopeCategoria(categoria_id=categoria_id, monto=monto))
    else:
        t.monto = monto


def sugerido(promedio: Decimal) -> Decimal | None:
    """Un tope razonable: lo que solés gastar, redondeado para arriba."""
    if promedio <= 0:
        return None
    paso = Decimal("5000") if promedio >= 50000 else Decimal("1000")
    return ((promedio / paso).to_integral_value(rounding="ROUND_CEILING")) * paso


