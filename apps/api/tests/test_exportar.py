import io
from datetime import date

from openpyxl import load_workbook

from tests.test_detectores import gasto


def test_excel_y_csv(client, base):
    hoy = date.today()
    gasto(client, base, 40000, hoy, "Nafta", cat="auto")
    gasto(client, base, 3500.5, hoy, "Café con medialunas", cat="comida")
    client.post("/movimientos", json={"tipo": "ingreso", "fecha": hoy.isoformat(), "monto": "900000", "descripcion": "Sueldo",
                                      "medio_pago_id": base["medios"]["debito"]["id"], "estado": "confirmado"})
    client.post("/movimientos", json={"tipo": "gasto", "fecha": hoy.isoformat(), "monto": "120000", "descripcion": "Heladera (12 cuotas)",
                                      "cuotas": 12, "medio_pago_id": base["medios"]["visa"]["id"], "estado": "confirmado"})
    r = client.get("/exportar?formato=xlsx")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="gyrfinanzas_')
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Movimientos", "Por mes", "Por categoría", "Cuentas", "Cuotas", "Deudas", "Gastos fijos"]
    mov = list(wb["Movimientos"].values)
    assert mov[0][0] == "Fecha" and len(mov) == 5
    nafta = next(f for f in mov if f[2] == "Nafta")
    assert nafta[4] == -40000 and nafta[3] == "Auto"
    mes = list(wb["Por mes"].values)
    assert mes[1][1] == 900000 and mes[1][2] == 163500.5
    cuotas = list(wb["Cuotas"].values)
    assert cuotas[1][1] == "Heladera" and cuotas[1][4] == 12

    c = client.get(f"/exportar?formato=csv&desde={hoy.isoformat()}")
    texto = c.content.decode("utf-8")
    assert texto.startswith("﻿Fecha;Tipo;Descripción")
    assert f"{hoy:%d/%m/%Y};Gasto;Café con medialunas;Comida afuera;-3500,50;ARS" in texto
