"""Etiquetas: agrupan gastos de distintas categorías bajo un nombre (#vacaciones2027, #mudanza).

Se ponen escribiendo «#algo» al cargar, a mano en el movimiento, o con una etiqueta activa
(«modo viaje»): mientras está prendida, todo lo que cargás la lleva.
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Ajuste, EstadoMovimiento, Etiqueta, Moneda, Movimiento, MovimientoEtiqueta, TipoMovimiento
from app.services.captura import normalizar

RE_ETIQUETA = re.compile(r"(?<![\w#])#([^\s#,;.!?]{1,40})")
CERO = Decimal("0")


def limpiar(nombre: str) -> str:
    n = normalizar(nombre.strip().lstrip("#"))
    n = re.sub(r"\s+", "-", n)
    return re.sub(r"[^a-z0-9_-]", "", n)[:40]


def extraer(texto: str) -> tuple[str, list[str], list[tuple[int, int]]]:
    """Saca los «#algo» del texto: devuelve el texto con espacios en su lugar (mismas
    posiciones, para resaltar), las etiquetas y dónde estaban."""
    tags, spans = [], []
    for m in RE_ETIQUETA.finditer(texto):
        t = limpiar(m.group(1))
        if t and t not in tags:
            tags.append(t)
        spans.append(m.span())
    limpio = texto
    for a, b in spans:
        limpio = limpio[:a] + " " * (b - a) + limpio[b:]
    return limpio, tags, spans


def obtener(db: Session, nombre: str) -> Etiqueta | None:
    n = limpiar(nombre)
    if not n:
        return None
    e = db.scalar(select(Etiqueta).where(Etiqueta.nombre == n))
    if e is None:
        e = Etiqueta(nombre=n)
        db.add(e)
        db.flush()
    return e


def asignar(db: Session, mov: Movimiento, nombres: list[str]) -> None:
    """Deja el movimiento con exactamente estas etiquetas."""
    nuevas = [e for e in (obtener(db, n) for n in nombres) if e]
    mov.etiquetas = list({e.id: e for e in nuevas}.values())


def agregar(db: Session, mov: Movimiento, nombres: list[str]) -> None:
    actuales = [e.nombre for e in mov.etiquetas]
    asignar(db, mov, actuales + [n for n in nombres if limpiar(n) not in actuales])


# ───────────────────────── etiqueta activa ─────────────────────────
CLAVE_ACTIVA = "etiqueta_activa"


def activa(db: Session) -> str | None:
    a = db.get(Ajuste, CLAVE_ACTIVA)
    return a.valor if a else None


def set_activa(db: Session, nombre: str | None) -> str | None:
    a = db.get(Ajuste, CLAVE_ACTIVA)
    n = limpiar(nombre) if nombre else None
    if not n:
        if a:
            db.delete(a)
        return None
    obtener(db, n)
    if a:
        a.valor = n
    else:
        db.add(Ajuste(clave=CLAVE_ACTIVA, valor=n))
    return n


# ───────────────────────── totales ─────────────────────────
@dataclass
class Resumen:
    id: str
    nombre: str
    total: Decimal = CERO
    total_usd: Decimal = CERO
    cantidad: int = 0
    desde: date | None = None
    hasta: date | None = None
    por_categoria: list[tuple[str, str, str, Decimal]] = field(default_factory=list)  # nombre, icono, color, total


def _movs(db: Session, etiqueta_id=None) -> list[Movimiento]:
    q = (select(Movimiento).join(MovimientoEtiqueta, MovimientoEtiqueta.movimiento_id == Movimiento.id)
         .options(selectinload(Movimiento.categoria), selectinload(Movimiento.etiquetas))
         .where(Movimiento.estado == EstadoMovimiento.confirmado, Movimiento.tipo == TipoMovimiento.gasto))
    if etiqueta_id:
        q = q.where(MovimientoEtiqueta.etiqueta_id == etiqueta_id)
    return list(db.scalars(q.order_by(Movimiento.fecha)).unique())


def _resumir(e: Etiqueta, movs: list[Movimiento]) -> Resumen:
    r = Resumen(str(e.id), e.nombre)
    cats: dict[str, list] = defaultdict(lambda: ["", "", CERO])
    for m in movs:
        r.cantidad += 1
        r.desde = min(r.desde or m.fecha, m.fecha)
        r.hasta = max(r.hasta or m.fecha, m.fecha)
        if m.moneda == Moneda.USD:
            r.total_usd += m.monto
            continue
        r.total += m.monto
        c = m.categoria
        k = c.nombre if c else "Sin categoría"
        cats[k][0], cats[k][1] = (c.icono, c.color) if c else ("", "")
        cats[k][2] += m.monto
    r.por_categoria = sorted(((k, v[0], v[1], v[2]) for k, v in cats.items()), key=lambda x: -x[3])
    return r


def resumenes(db: Session) -> list[Resumen]:
    por: dict = defaultdict(list)
    for m in _movs(db):
        for e in m.etiquetas:
            por[e.id].append(m)
    out = [_resumir(e, por.get(e.id, [])) for e in db.scalars(select(Etiqueta))]
    return sorted(out, key=lambda r: (r.hasta is None, r.hasta or date.min), reverse=True)


def resumen(db: Session, e: Etiqueta) -> tuple[Resumen, list[Movimiento]]:
    movs = _movs(db, e.id)
    return _resumir(e, movs), movs
