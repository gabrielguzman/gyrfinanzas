from datetime import date
from decimal import Decimal

import pytest

from app.models import Cuenta, PlanCuotas, TipoLinea
from app.services.resumen_pdf import con_reglas, texto_del_pdf
from app.services.tarjetas import mejor_dia_de_compra, periodo_de_compra
from tests.datos.resumen_ejemplo import generar


@pytest.fixture()
def pdf_ejemplo(tmp_path):
    ruta = tmp_path / "resumen.pdf"
    generar(str(ruta))
    return ruta.read_bytes()


def test_lectura_con_reglas(pdf_ejemplo):
    ex = con_reglas(texto_del_pdf(pdf_ejemplo))
    assert ex.fecha_cierre == date(2026, 11, 26) and ex.fecha_vencimiento == date(2026, 12, 5)
    assert ex.total_ars == Decimal("128019.50") and ex.pago_minimo == Decimal("19050.00")
    assert ex.saldo_anterior == Decimal("310000.00") and ex.tna == Decimal("78.50")
    por_desc = {l.descripcion: l for l in ex.lineas}
    assert por_desc["SU PAGO EN PESOS"].tipo == TipoLinea.pago
    heladera = por_desc["FRAVEGA HELADERA"]
    assert (heladera.tipo, heladera.cuota_n, heladera.cuota_total, heladera.monto) == (TipoLinea.cuota, 3, 12, Decimal("38900.00"))
    assert por_desc["IMPUESTO DE SELLOS"].tipo == TipoLinea.impuesto
    assert "YPF SERVICENTRO" in por_desc and len(ex.lineas) == 9


def test_periodos():
    c = Cuenta(dia_cierre=26)
    assert periodo_de_compra(c, date(2026, 11, 26)) == "2026-11"
    assert periodo_de_compra(c, date(2026, 11, 27)) == "2026-12"
    assert mejor_dia_de_compra(c, date(2026, 11, 3)) == date(2026, 11, 27)
    assert mejor_dia_de_compra(c, date(2026, 11, 28)) == date(2026, 12, 27)


def _tarjeta(client, base):
    client.patch(f"/cuentas/{base['visa']['id']}", json={"dia_cierre": 26, "dia_vencimiento": 5})
    return base["visa"]["id"]


def _db(client):
    from app.db import get_db
    from app.main import app
    return next(app.dependency_overrides[get_db]())


def test_compra_en_cuotas_crea_plan_y_compromisos(client, base):
    tid = _tarjeta(client, base)
    mov = client.post("/captura", json={"texto": "heladera 466800 12 cuotas visa"}).json()
    assert mov["descripcion"] == "Heladera (12 cuotas)"
    client.post(f"/movimientos/{mov['id']}/confirmar")
    t = client.get(f"/tarjetas/{tid}").json()
    assert len(t["planes"]) == 1
    plan = t["planes"][0]
    assert Decimal(plan["monto_cuota"]) == Decimal("38900.00") and plan["cuotas_total"] == 12
    assert plan["cuota_actual"] == 1 and plan["restantes"] == 12
    assert [Decimal(c["total"]) for c in t["compromisos"]] == [Decimal("38900.00")] * 6
    # Confirmar dos veces no duplica el plan
    client.post(f"/movimientos/{mov['id']}/desconfirmar")
    client.post(f"/movimientos/{mov['id']}/confirmar")
    assert len(client.get(f"/tarjetas/{tid}").json()["planes"]) == 1


def test_plan_manual_y_liberacion(client, base):
    tid = _tarjeta(client, base)
    client.post(f"/tarjetas/{tid}/planes", json={"descripcion": "Notebook", "monto_cuota": "47400", "cuotas_total": 9, "cuota_actual": 8})
    client.post(f"/tarjetas/{tid}/planes", json={"descripcion": "Colchón", "monto_cuota": "24400", "cuotas_total": 6, "cuota_actual": 2})
    t = client.get(f"/tarjetas/{tid}").json()
    totales = [Decimal(c["total"]) for c in t["compromisos"]]
    assert totales[:3] == [Decimal("71800"), Decimal("71800"), Decimal("24400")]
    assert Decimal(t["liberacion"]["monto"]) == Decimal("47400") and t["liberacion"]["planes_que_terminan"] == 1


def test_flujo_resumen_completo(client, base, pdf_ejemplo):
    tid = _tarjeta(client, base)
    # Ya tenía cargada la nafta del 30/10 con la Visa
    client.post("/movimientos", json={"tipo": "gasto", "fecha": "2026-10-30", "monto": "40000", "descripcion": "Nafta",
                                      "medio_pago_id": base["medios"]["visa"]["id"]})
    # Y venía pagando la heladera: cuota 3/12 cae en el resumen de noviembre
    client.post(f"/tarjetas/{tid}/planes", json={"descripcion": "Heladera Fravega", "monto_cuota": "38900", "cuotas_total": 12})
    db = _db(client)
    db.query(PlanCuotas).one().primer_periodo = "2026-09"
    db.commit()

    r = client.post(f"/tarjetas/{tid}/resumenes", files={"archivo": ("resumen.pdf", pdf_ejemplo, "application/pdf")})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    res = client.get(f"/resumenes/{rid}").json()
    assert res["estado"] == "revision", res.get("error")
    assert res["periodo"] == "2026-11" and res["metodo"] == "reglas"
    assert res["verificacion"]["cuadra"], res["verificacion"]
    por_desc = {l["descripcion"]: l for l in res["lineas"]}
    assert por_desc["YPF SERVICENTRO"]["accion"] == "vincular"
    assert por_desc["YPF SERVICENTRO"]["movimiento"].startswith("Nafta")
    assert por_desc["SU PAGO EN PESOS"]["accion"] == "ignorar"
    assert por_desc["FRAVEGA HELADERA"]["accion"] == "vincular" and por_desc["FRAVEGA HELADERA"]["plan_id"]
    assert por_desc["GARBARINO TV"]["accion"] == "crear"

    # Decido no cargar el kiosco
    kiosco = next(l for l in res["lineas"] if "KIOSCO" in l["descripcion"])
    client.patch(f"/resumenes/{rid}/lineas/{kiosco['id']}", json={"accion": "ignorar"})

    fin = client.post(f"/resumenes/{rid}/confirmar")
    assert fin.status_code == 200, fin.text
    assert fin.json()["estado"] == "confirmado"
    movs = client.get("/movimientos", params={"limit": 50}).json()
    descs = {m["descripcion"] for m in movs}
    assert {"Garbarino Tv (6 cuotas)", "Uber *Trip", "Impuesto De Sellos"} <= descs
    assert not any("Kiosco" in d for d in descs)
    tv = next(m for m in movs if m["descripcion"].startswith("Garbarino"))
    assert Decimal(tv["monto"]) == Decimal("150000.00") and tv["adjuntos"][0]["rol"] == "resumen"
    sellos = next(m for m in movs if m["descripcion"] == "Impuesto De Sellos")
    nafta = next(m for m in movs if m["descripcion"] == "Nafta")
    assert nafta["tiene_comprobante"] and sellos["origen"] == "pdf"
    t = client.get(f"/tarjetas/{tid}").json()
    assert t["ultimo_resumen"]["total_ars"] == "128019.50"
    assert Decimal(t["ultimo_resumen"]["interes_si_minimo"]) > 0
    assert {"Heladera Fravega", "Garbarino Tv"} <= {p["descripcion"] for p in t["planes"]}
    # Otro resumen del mismo mes no se puede confirmar
    r2 = client.post(f"/tarjetas/{tid}/resumenes", files={"archivo": ("otro.pdf", pdf_ejemplo + b"\n%", "application/pdf")}).json()
    assert client.post(f"/resumenes/{r2['id']}/confirmar").status_code == 409


def test_pdf_ilegible(client, base):
    tid = _tarjeta(client, base)
    r = client.post(f"/tarjetas/{tid}/resumenes", files={"archivo": ("x.pdf", b"%PDF-1.4 roto", "application/pdf")}).json()
    res = client.get(f"/resumenes/{r['id']}").json()
    assert res["estado"] == "error" and res["error"]


def test_solo_pdf_y_solo_tarjetas(client, base):
    tid = _tarjeta(client, base)
    r = client.post(f"/tarjetas/{tid}/resumenes", files={"archivo": ("x.png", b"\x89PNG", "image/png")})
    assert r.status_code == 415
    assert client.get(f"/tarjetas/{base['galicia']['id']}").status_code == 422
