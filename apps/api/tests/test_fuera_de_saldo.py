from datetime import date, timedelta


def _saldo(client, cuenta_id):
    return next(c for c in client.get("/cuentas").json() if c["id"] == cuenta_id)["saldo"]


def test_ya_estaba_descontado_no_mueve_el_saldo(client, base):
    mp = base["mp"]["id"]
    antes = _saldo(client, mp)
    hace = (date.today() - timedelta(days=20)).isoformat()
    m = client.post("/movimientos", json={"tipo": "gasto", "fecha": hace, "monto": "5000", "descripcion": "Farmacia",
                                          "medio_pago_id": base["medios"]["mp"]["id"], "categoria_id": base["cats"]["comida"]["id"],
                                          "estado": "confirmado", "fuera_de_saldo": True}).json()
    assert m["fuera_de_saldo"] is True
    assert _saldo(client, mp) == antes
    # Igual cuenta como gasto en los movimientos y en el resumen de su mes
    assert any(x["id"] == m["id"] for x in client.get("/movimientos?tipo=gasto").json())
    # Si lo apagás, se descuenta
    r = client.patch(f"/movimientos/{m['id']}", json={"fuera_de_saldo": False}).json()
    assert r["fuera_de_saldo"] is False
    assert float(_saldo(client, mp)) == float(antes) - 5000
    # Un PATCH que no lo menciona no lo cambia
    client.patch(f"/movimientos/{m['id']}", json={"fuera_de_saldo": True})
    client.patch(f"/movimientos/{m['id']}", json={"descripcion": "Farmacity"})
    assert client.get(f"/movimientos/{m['id']}").json()["fuera_de_saldo"] is True
    assert _saldo(client, mp) == antes
    assert client.get("/cuentas").json()[0]["creado"]
