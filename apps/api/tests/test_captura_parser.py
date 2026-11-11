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
