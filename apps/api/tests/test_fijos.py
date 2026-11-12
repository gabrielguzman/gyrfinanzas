import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import EstadoMovimiento, GastoFijo, Movimiento, OrigenMovimiento
from app.services import fijos as svc
from app.services.detectores import hallazgos, recurrentes
from tests.test_detectores import _db, gasto

HOY = date(2026, 11, 11)


def _internet(client, base):
    for f in (date(2026, 8, 5), date(2026, 9, 5), date(2026, 10, 5)):
        gasto(client, base, 28990, f, "Internet", cat="auto", medio="debito")


def test_sugerido_activar_y_generar(client, base):
    _internet(client, base)
    db = _db(client)
    sug = svc.sugeridos(db, HOY)
    assert [s.nombre for s in sug] == ["Internet"] and sug[0].dia == 5
    assert any(h.tipo == "fijos_sugeridos" for h in hallazgos(db, HOY))

    f = svc.desde_detectado(db, sug[0].clave, hoy=HOY)
    db.commit()
    assert (f.dia, f.monto, f.activo) == (5, Decimal("28990.00"), True)
    assert svc.sugeridos(db, HOY) == []

    nuevos = svc.generar(db, HOY)
    assert len(nuevos) == 1
    m = nuevos[0]
    assert (m.fecha, m.estado, m.origen, m.monto) == (date(2026, 11, 5), EstadoMovimiento.pendiente, OrigenMovimiento.fijo, Decimal("28990.00"))
    assert m.medio_pago_id is not None and m.categoria_id is not None
    assert svc.generar(db, HOY) == []  # idempotente

    # Confirmar con otro monto: el mes que viene propone el nuevo
    r = client.patch(f"/movimientos/{m.id}", json={"monto": "31500"})
    assert r.status_code == 200, r.text
    assert client.post(f"/movimientos/{m.id}/confirmar").status_code == 200
    db.expire_all()
    assert db.get(GastoFijo, f.id).monto == Decimal("31500.00")
    assert svc.generar(db, date(2026, 12, 4)) == []          # todavía no toca
    dic = svc.generar(db, date(2026, 12, 5))
    assert len(dic) == 1 and dic[0].monto == Decimal("31500.00")


def test_atrasado_y_no_es_fijo(client, base):
    _internet(client, base)
    db = _db(client)
    clave = svc.sugeridos(db, HOY)[0].clave
    svc.desde_detectado(db, clave, hoy=HOY)
    db.commit()
    svc.generar(db, HOY)
    hs = {h.tipo: h for h in hallazgos(db, HOY)}
    assert hs["fijo_atrasado"].titulo == "Internet: ¿ya lo pagaste?"
    assert "hace 6 días" in hs["fijo_atrasado"].detalle

    # «No es un fijo»: deja de contar y de sugerirse
    svc.desde_detectado(db, clave, activo=False, hoy=HOY)
    db.commit()
    assert recurrentes(db, HOY) == [] and svc.sugeridos(db, HOY) == []


def test_ya_pagado_no_se_genera_y_carga_manual_reemplaza(client, base):
    _internet(client, base)
    gasto(client, base, 29500, date(2026, 11, 3), "Internet", cat="auto", medio="debito")
    db = _db(client)
    f = svc.desde_detectado(db, svc.sugeridos(db, HOY)[0].clave, hoy=HOY)
    db.commit()
    assert f.ultimo_periodo == "2026-11" and svc.generar(db, HOY) == []

    # Diciembre: se genera el 5; si lo cargás vos (Telegram, texto), el tuyo manda
    gen = svc.generar(db, date(2026, 12, 5))
    assert len(gen) == 1
    r = client.post("/movimientos", json={"tipo": "gasto", "fecha": "2026-12-06", "monto": "30100", "descripcion": "Internet",
                                          "medio_pago_id": base["medios"]["debito"]["id"], "estado": "confirmado"})
    assert r.status_code == 201, r.text
    db.expire_all()
    movs = db.scalars(select(Movimiento).where(Movimiento.fijo_id == f.id, Movimiento.fecha >= date(2026, 12, 1))).all()
    assert [(m.monto, m.estado) for m in movs] == [(Decimal("30100.00"), EstadoMovimiento.confirmado)]


def test_api_manual_saltear_y_plan(client, base):
    r = client.post("/fijos", json={"nombre": "Alquiler", "monto": "450000", "dia": 1,
                                    "medio_pago_id": base["medios"]["debito"]["id"]})
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["este_mes"] == "en_bandeja"  # el día 1 ya pasó (o es hoy): está en la bandeja
    lista = client.get("/fijos").json()
    assert lista["total_mensual"] == "450000"
    assert [x["nombre"] for x in lista["fijos"]] == ["Alquiler"]
    # Cuenta en el plan como fijo aunque no haya pagos anteriores
    db = _db(client)
    assert [r.nombre for r in recurrentes(db, date.today())] == ["Alquiler"]
    # Este mes no va
    s = client.post(f"/fijos/{f['id']}/saltear").json()
    assert s["este_mes"] == "por_venir"
    pend = client.get("/movimientos?estado=pendiente").json()
    assert not [m for m in pend if m["descripcion"] == "Alquiler"]
    assert client.delete(f"/fijos/{f['id']}").status_code == 204
    assert client.get("/fijos").json()["total_mensual"] == "0"


def test_no_mensuales(client, base):
    from app.services.plan import calendario
    db = _db(client)
    f = svc.nuevo(db, nombre="Patente", monto=Decimal("90000"), dia=10, cada_meses=2, mes_inicio=12,
                  medio_pago_id=uuid.UUID(base["medios"]["debito"]["id"]), hoy=HOY)
    db.commit()
    assert svc.por_mes(f) == Decimal("45000")
    assert svc.proxima(f, HOY) == date(2026, 12, 10)
    assert svc.ocurrencias(f, HOY, date(2027, 6, 30)) == [date(2026, 12, 10), date(2027, 2, 10), date(2027, 4, 10), date(2027, 6, 10)]
    # Noviembre no toca; diciembre sí
    assert svc.generar(db, HOY) == []
    assert len(svc.generar(db, date(2026, 12, 10))) == 1
    # En el plan cuenta lo que hay que apartar por mes
    r = [x for x in recurrentes(db, HOY) if x.nombre == "Patente"][0]
    assert (r.ultimo, r.cada_meses, r.monto_total) == (Decimal("45000"), 2, Decimal("90000.00"))
    # Aviso unas semanas antes
    hs = {h.tipo: h for h in hallazgos(db, date(2026, 11, 25))}
    assert hs["no_mensual"].titulo == "Patente: es en 15 días"
    assert "no_mensual" not in {h.tipo for h in hallazgos(db, HOY)}
    # En el calendario aparece entero en su fecha
    client.put("/plan/ajustes", json={"dia_cobro": 1, "ingreso_mensual": "900000"})
    ev = [e for e in calendario(db, HOY, 40).eventos if e.titulo == "Patente"]
    assert [(e.fecha, e.monto) for e in ev] == [(date(2026, 12, 10), Decimal("-90000.00"))]


def test_api_frecuencia(client, base):
    r = client.post("/fijos", json={"nombre": "Seguro", "monto": "120000", "dia": 20, "cada_meses": 12}).json()
    assert r["cada_meses"] == 12 and r["mes_inicio"] in range(1, 13) and r["por_mes"] == "10000"
    l = client.get("/fijos").json()
    assert l["total_mensual"] == "10000"
    r = client.patch(f"/fijos/{r['id']}", json={"cada_meses": 1}).json()
    assert r["mes_inicio"] is None and r["por_mes"] == "120000"
    assert client.post("/fijos", json={"nombre": "X", "monto": "1", "dia": 1, "cada_meses": 5}).status_code == 422
