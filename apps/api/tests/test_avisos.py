from datetime import date, datetime

from app.models import PushSuscripcion
from app.services import avisos as svc
from app.services import fijos as svc_fijos
from tests.test_detectores import _db, gasto

SUB = {"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "BPk", "auth": "xyz"}, "dispositivo": "iPhone"}


def _capturar(monkeypatch, status=None):
    enviados = []
    monkeypatch.setattr(svc, "_mandar_uno", lambda sub, datos, vapid: enviados.append(datos) or status)
    return enviados


def test_claves_suscripcion_y_prueba(client, base, monkeypatch):
    e = client.get("/avisos").json()
    assert len(e["clave_publica"]) == 87 and e["dispositivos"] == 0  # punto P-256 sin comprimir, base64url
    assert client.get("/avisos").json()["clave_publica"] == e["clave_publica"]  # no se regenera
    db = _db(client)
    assert svc._vapid(db) is not None
    assert client.post("/avisos/suscribir", json=SUB).json()["dispositivos"] == 1
    assert client.post("/avisos/suscribir", json=SUB).json()["dispositivos"] == 1
    env = _capturar(monkeypatch)
    assert client.post("/avisos/probar", json={}).json() == {"enviadas": 1}
    assert "Así te van a llegar" in env[0]
    # El navegador la dio de baja: se borra
    _capturar(monkeypatch, status=410)
    assert client.post("/avisos/probar", json={}).json() == {"enviadas": 0}
    assert client.get("/avisos").json()["dispositivos"] == 0


def test_tick_manda_una_vez_y_respeta_horario(client, base, monkeypatch):
    client.post("/avisos/suscribir", json=SUB)
    client.put("/plan/ajustes", json={"dia_cobro": 1, "ingreso_mensual": "900000"})
    hoy = date.today()
    client.post("/fijos", json={"nombre": "Internet", "monto": "28990", "dia": hoy.day,
                                "medio_pago_id": base["medios"]["debito"]["id"]})
    env = _capturar(monkeypatch)
    db = _db(client)
    temprano = datetime(hoy.year, hoy.month, hoy.day, 7, 0)
    assert svc.tick(db, temprano) == []
    a = svc.tick(db, temprano.replace(hour=9, minute=10))
    claves = [x.clave.split(":")[0] for x in a]
    assert claves[:2] == ["hoy", "fijos"]
    assert a[0].titulo.startswith("Hoy podés gastar $")
    assert a[1].titulo == "Hoy toca Internet"
    assert len(env) == len(a)
    assert svc.tick(db, temprano.replace(hour=9, minute=20)) == []  # no repite
    assert svc.tick(db, temprano.replace(hour=23)) == []


def test_preferencias(client, base, monkeypatch):
    client.post("/avisos/suscribir", json=SUB)
    client.put("/plan/ajustes", json={"dia_cobro": 1, "ingreso_mensual": "900000"})
    r = client.put("/avisos/preferencias", json={"notif_hoy": False, "notif_hora": "8:5"}).json()
    assert r["preferencias"]["notif_hoy"] is False and r["preferencias"]["notif_hora"] == "08:05"
    _capturar(monkeypatch)
    hoy = date.today()
    a = svc.tick(_db(client), datetime(hoy.year, hoy.month, hoy.day, 8, 30))
    assert "hoy" not in [x.clave.split(":")[0] for x in a]
