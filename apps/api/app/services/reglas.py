"""Reglas de categorías: «todo lo que diga Uber va a Transporte».

Una regla es un texto (sin tildes, minúsculas) que, si aparece como palabra en la
descripción o en lo que escribiste, decide la categoría. Gana sobre las palabras clave
de las categorías y sobre lo aprendido de cargas anteriores.
"""
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Categoria, Movimiento, ReglaCategoria, TipoCategoria, TipoMovimiento
from app.services.captura import NO_NOMBRES, normalizar

VACIAS = NO_NOMBRES | {"pago", "compra", "gasto", "cuota", "cuotas", "visa", "master", "mastercard", "debito", "credito"}


def limpiar(texto: str) -> str:
    return re.sub(r"\s+", " ", normalizar(texto)).strip()


def _patron(texto: str) -> re.Pattern:
    return re.compile(rf"(?<!\w){re.escape(texto)}(?!\w)")


def coincide(regla_texto: str, *textos: str | None) -> bool:
    p = _patron(regla_texto)
    return any(t and p.search(limpiar(t)) for t in textos)


def todas(db: Session) -> list[ReglaCategoria]:
    # Las más largas primero: «uber eats» gana sobre «uber»
    return sorted(db.scalars(select(ReglaCategoria)), key=lambda r: -len(r.texto))


def categoria_para(db: Session, *textos: str | None, tipo: TipoMovimiento = TipoMovimiento.gasto,
                   reglas: list[ReglaCategoria] | None = None) -> Categoria | None:
    tipo_cat = TipoCategoria.ingreso if tipo == TipoMovimiento.ingreso else TipoCategoria.gasto
    for r in reglas if reglas is not None else todas(db):
        if r.categoria.tipo == tipo_cat and coincide(r.texto, *textos):
            return r.categoria
    return None


def coincidencias(db: Session, texto: str, tipo_cat: TipoCategoria | None = None) -> list[Movimiento]:
    """Movimientos (no transferencias) que cumplen la regla."""
    texto = limpiar(texto)
    movs = db.scalars(select(Movimiento).where(Movimiento.tipo != TipoMovimiento.transferencia)
                      .order_by(Movimiento.fecha.desc()))
    out = []
    for m in movs:
        if tipo_cat and (m.tipo == TipoMovimiento.ingreso) != (tipo_cat == TipoCategoria.ingreso):
            continue
        if coincide(texto, m.descripcion, m.texto_original):
            out.append(m)
    return out


@dataclass
class Previa:
    texto: str
    total: int
    a_cambiar: int
    ejemplos: list[str] = field(default_factory=list)


def previa(db: Session, texto: str, categoria_id: uuid.UUID | None) -> Previa:
    cat = db.get(Categoria, categoria_id) if categoria_id else None
    ms = coincidencias(db, texto, cat.tipo if cat else None)
    cambian = [m for m in ms if m.categoria_id != categoria_id]
    ejemplos = list(dict.fromkeys(m.descripcion for m in ms))[:4]
    return Previa(limpiar(texto), len(ms), len(cambian), ejemplos)


def crear(db: Session, texto: str, categoria_id: uuid.UUID, aplicar: bool) -> tuple[ReglaCategoria, int]:
    texto = limpiar(texto)
    r = db.scalar(select(ReglaCategoria).where(ReglaCategoria.texto == texto))
    if r is None:
        r = ReglaCategoria(texto=texto, categoria_id=categoria_id)
        db.add(r)
    r.categoria_id = categoria_id
    db.flush()
    cambiados = 0
    if aplicar:
        cat = db.get(Categoria, categoria_id)
        for m in coincidencias(db, texto, cat.tipo):
            if m.categoria_id != categoria_id:
                m.categoria_id = categoria_id
                cambiados += 1
    return r, cambiados


def sugerir_texto(descripcion: str) -> str | None:
    """La palabra que mejor identifica un gasto: «Uber al centro» → «uber»."""
    d = re.sub(r"\s*\(\d+ cuotas\)$", "", descripcion)
    for w in limpiar(d).split(" "):
        if len(w) >= 3 and w not in VACIAS and not any(c.isdigit() for c in w):
            return w
    return None
