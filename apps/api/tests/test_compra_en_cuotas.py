from datetime import date
from decimal import Decimal


def test_compra_en_cuotas_con_interes(client, base):
    """1.000.000 en 12 cuotas de 110.000 con tarjeta: deuda real, sin vaciar el disponible ni inflar el mes."""
    hogar = client.post("/categorias", json={"nombre": "Hogar", "palabras": "heladera"}).json()
    antes = client.get("/inicio").json()["totales"][0]

    m = client.post("/captura", json={"texto": "heladera 1M en 12 cuotas de 110k visa"}).json()
    assert Decimal(m["monto"]) == 1_320_000 and m["categoria_id"] == hogar["id"]
    client.post(f"/movimientos/{m['id']}/confirmar")

    # La tarjeta debe el total con interés, en 12 cuotas de 110.000
    t = client.get(f"/tarjetas/{base['visa']['id']}").json()
    assert t["planes"][0]["cuotas_total"] == 12 and Decimal(t["planes"][0]["monto_cuota"]) == 110_000
    assert Decimal(t["deuda"]) == 1_320_000

    # El banco no se toca; el disponible solo resta lo que vence ahora (una cuota), no las 12
    ahora = client.get("/inicio").json()["totales"][0]
    assert ahora["en_cuentas"] == antes["en_cuentas"]
    assert Decimal(ahora["deuda_tarjetas"]) == 110_000
    assert Decimal(ahora["cuotas_futuras"]) == 1_210_000
    assert Decimal(ahora["disponible"]) == Decimal(antes["disponible"]) - 110_000

    # En el mes cuenta la cuota (si cae en el resumen de este mes), nunca el total
    r = client.get("/resumen").json()
    assert Decimal(r["gastos"]) in (Decimal(0), Decimal(110_000))
    assert Decimal(r["gastos"]) < 1_000_000

    # El patrimonio sí muestra la deuda completa
    p = client.get("/patrimonio").json()
    assert sum(Decimal(i["monto"]) for i in p["items"] if i["grupo"] == "Tarjetas") == 1_320_000
