"""Resumen de la semana y repaso «¿valió la pena?»."""
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Cuenta,
    Deuda,
    EstadoMovimiento,
    EstadoResumen,
    Movimiento,
    ResumenTarjeta,
    TipoCuenta,
    TipoDeuda,
)
from app.services import deudas as svc_deudas
from app.services.detectores import Hallazgo, clave_desc, gastos, hallazgos, recurrentes
from app.services.saldos import saldos_por_cuenta

CERO = Decimal("0")
NO_REPASAR = {"Casa", "Deudas y préstamos", "Comisiones e intereses", "Suscripciones", "Salud"}


def semana_pasada(hoy: date) -> tuple[date, date]:
    """Lunes a domingo de la última semana completa."""
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    return lunes, lunes + timedelta(days=6)


# ───────────────────────── repaso ─────────────────────────
def para_repasar(db: Session, hoy: date | None = None, cantidad: int = 5) -> list[Movimiento]:
    """Hasta 5 gastos de los últimos 7 días (o 14) sin responder, elegidos al azar pero fijos en la semana."""
    hoy = hoy or date.today()
    fijos = {r.clave for r in recurrentes(db, hoy)}
    for dias in (7, 14):
        candidatos = [
            m for m in gastos(db, hoy - timedelta(days=dias), hoy)
            if m.valio is None and not m.deuda_id and not m.cuotas
            and not (m.categoria and m.categoria.nombre in NO_REPASAR)
            and clave_desc(m.descripcion) not in fijos
        ]
        if len(candidatos) >= 3 or dias == 14:
            break
    anio, semana, _ = hoy.isocalendar()
    rnd = random.Random(anio * 100 + semana)
    rnd.shuffle(candidatos)
    return sorted(candidatos[:cantidad], key=lambda m: m.fecha, reverse=True)


@dataclass
class Arrepentimiento:
    categoria: str
    respondidos: int
    no: int


def arrepentimientos(db: Session, minimo: int = 4) -> list[Arrepentimiento]:
    filas = db.execute(
        select(Movimiento.categoria_id, Movimiento.valio, func.count())
        .where(Movimiento.valio.is_not(None)).group_by(Movimiento.categoria_id, Movimiento.valio)
    ).all()
    from app.models import Categoria
    nombres = {c.id: c.nombre for c in db.scalars(select(Categoria))}
    por: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for cat, valio, n in filas:
        k = nombres.get(cat, "Sin categoría")
        por[k][0] += n
        if not valio:
            por[k][1] += n
    out = [Arrepentimiento(k, t, no) for k, (t, no) in por.items() if t >= minimo]
    return sorted(out, key=lambda a: (-a.no / a.respondidos, -a.respondidos))


# ───────────────────────── vencimientos ─────────────────────────
@dataclass
class Vencimiento:
    fecha: date
    que: str
    monto: Decimal


def vencimientos(db: Session, desde: date, dias: int = 7) -> list[Vencimiento]:
    hasta = desde + timedelta(days=dias)
    out: list[Vencimiento] = []
    saldos = saldos_por_cuenta(db)
    for c in db.scalars(select(Cuenta).where(Cuenta.tipo == TipoCuenta.tarjeta_credito, Cuenta.archivada.is_(False))):
        r = db.scalar(select(ResumenTarjeta).where(
            ResumenTarjeta.cuenta_id == c.id, ResumenTarjeta.estado == EstadoResumen.confirmado)
            .order_by(ResumenTarjeta.periodo.desc()).limit(1))
        if r and r.fecha_vencimiento and desde <= r.fecha_vencimiento <= hasta and saldos.get(c.id, CERO) < 0 and r.total_ars:
            out.append(Vencimiento(r.fecha_vencimiento, f"Resumen {c.nombre}", r.total_ars))
    for d in db.scalars(select(Deuda).where(Deuda.cerrada.is_(False), Deuda.tipo == TipoDeuda.prestamo)):
        e = svc_deudas.estado(db, d, desde)
        cuota = svc_deudas.cuota_sugerida(d, e)
        if e.proximo_vencimiento and e.proximo_vencimiento <= hasta and cuota:
            out.append(Vencimiento(e.proximo_vencimiento, f"Cuota {d.nombre}", cuota))
    return sorted(out, key=lambda v: v.fecha)


# ───────────────────────── resumen semanal ─────────────────────────
@dataclass
class Semana:
    desde: date
    hasta: date
    gastos: Decimal
    gastos_anterior: Decimal
    cantidad: int
    fijos: Decimal            # alquiler, servicios, suscripciones de la semana
    variables: Decimal        # el resto: lo que se compara
    variables_anterior: Decimal
    top: list[tuple[str, str, str, Decimal]]  # nombre, icono, color, total
    mayor: tuple[str, Decimal, date] | None
    pendientes: int
    vencimientos: list[Vencimiento]
    hallazgos: list[Hallazgo]
    repaso: list[Movimiento] = field(default_factory=list)


def armar(db: Session, hoy: date | None = None) -> Semana:
    hoy = hoy or date.today()
    desde, hasta = semana_pasada(hoy)
    ms = [m for m in gastos(db, desde, hasta) if not m.deuda_id]
    antes = [m for m in gastos(db, desde - timedelta(days=7), desde - timedelta(days=1)) if not m.deuda_id]
    claves_fijas = {r.clave for r in recurrentes(db, hoy)}
    es_fijo = lambda m: clave_desc(m.descripcion) in claves_fijas or bool(m.cuotas)  # noqa: E731
    por_cat: dict[str, list] = {}
    for m in ms:
        c = m.categoria
        k = c.nombre if c else "Sin categoría"
        g = por_cat.setdefault(k, [k, (c.icono if c else "") or "otros", (c.color if c else "") or "slate", CERO])
        g[3] += m.monto
    mayor = max(ms, key=lambda m: m.monto, default=None)
    pendientes = db.scalar(select(func.count()).select_from(Movimiento).where(
        Movimiento.estado == EstadoMovimiento.pendiente)) or 0
    return Semana(
        desde=desde, hasta=hasta,
        gastos=sum((m.monto for m in ms), CERO), gastos_anterior=sum((m.monto for m in antes), CERO),
        cantidad=len(ms),
        fijos=sum((m.monto for m in ms if es_fijo(m)), CERO),
        variables=sum((m.monto for m in ms if not es_fijo(m)), CERO),
        variables_anterior=sum((m.monto for m in antes if not es_fijo(m)), CERO),
        top=[tuple(g) for g in sorted(por_cat.values(), key=lambda g: -g[3])[:4]],
        mayor=(mayor.descripcion, mayor.monto, mayor.fecha) if mayor else None,
        pendientes=pendientes,
        vencimientos=vencimientos(db, hoy),
        hallazgos=[h for h in hallazgos(db, hoy) if h.tono == "aviso"][:3],
        repaso=para_repasar(db, hoy),
    )


def _p(v: Decimal) -> str:
    return "$ " + f"{abs(v):,.0f}".replace(",", ".")


def texto_telegram(s: Semana) -> str:
    """El resumen en HTML de Telegram (corto: se lee en el celu)."""
    l = [f"<b>Tu semana</b> · {s.desde:%d/%m} al {s.hasta:%d/%m}", ""]
    if s.cantidad == 0:
        l.append("No registraste gastos la semana pasada.")
    else:
        l.append(f"Gastaste <b>{_p(s.gastos)}</b> en {s.cantidad} gastos.")
        if s.fijos > 0:
            l.append(f"De eso, {_p(s.fijos)} fueron fijos (alquiler, servicios, cuotas).")
        if s.variables_anterior > 0:
            dif = s.variables - s.variables_anterior
            pct = round(abs(dif) / s.variables_anterior * 100)
            base = "Sin contar fijos" if s.fijos > 0 else "Comparado con la anterior"
            l.append(f"{base}: {_p(s.variables)}, " + (f"{pct}% {'menos' if dif < 0 else 'más'} que la semana anterior." if pct >= 3 else "casi igual que la semana anterior."))
        if s.top:
            l.append("Lo que más: " + ", ".join(f"{n} {_p(t)}" for n, _, _, t in s.top[:3]) + ".")
        if s.mayor:
            l.append(f"El más grande: {s.mayor[0]}, {_p(s.mayor[1])}.")
    if s.vencimientos:
        l += ["", "<b>Esta semana vence</b>"]
        l += [f"• {v.fecha:%d/%m} {v.que}: {_p(v.monto)}" for v in s.vencimientos]
    if s.hallazgos:
        l += ["", "<b>Para mirar</b>"]
        l += [f"• {h.titulo}" for h in s.hallazgos]
    if s.pendientes:
        l += ["", f"Tenés {s.pendientes} {'cosa' if s.pendientes == 1 else 'cosas'} en la bandeja. /bandeja"]
    return "\n".join(l)
