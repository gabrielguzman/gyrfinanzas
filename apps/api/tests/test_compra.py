from datetime import date
from decimal import Decimal

from app.services.compra import cuotas_vs_contado

HOY = date.today()


def test_cuotas_o_contado():
    # 12 cuotas sin interés con 2% de inflación: conviene cuotas
    c = cuotas_vs_contado(Decimal(1_000_000), Decimal(1_000_000), 12, Decimal(2), 1)
    assert c.conviene == "cuotas" and c.tasa_mensual == 0
    assert abs(c.valor_hoy_cuotas - 881_278) <= 2 and c.diferencia > 100_000
    # Cuotas 30% más caras que contado: la tasa implícita (~4% mensual) le gana a la inflación
    c = cuotas_vs_contado(Decimal(1_000_000), Decimal(1_300_000), 12, Decimal(2), 1)
    assert c.conviene == "contado" and Decimal(3) < c.tasa_mensual < Decimal(5)


def contar(client):
    from app.db import get_db
    from app.main import app
    from sqlalchemy import func, select
    from app.models import Movimiento, PlanCuotas
    db = next(app.dependency_overrides[get_db]())
    return db.scalar(select(func.count()).select_from(Movimiento)), db.scalar(select(func.count()).select_from(PlanCuotas))


def test_simular_no_guarda_y_veredictos(client, base):
    client.put("/plan/ajustes", json={"dia_cobro": 1, "ingreso_mensual": "1000000"})
    antes = contar(client)

    chico = client.post("/compra/simular", json={"texto": "auriculares 30k debito"}).json()
    assert chico["veredicto"] == "si" and chico["medio"] == "Débito Galicia"
    assert Decimal(chico["despues"]["hoy"]) < Decimal(chico["antes"]["hoy"])

    grande = client.post("/compra/simular", json={"texto": "moto 2.5M debito"}).json()
    assert grande["veredicto"] == "no"
    assert "te pasarías" in grande["motivos"][0]

    nb = client.post("/compra/simular", json={"texto": "notebook 1.2M en 12 cuotas visa"}).json()
    assert nb["con_tarjeta"] and nb["cuotas"] == 12
    # La cuota (100k) baja lo que tenés para gastar en los meses en que se paga
    difs = [Decimal(a["para_gastar"]) - Decimal(d["para_gastar"]) for a, d in zip(nb["antes"]["meses"], nb["despues"]["meses"])]
    assert Decimal(100_000) in difs
    assert nb["cuotas_contado"]["conviene"] == "cuotas"
    assert nb["primera_cuota"] is not None

    # Nada quedó guardado
    assert contar(client) == antes


def test_lo_compre_crea_el_plan(client, base):
    r = client.post("/movimientos", json={
        "tipo": "gasto", "fecha": HOY.isoformat(), "monto": "600000", "descripcion": "Heladera (6 cuotas)",
        "medio_pago_id": base["medios"]["visa"]["id"], "cuotas": 6})
    assert r.status_code == 201
    t = client.get(f"/tarjetas/{base['visa']['id']}").json()
    assert len(t["planes"]) == 1 and Decimal(t["planes"][0]["monto_cuota"]) == 100_000


def test_sin_monto(client, base):
    assert client.post("/compra/simular", json={"texto": "una bici"}).status_code == 422


def test_sin_medio_sale_de_la_cuenta_con_mas_plata(client, base):
    s = client.post("/compra/simular", json={"texto": "zapatillas 50k"}).json()
    # Galicia (100k) es la que más tiene: el saldo más bajo baja 50k
    assert Decimal(s["despues"]["minimo"]["saldo"]) <= Decimal(s["antes"]["minimo"]["saldo"]) - 50_000
