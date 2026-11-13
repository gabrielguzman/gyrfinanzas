from datetime import date

from app.services.detectores import hallazgos
from tests.test_detectores import _db, gasto


def _saldo(client, cid):
    return float(next(c for c in client.get("/cuentas").json() if c["id"] == cid)["saldo"])


def test_corregir_saldo_de_hoy(client, base):
    mp = base["mp"]["id"]
    gasto(client, base, 3000, date.today(), "cafe")
    assert _saldo(client, mp) == 17000
    r = client.patch(f"/cuentas/{mp}", json={"saldo_actual": "25000"})
    assert r.status_code == 200 and float(r.json()["saldo"]) == 25000
    assert float(r.json()["saldo_inicial"]) == 28000  # los movimientos quedan como estaban
    # Tarjeta: «debo 150.000» es saldo −150.000
    visa = base["visa"]["id"]
    client.patch(f"/cuentas/{visa}", json={"saldo_actual": "-150000"})
    assert _saldo(client, visa) == -150000


def test_topes(client, base):
    hoy = date.today()
    comida = base["cats"]["comida"]["id"]
    r = client.put(f"/topes/{comida}", json={"monto": "10000"}).json()
    assert len(r) == 1 and r[0]["estado"] == "ok" and r[0]["gastado"] == "0"
    gasto(client, base, 8500, hoy, "cena")
    t = client.get("/topes").json()[0]
    assert (t["estado"], t["porcentaje"], t["queda"]) == ("cerca", 85, "1500.00")
    h = {x.tipo: x for x in hallazgos(_db(client), hoy)}
    assert h["tope"].titulo == "Comida afuera: llevás el 85% del tope"
    gasto(client, base, 2000, hoy, "cafe")
    t = client.get("/topes").json()[0]
    assert t["estado"] == "pasado"
    assert "Te pasaste del tope de Comida afuera" in [x.titulo for x in hallazgos(_db(client), hoy)]
    # Todas: incluye las que no tienen tope
    todas = client.get("/topes?todas=true").json()
    assert {x["categoria"] for x in todas} >= {"Comida afuera", "Auto"}
    # Sacar el tope
    assert client.put(f"/topes/{comida}", json={"monto": None}).json() == []
    assert client.put(f"/topes/{base['cats']['sueldo']['id']}", json={"monto": "1"}).status_code == 422
