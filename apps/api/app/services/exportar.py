"""Exportar todo a Excel (varias hojas, con formato) o CSV (movimientos, para Excel en castellano)."""
import csv
import io
from collections import defaultdict
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Cuenta, Deuda, EstadoMovimiento, GastoFijo, Moneda, Movimiento, PlanCuotas, TipoDeuda, TipoMovimiento,
)
from app.services import deudas as svc_deudas
from app.services import tarjetas as svc_t
from app.services.saldos import saldos_por_cuenta

CERO = Decimal("0")
TIPO = {"gasto": "Gasto", "ingreso": "Ingreso", "transferencia": "Transferencia"}
TIPO_CUENTA = {"banco": "Banco", "billetera": "Billetera", "efectivo": "Efectivo", "tarjeta_credito": "Tarjeta de crédito"}
TIPO_DEUDA = {"prestamo": "Préstamo", "debo": "Le debés", "me_deben": "Te deben"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

COLUMNAS = ["Fecha", "Tipo", "Descripción", "Categoría", "Importe", "Moneda", "Medio de pago", "Cuenta",
            "Cuenta destino", "Cuotas", "Estado", "Lo que escribiste"]


def movimientos(db: Session, desde: date | None, hasta: date | None, pendientes: bool = False) -> list[Movimiento]:
    q = (select(Movimiento)
         .options(selectinload(Movimiento.categoria), selectinload(Movimiento.medio_pago),
                  selectinload(Movimiento.cuenta), selectinload(Movimiento.cuenta_destino))
         .order_by(Movimiento.fecha, Movimiento.creado))
    if not pendientes:
        q = q.where(Movimiento.estado == EstadoMovimiento.confirmado)
    if desde:
        q = q.where(Movimiento.fecha >= desde)
    if hasta:
        q = q.where(Movimiento.fecha <= hasta)
    return list(db.scalars(q))


def _importe(m: Movimiento) -> Decimal:
    return -m.monto if m.tipo == TipoMovimiento.gasto else m.monto


def _fila(m: Movimiento) -> list:
    return [
        m.fecha, TIPO[m.tipo.value], m.descripcion, m.categoria.nombre if m.categoria else "",
        _importe(m), m.moneda.value, m.medio_pago.nombre if m.medio_pago else "",
        m.cuenta.nombre if m.cuenta else "", m.cuenta_destino.nombre if m.cuenta_destino else "",
        m.cuotas or "", "Confirmado" if m.estado == EstadoMovimiento.confirmado else "En la bandeja",
        m.texto_original or "",
    ]


# ───────────────────────── CSV ─────────────────────────
def csv_movimientos(db: Session, desde: date | None = None, hasta: date | None = None) -> bytes:
    """Separado por «;» y con coma decimal: Excel en castellano lo abre bien con doble clic."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(COLUMNAS)
    for m in movimientos(db, desde, hasta):
        f = _fila(m)
        f[0] = m.fecha.strftime("%d/%m/%Y")
        f[4] = f"{f[4]:.2f}".replace(".", ",")
        w.writerow(f)
    return ("﻿" + buf.getvalue()).encode("utf-8")


# ───────────────────────── Excel ─────────────────────────
TITULO = Font(bold=True, color="FFFFFF")
FONDO = PatternFill("solid", fgColor="2F5BEA")
PESOS = '"$" #,##0.00;[Red]-"$" #,##0.00'
FECHA = "dd/mm/yyyy"


def _hoja(wb: Workbook, nombre: str, columnas: list[str], filas: list[list], formatos: dict[int, str] | None = None,
          anchos: dict[int, int] | None = None, primera: bool = False):
    ws = wb.active if primera else wb.create_sheet()
    ws.title = nombre
    ws.append(columnas)
    for c in ws[1]:
        c.font, c.fill, c.alignment = TITULO, FONDO, Alignment(vertical="center")
    ws.row_dimensions[1].height = 22
    for f in filas:
        ws.append(f)
    formatos = formatos or {}
    for i, col in enumerate(columnas, start=1):
        letra = get_column_letter(i)
        if i in formatos:
            for celda in ws[letra][1:]:
                celda.number_format = formatos[i]
        largo = max([len(str(col))] + [len(str(f[i - 1])) for f in filas[:300] if i - 1 < len(f)])
        ws.column_dimensions[letra].width = (anchos or {}).get(i, min(48, max(10, largo + 2)))
    ws.freeze_panes = "A2"
    if filas:
        ws.auto_filter.ref = ws.dimensions
    return ws


def _periodo(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def _nombre_mes(p: str) -> str:
    a, m = p.split("-")
    return f"{MESES[int(m) - 1]} {a}"


def excel(db: Session, desde: date | None = None, hasta: date | None = None, hoy: date | None = None) -> bytes:
    hoy = hoy or date.today()
    wb = Workbook()
    movs = movimientos(db, desde, hasta)

    # 1) Movimientos
    _hoja(wb, "Movimientos", COLUMNAS, [_fila(m) for m in movs], {1: FECHA, 5: PESOS},
          {3: 34, 12: 40}, primera=True)

    # 2) Resumen por mes y 3) por categoría (pesos; las compras en cuotas van enteras en el mes de compra)
    por_mes: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"ing": CERO, "gas": CERO})
    por_cat: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: CERO))
    for m in movs:
        if m.moneda != Moneda.ARS or m.tipo == TipoMovimiento.transferencia:
            continue
        p = _periodo(m.fecha)
        if m.tipo == TipoMovimiento.ingreso:
            por_mes[p]["ing"] += m.monto
        else:
            por_mes[p]["gas"] += m.monto
            por_cat[m.categoria.nombre if m.categoria else "Sin categoría"][p] += m.monto
    meses = sorted(por_mes)
    filas = [[_nombre_mes(p), v["ing"], v["gas"], v["ing"] - v["gas"]] for p, v in ((p, por_mes[p]) for p in meses)]
    if filas:
        filas.append(["Total", sum((f[1] for f in filas), CERO), sum((f[2] for f in filas), CERO),
                      sum((f[3] for f in filas), CERO)])
    ws = _hoja(wb, "Por mes", ["Mes", "Ingresos", "Gastos", "Te quedó"], filas, {2: PESOS, 3: PESOS, 4: PESOS})
    if filas:
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
    cats = sorted(por_cat, key=lambda c: -sum(por_cat[c].values()))
    _hoja(wb, "Por categoría", ["Categoría"] + [_nombre_mes(p) for p in meses] + ["Total"],
          [[c] + [por_cat[c].get(p, CERO) for p in meses] + [sum(por_cat[c].values(), CERO)] for c in cats],
          {i: PESOS for i in range(2, len(meses) + 3)})

    # 4) Cuentas
    saldos = saldos_por_cuenta(db)
    _hoja(wb, "Cuentas", ["Cuenta", "Tipo", "Moneda", "Saldo hoy"],
          [[c.nombre, TIPO_CUENTA[c.tipo.value], c.moneda.value, saldos.get(c.id, CERO)]
           for c in db.scalars(select(Cuenta).where(Cuenta.archivada.is_(False)).order_by(Cuenta.nombre))],
          {4: PESOS})

    # 5) Compras en cuotas que siguen
    filas = []
    for p in db.scalars(select(PlanCuotas).options(selectinload(PlanCuotas.cuenta)).order_by(PlanCuotas.primer_periodo)):
        prox = svc_t.proximo_periodo(p.cuenta, hoy)
        restantes = max(0, min(p.cuotas_total, p.cuotas_total - svc_t.distancia(p.primer_periodo, prox)))
        if restantes:
            filas.append([p.cuenta.nombre, p.descripcion, p.monto_cuota, p.cuotas_total, restantes,
                          p.monto_cuota * restantes, _nombre_mes(svc_t.ultimo_periodo(p))])
    _hoja(wb, "Cuotas", ["Tarjeta", "Compra", "Cuota", "Cuotas", "Faltan", "Te falta pagar", "Última cuota"],
          filas, {3: PESOS, 6: PESOS})

    # 6) Deudas
    filas = []
    for d in db.scalars(select(Deuda).where(Deuda.cerrada.is_(False)).order_by(Deuda.tipo, Deuda.nombre)):
        e = svc_deudas.estado(db, d, hoy)
        if e.saldo > 0:
            filas.append([d.nombre, TIPO_DEUDA[d.tipo.value], d.moneda.value, e.saldo,
                          svc_deudas.cuota_sugerida(d, e) if d.tipo == TipoDeuda.prestamo else None,
                          float(d.tna) / 100 if d.tna else None, e.proximo_vencimiento])
    ws = _hoja(wb, "Deudas", ["Nombre", "Tipo", "Moneda", "Saldo", "Cuota", "TNA", "Próximo vencimiento"],
               filas, {4: PESOS, 5: PESOS, 6: "0.0%", 7: FECHA})

    # 7) Gastos fijos
    _hoja(wb, "Gastos fijos", ["Nombre", "Monto", "Día", "Categoría", "Medio de pago"],
          [[f.nombre, f.monto, f.dia, f.categoria.nombre if f.categoria else "", f.medio_pago.nombre if f.medio_pago else ""]
           for f in db.scalars(select(GastoFijo).where(GastoFijo.activo.is_(True)).order_by(GastoFijo.dia))],
          {2: PESOS})

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def nombre_archivo(ext: str, desde: date | None, hasta: date | None, hoy: date | None = None) -> str:
    hoy = hoy or date.today()
    if desde and hasta:
        return f"gyrfinanzas_{desde:%Y-%m-%d}_a_{hasta:%Y-%m-%d}.{ext}"
    return f"gyrfinanzas_{hoy:%Y-%m-%d}.{ext}"

