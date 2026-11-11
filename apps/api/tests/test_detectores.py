from datetime import date, datetime, timedelta
from decimal import Decimal

from app.services.detectores import hallazgos
from app.services.semanal import semana_pasada


def _db(client):
    from app.db import get_db
    from app.main import app
    return next(app.dependency_overrides[get_db]())


def gasto(client, base, monto, fecha, desc, cat="comida", medio="mp"):
    r = client.post("/movimientos", json={
        "tipo": "gasto", "fecha": fecha.isoformat(), "monto": str(monto), "descripcion": desc,
        "categoria_id": base["cats"][cat]["id"] if cat else None, "medio_pago_id": base["medios"][medio]["id"]})
    assert r.status_code == 201, r.text
    return r.json()


def mes_atras(hoy: date, n: int, dia: int) -> date:
    a, m = hoy.year, hoy.month - n
    while m < 1:
        a, m = a - 1, m + 12
    return date(a, m, dia)


def test_aumento_de_suscripcion_y_fijos(client, base):
    hoy = date.today()
    sus = client.post("/categorias", json={"nombre": "Suscripciones", "palabras": "netflix"}).json()
    base["cats"]["sus"] = sus
    for n, monto in ((2, 9999), (1, 9999), (0, 11999)):
        gasto(client, base, monto, hoy - timedelta(days=30 * n + 1), "Netflix", cat="sus", medio="visa")
    for n in (2, 1, 0):
        gasto(client, base, 28990, hoy - timedelta(days=30 * n + 2), "Internet", cat="auto", medio="debito")
    hs = client.get("/hallazgos").json()
    tipos = {h["tipo"]: h for h in hs}
    assert tipos["suscripcion_aumento"]["titulo"] == "Netflix subió 20%"
    assert "24.000" in tipos["suscripcion_aumento"]["detalle"]
    assert tipos["fijos"]["titulo"].startswith("Tus 2 gastos fijos suman $ 40.989")
    # Descartar lo saca; restaurar lo devuelve
    client.post("/hallazgos/descartar", json={"clave": tipos["suscripcion_aumento"]["clave"]})
    assert "suscripcion_aumento" not in {h["tipo"] for h in client.get("/hallazgos").json()}
    client.post("/hallazgos/restaurar", json={"clave": tipos["suscripcion_aumento"]["clave"]})
    assert "suscripcion_aumento" in {h["tipo"] for h in client.get("/hallazgos").json()}


def test_hormiga_duplicado_y_comisiones(client, base):
    hoy = date.today()
    for i in range(8):
        gasto(client, base, 2500, hoy - timedelta(days=i * 3), "Café")
    gasto(client, base, 150000, hoy - timedelta(days=5), "Súper", cat="auto", medio="debito")
    gasto(client, base, 40000, hoy, "Nafta", cat="auto", medio="visa")
    gasto(client, base, 40000, hoy, "Nafta", cat="auto", medio="visa")
    com = client.post("/categorias", json={"nombre": "Comisiones e intereses"}).json()
    base["cats"]["com"] = com
    gasto(client, base, 3120, hoy - timedelta(days=2), "Seguro de vida", cat="com", medio="visa")
    hs = {h["tipo"]: h for h in client.get("/hallazgos").json()}
    assert hs["hormiga"]["titulo"] == "8 gastos chicos en Comida afuera: $ 20.000"
    assert hs["duplicado"]["titulo"] == "¿Cargaste dos veces Nafta?" and len(hs["duplicado"]["movimientos"]) == 2
    assert hs["plata_tirada"]["titulo"].startswith("$ 3.120")
    assert client.get("/hallazgos").json()[0]["tipo"] == "duplicado"  # lo más urgente primero


def test_desvio_por_categoria(client, base):
    hoy = date(2026, 11, 20)
    for n in (1, 2, 3):
        gasto(client, base, 10000, mes_atras(hoy, n, 5), "Delivery")
        gasto(client, base, 50000, mes_atras(hoy, n, 6), "Súper", cat="auto", medio="debito")
    gasto(client, base, 30000, date(2026, 11, 8), "Delivery")
    gasto(client, base, 50000, date(2026, 11, 6), "Súper", cat="auto", medio="debito")
    hs = {h.tipo: h for h in hallazgos(_db(client), hoy)}
    assert hs["desvio"].titulo == "Comida afuera: 200% más que tu promedio"


def test_repaso_y_arrepentimientos(client, base):
    hoy = date.today()
    ids = [gasto(client, base, 5000 + i, hoy - timedelta(days=i), f"Delivery {i}")["id"] for i in range(6)]
    rep = client.get("/repaso").json()
    assert len(rep) == 5 and all(m["valio"] is None for m in rep)
    assert client.get("/repaso").json() == rep  # mismo set durante la semana
    for i, mid in enumerate(ids[:5]):
        client.post(f"/movimientos/{mid}/valio", json={"valio": i == 0})
    a = client.get("/repaso/arrepentimientos").json()
    assert a == [{"categoria": "Comida afuera", "respondidos": 5, "no": 4}]
    assert [m["id"] for m in client.get("/repaso").json()] == [ids[5]]


def test_resumen_semanal(client, base):
    hoy = date.today()
    desde, hasta = semana_pasada(hoy)
    gasto(client, base, 12000, desde, "Delivery")
    gasto(client, base, 40000, desde + timedelta(days=2), "Nafta", cat="auto", medio="visa")
    gasto(client, base, 20000, desde - timedelta(days=3), "Nafta", cat="auto", medio="visa")
    s = client.get("/semana").json()
    assert s["desde"] == desde.isoformat() and s["hasta"] == hasta.isoformat()
    assert Decimal(s["gastos"]) == 52000 and Decimal(s["gastos_anterior"]) == 20000
    assert s["top"][0]["nombre"] == "Auto" and s["mayor"]["descripcion"] == "Nafta"


def test_bot_semana_y_repaso(client, base):
    from tests.test_bot import FakeCliente
    from app.bot.logica import Bot
    from app.db import get_db
    from app.main import app
    from app.models import TelegramChat
    Sesion = lambda: next(app.dependency_overrides[get_db]())  # noqa: E731
    db = Sesion()
    db.add(TelegramChat(chat_id=111, nombre="Gabriel"))
    db.commit()
    hoy = date.today()
    gasto(client, base, 12000, hoy - timedelta(days=1), "Delivery")
    cli = FakeCliente()
    bot = Bot(cliente=cli, sesiones=Sesion, codigo="X")
    lunes = datetime.combine(hoy - timedelta(days=hoy.weekday()), datetime.min.time()).replace(hour=10)
    assert bot.semanal_si_toca(lunes.replace(hour=8)) == 0
    assert bot.semanal_si_toca(lunes) == 1
    assert bot.semanal_si_toca(lunes) == 0  # una sola vez por lunes
    assert cli.enviados[0][1].startswith("<b>Tu semana</b>")
    data = next(d for _, _, b in cli.enviados if b for fila in b for t, d in fila if t.startswith("👎"))
    bot.procesar({"update_id": 1, "callback_query": {"id": "c", "data": data, "message": {"message_id": 9, "chat": {"id": 111}}}})
    assert cli.editados[-1][2].startswith("👎")
    assert client.get("/repaso/arrepentimientos").json() == []  # menos de 4 respuestas: todavía no opina


def test_semana_separa_fijos(client, base):
    hoy = date.today()
    desde, _ = semana_pasada(hoy)
    for n in (2, 1):  # el alquiler ya se repitió dos meses: es fijo
        gasto(client, base, 420000, desde - timedelta(days=30 * n), "Alquiler", cat="auto", medio="debito")
    gasto(client, base, 420000, desde, "Alquiler", cat="auto", medio="debito")
    gasto(client, base, 10000, desde + timedelta(days=1), "Delivery")
    gasto(client, base, 8000, desde - timedelta(days=2), "Delivery")
    s = client.get("/semana").json()
    assert Decimal(s["fijos"]) == 420000 and Decimal(s["variables"]) == 10000 and Decimal(s["variables_anterior"]) == 8000
