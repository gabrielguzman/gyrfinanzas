from datetime import date
from decimal import Decimal

import pytest

from app.services.captura import _numero, interpretar


@pytest.mark.parametrize(
    "crudo,mult,esperado",
    [
        ("2.500", False, "2500"),
        ("1.450.000", False, "1450000"),
        ("1.234,56", False, "1234.56"),
        ("63280,50", False, "63280.50"),
        ("1.45", True, "1.45"),
        ("1,5", True, "1.5"),
        ("40", False, "40"),
    ],
)
def test_numeros_formato_argentino(crudo, mult, esperado):
    assert _numero(crudo, mult) == Decimal(esperado)


@pytest.mark.parametrize(
    "texto,monto,tipo",
    [
        ("nafta 40k visa", "40000", "gasto"),
        ("40 lucas nafta", "40000", "gasto"),
        ("cobré el sueldo 1.45M", "1450000", "ingreso"),
        ("heladera 466k 12 cuotas", "466000", "gasto"),
        ("farmacia $ 18.900", "18900", "gasto"),
    ],
)
def test_montos_y_tipo(texto, monto, tipo):
    r = interpretar(texto, [], [], hoy=date(2026, 11, 2))
    assert r.monto == Decimal(monto)
    assert r.tipo.value == tipo


def test_ayer_cuotas_y_usd():
    r = interpretar("ayer 100 usd regalo en 3 cuotas", [], [], hoy=date(2026, 11, 2))
    assert r.fecha == date(2026, 11, 1)
    assert r.moneda.value == "USD"
    assert r.cuotas == 3
    assert r.descripcion == "Regalo"


import pytest as _pytest


@_pytest.mark.parametrize("texto,cuotas", [
    ("switch 2000000 12 sin interes", 12),
    ("tele 900k x12", 12),
    ("aire 600k en 6", 6),
    ("aire 600k en 6 visa", 6),
    ("cena en 2 horas 30k", None),
    ("nafta 40k", None),
])
def test_otras_formas_de_cuotas(texto, cuotas):
    from datetime import date
    assert interpretar(texto, [], [], hoy=date(2026, 11, 11)).cuotas == cuotas


def test_fechas_explicitas():
    from datetime import date
    from app.services.captura import interpretar
    hoy = date(2026, 11, 12)
    casos = {
        "farmacia 5000 mp 3/11": (date(2026, 11, 3), 5000),
        "farmacia 5000 el 03/11/2026": (date(2026, 11, 3), 5000),
        "regalo 25k el 20/12": (date(2025, 12, 20), 25000),   # sin año y en el futuro: el año pasado
        "nafta 40k 5 de noviembre": (date(2026, 11, 5), 40000),
        "luz 18k el 2 de oct": (date(2026, 10, 2), 18000),
        "super 12500 31/02": (hoy, 12500),                    # fecha imposible: hoy
    }
    for texto, (f, m) in casos.items():
        r = interpretar(texto, [], [], hoy=hoy)
        assert (r.fecha, r.monto) == (f, m), texto
    assert interpretar("farmacia 5000 3/11", [], [], hoy=hoy).descripcion == "Farmacia"
    assert interpretar("nafta 40k el 5 de noviembre", [], [], hoy=hoy).descripcion == "Nafta"


def test_mas_palabras_de_ingreso():
    from app.models import TipoMovimiento
    from app.services.captura import interpretar
    for t in ("honorarios 300k", "me pagaron el freelance 250k", "me regalaron 20k", "gané 50k en el bingo", "me devolvieron 8000"):
        assert interpretar(t, [], []).tipo == TipoMovimiento.ingreso, t
    assert interpretar("cafe 3000", [], []).tipo == TipoMovimiento.gasto
