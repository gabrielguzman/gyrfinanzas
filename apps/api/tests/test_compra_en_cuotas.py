import uuid
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


def test_cuotas_sin_tarjeta_no_van_a_la_billetera(client, base):
    # «visa» existe en el fixture; probamos con una tarjeta que no está cargada
    v = client.post("/captura/previsualizar", json={"texto": "switch 1.4M en 12 cuotas master"}).json()
    assert v["medio_pago_id"] is None and "Master" in v["aviso"]
    # Aunque elijas Mercado Pago, en cuotas no se confirma
    m = client.post("/captura", json={"texto": "switch 1.4M en 12 cuotas"}).json()
    assert m["estado"] == "pendiente"
    client.patch(f"/movimientos/{m['id']}", json={"medio_pago_id": base["medios"]["mp"]["id"]})
    r = client.post(f"/movimientos/{m['id']}/confirmar")
    assert r.status_code == 422 and "tarjeta de crédito" in r.json()["detail"]
    # Con la Visa sí: plan de cuotas y la billetera intacta
    client.patch(f"/movimientos/{m['id']}", json={"medio_pago_id": base["medios"]["visa"]["id"]})
    assert client.post(f"/movimientos/{m['id']}/confirmar").status_code == 200
    t = client.get(f"/tarjetas/{base['visa']['id']}").json()
    assert len(t["planes"]) == 1


def test_arreglar_una_compra_cargada_con_otro_medio(client, base):
    """Una compra en cuotas que quedó en la billetera (datos viejos) se arregla cambiando el medio."""
    from app.db import get_db
    from app.main import app
    from app.models import EstadoMovimiento, Movimiento, TipoMovimiento
    db = next(app.dependency_overrides[get_db]())
    mov = Movimiento(tipo=TipoMovimiento.gasto, estado=EstadoMovimiento.confirmado, fecha=date.today(),
                     monto=Decimal(1_400_000), descripcion="Switch (12 cuotas)", cuotas=12,
                     medio_pago_id=uuid.UUID(base["medios"]["mp"]["id"]), cuenta_id=uuid.UUID(base["mp"]["id"]))
    db.add(mov)
    db.commit()
    saldos = {c["nombre"]: Decimal(c["saldo"]) for c in client.get("/cuentas").json()}
    assert saldos["Mercado Pago"] == 20_000 - 1_400_000
    r = client.patch(f"/movimientos/{mov.id}", json={"medio_pago_id": base["medios"]["visa"]["id"]})
    assert r.status_code == 200
    saldos = {c["nombre"]: Decimal(c["saldo"]) for c in client.get("/cuentas").json()}
    assert saldos["Mercado Pago"] == 20_000 and saldos["Visa Galicia"] == -1_400_000
    t = client.get(f"/tarjetas/{base['visa']['id']}").json()
    assert len(t["planes"]) == 1 and t["planes"][0]["cuotas_total"] == 12
