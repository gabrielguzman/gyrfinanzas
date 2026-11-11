"""Cotización del dólar para pasar todo a pesos (o a dólares).

Fuente: DolarAPI (https://dolarapi.com). Se guarda la última que se consiguió; si no hay red,
se usa esa. También se puede fijar una a mano.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy.orm import Session

from app.models import Ajuste

log = logging.getLogger(__name__)

URL = "https://dolarapi.com/v1/dolares"
CASAS = {
    "bolsa": "MEP",
    "oficial": "Oficial",
    "blue": "Blue",
    "contadoconliqui": "CCL",
    "cripto": "Cripto",
    "tarjeta": "Tarjeta",
    "mayorista": "Mayorista",
}
CASA_POR_DEFECTO = "bolsa"
VIGENCIA = timedelta(hours=3)


@dataclass
class Cotizacion:
    valor: Decimal
    casa: str            # bolsa, oficial, blue… o "manual"
    nombre: str          # MEP, Oficial, Blue… o "a mano"
    fecha: datetime | None
    vieja: bool = False  # no se pudo actualizar: es la última guardada


def _leer(db: Session, clave: str) -> str | None:
    a = db.get(Ajuste, clave)
    return a.valor if a else None


def _escribir(db: Session, clave: str, valor: str | None) -> None:
    a = db.get(Ajuste, clave)
    if valor is None:
        if a:
            db.delete(a)
    elif a:
        a.valor = valor
    else:
        db.add(Ajuste(clave=clave, valor=valor))


def descargar() -> dict[str, Decimal]:
    """{casa: precio de venta}. Se reemplaza en los tests."""
    r = httpx.get(URL, timeout=5)
    r.raise_for_status()
    salida = {}
    for d in r.json():
        try:
            salida[str(d["casa"])] = Decimal(str(d["venta"]))
        except (KeyError, InvalidOperation, TypeError):
            continue
    return salida


def casa_elegida(db: Session) -> str:
    return _leer(db, "cotizacion_casa") or CASA_POR_DEFECTO


def configurar(db: Session, casa: str | None = None, manual: Decimal | None = None, borrar_manual: bool = False) -> None:
    if casa:
        _escribir(db, "cotizacion_casa", casa)
        _escribir(db, "cotizacion_fecha", None)  # forzar a bajarla de nuevo
    if manual is not None:
        _escribir(db, "cotizacion_manual", str(manual))
    elif borrar_manual:
        _escribir(db, "cotizacion_manual", None)


def obtener(db: Session, ahora: datetime | None = None) -> Cotizacion | None:
    ahora = ahora or datetime.now(timezone.utc)
    manual = _leer(db, "cotizacion_manual")
    if manual:
        return Cotizacion(Decimal(manual), "manual", "a mano", None)
    casa = casa_elegida(db)
    guardada, fecha = _leer(db, "cotizacion_valor"), _leer(db, "cotizacion_fecha")
    f = datetime.fromisoformat(fecha) if fecha else None
    if guardada and f and ahora - f < VIGENCIA:
        return Cotizacion(Decimal(guardada), casa, CASAS.get(casa, casa), f)
    fallo = _leer(db, "cotizacion_fallo")
    if fallo and ahora - datetime.fromisoformat(fallo) < timedelta(minutes=15):
        precios = {}  # falló hace poco: no reintentar en cada pedido
    else:
        precios = None
    try:
        if precios is None:
            precios = descargar()
        if casa in precios:
            _escribir(db, "cotizacion_valor", str(precios[casa]))
            _escribir(db, "cotizacion_fecha", ahora.isoformat())
            db.commit()
            return Cotizacion(precios[casa], casa, CASAS.get(casa, casa), ahora)
    except Exception as e:  # sin red, API caída: seguimos con la guardada
        log.warning("No pude actualizar la cotización: %s", e)
        _escribir(db, "cotizacion_fallo", ahora.isoformat())
        db.commit()
    if guardada:
        return Cotizacion(Decimal(guardada), casa, CASAS.get(casa, casa), f, vieja=True)
    return None


def a_pesos(monto: Decimal, moneda: str, cot: Cotizacion | None) -> Decimal | None:
    if moneda == "ARS":
        return monto
    return (monto * cot.valor).quantize(Decimal("0.01")) if cot else None
