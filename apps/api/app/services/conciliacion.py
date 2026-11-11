"""Del resumen leído a movimientos y planes: proponer, verificar y aplicar."""
import re
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AccionLinea,
    Categoria,
    Cuenta,
    EstadoMovimiento,
    MedioPago,
    Moneda,
    Movimiento,
    OrigenMovimiento,
    PlanCuotas,
    ResumenLinea,
    ResumenTarjeta,
    TipoCategoria,
    TipoLinea,
    TipoMedioPago,
    TipoMovimiento,
)
from app.services.captura import _buscar_categoria, _plano
from app.services.resumen_pdf import Extraccion
from app.services.tarjetas import periodo, plan_desde_movimiento, sumar_meses

CERO = Decimal("0")
SUMAN = {TipoLinea.consumo, TipoLinea.cuota, TipoLinea.impuesto, TipoLinea.interes, TipoLinea.cargo}


def _palabras(s: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", _plano(s)))


def _parecido(a: str, b: str) -> float:
    pa, pb = _palabras(a), _palabras(b)
    return len(pa & pb) / max(1, min(len(pa), len(pb))) if pa and pb else 0.0


# ---------- verificación ----------
def verificar(r: ResumenTarjeta) -> dict:
    """¿La suma de lo leído da el total del resumen? (en pesos)."""
    lineas = [l for l in r.lineas if l.moneda == Moneda.ARS]
    cargos = sum((l.monto for l in lineas if l.tipo in SUMAN), CERO)
    restas = sum((l.monto for l in lineas if l.tipo in (TipoLinea.pago, TipoLinea.ajuste)), CERO)
    calculado = (r.saldo_anterior or CERO) + cargos - restas
    diferencia = None if r.total_ars is None else (r.total_ars - calculado)
    return {
        "saldo_anterior": r.saldo_anterior or CERO,
        "cargos": cargos,
        "pagos_y_ajustes": restas,
        "calculado": calculado,
        "total": r.total_ars,
        "diferencia": diferencia,
        "cuadra": diferencia is not None and abs(diferencia) <= Decimal("1.00"),
        "por_tipo": {t.value: sum((l.monto for l in lineas if l.tipo == t), CERO) for t in TipoLinea},
    }


# ---------- propuesta ----------
def cargar_extraccion(db: Session, r: ResumenTarjeta, ex: Extraccion) -> None:
    r.metodo = ex.metodo
    r.fecha_cierre, r.fecha_vencimiento = ex.fecha_cierre, ex.fecha_vencimiento
    r.saldo_anterior, r.total_ars, r.total_usd = ex.saldo_anterior, ex.total_ars, ex.total_usd
    r.pago_minimo, r.tna = ex.pago_minimo, ex.tna
    if ex.fecha_cierre:
        p = periodo(ex.fecha_cierre.year, ex.fecha_cierre.month)
        otro = db.scalar(select(ResumenTarjeta).where(
            ResumenTarjeta.cuenta_id == r.cuenta_id, ResumenTarjeta.periodo == p, ResumenTarjeta.id != r.id))
        r.periodo = None if otro else p
    for i, l in enumerate(ex.lineas):
        r.lineas.append(ResumenLinea(
            orden=i, fecha=l.fecha, descripcion=l.descripcion, monto=l.monto, moneda=l.moneda,
            tipo=l.tipo, cuota_n=l.cuota_n, cuota_total=l.cuota_total,
        ))
    db.flush()
    proponer(db, r)


def proponer(db: Session, r: ResumenTarjeta) -> None:
    """Para cada línea: vincular con algo ya cargado, crear, o ignorar (pagos)."""
    ref = r.fecha_cierre or max((l.fecha for l in r.lineas if l.fecha), default=None)
    candidatos: list[Movimiento] = []
    if ref:
        candidatos = list(db.scalars(select(Movimiento).where(
            Movimiento.cuenta_id == r.cuenta_id,
            Movimiento.tipo == TipoMovimiento.gasto,
            Movimiento.fecha.between(ref - timedelta(days=75), ref + timedelta(days=3)),
        )))
    # Movimientos ya enlazados a líneas de otros resúmenes no se reutilizan
    usados = set(db.scalars(select(ResumenLinea.movimiento_id).where(
        ResumenLinea.movimiento_id.is_not(None), ResumenLinea.resumen_id != r.id)))
    planes = list(db.scalars(select(PlanCuotas).where(PlanCuotas.cuenta_id == r.cuenta_id)))

    for l in r.lineas:
        l.movimiento_id = None
        l.plan_id = None
        if l.tipo == TipoLinea.pago:
            l.accion = AccionLinea.ignorar
            continue
        if l.tipo == TipoLinea.cuota and (l.cuota_n or 1) > 1:
            # Cuota de una compra anterior: se enlaza a su plan (o se crea el plan al confirmar).
            plan = _plan_para(l, planes)
            l.plan_id = plan.id if plan else None
            l.accion = AccionLinea.vincular if plan else AccionLinea.crear
            continue
        mov = _buscar_movimiento(l, candidatos, usados)
        if mov:
            usados.add(mov.id)
            l.movimiento_id = mov.id
            l.accion = AccionLinea.vincular
        else:
            l.accion = AccionLinea.crear


def _plan_para(l: ResumenLinea, planes: list[PlanCuotas]) -> PlanCuotas | None:
    mejor, puntaje = None, 0.0
    for p in planes:
        if p.cuotas_total != l.cuota_total or p.moneda != l.moneda:
            continue
        if abs(p.monto_cuota - l.monto) > max(Decimal("1"), l.monto * Decimal("0.02")):
            continue
        s = 1 + _parecido(p.descripcion, l.descripcion)
        if s > puntaje:
            mejor, puntaje = p, s
    return mejor


def _buscar_movimiento(l: ResumenLinea, candidatos: list[Movimiento], usados: set) -> Movimiento | None:
    objetivo = [l.monto]
    if l.tipo == TipoLinea.cuota and l.cuota_total:  # 1ª cuota: la compra se cargó por el total
        objetivo.append(l.monto * l.cuota_total)
    mejor, puntaje = None, -1.0
    for m in candidatos:
        if m.id in usados or m.moneda != l.moneda:
            continue
        if not any(abs(m.monto - o) <= max(Decimal("1"), o * Decimal("0.005")) for o in objetivo):
            continue
        dias = abs((m.fecha - l.fecha).days) if l.fecha else 0
        if dias > 5:
            continue
        s = 10 - dias + 3 * _parecido(m.descripcion, l.descripcion)
        if s > puntaje:
            mejor, puntaje = m, s
    return mejor


# ---------- aplicar ----------
def _medio_credito(db: Session, cuenta_id) -> MedioPago | None:
    return db.scalar(select(MedioPago).where(
        MedioPago.cuenta_id == cuenta_id, MedioPago.tipo == TipoMedioPago.credito).limit(1))


def _categoria(l: ResumenLinea, categorias: list[Categoria]) -> Categoria | None:
    if l.tipo in (TipoLinea.impuesto, TipoLinea.interes, TipoLinea.cargo):
        return next((c for c in categorias if c.nombre == "Comisiones e intereses"), None)
    cat, _ = _buscar_categoria(_plano(l.descripcion), categorias, TipoMovimiento.gasto)
    return cat


def titulo(desc: str) -> str:
    d = re.sub(r"^(MERPAGO\*|MERCADOPAGO\*|DLO\*|PAYU\*|SP \*)", "", desc.strip(), flags=re.I).strip()
    d = d.title() if d.isupper() else d
    return d[:200] or "Consumo"


def confirmar(db: Session, r: ResumenTarjeta) -> dict:
    cuenta = db.get(Cuenta, r.cuenta_id)
    medio = _medio_credito(db, r.cuenta_id)
    categorias = list(db.scalars(select(Categoria).where(Categoria.tipo == TipoCategoria.gasto)))
    creados = vinculados = planes_nuevos = 0
    for l in r.lineas:
        if l.accion == AccionLinea.ignorar:
            continue
        if l.accion == AccionLinea.vincular:
            vinculados += 1
            # 1ª cuota de una compra cargada por el total: le falta el plan
            if l.tipo == TipoLinea.cuota and l.movimiento_id and (l.cuota_total or 1) > 1:
                mov = db.get(Movimiento, l.movimiento_id)
                if mov is not None and not mov.cuotas:
                    mov.cuotas = l.cuota_total
                plan = plan_desde_movimiento(db, mov) if mov is not None else None
                if plan:
                    plan.primer_periodo = r.periodo or plan.primer_periodo
                    db.flush()
                    l.plan_id = plan.id
                    planes_nuevos += 1
            continue
        if l.tipo == TipoLinea.cuota and (l.cuota_n or 1) > 1:
            base = r.periodo or periodo(l.fecha.year, l.fecha.month)
            plan = PlanCuotas(cuenta_id=r.cuenta_id, descripcion=titulo(l.descripcion), monto_cuota=l.monto,
                              cuotas_total=l.cuota_total or 1, moneda=l.moneda,
                              primer_periodo=sumar_meses(base, -((l.cuota_n or 1) - 1)))
            db.add(plan)
            db.flush()
            l.plan_id = plan.id
            planes_nuevos += 1
            continue
        en_cuotas = l.tipo == TipoLinea.cuota and (l.cuota_total or 1) > 1
        ajuste = l.tipo == TipoLinea.ajuste
        cat = None if ajuste else _categoria(l, categorias)
        mov = Movimiento(
            tipo=TipoMovimiento.ingreso if ajuste else TipoMovimiento.gasto,
            estado=EstadoMovimiento.confirmado, origen=OrigenMovimiento.pdf,
            fecha=l.fecha or r.fecha_cierre, monto=l.monto * (l.cuota_total or 1) if en_cuotas else l.monto,
            moneda=l.moneda,
            descripcion=titulo(l.descripcion) + (f" ({l.cuota_total} cuotas)" if en_cuotas else ""),
            categoria_id=cat.id if cat else None,
            medio_pago_id=medio.id if medio else None, cuenta_id=cuenta.id,
            cuotas=l.cuota_total if en_cuotas else None,
        )
        db.add(mov)
        db.flush()
        l.movimiento_id = mov.id
        creados += 1
        if en_cuotas:
            plan = plan_desde_movimiento(db, mov)
            if plan:
                plan.primer_periodo = r.periodo or plan.primer_periodo
                db.flush()
                l.plan_id = plan.id
                planes_nuevos += 1
    return {"creados": creados, "vinculados": vinculados, "planes_nuevos": planes_nuevos}
