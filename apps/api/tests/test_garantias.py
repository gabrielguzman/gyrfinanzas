from datetime import date, timedelta

import pytest

from app.services.captura import interpretar
from app.services.garantias import mas_meses


@pytest.mark.parametrize("texto,monto,meses,desc", [
    ("heladera 850k garantía 1 año", 850000, 12, "Heladera"),
    ("notebook 1.2M con garantia de 2 años en 12 cuotas", 1200000, 24, "Notebook"),
    ("auriculares 45 lucas garantía 6 meses", 45000, 6, "Auriculares"),
    ("tele 600k garantía", 600000, 12, "Tele"),
    ("microondas 180k garantía tres años", 180000, 36, "Microondas"),
    ("nafta 40k", 40000, None, "Nafta"),
])
def test_parser_garantia(texto, monto, meses, desc):
    r = interpretar(texto, [], [], hoy=date(2026, 11, 10))
    assert r.monto == monto
    assert r.garantia_meses == meses
    assert r.descripcion == desc
    if meses:
        assert any(t == "garantia" for _, _, t in r.partes)


def test_mas_meses_fin_de_mes():
    assert mas_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert mas_meses(date(2026, 11, 10), 14) == date(2028, 1, 10)


def test_captura_crea_garantia_y_deshacer_la_borra(client, base):
    mov = client.post("/captura", json={"texto": "heladera 850k visa garantía 1 año"}).json()
    assert mov["garantia"]["vence"] == mas_meses(date.today(), 12).isoformat()
    gs = client.get("/garantias").json()
    assert len(gs) == 1 and gs[0]["producto"] == "Heladera" and gs[0]["movimiento_id"] == mov["id"]
    assert gs[0]["medio_pago"] == "Visa Galicia" and gs[0]["estado"] == "vigente"
    client.delete(f"/movimientos/{mov['id']}")
    assert client.get("/garantias").json() == []


def test_alta_desde_gasto_reparacion_y_avisos(client, base):
    hace = date.today() - timedelta(days=350)
    mov = client.post("/movimientos", json={
        "tipo": "gasto", "fecha": hace.isoformat(), "monto": "420000", "descripcion": "Lavarropas (6 cuotas)",
        "medio_pago_id": base["medios"]["visa"]["id"], "cuotas": 6}).json()
    g = client.post("/garantias", json={"movimiento_id": mov["id"], "meses": 12, "comercio": "Frávega"}).json()
    assert g["producto"] == "Lavarropas" and g["fecha_compra"] == hace.isoformat()
    assert g["estado"] == "por_vencer" and 0 < g["dias_restantes"] <= 30
    # Una sola garantía por compra
    assert client.post("/garantias", json={"movimiento_id": mov["id"]}).status_code == 409
    # Aparece en «Para mirar»
    hs = {h["tipo"]: h for h in client.get("/hallazgos").json()}
    assert hs["garantia"]["titulo"].startswith("La garantía de Lavarropas vence en")
    assert hs["garantia"]["accion"] == {"tipo": "garantia", "valor": g["id"]}

    # Al service 10 días: no corre mientras está allá, y al volver se estira
    envio = date.today() - timedelta(days=10)
    r = client.post(f"/garantias/{g['id']}/reparacion", json={"accion": "enviar", "fecha": envio.isoformat()}).json()
    assert r["estado"] == "en_reparacion"
    assert r["dias_restantes"] == g["dias_restantes"] + 10
    r = client.post(f"/garantias/{g['id']}/reparacion", json={"accion": "volvio"}).json()
    assert r["dias_reparacion"] == 10 and r["en_reparacion_desde"] is None
    assert date.fromisoformat(r["vence"]) == date.fromisoformat(g["vence"]) + timedelta(days=10)

    # Editar los meses recalcula el vencimiento conservando los días de service
    r = client.patch(f"/garantias/{g['id']}", json={"meses": 24}).json()
    assert date.fromisoformat(r["vence"]) == mas_meses(hace, 24) + timedelta(days=10)
    assert r["estado"] == "vigente"


def test_compra_grande_sin_garantia_sugiere_cargarla(client, base):
    hogar = client.post("/categorias", json={"nombre": "Hogar", "palabras": "heladera"}).json()
    mov = client.post("/movimientos", json={
        "tipo": "gasto", "fecha": date.today().isoformat(), "monto": "300000", "descripcion": "Colchón",
        "categoria_id": hogar["id"], "medio_pago_id": base["medios"]["debito"]["id"]}).json()
    client.post(f"/movimientos/{mov['id']}/confirmar")
    hs = {h["tipo"]: h for h in client.get("/hallazgos").json()}
    assert hs["sin_garantia"]["accion"] == {"tipo": "garantia_nueva", "valor": mov["id"]}
    client.post("/garantias", json={"movimiento_id": mov["id"], "meses": 6})
    assert "sin_garantia" not in {h["tipo"] for h in client.get("/hallazgos").json()}


def test_garantia_suelta_con_comprobante(client, base):
    arch = client.post("/archivos", files={"archivo": ("garantia.pdf", b"%PDF-1.4 fake", "application/pdf")}).json()
    g = client.post("/garantias", json={
        "producto": "Aire acondicionado", "fecha_compra": "2025-12-01", "meses": 24, "archivo_id": arch["id"],
        "serie": "AB123"}).json()
    assert g["vence"] == "2027-12-01" and g["archivos"][0]["id"] == arch["id"]
    assert client.post("/garantias", json={"fecha_compra": "2025-12-01"}).status_code == 422
    vencida = client.post("/garantias", json={"producto": "Licuadora", "fecha_compra": "2024-01-01", "meses": 6}).json()
    assert vencida["estado"] == "vencida"
    orden = [x["producto"] for x in client.get("/garantias").json()]
    assert orden == ["Aire acondicionado", "Licuadora"]
