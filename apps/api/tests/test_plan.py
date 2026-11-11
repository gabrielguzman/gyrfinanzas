from datetime import date
from decimal import Decimal

from app.services.plan import ciclo, dia_en

HOY = date(2026, 11, 10)


def mov(client, base, tipo, monto, fecha, desc, medio="debito", cat=None, **extra):
    r = client.post("/movimientos", json={
        "tipo": tipo, "fecha": fecha, "monto": str(monto), "descripcion": desc,
        "medio_pago_id": base["medios"][medio]["id"],
        "categoria_id": base["cats"][cat]["id"] if cat else None, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_ciclo_y_fin_de_mes():
    assert ciclo(1, HOY) == (date(2026, 11, 1), date(2026, 11, 30), date(2026, 12, 1))
    assert ciclo(15, HOY) == (date(2026, 10, 15), date(2026, 11, 14), date(2026, 11, 15))
    # Cobrás el 31: en febrero es el 28
    assert ciclo(31, date(2027, 2, 10)) == (date(2027, 1, 31), date(2027, 2, 27), date(2027, 2, 28))
    assert dia_en(2028, 2, 31) == date(2028, 2, 29)


def test_sin_ingresos_no_hay_plan(client, base):
    p = client.get("/plan", params={"hoy": HOY.isoformat()}).json()
    assert p["configurado"] is False and p["estado"] == "sin_datos"


def test_hoy_podes_gastar(client, base):
    mov(client, base, "ingreso", 1_000_000, "2026-11-01", "Sueldo", cat="sueldo")
    for f in ("2026-09-05", "2026-10-05", "2026-11-05"):
        mov(client, base, "gasto", 300_000, f, "Alquiler", cat="auto")
    mov(client, base, "gasto", 10_000, "2026-11-03", "Café", cat="comida")
    mov(client, base, "gasto", 40_000, "2026-11-09", "Súper", cat="comida")
    mov(client, base, "gasto", 5_000, "2026-11-10", "Kiosco", cat="comida")
    # Una compra en 6 cuotas no se come el día: cuenta por cuota, cuando pagás el resumen
    bici = client.post("/captura", json={"texto": "bici 120k visa 6 cuotas"}).json()
    client.patch(f"/movimientos/{bici['id']}", json={"fecha": "2026-11-02"})
    assert client.post(f"/movimientos/{bici['id']}/confirmar").status_code == 200

    p = client.get("/plan", params={"hoy": HOY.isoformat()}).json()
    assert p["dia_cobro"] == 1 and p["cobro_detectado"] is True
    assert p["desde"] == "2026-11-01" and p["proximo_cobro"] == "2026-12-01" and p["dias_restantes"] == 21
    assert Decimal(p["fijos"]) == 300_000
    assert Decimal(p["para_gastar"]) == 700_000
    assert Decimal(p["gastado"]) == 55_000 and Decimal(p["gastado_hoy"]) == 5_000
    assert Decimal(p["por_dia"]) == 30_952          # (645.000 + 5.000) / 21
    assert Decimal(p["hoy"]) == 25_952
    assert Decimal(p["manana"]) == 32_250           # 645.000 / 20
    assert p["estado"] == "bien"

    # Ahorro de 100k por mes: baja lo que podés gastar
    p = client.put("/plan/ajustes", json={"ahorro_mensual": "100000"}).json()
    p = client.get("/plan", params={"hoy": HOY.isoformat()}).json()
    assert Decimal(p["para_gastar"]) == 600_000 and Decimal(p["por_dia"]) == 26_190  # 550.000 / 21

    # Gastar de más lo pone en rojo
    mov(client, base, "gasto", 600_000, "2026-11-10", "Viaje", cat="comida")
    p = client.get("/plan", params={"hoy": HOY.isoformat()}).json()
    assert p["estado"] == "pasado" and Decimal(p["restante"]) < 0

    # El calendario muestra la cuota de la bici en el resumen de diciembre
    c = client.get("/plan/calendario", params={"hoy": HOY.isoformat()}).json()
    visa = [e for e in c["eventos"] if e["tipo"] == "tarjeta"]
    assert any(Decimal(e["monto"]) == -20_000 for e in visa)
    assert any(e["tipo"] == "fijo" and e["titulo"] == "Alquiler" and e["fecha"] == "2026-12-05" for e in c["eventos"])
    assert any(e["tipo"] == "cobro" and e["fecha"] == "2026-12-01" for e in c["eventos"])


def test_ajustes_y_calendario_en_rojo(client, base):
    p = client.put("/plan/ajustes", json={"dia_cobro": 5, "ingreso_mensual": "500000"}).json()
    assert p["dia_cobro"] == 5 and p["cobro_detectado"] is False
    client.post("/deudas", json={
        "tipo": "prestamo", "nombre": "Préstamo", "monto_inicial": "2000000", "cuota": "700000",
        "cuotas_total": 12, "dia_vencimiento": 20, "tna": "0"})
    c = client.get("/plan/calendario", params={"hoy": HOY.isoformat()}).json()
    # Galicia 100k + MP 20k: la cuota de 700k del 20 lo deja en negativo
    assert c["saldo_hoy"] == "120000"
    assert c["rojo"]["fecha"] == "2026-11-20"
    assert any(e["tipo"] == "prestamo" and e["fecha"] == "2026-12-20" for e in c["eventos"])
    # Borrar un ajuste vuelve a detectar
    client.put("/plan/ajustes", json={"dia_cobro": None, "ingreso_mensual": None})
    assert client.get("/plan").json()["dia_cobro"] is None
