from decimal import Decimal

from app.services.deudas import DeudaSim, simular


def D(x):
    return Decimal(str(x))


def test_simulador_avalancha_ahorra_intereses():
    deudas = [
        DeudaSim("tarjeta", "Tarjeta", D(180000), D("0.065"), D(20000)),
        DeudaSim("personal", "Personal", D(420000), D("0.0375"), D(35000)),
        DeudaSim("amigo", "Amigo", D(60000), D(0), D(0)),
    ]
    av = simular(deudas, D(30000), "avalancha")
    bn = simular(deudas, D(30000), "bola_de_nieve")
    assert av.meses and bn.meses
    assert av.orden[0] == "tarjeta" and bn.orden[0] == "amigo"
    assert av.intereses < bn.intereses
    assert av.serie[-1] == 0


def test_simulador_detecta_que_no_termina():
    r = simular([DeudaSim("x", "X", D(100000), D("0.10"), D(5000))], D(0), "avalancha")
    assert r.meses is None


def _medio(base, k):
    return base["medios"][k]["id"]


def test_prestamo_con_cuotas_y_pagos(client, base):
    d = client.post("/deudas", json={
        "tipo": "prestamo", "nombre": "Préstamo personal", "monto_inicial": "420000", "tna": "45",
        "cuota": "35000", "cuotas_total": 24, "cuotas_pagadas": 10, "dia_vencimiento": 10,
        "cuenta_id": base["galicia"]["id"]}).json()
    assert d["cuotas_restantes"] == 14 and Decimal(d["saldo"]) == Decimal("420000.00")
    assert Decimal(d["cuota_sugerida"]) == Decimal("35000.00") and d["proximo_vencimiento"]
    r = client.post(f"/deudas/{d['id']}/movimientos", json={"accion": "pago"})
    assert r.status_code == 201, r.text
    det = r.json()
    # 35.000 de cuota: 15.750 de interés (45%/12 sobre 420.000) y 19.250 de capital
    assert Decimal(det["saldo"]) == Decimal("400750.00")
    assert Decimal(det["intereses_pagados"]) == Decimal("15750.00")
    assert det["cuotas_restantes"] == 13
    assert det["movimientos"][0]["descripcion"] == "Cuota 11/24 Préstamo personal"
    assert Decimal(client.get(f"/cuentas/{base['galicia']['id']}").json()["saldo"]) == Decimal("65000.00")


def test_carga_por_texto_de_prestamos_entre_personas(client, base):
    mov = client.post("/captura", json={"texto": "le presté 20 lucas a juan mp"}).json()
    assert mov["descripcion"] == "Préstamo a Juan" and mov["tipo"] == "gasto"
    client.post(f"/movimientos/{mov['id']}/confirmar")
    deudas = client.get("/deudas").json()
    juan = next(d for d in deudas if d["nombre"] == "Juan")
    assert juan["tipo"] == "me_deben" and Decimal(juan["saldo"]) == Decimal("20000.00")
    # Me devuelve una parte
    m2 = client.post("/captura", json={"texto": "juan me devolvió 5 lucas mp"}).json()
    client.post(f"/movimientos/{m2['id']}/confirmar")
    juan = client.get(f"/deudas/{juan['id']}").json()
    assert Decimal(juan["saldo"]) == Decimal("15000.00") and len(juan["movimientos"]) == 2
    # Prestar no cuenta como gasto del mes
    assert Decimal(client.get("/resumen").json()["gastos"]) == 0


def test_le_debo_y_cierre_automatico(client, base):
    d = client.post("/deudas", json={"tipo": "debo", "nombre": "Caro", "monto_inicial": "60000"}).json()
    r = client.post(f"/deudas/{d['id']}/movimientos", json={"accion": "pago", "monto": "60000", "medio_pago_id": _medio(base, "mp")})
    assert r.status_code == 201
    assert Decimal(r.json()["saldo"]) == 0 and r.json()["cerrada"] is True
    assert client.get("/deudas").json() == []
    assert client.delete(f"/deudas/{d['id']}").status_code == 409


def test_simular_endpoint(client, base):
    client.post("/deudas", json={"tipo": "prestamo", "nombre": "Personal", "monto_inicial": "420000", "tna": "45",
                                 "cuota": "35000", "cuotas_total": 24, "cuotas_pagadas": 10})
    client.post("/deudas", json={"tipo": "debo", "nombre": "Caro", "monto_inicial": "60000"})
    client.post("/deudas", json={"tipo": "me_deben", "nombre": "Juan", "monto_inicial": "20000"})
    r = client.post("/deudas/simular", json={"extra_mensual": "20000", "inflacion_mensual": "2.5"}).json()
    assert {d["nombre"] for d in r["deudas"]} == {"Personal", "Caro"}
    assert Decimal(r["presupuesto_mensual"]) == Decimal("55000")
    assert r["avalancha"]["meses"] and r["bola_de_nieve"]["orden"][0]["nombre"] == "Caro"
    caro = next(d for d in r["deudas"] if d["nombre"] == "Caro")
    assert Decimal(caro["tasa_real_anual"]) < 0  # sin interés, la inflación la licúa


def test_mismo_nombre_con_y_sin_tilde(client, base):
    for t in ("le presté 10k a martín mp", "le presté 5k a martin mp"):
        m = client.post("/captura", json={"texto": t}).json()
        client.post(f"/movimientos/{m['id']}/confirmar")
    deudas = client.get("/deudas").json()
    assert len(deudas) == 1 and deudas[0]["nombre"] == "Martín" and Decimal(deudas[0]["saldo"]) == Decimal("15000.00")
