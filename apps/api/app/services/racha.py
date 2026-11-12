"""Racha de registro: días seguidos con todo cargado.

Un día cuenta si cargaste algo con esa fecha, si ese día cargaste algo, o si marcaste
«hoy no gasté nada». Hoy todavía no cortó la racha: se corta si pasa el día sin nada.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DiaSinGastos, Movimiento


@dataclass
class Racha:
    actual: int
    mejor: int
    hoy: str                        # cargado | sin_gastos | vacio
    dias: list[tuple[date, str]]    # los últimos 14, del más viejo a hoy


def dias_registrados(db: Session) -> dict[date, str]:
    out: dict[date, str] = {d: "sin_gastos" for d in db.scalars(select(DiaSinGastos.fecha))}
    for d in db.scalars(select(Movimiento.fecha).distinct()):
        out[d] = "cargado"
    for c in db.scalars(select(Movimiento.creado)):
        if c is not None:
            d = c.astimezone().date() if c.tzinfo else c.date()
            out[d] = "cargado"
    return out


def calcular(db: Session, hoy: date | None = None) -> Racha:
    hoy = hoy or date.today()
    reg = {d: v for d, v in dias_registrados(db).items() if d <= hoy}
    # Racha actual: desde hoy (o ayer, si hoy todavía no cargaste) hacia atrás
    d = hoy if hoy in reg else hoy - timedelta(days=1)
    actual = 0
    while d in reg:
        actual += 1
        d -= timedelta(days=1)
    # La mejor de la historia
    mejor, corrida, prev = 0, 0, None
    for x in sorted(reg):
        corrida = corrida + 1 if prev and (x - prev).days == 1 else 1
        mejor, prev = max(mejor, corrida), x
    dias = [(hoy - timedelta(days=k), reg.get(hoy - timedelta(days=k), "vacio")) for k in range(13, -1, -1)]
    return Racha(actual, max(mejor, actual), reg.get(hoy, "vacio"), dias)


def marcar_sin_gastos(db: Session, fecha: date, sin: bool = True) -> None:
    d = db.get(DiaSinGastos, fecha)
    if sin and d is None:
        db.add(DiaSinGastos(fecha=fecha))
    elif not sin and d is not None:
        db.delete(d)


