from datetime import date

from tests.test_detectores import gasto


def test_regla_aplica_a_anteriores_y_a_lo_nuevo(client, base):
    transp = client.post("/categorias", json={"nombre": "Transporte"}).json()
    hoy = date.today()
    a = gasto(client, base, 3500, hoy, "Uber al centro", cat="comida")
    gasto(client, base, 4200, hoy, "uber", cat=None)
    gasto(client, base, 9000, hoy, "Uber Eats pizza", cat="comida")
    gasto(client, base, 1000, hoy, "Superuber", cat=None)  # no es la palabra

    s = client.get(f"/reglas/sugerencia/{a['id']}").json()
    assert s["texto"] == "uber" and s["total"] == 2

    p = client.post("/reglas/previa", json={"texto": "Úber", "categoria_id": transp["id"]}).json()
    assert (p["texto"], p["total"], p["a_cambiar"]) == ("uber", 3, 3)

    r = client.post("/reglas", json={"texto": "Uber", "categoria_id": transp["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["cambiados"] == 3
    # «uber eats» es más específica y gana
    client.post("/reglas", json={"texto": "uber eats", "categoria_id": base["cats"]["comida"]["id"], "aplicar": False})

    i = client.post("/captura/previsualizar", json={"texto": "uber 5k mp"}).json()
    assert i["categoria_id"] == transp["id"]
    i = client.post("/captura/previsualizar", json={"texto": "uber eats 12k mp"}).json()
    assert i["categoria_id"] == base["cats"]["comida"]["id"]
    m = client.post("/movimientos", json={"tipo": "gasto", "fecha": hoy.isoformat(), "monto": "100", "descripcion": "Uber",
                                          "medio_pago_id": base["medios"]["mp"]["id"]}).json()
    assert m["categoria_id"] == transp["id"]

    assert [x["texto"] for x in client.get("/reglas").json()] == ["uber", "uber eats"]


def test_recategorizar_en_lote(client, base):
    hoy = date.today()
    ids = [gasto(client, base, 100 * k, hoy, f"cosa {k}", cat="comida")["id"] for k in range(1, 4)]
    r = client.post("/movimientos/lote/categoria", json={"ids": ids[:2], "categoria_id": base["cats"]["auto"]["id"]}).json()
    assert r["actualizados"] == 2
    cats = {m["id"]: m["categoria"] for m in client.get("/movimientos").json()}
    assert [cats[i] for i in ids] == ["Auto", "Auto", "Comida afuera"]
