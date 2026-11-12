import io
from datetime import date, datetime, timedelta

from openpyxl import load_workbook

from app.services import avisos as svc_avisos
from app.services import racha as svc_racha
from tests.test_detectores import _db, gasto


def test_etiquetas_al_cargar_y_totales(client, base):
    i = client.post("/captura/previsualizar", json={"texto": "cena 45k mp #Vacaciones2027 #salta"}).json()
    assert i["etiquetas"] == ["vacaciones2027", "salta"] and float(i["monto"]) == 45000
    assert i["descripcion"] == "Cena"
    assert any(p["tipo"] == "etiqueta" for p in i["partes"])
    m = client.post("/captura", json={"texto": "cena 45k mp #Vacaciones2027 #salta"}).json()
    assert m["etiquetas"] == ["salta", "vacaciones2027"]
    client.post(f"/movimientos/{m['id']}/confirmar")
    # Etiqueta activa: todo lo que cargás la lleva
    client.put("/etiquetas/activa", json={"nombre": "#Vacaciones 2027"})  # se normaliza a vacaciones-2027
    assert client.get("/etiquetas").json()["activa"] == "vacaciones-2027"
    client.put("/etiquetas/activa", json={"nombre": "vacaciones2027"})
    n = client.post("/movimientos", json={"tipo": "gasto", "fecha": date.today().isoformat(), "monto": "30000",
                                          "descripcion": "Nafta", "medio_pago_id": base["medios"]["mp"]["id"],
                                          "categoria_id": base["cats"]["auto"]["id"], "estado": "confirmado"}).json()
    assert n["etiquetas"] == ["vacaciones2027"]
    lista = client.get("/etiquetas").json()
    v = next(e for e in lista["etiquetas"] if e["nombre"] == "vacaciones2027")
    assert (v["total"], v["cantidad"], v["activa"]) == ("75000.00", 2, True)
    assert [c["nombre"] for c in v["por_categoria"]] == ["Sin categoría", "Auto"]
    # Filtro y edición
    assert len(client.get("/movimientos?etiqueta=vacaciones2027").json()) == 2
    r = client.patch(f"/movimientos/{n['id']}", json={"etiquetas": ["auto"]}).json()
    assert r["etiquetas"] == ["auto"]
    # Export
    wb = load_workbook(io.BytesIO(client.get("/exportar").content))
    fila = next(f for f in wb["Movimientos"].values if f[2] == "Cena")
    assert fila[10] == "#salta #vacaciones2027"
    # Renombrar y borrar
    client.put("/etiquetas/activa", json={"nombre": ""})
    assert client.get("/etiquetas").json()["activa"] is None
    assert client.patch(f"/etiquetas/{v['id']}", json={"nombre": "Salta"}).status_code == 409
    assert client.delete(f"/etiquetas/{v['id']}").status_code == 204
    assert client.get(f"/movimientos/{m['id']}").json()["etiquetas"] == ["salta"]


def test_racha(client, base, monkeypatch):
    hoy = date.today()
    for k in (1, 2, 4):
        gasto(client, base, 1000, hoy - timedelta(days=k), "café")
    r = client.get("/racha").json()
    # Cargué todo hoy (creado hoy) → cuenta hoy; ayer y anteayer por fecha; el día 3 falta
    assert r["hoy"] == "cargado" and r["actual"] == 3
    client.post("/racha/sin-gastos", json={"fecha": (hoy - timedelta(days=3)).isoformat()})
    r = client.get("/racha").json()
    assert r["actual"] == 5 and r["mejor"] == 5 and len(r["dias"]) == 14
    assert client.post("/racha/sin-gastos", json={"fecha": (hoy + timedelta(days=1)).isoformat()}).status_code == 422


def test_aviso_de_racha(client, base, monkeypatch):
    db = _db(client)
    client.post("/avisos/suscribir", json={"endpoint": "https://push.example.com/x", "keys": {"p256dh": "a", "auth": "b"}})
    monkeypatch.setattr(svc_avisos, "_mandar_uno", lambda *a: None)
    manana = date.today() + timedelta(days=1)
    # Mañana a las 21 todavía no cargaste nada: aviso suave
    monkeypatch.setattr(svc_racha, "calcular", lambda db, hoy: svc_racha.Racha(4, 6, "vacio", []))
    a = svc_avisos.tick(db, datetime(manana.year, manana.month, manana.day, 21, 5))
    assert [x.titulo for x in a if x.clave.startswith("racha")] == ["No cortes tu racha de 4 días"]
