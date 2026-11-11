import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.config import settings
from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _db():
        db = Sesion()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    original = settings.upload_dir
    settings.upload_dir = str(tmp_path / "uploads")
    with TestClient(app) as c:
        yield c
    settings.upload_dir = original
    app.dependency_overrides.clear()


@pytest.fixture()
def base(client):
    """Cuentas, medios y categorías típicos."""
    galicia = client.post("/cuentas", json={"nombre": "Galicia", "tipo": "banco", "saldo_inicial": "100000"}).json()
    visa = client.post("/cuentas", json={"nombre": "Visa Galicia", "tipo": "tarjeta_credito", "dia_cierre": 26}).json()
    mp = client.post("/cuentas", json={"nombre": "Mercado Pago", "tipo": "billetera", "saldo_inicial": "20000"}).json()
    medios = {
        "debito": client.post("/medios-pago", json={"nombre": "Débito Galicia", "tipo": "debito", "cuenta_id": galicia["id"], "alias": "debito"}).json(),
        "visa": client.post("/medios-pago", json={"nombre": "Visa Galicia", "tipo": "credito", "cuenta_id": visa["id"], "alias": "visa"}).json(),
        "mp": client.post("/medios-pago", json={"nombre": "Mercado Pago", "tipo": "qr", "cuenta_id": mp["id"], "alias": "mp,mercadopago"}).json(),
    }
    cats = {
        "auto": client.post("/categorias", json={"nombre": "Auto", "palabras": "nafta,ypf"}).json(),
        "comida": client.post("/categorias", json={"nombre": "Comida afuera", "palabras": "cafe"}).json(),
        "sueldo": client.post("/categorias", json={"nombre": "Sueldo", "tipo": "ingreso", "palabras": "sueldo"}).json(),
    }
    return {"galicia": galicia, "visa": visa, "mp": mp, "medios": medios, "cats": cats}


@pytest.fixture(autouse=True)
def cotizacion_fija(monkeypatch):
    """Sin internet en los tests: el dólar MEP a 1.200."""
    from decimal import Decimal
    from app.services import cotizacion
    monkeypatch.setattr(cotizacion, "descargar", lambda: {
        "bolsa": Decimal("1200"), "blue": Decimal("1250"), "oficial": Decimal("1000")})
