from datetime import date, timedelta
from decimal import Decimal


def test_previsualizar_devuelve_partes_e_icono(client, base):
    client.patch(f"/categorias/{base['cats']['auto']['id']}", json={"icono": "auto", "color": "red"})
    r = client.post("/captura/previsualizar", json={"texto": "nafta 40k visa"}).json()
    texto = "nafta 40k visa"
    assert [(texto[p["inicio"]:p["fin"]], p["tipo"]) for p in r["partes"]] == [
        ("nafta", "categoria"), ("40k", "monto"), ("visa", "medio")]
    assert r["categoria_icono"] == "auto" and r["categoria_color"] == "red"


def _gasto(client, base, monto, fecha, desc="Nafta", cat="auto", medio="visa"):
    r = client.post("/movimientos", json={
        "tipo": "gasto", "fecha": fecha.isoformat(), "monto": str(monto), "descripcion": desc,
        "categoria_id": base["cats"][cat]["id"], "medio_pago_id": base["medios"][medio]["id"]})
    assert r.status_code == 201, r.text


def test_resumen_del_mes(client, base):
    hoy = date.today()
    _gasto(client, base, 1000, hoy.replace(day=1))
    _gasto(client, base, 500, hoy.replace(day=1), desc="Café", cat="comida", medio="mp")
    anterior = hoy.replace(day=1) - timedelta(days=1)
    _gasto(client, base, 3000, anterior.replace(day=1))
    r = client.get("/resumen").json()
    assert Decimal(r["gastos"]) == 1500
    assert [c["nombre"] for c in r["por_categoria"]] == ["Auto", "Comida afuera"]
    assert r["dia_hoy"] == hoy.day and len(r["diario"]) == hoy.day
    assert Decimal(r["diario"][-1]["acumulado"]) == 1500
    assert Decimal(r["gastos_anterior_total"]) == 3000
    assert Decimal(r["gastos_anterior_a_la_fecha"]) == 3000


def test_frecuentes(client, base):
    hoy = date.today()
    for _ in range(3):
        _gasto(client, base, 2500, hoy, desc="Café", cat="comida", medio="mp")
    _gasto(client, base, 40000, hoy)
    f = client.get("/captura/frecuentes").json()
    assert len(f) == 1 and f[0]["texto"] == "café 2500 mp" and f[0]["veces"] == 3


def test_desconfirmar_vuelve_a_bandeja(client, base):
    mov = client.post("/captura", json={"texto": "nafta 40k visa"}).json()
    client.post(f"/movimientos/{mov['id']}/confirmar")
    r = client.post(f"/movimientos/{mov['id']}/desconfirmar").json()
    assert r["estado"] == "pendiente"
    assert client.get(f"/cuentas/{base['visa']['id']}").json()["saldo"] == "0.00"
