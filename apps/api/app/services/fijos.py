"""Gastos fijos que se cargan solos.

Un fijo activo genera, el día que toca, un movimiento PENDIENTE en la bandeja con el último
monto que pagaste: lo confirmás con un toque (o lo corregís si cambió). Si ese mes ya lo
cargaste por tu cuenta, no se genera; si lo cargás después, el tuyo reemplaza al generado.
"""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EstadoMovimiento, GastoFijo, Movimiento, OrigenMovimiento, TipoMovimiento

CERO = Decimal("0")


def periodo(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def dia_en(a: int, m: int, dia: int) -> date:
    return date(a, m, min(dia, calendar.monthrange(a, m)[1]))


FRECUENCIAS = (1, 2, 3, 4, 6, 12)


def _sumar_mes(a: int, m: int, n: int = 1) -> tuple[int, int]:
    t = a * 12 + (m - 1) + n
    return t // 12, t % 12 + 1


def toca_en(f: GastoFijo, a: int, m: int) -> bool:
    """¿Este fijo se paga en el mes (a, m)?"""
    cada = f.cada_meses or 1
    if cada <= 1:
        return True
    return (m - (f.mes_inicio or 1)) % cada == 0


def por_mes(f: GastoFijo) -> Decimal:
    """Lo que hay que apartar por mes: el monto entero si es mensual; si no, la parte."""
    return (f.monto / (f.cada_meses or 1)).quantize(Decimal("1"))


def ocurrencias(f: GastoFijo, desde: date, hasta: date) -> list[date]:
    out, (a, m) = [], (desde.year, desde.month)
    while date(a, m, 1) <= hasta:
        if toca_en(f, a, m):
            d = dia_en(a, m, f.dia)
            if desde <= d <= hasta:
                out.append(d)
        a, m = _sumar_mes(a, m)
    return out


def proxima(f: GastoFijo, hoy: date) -> date:
    """La próxima fecha en que toca (hoy incluido) que todavía no se resolvió."""
    a, m = hoy.year, hoy.month
    for _ in range(25):
        if toca_en(f, a, m):
            d = dia_en(a, m, f.dia)
            if not (a == hoy.year and m == hoy.month and (f.ultimo_periodo == periodo(hoy) or d < hoy)):
                return d
        a, m = _sumar_mes(a, m)
    return dia_en(*_sumar_mes(hoy.year, hoy.month), f.dia)


def mes_inicial(dia: int, hoy: date) -> int:
    """Si no dijiste en qué mes, el próximo en que cae ese día."""
    return hoy.month if dia >= hoy.day else _sumar_mes(hoy.year, hoy.month)[1]


def _clave(desc: str) -> str:
    from app.services.detectores import clave_desc
    return clave_desc(desc)


def todos(db: Session) -> list[GastoFijo]:
    return list(db.scalars(select(GastoFijo).order_by(GastoFijo.dia, GastoFijo.nombre)))


def del_mes(db: Session, f: GastoFijo, hoy: date) -> Movimiento | None:
    """El pago de este fijo en el mes de `hoy` (generado o cargado a mano), si existe."""
    ini = hoy.replace(day=1)
    fin = dia_en(hoy.year, hoy.month, 31)
    movs = db.scalars(select(Movimiento).where(
        Movimiento.tipo == TipoMovimiento.gasto, Movimiento.fecha.between(ini, fin)))
    for m in movs:
        if (f.id is not None and m.fijo_id == f.id) or _clave(m.descripcion) == f.clave:
            return m
    return None


def _nuevo_mov(f: GastoFijo, fecha: date) -> Movimiento:
    return Movimiento(
        tipo=TipoMovimiento.gasto, estado=EstadoMovimiento.pendiente, origen=OrigenMovimiento.fijo,
        fecha=fecha, monto=f.monto, descripcion=f.nombre[:200], fijo_id=f.id,
        categoria_id=f.categoria_id, medio_pago_id=f.medio_pago_id,
        cuenta_id=f.medio_pago.cuenta_id if f.medio_pago else None,
    )


def generar(db: Session, hoy: date | None = None) -> list[Movimiento]:
    """Pone en la bandeja los fijos que tocan hasta hoy y todavía no están cargados este mes.
    Idempotente: se puede llamar cada vez que abrís la app."""
    hoy = hoy or date.today()
    per = periodo(hoy)
    nuevos = []
    for f in db.scalars(select(GastoFijo).where(GastoFijo.activo.is_(True))):
        if f.ultimo_periodo == per or f.monto <= 0 or not toca_en(f, hoy.year, hoy.month):
            continue
        fecha = dia_en(hoy.year, hoy.month, f.dia)
        if fecha > hoy:
            continue
        existente = del_mes(db, f, hoy)
        if existente:
            if existente.fijo_id is None:
                existente.fijo_id = f.id
        else:
            mov = _nuevo_mov(f, fecha)
            db.add(mov)
            nuevos.append(mov)
        f.ultimo_periodo = per
    if db.new or db.dirty:
        db.commit()
    return nuevos


def absorber(db: Session, mov: Movimiento) -> None:
    """Cargaste a mano algo que es un fijo: lo vincula y, si ya había uno generado
    esperando en la bandeja ese mes, lo saca (el tuyo manda). No hace commit."""
    if mov.tipo != TipoMovimiento.gasto:
        return
    clave = _clave(mov.descripcion)
    f = db.scalar(select(GastoFijo).where(GastoFijo.clave == clave, GastoFijo.activo.is_(True)))
    if f is None:
        return
    mov.fijo_id = f.id
    ini, fin = mov.fecha.replace(day=1), dia_en(mov.fecha.year, mov.fecha.month, 31)
    for g in db.scalars(select(Movimiento).where(
            Movimiento.fijo_id == f.id, Movimiento.origen == OrigenMovimiento.fijo,
            Movimiento.estado == EstadoMovimiento.pendiente, Movimiento.fecha.between(ini, fin))):
        if g is not mov and g.id != mov.id:
            db.delete(g)
    f.ultimo_periodo = max(f.ultimo_periodo or "", periodo(mov.fecha))


def al_confirmar(db: Session, mov: Movimiento) -> None:
    """El monto que confirmaste es el que se propone el mes que viene."""
    if mov.fijo_id:
        f = db.get(GastoFijo, mov.fijo_id)
        if f and mov.monto and periodo(mov.fecha) >= (f.ultimo_periodo or ""):
            f.monto = mov.monto
            if f.medio_pago_id is None and mov.medio_pago_id:
                f.medio_pago_id = mov.medio_pago_id


def atrasados(db: Session, hoy: date, dias: int = 2) -> list[Movimiento]:
    """Fijos generados que siguen sin confirmar varios días después de la fecha."""
    return list(db.scalars(select(Movimiento).where(
        Movimiento.fijo_id.is_not(None), Movimiento.estado == EstadoMovimiento.pendiente,
        Movimiento.fecha <= hoy - timedelta(days=dias)).order_by(Movimiento.fecha)))


def de_hoy(db: Session, hoy: date) -> list[Movimiento]:
    return list(db.scalars(select(Movimiento).where(
        Movimiento.fijo_id.is_not(None), Movimiento.estado == EstadoMovimiento.pendiente,
        Movimiento.origen == OrigenMovimiento.fijo, Movimiento.fecha == hoy)))


# ───────────────────────── altas ─────────────────────────
def _ultimo_pago(db: Session, clave: str) -> Movimiento | None:
    movs = db.scalars(select(Movimiento).where(
        Movimiento.tipo == TipoMovimiento.gasto, Movimiento.estado == EstadoMovimiento.confirmado)
        .order_by(Movimiento.fecha.desc()).limit(600))
    return next((m for m in movs if _clave(m.descripcion) == clave), None)


def desde_detectado(db: Session, clave: str, activo: bool = True, hoy: date | None = None) -> GastoFijo:
    """Activa (o descarta, con activo=False) un fijo detectado en tus movimientos."""
    hoy = hoy or date.today()
    f = db.scalar(select(GastoFijo).where(GastoFijo.clave == clave))
    ult = _ultimo_pago(db, clave)
    if f is None:
        f = GastoFijo(clave=clave, nombre=ult.descripcion if ult else clave.capitalize())
        db.add(f)
    f.activo = activo
    if ult:
        f.monto, f.dia = ult.monto, ult.fecha.day
        f.categoria_id = f.categoria_id or ult.categoria_id
        f.medio_pago_id = f.medio_pago_id or ult.medio_pago_id
        # Si este mes ya lo pagaste, no hay nada que generar hasta el que viene
        if periodo(ult.fecha) == periodo(hoy):
            f.ultimo_periodo = periodo(ult.fecha)
    db.flush()
    if ult and activo and ult.fijo_id is None:
        ult.fijo_id = f.id
    return f


def nuevo(db: Session, *, nombre: str, monto: Decimal, dia: int, categoria_id=None, medio_pago_id=None,
          cada_meses: int = 1, mes_inicio: int | None = None, hoy: date | None = None) -> GastoFijo:
    clave = _clave(nombre)
    f = db.scalar(select(GastoFijo).where(GastoFijo.clave == clave))
    if f is None:
        f = GastoFijo(clave=clave)
        db.add(f)
    f.nombre, f.monto, f.dia, f.activo = nombre.strip(), monto, max(1, min(31, dia)), True
    f.categoria_id, f.medio_pago_id = categoria_id, medio_pago_id
    hoy = hoy or date.today()
    f.cada_meses = cada_meses if cada_meses in FRECUENCIAS else 1
    f.mes_inicio = None if f.cada_meses == 1 else (mes_inicio or mes_inicial(f.dia, hoy))
    db.flush()
    if toca_en(f, hoy.year, hoy.month) and del_mes(db, f, hoy):
        f.ultimo_periodo = periodo(hoy)
    return f


@dataclass
class Sugerido:
    clave: str
    nombre: str
    monto: Decimal
    dia: int
    meses: int
    categoria: str | None


def sugeridos(db: Session, hoy: date) -> list[Sugerido]:
    """Lo que parece fijo en tus movimientos y todavía no decidiste."""
    from app.services.detectores import recurrentes_detectados
    decididos = set(db.scalars(select(GastoFijo.clave)))
    return [Sugerido(r.clave, r.nombre, r.ultimo, r.ultima.day if r.ultima else 1, r.meses, r.categoria)
            for r in recurrentes_detectados(db, hoy) if r.clave not in decididos]


def proximos_no_mensuales(db: Session, hoy: date, dias: int = 21) -> list[tuple[GastoFijo, date]]:
    """Los que no son de todos los meses y se vienen pronto (para avisar antes)."""
    out = []
    for f in db.scalars(select(GastoFijo).where(GastoFijo.activo.is_(True), GastoFijo.cada_meses > 1)):
        d = proxima(f, hoy)
        if d <= hoy + timedelta(days=dias):
            out.append((f, d))
    return sorted(out, key=lambda x: x[1])
