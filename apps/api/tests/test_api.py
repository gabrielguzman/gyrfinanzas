from decimal import Decimal


def D(x) -> Decimal:
    return Decimal(str(x))


def saldo(client, cuenta_id) -> Decimal:
    return D(client.get(f"/cuentas/{cuenta_id}").json()["saldo"])


def test_captura_va_a_bandeja_y_no_afecta_saldo(client, base):
    r = client.post("/captura", json={"texto": "nafta 40k visa"})
    assert r.status_code == 201, r.text
    mov = r.json()
    assert mov["estado"] == "pendiente"
    assert mov["medio_pago"] == "Visa Galicia"
    assert mov["categoria"] == "Auto"
    assert mov["cuenta_id"] == base["visa"]["id"]
    assert saldo(client, base["visa"]["id"]) == 0
    assert client.get("/inicio").json()["pendientes"] == 1


def test_confirmar_compra_con_tarjeta_genera_deuda_sin_tocar_banco(client, base):
    mov = client.post("/captura", json={"texto": "nafta 40k visa"}).json()
    r = client.post(f"/movimientos/{mov['id']}/confirmar")
    assert r.status_code == 200, r.text
    assert saldo(client, base["visa"]["id"]) == D(-40000)
    assert saldo(client, base["galicia"]["id"]) == D(100000)
    ars = next(t for t in client.get("/inicio").json()["totales"] if t["moneda"] == "ARS")
    assert D(ars["en_cuentas"]) == D(120000)
    assert D(ars["deuda_tarjetas"]) == D(40000)
    assert D(ars["disponible"]) == D(80000)


def test_pagar_resumen_es_transferencia(client, base):
    mov = client.post("/captura", json={"texto": "nafta 40k visa"}).json()
    client.post(f"/movimientos/{mov['id']}/confirmar")
    r = client.post("/movimientos", json={
        "tipo": "transferencia", "fecha": "2026-11-05", "monto": "40000", "descripcion": "Pago resumen Visa",
        "cuenta_id": base["galicia"]["id"], "cuenta_destino_id": base["visa"]["id"],
    })
    assert r.status_code == 201, r.text
    assert saldo(client, base["visa"]["id"]) == 0
    assert saldo(client, base["galicia"]["id"]) == D(60000)


def test_no_se_confirma_sin_medio_de_pago(client, base):
    mov = client.post("/captura", json={"texto": "regalo 5000"}).json()
    assert mov["medio_pago"] is None
    r = client.post(f"/movimientos/{mov['id']}/confirmar")
    assert r.status_code == 422
    client.patch(f"/movimientos/{mov['id']}", json={"medio_pago_id": base["medios"]["mp"]["id"]})
    assert client.post(f"/movimientos/{mov['id']}/confirmar").status_code == 200
    assert saldo(client, base["mp"]["id"]) == D(15000)


def test_aprende_medio_de_movimientos_anteriores(client, base):
    primero = client.post("/captura", json={"texto": "cafe 2500 mp"}).json()
    client.post(f"/movimientos/{primero['id']}/confirmar")
    prev = client.post("/captura/previsualizar", json={"texto": "cafe 3000"}).json()
    assert prev["medio_pago"] == "Mercado Pago"
    assert prev["motivo_medio"]


def test_sin_monto_da_error_claro(client, base):
    r = client.post("/captura", json={"texto": "nafta visa"})
    assert r.status_code == 422
    assert "monto" in r.json()["detail"]


def test_comprobantes_se_vinculan_y_deduplican(client, base):
    mov = client.post("/captura", json={"texto": "super 63280 debito"}).json()
    pdf = b"%PDF-1.4 ticket de prueba"
    r = client.post(f"/movimientos/{mov['id']}/adjuntos/subir",
                    files={"archivo": ("ticket.pdf", pdf, "application/pdf")}, data={"rol": "ticket"})
    assert r.status_code == 200, r.text
    assert r.json()["tiene_comprobante"] is True

    # Mismo archivo subido de nuevo: no se duplica.
    dup = client.post("/archivos", files={"archivo": ("otra.pdf", pdf, "application/pdf")}).json()
    assert dup["id"] == r.json()["adjuntos"][0]["archivo_id"]
    assert len(client.get("/archivos").json()) == 1

    # Un mismo archivo puede respaldar dos movimientos.
    otro = client.post("/captura", json={"texto": "super 1000 debito"}).json()
    client.post(f"/movimientos/{otro['id']}/adjuntos", json={"archivo_id": dup["id"], "rol": "factura"})
    assert len(client.get(f"/archivos/{dup['id']}").json()["movimientos"]) == 2

    contenido = client.get(f"/archivos/{dup['id']}/contenido")
    assert contenido.status_code == 200 and contenido.content == pdf

    # Desvincular no borra el archivo.
    r = client.delete(f"/movimientos/{otro['id']}/adjuntos/{dup['id']}")
    assert r.json()["tiene_comprobante"] is False
    assert client.get(f"/archivos/{dup['id']}").status_code == 200


def test_filtro_sin_comprobante(client, base):
    a = client.post("/captura", json={"texto": "nafta 40k visa"}).json()
    b = client.post("/captura", json={"texto": "super 5000 debito"}).json()
    client.post(f"/movimientos/{b['id']}/adjuntos/subir", files={"archivo": ("t.png", b"\x89PNG fake", "image/png")})
    ids = [m["id"] for m in client.get("/movimientos", params={"sin_comprobante": True}).json()]
    assert ids == [a["id"]]


def test_rechaza_tipo_de_archivo(client, base):
    r = client.post("/archivos", files={"archivo": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415


def test_moneda_distinta_a_la_cuenta(client, base):
    mov = client.post("/captura", json={"texto": "100 usd regalo visa"}).json()
    r = client.post(f"/movimientos/{mov['id']}/confirmar")
    assert r.status_code == 422
