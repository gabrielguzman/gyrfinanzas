from datetime import date

from tests.test_detectores import gasto


def test_crear_editar_sugeridas_y_fusionar(client, base):
    assert client.post("/categorias", json={"nombre": "  auto "}).status_code == 409  # ya existe «Auto»
    m = client.post("/categorias", json={"nombre": "Mascotas", "icono": "mascotas", "color": "teal", "palabras": "veterinaria"})
    assert m.status_code == 201
    mid = m.json()["id"]
    sug = client.get("/categorias/sugeridas").json()
    nombres = {s["nombre"] for s in sug}
    assert "Kiosco" in nombres and "Farmacia" in nombres and "Mascotas" not in nombres
    nuevas = client.post("/categorias/sugeridas", json={"nombres": ["Kiosco", "Farmacia", "Inventada"]}).json()
    assert sorted(c["nombre"] for c in nuevas) == ["Farmacia", "Kiosco"]
    kiosco = next(c for c in nuevas if c["nombre"] == "Kiosco")
    i = client.post("/captura/previsualizar", json={"texto": "alfajor 1500 mp"}).json()
    assert i["categoria_id"] == kiosco["id"]

    # Fusionar: los movimientos de Farmacia pasan a Mascotas... no, a Comida (otra del mismo tipo)
    farmacia = next(c for c in nuevas if c["nombre"] == "Farmacia")
    g = gasto(client, base, 4000, date.today(), "farmacity", cat=None)
    client.patch(f"/movimientos/{g['id']}", json={"categoria_id": farmacia["id"]})
    uso = {c["nombre"]: c["cantidad"] for c in client.get("/categorias/uso").json()}
    assert uso["Farmacia"] == 1
    assert client.delete(f"/categorias/{farmacia['id']}?mover_a={base['cats']['sueldo']['id']}").status_code == 422
    assert client.delete(f"/categorias/{farmacia['id']}?mover_a={mid}").status_code == 204
    assert client.get(f"/movimientos/{g['id']}").json()["categoria_id"] == mid
    # Las palabras de la borrada pasan a la otra
    pal = next(c for c in client.get("/categorias").json() if c["id"] == mid)["palabras"]
    assert "farmacity" in pal and "veterinaria" in pal
    # Renombrar a un nombre que ya existe no
    assert client.patch(f"/categorias/{mid}", json={"nombre": "Kiosco"}).status_code == 409
