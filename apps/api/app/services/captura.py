"""Interpretación de texto libre ("nafta 40k visa") en un movimiento.

Primera versión con reglas: rápida, gratis y predecible. Más adelante se puede
sumar un LLM para los casos que las reglas no entienden, manteniendo esta misma
salida (`Interpretacion`).
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from app.models import Categoria, MedioPago, Moneda, TipoCategoria, TipoMovimiento

MULTIPLICADORES = {
    "k": 1_000, "mil": 1_000, "luca": 1_000, "lucas": 1_000,
    "m": 1_000_000, "palo": 1_000_000, "palos": 1_000_000,
    "millon": 1_000_000, "millones": 1_000_000,
}
PALABRAS_USD = {"usd", "u$s", "us$", "dolar", "dolares", "verdes"}
PALABRAS_INGRESO = {
    "cobre", "cobro", "sueldo", "aguinaldo", "ingreso", "vendi", "reintegro",
    "depositaron", "transfirieron", "pagaron",
}
RELLENO = {
    "el", "la", "los", "las", "de", "del", "en", "con", "un", "una", "me", "le", "por",
    "y", "a", "al", "pague", "gaste", "compre", "cobre", "cobro", "hoy", "ayer",
    "anteayer", "pesos", "peso", "$", "cuota", "cuotas", "fijas", "sin", "interes",
} | PALABRAS_USD

# Marcas de tarjeta: si las nombrás y no tenés esa tarjeta cargada, te aviso en vez de usar otro medio
MARCAS_TARJETA = {"visa", "master", "mastercard", "amex", "cabal", "diners"}

RE_MONTO = re.compile(
    r"(?<![\w.,])(\d+(?:[.,]\d+)*)\s*(k|mil|lucas?|palos?|millon(?:es)?|m)?(?![\w])"
)
RE_CUOTAS = re.compile(
    r"(?<![\w.,])(\d{1,2})\s*cuotas?(?:\s+(?:fijas\s+)?de\s+\$?\s*(\d+(?:[.,]\d+)*)\s*(k|mil|lucas?|palos?|millon(?:es)?|m)?(?!\w))?"
)
# «garantía 1 año», «con garantía de 6 meses», «garantia 2 años», «garantía» a secas
RE_GARANTIA = re.compile(
    r"(?<!\w)(?:con\s+)?garantia(?:\s+(?:de|por))?"
    r"(?:\s+(\d+|un|una|dos|tres|cinco)\s*(anos?|anios?|mes(?:es)?)(?!\w))?"
)
NUMEROS = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cinco": 5}


# Otras formas de decir cuotas: «12 sin interés», «x12», «en 12» (solo cantidades típicas)
RE_CUOTAS_OTRAS = re.compile(
    r"(?<![\w.,])(?:(\d{1,2})\s+(?:pagos\s+)?sin\s+interes|x\s?(\d{1,2})(?!\w)|en\s+(2|3|6|9|10|12|15|18|24|36)(?=\s*$|\s*[,;]|\s+(?:visa|master|mastercard|amex|cabal|naranja|con|sin)\b))"
)


def _garantia(norm: str) -> tuple[int | None, tuple[int, int] | None]:
    m = RE_GARANTIA.search(norm)
    if not m:
        return None, None
    if not m.group(1):
        return 12, m.span()  # sin plazo: lo típico de fábrica
    n = NUMEROS.get(m.group(1)) or int(m.group(1))
    meses = n if m.group(2).startswith("mes") else n * 12
    return (meses if 0 < meses <= 240 else None), m.span()


def _plano(texto: str) -> str:
    """Sin tildes y en minúsculas. Conserva la longitud en texto en español,
    así las posiciones sirven para resaltar el texto original."""
    return "".join(
        unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode()[:1] or " " for c in texto
    ).lower()


def normalizar(texto: str) -> str:
    return _plano(texto).strip()


def _numero(crudo: str, con_multiplicador: bool) -> Decimal | None:
    """Convierte '2.500', '1.234,56', '1,45', '40' a Decimal (formato argentino)."""
    s = crudo
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s or "." in s:
        sep = "," if "," in s else "."
        partes = s.split(sep)
        miles = all(len(p) == 3 for p in partes[1:])
        if miles and not con_multiplicador:
            s = s.replace(sep, "")
        elif len(partes) == 2:
            s = s.replace(sep, ".")
        else:
            s = s.replace(sep, "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


@dataclass
class Resultado:
    tipo: TipoMovimiento
    monto: Decimal | None
    moneda: Moneda
    descripcion: str
    fecha: date
    medio: MedioPago | None
    motivo_medio: str | None
    categoria: Categoria | None
    cuotas: int | None
    garantia_meses: int | None = None
    partes: list[tuple[int, int, str]] = field(default_factory=list)
    aviso: str | None = None  # algo que conviene decirte antes de guardar (p. ej. falta la tarjeta)
    # Préstamos entre personas: ("me_deben" | "debo", nombre)
    deuda: tuple[str, str] | None = None

    @property
    def faltantes(self) -> list[str]:
        f = []
        if self.monto is None:
            f.append("monto")
        if self.medio is None:
            f.append("medio_pago")
        if self.categoria is None:
            f.append("categoria")
        return f


def _buscar_monto(norm: str) -> tuple[Decimal | None, tuple[int, int] | None]:
    cuotas_spans = [m.span(1) for m in RE_CUOTAS.finditer(norm)]
    cuotas_spans += [m.span(next(i for i in (1, 2, 3) if m.group(i))) for m in RE_CUOTAS_OTRAS.finditer(norm)]
    cuotas_spans += [m.span(2) for m in RE_CUOTAS.finditer(norm) if m.group(2)]  # «de 110k» es la cuota
    cuotas_spans += [m.span(1) for m in RE_GARANTIA.finditer(norm) if m.group(1)]
    candidatos = []
    for m in RE_MONTO.finditer(norm):
        if any(m.start(1) == s for s, _ in cuotas_spans):
            continue  # "12 cuotas" no es el monto
        mult = m.group(2)
        valor = _numero(m.group(1), bool(mult))
        if valor is None:
            continue
        if mult:
            valor *= MULTIPLICADORES[mult]
        # Preferimos montos con multiplicador; si no, el más grande.
        candidatos.append((1 if mult else 0, valor, m.span()))
    if not candidatos:
        return None, None
    _, valor, span = max(candidatos, key=lambda c: (c[0], c[1]))
    return valor.quantize(Decimal("0.01")), span


def _buscar_medio(norm: str, medios: list[MedioPago]):
    mejor: tuple[int, MedioPago, str, tuple[int, int]] | None = None
    for medio in medios:
        if medio.archivado:
            continue
        alias = [normalizar(a) for a in medio.alias.split(",") if a.strip()]
        alias.append(normalizar(medio.nombre))
        for a in alias:
            m = re.search(rf"(?<!\w){re.escape(a)}(?!\w)", norm) if a else None
            if m and (mejor is None or len(a) > mejor[0]):
                mejor = (len(a), medio, a, m.span())
    if mejor:
        return mejor[1], f"dijiste «{mejor[2]}»", mejor[2], mejor[3]
    return None, None, None, None


def _buscar_categoria(norm: str, categorias: list[Categoria], tipo: TipoMovimiento):
    tipo_cat = TipoCategoria.ingreso if tipo == TipoMovimiento.ingreso else TipoCategoria.gasto
    for cat in categorias:
        if cat.tipo != tipo_cat:
            continue
        claves = {normalizar(p) for p in cat.palabras.split(",") if p.strip()}
        claves.add(normalizar(cat.nombre))
        for clave in sorted(claves, key=len, reverse=True):
            m = re.search(rf"(?<!\w){re.escape(clave)}(?!\w)", norm) if clave else None
            if m:
                return cat, m.span()
    return None, None


NO_NOMBRES = {"mi", "la", "el", "los", "las", "un", "una", "con", "en", "de", "del", "por", "para", "que",
              "lucas", "luca", "mil", "pesos", "peso", "palos", "k", "m", "usd", "dolares", "hoy", "ayer"}


def _nombre(candidatos: list[str]) -> str | None:
    for c in candidatos:
        if c and c not in NO_NOMBRES and not c.isdigit():
            return c.capitalize()
    return None


def detectar_prestamo(norm: str) -> tuple[str, str, TipoMovimiento, str] | None:
    """«le presté 20 lucas a juan» → (me_deben, Juan, gasto, «Préstamo a Juan»)."""
    def despues_de_a(resto: str) -> str | None:
        return _nombre(list(reversed(re.findall(r"\ba\s+(?:mi\s+|la\s+|el\s+)?([a-z]+)", resto))))

    m = re.search(r"\b(?:le\s+)?preste\b(.*)", norm)
    if m and (n := despues_de_a(m.group(1))):
        return "me_deben", n, TipoMovimiento.gasto, f"Préstamo a {n}"
    m = re.search(r"\b(?:le\s+)?devolvi\b(.*)", norm)
    if m and (n := despues_de_a(m.group(1))):
        return "debo", n, TipoMovimiento.gasto, f"Devolución a {n}"
    m = re.search(r"\b([a-z]+)\s+me\s+(presto|devolvio)\b", norm) or re.search(
        r"\bme\s+(presto|devolvio)\s+(?:mi\s+|la\s+|el\s+)?([a-z]+)", norm)
    if m:
        g = m.groups()
        verbo, quien = (g[1], g[0]) if g[0] not in ("presto", "devolvio") else (g[0], g[1])
        n = _nombre([quien])
        if n:
            if verbo == "presto":
                return "debo", n, TipoMovimiento.ingreso, f"{n} me prestó"
            return "me_deben", n, TipoMovimiento.ingreso, f"{n} me devolvió"
    return None


def interpretar(
    texto: str,
    medios: list[MedioPago],
    categorias: list[Categoria],
    hoy: date | None = None,
) -> Resultado:
    hoy = hoy or date.today()
    norm = _plano(texto)
    palabras = set(re.findall(r"[\w$]+", norm))
    partes: list[tuple[int, int, str]] = []

    tipo = TipoMovimiento.ingreso if palabras & PALABRAS_INGRESO else TipoMovimiento.gasto
    m_usd = re.search(r"(?<!\w)(usd|u\$s|us\$|dolares|dolar|verdes)(?!\w)", norm)
    moneda = Moneda.USD if m_usd else Moneda.ARS
    if m_usd:
        partes.append((*m_usd.span(), "moneda"))

    m_fecha = re.search(r"(?<!\w)(anteayer|ayer|hoy)(?!\w)", norm)
    if m_fecha and m_fecha.group(1) == "anteayer":
        fecha = hoy - timedelta(days=2)
    elif m_fecha and m_fecha.group(1) == "ayer":
        fecha = hoy - timedelta(days=1)
    else:
        fecha = hoy
    if m_fecha:
        partes.append((*m_fecha.span(), "fecha"))

    monto, span_monto = _buscar_monto(norm)
    if span_monto:
        partes.append((*span_monto, "monto"))
    m_cuotas = RE_CUOTAS.search(norm)
    cuotas = int(m_cuotas.group(1)) if m_cuotas else None
    m_otras = None if m_cuotas else RE_CUOTAS_OTRAS.search(norm)
    if m_otras and monto is not None:  # «en 12» solo si además hay un precio
        cuotas = int(next(g for g in m_otras.groups() if g))
        partes.append((*m_otras.span(), "cuotas"))
    # «12 cuotas de 110k»: lo que se debe es 12 × la cuota (incluye el interés)
    if m_cuotas and m_cuotas.group(2) and cuotas:
        valor = _numero(m_cuotas.group(2), bool(m_cuotas.group(3)))
        if valor:
            if m_cuotas.group(3):
                valor *= MULTIPLICADORES[m_cuotas.group(3)]
            monto = (valor * cuotas).quantize(Decimal("0.01"))
            if span_monto is None:
                span_monto = m_cuotas.span(2)
    if m_cuotas:
        partes.append((*m_cuotas.span(), "cuotas"))
    garantia_meses, span_gar = _garantia(norm)
    if span_gar:
        partes.append((*span_gar, "garantia"))
    medio, motivo, alias_usado, span_medio = _buscar_medio(norm, medios)
    if span_medio:
        partes.append((*span_medio, "medio"))
    categoria, span_cat = _buscar_categoria(norm, categorias, tipo)
    if span_cat:
        partes.append((*span_cat, "categoria"))

    # Sin superposiciones (gana la que aparece primero en la lista de prioridad).
    prioridad = {"monto": 0, "medio": 1, "cuotas": 2, "garantia": 3, "fecha": 4, "moneda": 5, "categoria": 6}
    elegidas: list[tuple[int, int, str]] = []
    for p in sorted(partes, key=lambda p: prioridad[p[2]]):
        if all(p[1] <= q[0] or p[0] >= q[1] for q in elegidas):
            elegidas.append(p)
    partes = sorted(elegidas) if len(norm) == len(texto) else []

    # Descripción: lo que queda al sacar montos, medio de pago y palabras de relleno.
    sacar = set(RELLENO) | set(MULTIPLICADORES) | MARCAS_TARJETA
    if alias_usado:
        sacar |= set(alias_usado.split())
    texto_desc = texto
    if span_gar and len(norm) == len(texto):
        texto_desc = texto[:span_gar[0]] + " " * (span_gar[1] - span_gar[0]) + texto[span_gar[1]:]
    restantes = [
        w for w in texto_desc.split()
        if normalizar(w).strip(".,;:") not in sacar and not re.search(r"\d", w)
    ]
    descripcion = " ".join(restantes).strip(" .,;:")
    if not descripcion:
        descripcion = categoria.nombre if categoria else ("Ingreso" if tipo == TipoMovimiento.ingreso else "Gasto")
    descripcion = descripcion[:1].upper() + descripcion[1:]

    deuda = None
    prestamo = detectar_prestamo(norm)
    if prestamo:
        tipo_deuda, nombre, tipo, descripcion = prestamo
        # Recuperar el nombre como lo escribiste (con tildes: «martín» → «Martín»)
        original = next((w for w in re.findall(r"\w+", texto) if _plano(w) == nombre.lower()), None)
        if original:
            bien = original[:1].upper() + original[1:]
            descripcion = descripcion.replace(nombre, bien)
            nombre = bien
        deuda, categoria, cuotas, garantia_meses = (tipo_deuda, nombre), None, None, None
        partes = [p for p in partes if p[2] != "categoria"]

    return Resultado(
        tipo=tipo, monto=monto, moneda=moneda, descripcion=descripcion[:200], fecha=fecha,
        medio=medio, motivo_medio=motivo, categoria=categoria, cuotas=cuotas, partes=partes, deuda=deuda,
        garantia_meses=garantia_meses if tipo == TipoMovimiento.gasto else None,
    )
