"""Metas de ahorro: cuánto llevás, cuánto falta, cuánto apartar por mes y si vas en camino."""
import math
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Cuenta, Meta
from app.services.cotizacion import Cotizacion, a_pesos
from app.services.garantias import mas_meses
from app.services.saldos import saldos_por_cuenta

CERO = Decimal("0")


def meses_entre(desde: date, hasta: date) -> int:
    """Meses que quedan para aportar (el mes en curso cuenta)."""
    m = (hasta.year - desde.year) * 12 + hasta.month - desde.month
    return max(1, m + (1 if hasta.day >= desde.day else 0))


@dataclass
class EstadoMeta:
    ahorrado: Decimal
    falta: Decimal
    progreso: float
    cumplida: bool
    por_mes: Decimal | None        # en la moneda de la meta
    por_mes_ars: Decimal | None    # para descontar en «Hoy podés gastar»
    meses_restantes: int | None
    fecha_estimada: date | None    # cuándo llegás al ritmo que te propusiste
    ritmo: Decimal | None          # lo que realmente pusiste por mes (últimos 3 meses)
    en_camino: bool | None


def _ahorrado(db: Session, m: Meta, hasta: date | None, saldos=None) -> Decimal:
    if m.cuenta_id:
        s = (saldos if saldos is not None and hasta is None else saldos_por_cuenta(db, hasta))
        return max(CERO, s.get(m.cuenta_id, CERO))
    return sum((a.monto for a in m.aportes if hasta is None or a.fecha <= hasta), CERO)


def estado(db: Session, m: Meta, hoy: date, cot: Cotizacion | None, saldos=None) -> EstadoMeta:
    ahorrado = _ahorrado(db, m, None, saldos)
    falta = max(CERO, m.objetivo - ahorrado)
    progreso = float(min(Decimal(1), ahorrado / m.objetivo)) if m.objetivo > 0 else 1.0
    cumplida = falta == 0
    por_mes = meses = fecha_est = None
    if not cumplida:
        if m.fecha_objetivo and m.fecha_objetivo >= hoy:
            meses = meses_entre(hoy, m.fecha_objetivo)
            por_mes = (falta / meses).quantize(Decimal("1"))
            fecha_est = m.fecha_objetivo
        elif m.aporte_mensual and m.aporte_mensual > 0:
            por_mes = m.aporte_mensual
            meses = math.ceil(falta / m.aporte_mensual)
            fecha_est = mas_meses(hoy, meses)
    # Ritmo real: lo que creció en los últimos 90 días (solo si la meta tiene al menos un mes)
    ritmo = en_camino = None
    creada = m.creado.date() if m.creado else hoy
    if (hoy - creada).days >= 30 or (m.aportes and (hoy - m.aportes[0].fecha).days >= 30):
        dias = min(90, max(30, (hoy - min([creada] + [a.fecha for a in m.aportes])).days))
        antes = _ahorrado(db, m, hoy - timedelta(days=dias))
        ritmo = ((ahorrado - antes) / Decimal(dias) * Decimal("30.4")).quantize(Decimal("1"))
        if por_mes:
            en_camino = ritmo >= por_mes * Decimal("0.8")
    por_mes_ars = a_pesos(por_mes, m.moneda.value, cot) if por_mes else None
    return EstadoMeta(ahorrado, falta, round(progreso, 4), cumplida, por_mes, por_mes_ars, meses, fecha_est, ritmo, en_camino)


def activas(db: Session) -> list[Meta]:
    return list(db.scalars(
        select(Meta).options(selectinload(Meta.aportes)).where(Meta.archivada.is_(False)).order_by(Meta.creado)))


def hay_en_dolares(db: Session) -> bool:
    if db.scalar(select(Meta.id).where(Meta.archivada.is_(False), Meta.moneda == "USD").limit(1)):
        return True
    return False


def cuenta_moneda_ok(db: Session, m: Meta) -> bool:
    if not m.cuenta_id:
        return True
    c = db.get(Cuenta, m.cuenta_id)
    return c is not None and c.moneda == m.moneda


# ───────────────────────── «aparté 50k para las vacaciones» ─────────────────────────
import re  # noqa: E402

RE_APORTE = re.compile(
    r"^\s*(?P<verbo>aparte|ahorre|guarde|puse|meti|sume|saque|retire)\s+(?P<monto>.+?)\s+"
    r"(?:para|en|a|de|del)\s+(?:la |el |las |los |mi |mis )?(?P<meta>.+?)\s*$"
)


def interpretar_aporte(db: Session, texto: str) -> tuple[Meta, Decimal] | None:
    from app.services.captura import _buscar_monto, _plano
    norm = _plano(texto).strip()
    m = RE_APORTE.match(norm)
    if not m:
        return None
    monto, _ = _buscar_monto(m.group("monto"))
    if not monto:
        return None
    buscado = m.group("meta").strip(" .!")
    # Solo si lo que escribiste empieza con el nombre de la meta (o al revés): «nafta en el auto» no es la meta «Auto»
    candidatas = [x for x in activas(db)
                  if buscado.startswith(_plano(x.nombre).strip()) or _plano(x.nombre).strip().startswith(buscado)]
    if len(candidatas) != 1:
        return None
    signo = -1 if m.group("verbo") in ("saque", "retire") else 1
    return candidatas[0], monto * signo
