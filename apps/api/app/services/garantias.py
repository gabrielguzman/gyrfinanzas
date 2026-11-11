"""Garantías: cuánto les queda, reparaciones y alta desde un gasto."""
import calendar
import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Garantia, Movimiento

AVISO_DIAS = 30  # cuándo empieza a avisar
MESES_SI_NO_DICE = 12  # «con garantía» sin plazo: lo típico de fábrica


def mas_meses(d: date, n: int) -> date:
    total = d.year * 12 + (d.month - 1) + n
    a, m = divmod(total, 12)
    m += 1
    return date(a, m, min(d.day, calendar.monthrange(a, m)[1]))


def producto_de(mov: Movimiento) -> str:
    return re.sub(r"\s*\(\d+ cuotas\)$", "", mov.descripcion).strip() or "Compra"


@dataclass
class Estado:
    estado: str          # vigente | por_vencer | vencida | en_reparacion
    vence: date          # con los días en reparación ya sumados
    dias_restantes: int
    progreso: float      # 0 = recién comprado, 1 = vencida


def estado(g: Garantia, hoy: date | None = None) -> Estado:
    hoy = hoy or date.today()
    vence = g.vence
    if g.en_reparacion_desde:
        # Mientras está en el service, la garantía no corre.
        vence = date.fromordinal(vence.toordinal() + max(0, (hoy - g.en_reparacion_desde).days))
    dias = (vence - hoy).days
    total = max(1, (vence - g.fecha_compra).days)
    progreso = min(1.0, max(0.0, (hoy - g.fecha_compra).days / total))
    if g.en_reparacion_desde:
        e = "en_reparacion"
    elif dias < 0:
        e = "vencida"
    elif dias <= AVISO_DIAS:
        e = "por_vencer"
    else:
        e = "vigente"
    return Estado(e, vence, dias, round(progreso, 3))


def nueva(db: Session, *, producto: str, fecha_compra: date, meses: int | None = None, vence: date | None = None,
          comercio: str = "", serie: str = "", notas: str = "", movimiento: Movimiento | None = None,
          archivo_id=None) -> Garantia:
    meses = meses or MESES_SI_NO_DICE
    g = Garantia(
        producto=producto[:120], comercio=comercio[:120], serie=serie[:80], notas=notas[:400],
        fecha_compra=fecha_compra, meses=meses, vence=vence or mas_meses(fecha_compra, meses),
        movimiento_id=movimiento.id if movimiento else None, archivo_id=archivo_id,
    )
    db.add(g)
    db.flush()
    return g


def recalcular(g: Garantia) -> None:
    g.vence = date.fromordinal(mas_meses(g.fecha_compra, g.meses).toordinal() + g.dias_reparacion)


def enviar_a_reparar(g: Garantia, fecha: date) -> None:
    if not g.en_reparacion_desde:
        g.en_reparacion_desde = fecha


def volvio_de_reparar(g: Garantia, fecha: date) -> int:
    """Suma al vencimiento los días que estuvo en el service. Devuelve cuántos."""
    if not g.en_reparacion_desde:
        return 0
    dias = max(0, (fecha - g.en_reparacion_desde).days)
    g.dias_reparacion += dias
    g.vence = date.fromordinal(g.vence.toordinal() + dias)
    g.en_reparacion_desde = None
    return dias


def activas(db: Session) -> list[Garantia]:
    return list(db.scalars(select(Garantia).order_by(Garantia.vence)))
