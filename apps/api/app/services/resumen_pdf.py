"""Lectura de resúmenes de tarjeta en PDF.

Dos caminos con la misma salida (`Extraccion`):
- con IA (Claude), si hay ANTHROPIC_API_KEY: entiende cualquier formato de banco;
- con reglas, sin clave: lee el texto del PDF y busca fechas, montos y cuotas.
En ambos casos el usuario revisa antes de confirmar, y la verificación de que
la suma cuadra con el total avisa si algo se leyó mal.
"""
import base64
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx

from app.config import settings
from app.models import Moneda, TipoLinea

log = logging.getLogger("gyr.resumen")


@dataclass
class LineaExtraida:
    fecha: date | None
    descripcion: str
    monto: Decimal
    moneda: Moneda = Moneda.ARS
    tipo: TipoLinea = TipoLinea.consumo
    cuota_n: int | None = None
    cuota_total: int | None = None


@dataclass
class Extraccion:
    metodo: str
    fecha_cierre: date | None = None
    fecha_vencimiento: date | None = None
    saldo_anterior: Decimal | None = None
    total_ars: Decimal | None = None
    total_usd: Decimal | None = None
    pago_minimo: Decimal | None = None
    tna: Decimal | None = None
    lineas: list[LineaExtraida] = field(default_factory=list)


class ErrorLectura(RuntimeError):
    pass


# ───────────────────────── utilidades ─────────────────────────
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
         "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}
RE_MONTO = r"-?\d{1,3}(?:\.\d{3})*,\d{2}-?"
RE_FECHA = r"(\d{1,2})[-/ .]([A-Za-z]{3}|\d{1,2})[a-z]*\.?[-/ .](\d{2,4})"


def monto_ar(s: str) -> Decimal | None:
    s = s.strip().replace(" ", "")
    negativo = s.startswith("-") or s.endswith("-")
    s = s.strip("-").replace(".", "").replace(",", ".")
    try:
        v = Decimal(s)
    except InvalidOperation:
        return None
    return -v if negativo else v


def fecha_ar(dia: str, mes: str, anio: str) -> date | None:
    try:
        m = int(mes) if mes.isdigit() else MESES.get(mes[:3].lower())
        a = int(anio)
        a = a + 2000 if a < 100 else a
        return date(a, m, int(dia)) if m else None
    except (ValueError, TypeError):
        return None


def texto_del_pdf(contenido: bytes) -> str:
    from pypdf import PdfReader
    try:
        lector = PdfReader(io.BytesIO(contenido))
        if lector.is_encrypted:
            lector.decrypt("")
        return "\n".join((p.extract_text() or "") for p in lector.pages)
    except Exception as e:  # PDF dañado o protegido
        raise ErrorLectura(f"No pude leer el PDF ({type(e).__name__}). ¿Está protegido con contraseña?")


# ───────────────────────── con reglas ─────────────────────────
RE_CUOTA = re.compile(r"\b(?:C\.?|CUOTA|CTA\.?)\s*(\d{1,2})\s*/\s*(\d{1,2})\b", re.I)
RE_LINEA = re.compile(rf"^\s*{RE_FECHA}\s+(.+?)\s+({RE_MONTO})(?:\s+({RE_MONTO}))?\s*$")
IMPUESTOS = ("IMPUESTO", "IMP.", "IVA", "SELLOS", "PERCEP", "IIBB", "DB.RG", "RG ", "LEY 27")
INTERESES = ("INTERES", "INTERÉS", "PUNITORIO", "FINANCIACION", "FINANCIACIÓN")
CARGOS = ("COMISION", "COMISIÓN", "MANTENIMIENTO", "SEGURO", "CARGO", "RENOVACION", "RENOVACIÓN")
PAGOS = ("SU PAGO", "PAGO EN PESOS", "PAGO EN DOLARES", "PAGO EN DÓLARES", "PAGO RECIBIDO")


def _tipo(desc: str) -> TipoLinea:
    d = desc.upper()
    if any(p in d for p in PAGOS):
        return TipoLinea.pago
    if any(p in d for p in INTERESES):
        return TipoLinea.interes
    if any(p in d for p in IMPUESTOS):
        return TipoLinea.impuesto
    if any(p in d for p in CARGOS):
        return TipoLinea.cargo
    return TipoLinea.consumo


def _campo(texto: str, etiquetas: tuple[str, ...]) -> Decimal | None:
    for et in etiquetas:
        m = re.search(rf"{et}[^\d\n-]{{0,40}}({RE_MONTO})", texto, re.I)
        if m:
            return monto_ar(m.group(1))
    return None


def _fecha_campo(texto: str, etiquetas: tuple[str, ...]) -> date | None:
    for et in etiquetas:
        m = re.search(rf"{et}[^\d\n]{{0,30}}{RE_FECHA}", texto, re.I)
        if m:
            f = fecha_ar(*m.groups())
            if f:
                return f
    return None


def con_reglas(texto: str) -> Extraccion:
    ex = Extraccion(metodo="reglas")
    ex.fecha_cierre = _fecha_campo(texto, ("CIERRE ACTUAL", "FECHA DE CIERRE", "CIERRE"))
    ex.fecha_vencimiento = _fecha_campo(texto, ("VENCIMIENTO ACTUAL", "FECHA DE VENCIMIENTO", "VENCIMIENTO", "VTO"))
    ex.saldo_anterior = _campo(texto, ("SALDO ANTERIOR",))
    ex.total_ars = _campo(texto, ("SALDO ACTUAL", "TOTAL A PAGAR", "SALDO A PAGAR"))
    ex.pago_minimo = _campo(texto, ("PAGO M[IÍ]NIMO",))
    m_usd = re.search(rf"SALDO ACTUAL[^\n]*?U\$?S[^\d\n-]{{0,10}}({RE_MONTO})", texto, re.I)
    if m_usd:
        ex.total_usd = monto_ar(m_usd.group(1))
    m_tna = re.search(r"T\.?N\.?A\.?[^\d\n]{0,25}(\d{1,3}(?:,\d{1,2})?)\s*%", texto, re.I)
    if m_tna:
        ex.tna = monto_ar(m_tna.group(1) + ("" if "," in m_tna.group(1) else ",00"))

    for linea in texto.splitlines():
        m = RE_LINEA.match(linea)
        if not m:
            continue
        dia, mes, anio, desc, m1, m2 = m.groups()
        fecha = fecha_ar(dia, mes, anio)
        if fecha is None:
            continue
        desc = re.sub(r"\s{2,}", " ", desc).strip(" *")
        desc_u = desc.upper()
        if any(x in desc_u for x in ("SALDO ANTERIOR", "SALDO ACTUAL", "PAGO MINIMO", "PAGO MÍNIMO")):
            continue
        # Dos montos al final: columna pesos y columna dólares.
        moneda = Moneda.ARS
        crudo = m1
        if m2 and monto_ar(m1) in (None, Decimal("0")):
            crudo, moneda = m2, Moneda.USD
        valor = monto_ar(crudo)
        if valor is None:
            continue
        tipo = _tipo(desc)
        cuota_n = cuota_total = None
        mc = RE_CUOTA.search(desc)
        if mc:
            cuota_n, cuota_total = int(mc.group(1)), int(mc.group(2))
            if cuota_total > 1 and tipo == TipoLinea.consumo:
                tipo = TipoLinea.cuota
            desc = RE_CUOTA.sub("", desc).strip()
        # Quitar números de comprobante y el prefijo de tipo de operación
        desc = re.sub(r"\s+\d{4,}$", "", desc)
        desc = re.sub(r"^[A-Z]\s+(?=[A-Z])", "", desc).strip() or "Movimiento"
        if valor < 0 and tipo != TipoLinea.pago:
            tipo = TipoLinea.ajuste if tipo == TipoLinea.consumo else tipo
        ex.lineas.append(LineaExtraida(fecha, re.sub(r"\s{2,}", " ", desc)[:200], abs(valor), moneda, tipo, cuota_n, cuota_total))
    if not ex.lineas:
        raise ErrorLectura("No encontré movimientos en el PDF. Si es una imagen escaneada, hace falta la lectura con IA.")
    return ex


# ───────────────────────── con IA ─────────────────────────
ESQUEMA = {
    "type": "object",
    "properties": {
        "fecha_cierre": {"type": ["string", "null"], "description": "YYYY-MM-DD del cierre actual"},
        "fecha_vencimiento": {"type": ["string", "null"], "description": "YYYY-MM-DD del vencimiento actual"},
        "saldo_anterior": {"type": ["number", "null"]},
        "total_ars": {"type": ["number", "null"], "description": "Saldo actual / total a pagar en pesos"},
        "total_usd": {"type": ["number", "null"], "description": "Saldo actual en dólares"},
        "pago_minimo": {"type": ["number", "null"]},
        "tna": {"type": ["number", "null"], "description": "TNA de financiación en pesos, en %"},
        "lineas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fecha": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                    "descripcion": {"type": "string", "description": "Comercio o concepto, sin números de comprobante"},
                    "monto": {"type": "number", "description": "Valor absoluto"},
                    "moneda": {"type": "string", "enum": ["ARS", "USD"]},
                    "tipo": {"type": "string", "enum": [t.value for t in TipoLinea]},
                    "cuota_n": {"type": ["integer", "null"]},
                    "cuota_total": {"type": ["integer", "null"]},
                },
                "required": ["descripcion", "monto", "moneda", "tipo"],
            },
        },
    },
    "required": ["lineas"],
}

INSTRUCCIONES = (
    "Es el resumen de una tarjeta de crédito argentina. Extraé TODAS las líneas del período: "
    "consumos, cuotas (ej. C.03/12 → cuota_n 3, cuota_total 12, tipo cuota), impuestos (sellos, IVA, "
    "percepciones), intereses, cargos (comisiones, seguros), pagos (tipo pago) y ajustes/bonificaciones "
    "(tipo ajuste). Montos en valor absoluto, en la moneda de su columna. No inventes líneas ni "
    "repitas los subtotales. Usá la herramienta registrar_resumen."
)


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v)).quantize(Decimal("0.01"))


def _fecha_iso(v) -> date | None:
    try:
        return date.fromisoformat(v) if v else None
    except ValueError:
        return None


def con_ia(contenido: bytes) -> Extraccion:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={
            "model": settings.anthropic_model,
            "max_tokens": 16000,
            "tools": [{"name": "registrar_resumen", "description": "Registra los datos del resumen", "input_schema": ESQUEMA}],
            "tool_choice": {"type": "tool", "name": "registrar_resumen"},
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                    "data": base64.b64encode(contenido).decode()}},
                    {"type": "text", "text": INSTRUCCIONES},
                ],
            }],
        },
        timeout=180,
    )
    if r.status_code != 200:
        raise ErrorLectura(f"La lectura con IA falló ({r.status_code}).")
    bloque = next((b for b in r.json().get("content", []) if b.get("type") == "tool_use"), None)
    if not bloque:
        raise ErrorLectura("La IA no devolvió datos.")
    d = bloque["input"]
    ex = Extraccion(
        metodo="ia",
        fecha_cierre=_fecha_iso(d.get("fecha_cierre")), fecha_vencimiento=_fecha_iso(d.get("fecha_vencimiento")),
        saldo_anterior=_dec(d.get("saldo_anterior")), total_ars=_dec(d.get("total_ars")),
        total_usd=_dec(d.get("total_usd")), pago_minimo=_dec(d.get("pago_minimo")), tna=_dec(d.get("tna")),
    )
    for l in d.get("lineas", []):
        try:
            ex.lineas.append(LineaExtraida(
                fecha=_fecha_iso(l.get("fecha")), descripcion=str(l["descripcion"])[:200], monto=abs(_dec(l["monto"])),
                moneda=Moneda(l.get("moneda", "ARS")), tipo=TipoLinea(l.get("tipo", "consumo")),
                cuota_n=l.get("cuota_n"), cuota_total=l.get("cuota_total"),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return ex


def extraer(contenido: bytes) -> Extraccion:
    if settings.anthropic_api_key:
        try:
            return con_ia(contenido)
        except Exception as e:
            log.warning("Lectura con IA falló, sigo con reglas: %s", e)
    return con_reglas(texto_del_pdf(contenido))
