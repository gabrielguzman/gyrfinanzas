"""Genera un resumen de tarjeta de ejemplo (ficticio) con un formato típico de banco argentino."""
from fpdf import FPDF

CABECERA = [
    "BANCO DE EJEMPLO S.A. - TARJETA VISA",
    "CIERRE ACTUAL 26-Nov-26        VENCIMIENTO ACTUAL 05-Dic-26",
    "SALDO ANTERIOR                                   310.000,00",
    "SALDO ACTUAL $                                   128.019,50",
    "PAGO MINIMO $                                     19.050,00",
    "T.N.A. 78,50 %",
    "",
    "FECHA    DETALLE                                 PESOS",
]
DETALLE = [
    "28-10-26 * MERPAGO*KIOSCO LA ESQUINA 004512            3.400,00",
    "30-10-26   YPF SERVICENTRO 001122                     40.000,00",
    "02-11-26   NETFLIX.COM 778811                          11.999,00",
    "05-11-26   SU PAGO EN PESOS                          -310.000,00",
    "15-08-26 K FRAVEGA HELADERA C.03/12 003311            38.900,00",
    "20-10-26 K GARBARINO TV C.01/06 004411                 25.000,00",
    "12-11-26   UBER *TRIP 009988                            6.850,00",
    "26-11-26   IMPUESTO DE SELLOS                            1.230,00",
    "26-11-26   DB IVA 21% COMISION                             640,50",
]


def generar(ruta: str) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Courier", size=9)
    for l in CABECERA + DETALLE:
        pdf.cell(0, 5, l, new_x="LMARGIN", new_y="NEXT")
    pdf.output(ruta)


if __name__ == "__main__":
    generar("resumen_ejemplo.pdf")
