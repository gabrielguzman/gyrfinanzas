import pytest

from app import auth
from app.config import settings


@pytest.fixture()
def con_login(monkeypatch):
    monkeypatch.setattr(settings, "app_password_hash", auth.generar_hash("mate y medialunas"))
    monkeypatch.setattr(settings, "secret_key", "clave-de-prueba")
    auth._fallos.clear()


def test_hash():
    h = auth.generar_hash("secreto")
    assert h.startswith("scrypt:") and "$" not in h and auth.verificar("secreto", h) and not auth.verificar("otro", h)
    assert not auth.verificar("secreto", "basura")


def test_sin_contraseña_queda_abierta(client):
    assert client.get("/cuentas").status_code == 200
    assert client.get("/auth/estado").json() == {"requiere": False, "ok": True}


def test_login(client, con_login):
    assert client.get("/cuentas").status_code == 401
    assert client.get("/salud").status_code == 200
    assert client.get("/auth/estado").json() == {"requiere": True, "ok": False}
    assert client.post("/auth/login", json={"password": "otra"}).status_code == 401
    r = client.post("/auth/login", json={"password": "mate y medialunas"})
    assert r.status_code == 200 and auth.COOKIE in r.cookies
    assert client.get("/cuentas").status_code == 200
    assert client.get("/auth/estado").json()["ok"] is True
    client.post("/auth/logout")
    client.cookies.clear()
    assert client.get("/cuentas").status_code == 401


def test_sesion_vencida_o_falsa(con_login):
    t = auth.crear_sesion(ahora=0)
    assert not auth.sesion_valida(t)
    vence = t.split(".")[0]
    assert not auth.sesion_valida(f"{int(vence) + 10**9}.{t.split('.')[1]}")


def test_limite_de_intentos(client, con_login):
    for _ in range(5):
        assert client.post("/auth/login", json={"password": "no"}).status_code == 401
    assert client.post("/auth/login", json={"password": "mate y medialunas"}).status_code == 429
