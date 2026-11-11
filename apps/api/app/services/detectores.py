"""Detectores: cosas que vale la pena mirar, calculadas sobre tus movimientos.

Cada hallazgo tiene una `clave` estable que incluye el dato que lo dispara: si lo
descartás y después cambia (otro aumento, otro duplicado), vuelve a aparecer.
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import EstadoMovimiento, Garantia, HallazgoDescartado, Moneda, Movimiento, TipoCuenta, TipoMovimiento
from app.services.captura import _plano

CERO = Decimal("0")


@dataclass
class Hallazgo:
    clave: str
    tipo: str            # suscripcion_aumento | fijos | hormiga | plata_tirada | duplicado | desvio | garantia | sin_garantia
    tono: str            # aviso | info
    titulo: str
    detalle: str
    monto: Decimal | None = None
    accion: dict | None = None  # {"tipo": "categoria"|"movimiento"|"buscar"|"garantia"|"garantia_nueva", "valor": str}
    orden: int = 50
    movimientos: list[str] = field(default_factory=list)


def clave_desc(desc: str) -> str:
    d = re.sub(r"\s*\(\d+ cuotas\)$", "", desc)
    return re.sub(r"\s+", " ", _plano(d)).strip()


def _pesos(v: Decimal) -> str:
    entero = f"{abs(v):,.0f}".replace(",", ".")
    return f"$ {entero}"


def gastos(db: Session, desde: date, hasta: date, incluir_cuotas: bool = False) -> list[Movimiento]:
    """Gastos confirmados en pesos, sin préstamos entre personas ni compras en cuotas (van por cuota)."""
    return [m for m in db.scalars(
        select(Movimiento)
        .options(selectinload(Movimiento.categoria), selectinload(Movimiento.garantias), selectinload(Movimiento.cuenta))
        .where(Movimiento.estado == EstadoMovimiento.confirmado, Movimiento.tipo == TipoMovimiento.gasto,
               Movimiento.moneda == Moneda.ARS, Movimiento.fecha.between(desde, hasta))
        .order_by(Movimiento.fecha, Movimiento.creado)
    ) if not (m.deuda_id and m.descripcion.startswith("Préstamo a")) and (incluir_cuotas or not (m.cuotas and m.cuotas > 1))]


# ───────────────────────── recurrentes ─────────────────────────
@dataclass
class Recurrente:
    clave: str
    nombre: str
    ultimo: Decimal
    anterior: Decimal | None
    meses: int
    categoria: str | None
    ultima: date | None = None      # fecha del último pago
    con_tarjeta: bool = False       # se paga con tarjeta de crédito (va al resumen)


def recurrentes(db: Session, hoy: date) -> list[Recurrente]:
    """Lo que se repite una vez por mes con montos parecidos (suscripciones, servicios, alquiler)."""
    movs = gastos(db, hoy - timedelta(days=125), hoy)
    por_clave: dict[str, list[Movimiento]] = defaultdict(list)
    for m in movs:
        if not m.cuotas:
            por_clave[clave_desc(m.descripcion)].append(m)
    salida = []
    for k, ms in por_clave.items():
        meses = {(m.fecha.year, m.fecha.month) for m in ms}
        if len(meses) < 2 or len(ms) > len(meses) + 1:  # más de una vez por mes no es fijo
            continue
        # Un fijo se repite cada ~mes: dos pagos con menos de 20 días de diferencia no lo son
        if any((b.fecha - a.fecha).days < 20 for a, b in zip(ms, ms[1:])):
            continue
        es_suscripcion = any(m.categoria and m.categoria.nombre == "Suscripciones" for m in ms)
        montos = [m.monto for m in ms]
        med = Decimal(str(median(montos)))
        if not es_suscripcion and any(abs(x - med) > med * Decimal("0.35") for x in montos):
            continue
        # Debe seguir vivo: el último pago en los últimos ~40 días
        if (hoy - ms[-1].fecha).days > 40:
            continue
        salida.append(Recurrente(
            k, ms[-1].descripcion, ms[-1].monto, ms[-2].monto if len(ms) > 1 else None, len(meses),
            ms[-1].categoria.nombre if ms[-1].categoria else None,
            ultima=ms[-1].fecha,
            con_tarjeta=bool(ms[-1].cuenta and ms[-1].cuenta.tipo == TipoCuenta.tarjeta_credito),
        ))
    return sorted(salida, key=lambda r: -r.ultimo)


# ───────────────────────── detectores ─────────────────────────
def _aumentos(rec: list[Recurrente]) -> list[Hallazgo]:
    out = []
    for r in rec:
        if r.anterior and r.ultimo > r.anterior * Decimal("1.05") and r.ultimo - r.anterior >= 500:
            pct = round((r.ultimo / r.anterior - 1) * 100)
            out.append(Hallazgo(
                clave=f"aumento:{r.clave}:{r.ultimo}", tipo="suscripcion_aumento", tono="aviso", orden=10,
                titulo=f"{r.nombre} subió {pct}%",
                detalle=f"Pasó de {_pesos(r.anterior)} a {_pesos(r.ultimo)}: son {_pesos((r.ultimo - r.anterior) * 12)} más por año.",
                monto=r.ultimo, accion={"tipo": "buscar", "valor": r.nombre},
            ))
    return out


def _fijos(rec: list[Recurrente]) -> list[Hallazgo]:
    if len(rec) < 2:
        return []
    mensual = sum((r.ultimo for r in rec), CERO)
    subs = [r for r in rec if r.categoria == "Suscripciones"]
    detalle = f"{', '.join(r.nombre for r in rec[:4])}{' y más' if len(rec) > 4 else ''}."
    if subs:
        detalle += f" Solo las suscripciones son {_pesos(sum((r.ultimo for r in subs), CERO) * 12)} por año."
    return [Hallazgo(
        clave=f"fijos:{len(rec)}:{round(mensual, -3)}", tipo="fijos", tono="info", orden=60,
        titulo=f"Tus {len(rec)} gastos fijos suman {_pesos(mensual)} por mes",
        detalle=detalle, monto=mensual,
    )]


def _hormiga(movs: list[Movimiento], hoy: date) -> list[Hallazgo]:
    total = sum((m.monto for m in movs), CERO)
    if total <= 0:
        return []
    umbral = max(Decimal("2000"), total * Decimal("0.015"))
    grupos: dict[str, list[Movimiento]] = defaultdict(list)
    for m in movs:
        if m.monto <= umbral and not m.deuda_id:
            grupos[m.categoria.nombre if m.categoria else clave_desc(m.descripcion).capitalize()].append(m)
    out = []
    for nombre, ms in grupos.items():
        suma = sum((m.monto for m in ms), CERO)
        if len(ms) >= 6 and suma >= total * Decimal("0.03"):
            cat = ms[0].categoria
            out.append(Hallazgo(
                clave=f"hormiga:{nombre}:{hoy:%Y-%m}", tipo="hormiga", tono="aviso", orden=20,
                titulo=f"{len(ms)} gastos chicos en {nombre}: {_pesos(suma)}",
                detalle=f"En los últimos 30 días. A este ritmo son {_pesos(suma * 12)} por año, de a poquito.",
                monto=suma, accion={"tipo": "categoria", "valor": str(cat.id)} if cat else {"tipo": "buscar", "valor": nombre},
            ))
    return sorted(out, key=lambda h: -(h.monto or 0))[:2]


def _plata_tirada(movs: list[Movimiento], hoy: date) -> list[Hallazgo]:
    ms = [m for m in movs if m.categoria and m.categoria.nombre == "Comisiones e intereses"]
    suma = sum((m.monto for m in ms), CERO)
    if suma < 500:
        return []
    return [Hallazgo(
        clave=f"tirada:{hoy:%Y-%m}:{round(suma, -2)}", tipo="plata_tirada", tono="aviso", orden=15,
        titulo=f"{_pesos(suma)} en comisiones, intereses e impuestos",
        detalle="En los últimos 30 días. Revisá si alguna se puede evitar (mantenimiento de cuenta, seguros, pagar el mínimo).",
        monto=suma, accion={"tipo": "categoria", "valor": str(ms[0].categoria_id)},
    )]


def _duplicados(movs: list[Movimiento]) -> list[Hallazgo]:
    out, vistos = [], set()
    for i, a in enumerate(movs):
        for b in movs[i + 1:]:
            if (b.fecha - a.fecha).days > 1:
                break
            if a.monto == b.monto and clave_desc(a.descripcion) == clave_desc(b.descripcion) and a.id not in vistos:
                vistos.update({a.id, b.id})
                out.append(Hallazgo(
                    clave=f"duplicado:{a.id}:{b.id}", tipo="duplicado", tono="aviso", orden=5,
                    titulo=f"¿Cargaste dos veces {a.descripcion}?",
                    detalle=f"Hay dos de {_pesos(a.monto)} el {a.fecha:%d/%m}{'' if a.fecha == b.fecha else f' y el {b.fecha:%d/%m}'}. Si es un error, borrá uno.",
                    monto=a.monto, accion={"tipo": "movimiento", "valor": str(b.id)}, movimientos=[str(a.id), str(b.id)],
                ))
    return out


def _desvios(db: Session, hoy: date) -> list[Hallazgo]:
    if hoy.day < 7:
        return []
    inicio = hoy.replace(day=1)
    actual: dict[str, Decimal] = defaultdict(lambda: CERO)
    ids: dict[str, str] = {}
    for m in gastos(db, inicio, hoy):
        if m.categoria and not m.deuda_id:
            actual[m.categoria.nombre] += m.monto
            ids[m.categoria.nombre] = str(m.categoria_id)
    previos: dict[str, list[Decimal]] = defaultdict(list)
    meses_con_datos = 0
    for k in (1, 2, 3):
        a, mm = (inicio.year, inicio.month - k) if inicio.month > k else (inicio.year - 1, inicio.month - k + 12)
        desde = date(a, mm, 1)
        hasta = date(a, mm, min(hoy.day, 28))
        ms = gastos(db, desde, hasta)
        if not ms:
            continue
        meses_con_datos += 1
        suma: dict[str, Decimal] = defaultdict(lambda: CERO)
        for m in ms:
            if m.categoria and not m.deuda_id:
                suma[m.categoria.nombre] += m.monto
        for nombre in set(suma) | set(actual):
            previos[nombre].append(suma.get(nombre, CERO))
    if meses_con_datos < 2:
        return []
    total = sum(actual.values(), CERO)
    out = []
    for nombre, v in actual.items():
        prom = sum(previos[nombre], CERO) / meses_con_datos
        if prom > 0 and v > prom * Decimal("1.4") and v - prom > max(Decimal("5000"), total * Decimal("0.05")):
            pct = round((v / prom - 1) * 100)
            out.append(Hallazgo(
                clave=f"desvio:{nombre}:{hoy:%Y-%m}", tipo="desvio", tono="aviso", orden=25,
                titulo=f"{nombre}: {pct}% más que tu promedio",
                detalle=f"Llevás {_pesos(v)} este mes; a esta altura solés ir por {_pesos(prom)}.",
                monto=v, accion={"tipo": "categoria", "valor": ids[nombre]},
            ))
    return sorted(out, key=lambda h: -(h.monto or 0))[:2]


def _garantias(db: Session, hoy: date) -> list[Hallazgo]:
    from app.services import garantias as svc_g
    out = []
    for g in db.scalars(select(Garantia).where(Garantia.vence >= hoy - timedelta(days=1))):
        e = svc_g.estado(g, hoy)
        if e.estado != "por_vencer":
            continue
        cuando = {0: "vence hoy", 1: "vence mañana"}.get(e.dias_restantes, f"vence en {e.dias_restantes} días")
        donde = f" en {g.comercio}" if g.comercio else ""
        out.append(Hallazgo(
            clave=f"garantia:{g.id}:{e.vence}", tipo="garantia", tono="aviso", orden=8,
            titulo=f"La garantía de {g.producto} {cuando}",
            detalle=f"La compraste el {g.fecha_compra:%d/%m/%Y}{donde}. Si anda algo raro, reclamá ahora: después cuesta mucho más.",
            accion={"tipo": "garantia", "valor": str(g.id)},
        ))
    return out


SIN_GARANTIA_CATS = {"Hogar", "Otros gastos"}


def _sin_garantia(movs: list[Movimiento]) -> list[Hallazgo]:
    """Compras grandes de cosas durables (o en cuotas) que no tienen garantía cargada."""
    out = []
    for m in sorted(movs, key=lambda m: -m.monto):
        cat = m.categoria.nombre if m.categoria else None
        durable = cat in SIN_GARANTIA_CATS or cat is None or (m.cuotas or 0) >= 3
        if m.monto < 100_000 or not durable or m.deuda_id or m.garantias:
            continue
        nombre = re.sub(r"\s*\(\d+ cuotas\)$", "", m.descripcion)
        out.append(Hallazgo(
            clave=f"sin_garantia:{m.id}", tipo="sin_garantia", tono="info", orden=55,
            titulo=f"¿{nombre} tiene garantía?",
            detalle=f"Compra de {_pesos(m.monto)} el {m.fecha:%d/%m}. Si la anotás, te aviso un mes antes de que venza.",
            monto=m.monto, accion={"tipo": "garantia_nueva", "valor": str(m.id)},
        ))
    return out[:2]


def _metas(db: Session, hoy: date) -> list[Hallazgo]:
    from app.services import cotizacion as svc_cot, metas as svc_metas
    cot = svc_cot.obtener(db) if svc_metas.hay_en_dolares(db) else None
    out = []
    for m in svc_metas.activas(db):
        e = svc_metas.estado(db, m, hoy, cot)
        nombre = f"{m.emoji} {m.nombre}".strip()
        if e.cumplida:
            out.append(Hallazgo(
                clave=f"meta_ok:{m.id}", tipo="meta", tono="info", orden=3,
                titulo=f"¡Llegaste a {nombre}!",
                detalle="Juntaste todo lo que te propusiste. Podés archivarla o subir el objetivo.",
                accion={"tipo": "link", "valor": "/metas"},
            ))
        elif e.en_camino is False and e.por_mes and e.ritmo is not None:
            out.append(Hallazgo(
                clave=f"meta_atrasada:{m.id}:{hoy:%Y-%m}", tipo="meta", tono="aviso", orden=30,
                titulo=f"{nombre} viene atrasada",
                detalle=(f"Para llegar {'a tiempo' if m.fecha_objetivo else 'al ritmo que pensaste'} necesitás "
                         f"{_pesos(e.por_mes)} por mes y venís poniendo {_pesos(max(e.ritmo, CERO))}."
                         if m.moneda.value == "ARS" else
                         f"Necesitás USD {e.por_mes:,.0f} por mes y venís poniendo USD {max(e.ritmo, CERO):,.0f}.".replace(",", ".")),
                accion={"tipo": "link", "valor": "/metas"},
            ))
    return out


def _inversiones(db: Session, hoy: date) -> list[Hallazgo]:
    from app.models import Inversion, TipoInversion
    from app.services.patrimonio import valor_inversion
    out = []
    for i in db.scalars(select(Inversion).where(Inversion.cerrada.is_(False))):
        if i.vence and -15 <= (i.vence - hoy).days <= 3:
            d = (i.vence - hoy).days
            cuando = "venció" if d < 0 else {0: "vence hoy", 1: "vence mañana"}.get(d, f"vence en {d} días")
            v = valor_inversion(i, hoy)
            monto = _pesos(v) if i.moneda.value == "ARS" else f"USD {v:,.0f}".replace(",", ".")
            out.append(Hallazgo(
                clave=f"inv_vence:{i.id}:{i.vence}", tipo="inversion", tono="aviso", orden=9,
                titulo=f"{i.nombre} {cuando}",
                detalle=f"Son unos {monto}. Decidí si lo renovás o lo pasás a otra cosa, y marcala como cerrada si la sacaste.",
                accion={"tipo": "link", "valor": "/patrimonio"},
            ))
        elif i.tipo in (TipoInversion.fci, TipoInversion.cripto, TipoInversion.acciones, TipoInversion.bonos):
            ultima = i.actualizado or i.fecha_inicio
            if (hoy - ultima).days > 30:
                out.append(Hallazgo(
                    clave=f"inv_valor:{i.id}:{hoy:%Y-%m}", tipo="inversion", tono="info", orden=58,
                    titulo=f"Actualizá cuánto vale {i.nombre}",
                    detalle=f"El último valor es del {ultima:%d/%m}. Con el número de hoy, tu patrimonio queda al día.",
                    accion={"tipo": "link", "valor": "/patrimonio"},
                ))
    return out


def hallazgos(db: Session, hoy: date | None = None, incluir_descartados: bool = False) -> list[Hallazgo]:
    hoy = hoy or date.today()
    ult30 = gastos(db, hoy - timedelta(days=30), hoy)
    rec = recurrentes(db, hoy)
    todos = (_duplicados(ult30) + _garantias(db, hoy) + _aumentos(rec) + _plata_tirada(ult30, hoy)
             + _hormiga(ult30, hoy) + _desvios(db, hoy) + _sin_garantia(gastos(db, hoy - timedelta(days=30), hoy, incluir_cuotas=True)) + _fijos(rec)
             + _metas(db, hoy) + _inversiones(db, hoy))
    if not incluir_descartados:
        descartados = set(db.scalars(select(HallazgoDescartado.clave)))
        todos = [h for h in todos if h.clave not in descartados]
    return sorted(todos, key=lambda h: h.orden)
