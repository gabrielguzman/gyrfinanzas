from datetime import date, timedelta
from decimal import Decimal

from app.services.garantias import mas_meses
from app.services.metas import meses_entre

HOY = date.today()


def test_meses_entre():
    assert meses_entre(date(2026, 11, 10), date(2027, 3, 10)) == 5
    assert meses_entre(date(2026, 11, 10), date(2027, 3, 9)) == 4
    assert meses_entre(date(2026, 11, 10), date(2026, 11, 20)) == 1


def test_meta_con_fecha_aportes_y_plan(client, base):
    fecha = mas_meses(HOY, 6)
    m = client.post("/metas", json={"nombre": "Vacaciones", "emoji": "✈️", "objetivo": "1200000",
                                    "fecha_objetivo": fecha.isoformat(), "ya_tengo": "200000"}).json()
    meses = meses_entre(HOY, fecha)
    assert Decimal(m["ahorrado"]) == 200_000 and Decimal(m["falta"]) == 1_000_000
    assert Decimal(m["por_mes"]) == round(Decimal(1_000_000) / meses)
    assert m["progreso"] == round(200_000 / 1_200_000, 4)

    m = client.post(f"/metas/{m['id']}/aportes", json={"monto": "100000"}).json()
    assert Decimal(m["ahorrado"]) == 300_000 and len(m["aportes"]) == 2
    m = client.delete(f"/metas/{m['id']}/aportes/{m['aportes'][0]['id']}").json()
    assert Decimal(m["ahorrado"]) == 200_000

    # Lo que pide la meta se descuenta de lo que podés gastar
    client.put("/plan/ajustes", json={"dia_cobro": 1, "ingreso_mensual": "1500000"})
    p = client.get("/plan").json()
    assert Decimal(p["metas"]) == Decimal(m["por_mes_ars"])
    assert p["detalle_metas"][0]["nombre"] == "✈️ Vacaciones"
    assert Decimal(p["para_gastar"]) == 1_500_000 - Decimal(m["por_mes_ars"])

    # Al llegar, aparece el festejo en «Para mirar» y deja de pedir plata
    client.post(f"/metas/{m['id']}/aportes", json={"monto": "1000000"})
    hs = {h["tipo"]: h for h in client.get("/hallazgos").json()}
    assert hs["meta"]["titulo"] == "¡Llegaste a ✈️ Vacaciones!"
    assert Decimal(client.get("/plan").json()["metas"]) == 0


def test_meta_sigue_una_cuenta_y_en_dolares(client, base):
    m = client.post("/metas", json={"nombre": "Colchón", "objetivo": "100000", "cuenta_id": base["mp"]["id"]}).json()
    assert Decimal(m["ahorrado"]) == 20_000 and m["cuenta"] == "Mercado Pago"
    assert client.post(f"/metas/{m['id']}/aportes", json={"monto": "1000"}).status_code == 422
    assert client.post("/metas", json={"nombre": "X", "objetivo": "10", "moneda": "USD",
                                       "cuenta_id": base["mp"]["id"]}).status_code == 422
    usd = client.post("/metas", json={"nombre": "Auto", "objetivo": "5000", "moneda": "USD",
                                      "aporte_mensual": "500"}).json()
    assert Decimal(usd["por_mes_ars"]) == 600_000  # 500 USD al MEP de 1.200
    assert usd["fecha_estimada"] == mas_meses(HOY, 10).isoformat()


def test_aporte_por_telegram_no_confunde_gastos(client, base):
    from app.db import get_db
    from app.main import app
    from app.services.metas import interpretar_aporte
    client.post("/metas", json={"nombre": "Vacaciones", "objetivo": "1000000"})
    client.post("/metas", json={"nombre": "Auto", "objetivo": "9000000"})
    db = next(app.dependency_overrides[get_db]())
    meta, monto = interpretar_aporte(db, "aparté 50 lucas para las vacaciones")
    assert meta.nombre == "Vacaciones" and monto == 50_000
    meta, monto = interpretar_aporte(db, "saqué 20k de vacaciones")
    assert monto == -20_000
    assert interpretar_aporte(db, "puse 40k de nafta en el auto") is None
    assert interpretar_aporte(db, "nafta 40k visa") is None


def test_patrimonio(client, base):
    usd = client.post("/cuentas", json={"nombre": "Dólares", "tipo": "efectivo", "moneda": "USD", "saldo_inicial": "500"}).json()
    pf = client.post("/inversiones", json={"nombre": "Plazo fijo Galicia", "tipo": "plazo_fijo", "capital": "1000000",
                                           "tna": "36", "fecha_inicio": (HOY - timedelta(days=30)).isoformat(),
                                           "vence": (HOY + timedelta(days=2)).isoformat()}).json()
    assert Decimal(pf["valor"]) == Decimal("1029589.04")
    client.post("/deudas", json={"tipo": "me_deben", "nombre": "Juan", "monto_inicial": "50000"})
    client.post("/deudas", json={"tipo": "prestamo", "nombre": "Préstamo", "monto_inicial": "200000"})
    client.post("/movimientos", json={"tipo": "gasto", "fecha": HOY.isoformat(), "monto": "40000",
                                      "descripcion": "Súper", "medio_pago_id": base["medios"]["visa"]["id"]})

    p = client.get("/patrimonio").json()
    activos = 100_000 + 20_000 + 600_000 + Decimal("1029589.04") + 50_000
    assert Decimal(p["activos"]) == activos
    assert Decimal(p["pasivos"]) == 240_000
    assert Decimal(p["neto"]) == activos - 240_000
    assert Decimal(p["neto_usd"]) == round((activos - 240_000) / 1200)
    assert p["cotizacion"]["nombre"] == "MEP" and Decimal(p["cotizacion"]["valor"]) == 1200
    grupos = {i["grupo"] for i in p["items"]}
    assert grupos == {"Pesos", "Dólares", "Inversiones", "Te deben", "Tarjetas", "Préstamos"}
    assert p["serie"][-1] == {"fecha": HOY.isoformat(), "neto": str(round(activos - 240_000)), "estimado": False}
    # Líquido: cuentas − tarjetas (el plazo fijo no es líquido hasta que vence)
    assert Decimal(p["liquido"]) == 100_000 + 20_000 + 600_000 - 40_000

    # Cotización a mano y otra casa
    c = client.put("/cotizacion", json={"manual": "1300"}).json()
    assert c["manual"] is True and Decimal(c["valor"]) == 1300
    c = client.put("/cotizacion", json={"borrar_manual": True, "casa": "blue"}).json()
    assert c["nombre"] == "Blue" and Decimal(c["valor"]) == 1250

    # El plazo fijo que vence pasado mañana aparece para mirar
    hs = [h for h in client.get("/hallazgos").json() if h["tipo"] == "inversion"]
    assert hs[0]["titulo"] == "Plazo fijo Galicia vence en 2 días"
    client.patch(f"/inversiones/{pf['id']}", json={"cerrada": True})
    assert not [h for h in client.get("/hallazgos").json() if h["tipo"] == "inversion"]
