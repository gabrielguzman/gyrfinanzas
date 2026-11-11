"""Reglas para registrar movimientos, compartidas por la API y el bot."""
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Archivo,
    Deuda,
    TipoDeuda,
    Categoria,
    Cuenta,
    EstadoMovimiento,
    MedioPago,
    Movimiento,
    MovimientoAdjunto,
    OrigenMovimiento,
    RolAdjunto,
    TipoCuenta,
    TipoMedioPago,
    TipoMovimiento,
)
from app.services.captura import Resultado, _plano, interpretar
from app.services.tarjetas import plan_desde_movimiento


def _obtener(db: Session, modelo, id_, nombre: str):
    obj = db.get(modelo, id_)
    if obj is None:
        raise HTTPException(404, f"{nombre} no encontrado/a")
    return obj


# ---------- Interpretación con memoria ----------
def _aprender(db: Session, r: Resultado) -> None:
    """Completa lo que el texto no dijo usando movimientos anteriores confirmados."""
    confirmados = select(Movimiento).where(Movimiento.estado == EstadoMovimiento.confirmado)

    # 1) Mismo concepto ya cargado antes ("nafta"): copiamos categoría y medio.
    previo = db.scalar(
        confirmados.where(func.lower(Movimiento.descripcion) == r.descripcion.lower())
        .order_by(Movimiento.fecha.desc(), Movimiento.creado.desc())
        .limit(1)
    )
    if previo:
        if r.categoria is None and previo.categoria_id:
            r.categoria = db.get(Categoria, previo.categoria_id)
        if r.medio is None and previo.medio_pago_id:
            r.medio = db.get(MedioPago, previo.medio_pago_id)
            r.motivo_medio = f"la última vez «{previo.descripcion}» fue con este"

    # 2) Sin medio todavía: el último usado en esa categoría.
    if r.medio is None and r.categoria is not None:
        ultimo = db.scalar(
            confirmados.where(Movimiento.categoria_id == r.categoria.id, Movimiento.medio_pago_id.is_not(None))
            .order_by(Movimiento.fecha.desc(), Movimiento.creado.desc())
            .limit(1)
        )
        if ultimo:
            r.medio = db.get(MedioPago, ultimo.medio_pago_id)
            r.motivo_medio = f"es el que usás para {r.categoria.nombre}"


def interpretar_texto(db: Session, texto: str) -> Resultado:
    medios = list(db.scalars(select(MedioPago)))
    categorias = list(db.scalars(select(Categoria)))
    r = interpretar(texto, medios, categorias)
    from app.services.reglas import categoria_para
    if r.deuda is None and (cat := categoria_para(db, texto, r.descripcion, tipo=r.tipo)):
        r.categoria = cat  # tus reglas mandan
    _aprender(db, r)
    _revisar_cuotas(r, medios, texto)
    return r


def _revisar_cuotas(r: Resultado, medios: list[MedioPago], texto: str) -> None:
    """Las compras en cuotas van con tarjeta de crédito: nunca con una billetera o débito."""
    from app.services.captura import MARCAS_TARJETA
    if not r.cuotas or r.cuotas < 2 or r.deuda:
        return
    creditos = [m for m in medios if m.tipo == TipoMedioPago.credito and not m.archivado]
    if r.medio and r.medio.tipo != TipoMedioPago.credito:
        r.medio, r.motivo_medio = None, None
    if r.medio:
        return
    marca = next((w for w in _plano(texto).split() if w.strip(".,") in MARCAS_TARJETA), None)
    if marca:
        r.aviso = (f"No tenés cargada la tarjeta «{marca.strip('.,').capitalize()}». Creala en Cuentas "
                   "(tipo tarjeta de crédito) y las cuotas van a quedar en su resumen.")
    elif not creditos:
        r.aviso = "Para comprar en cuotas necesitás cargar tu tarjeta de crédito en Cuentas."
    else:
        r.aviso = "Es en cuotas: elegí con qué tarjeta."


def sincronizar_plan(db: Session, mov: Movimiento) -> None:
    """Al editar una compra confirmada: el plan de cuotas sigue a la tarjeta, las cuotas y el monto."""
    from app.models import PlanCuotas
    from decimal import Decimal
    for pl in db.scalars(select(PlanCuotas).where(PlanCuotas.movimiento_id == mov.id)):
        cuenta = db.get(Cuenta, mov.cuenta_id) if mov.cuenta_id else None
        if not mov.cuotas or mov.cuotas < 2 or cuenta is None or cuenta.tipo != TipoCuenta.tarjeta_credito \
                or pl.cuenta_id != mov.cuenta_id:
            db.delete(pl)
        else:
            pl.cuotas_total = mov.cuotas
            pl.monto_cuota = (mov.monto / mov.cuotas).quantize(Decimal("0.01"))
    db.flush()
    if mov.estado == EstadoMovimiento.confirmado:
        plan_desde_movimiento(db, mov)


class SinMonto(ValueError):
    pass


def deuda_por_nombre(db: Session, tipo: str, nombre: str, moneda, fecha) -> Deuda:
    """La deuda abierta con esa persona, o una nueva en cero (el movimiento la mueve)."""
    t = TipoDeuda(tipo)
    abiertas = db.scalars(select(Deuda).where(Deuda.tipo == t, Deuda.cerrada.is_(False), Deuda.moneda == moneda))
    # «martin» y «Martín» son la misma persona
    d = next((x for x in abiertas if _plano(x.nombre).strip() == _plano(nombre).strip()), None)
    if d is None:
        d = Deuda(tipo=t, nombre=nombre, moneda=moneda, monto_inicial=0, fecha_alta=fecha)
        db.add(d)
        db.flush()
    return d


def crear_desde_texto(db: Session, texto: str, origen: OrigenMovimiento) -> tuple[Movimiento, Resultado]:
    """Interpreta el texto y crea el movimiento PENDIENTE (no hace commit)."""
    r = interpretar_texto(db, texto)
    if r.monto is None or r.monto <= 0:
        raise SinMonto("No encontré el monto. Probá con algo como «nafta 40k visa».")
    descripcion = r.descripcion
    if r.cuotas:
        descripcion = f"{descripcion} ({r.cuotas} cuotas)"
    deuda_id = None
    if r.deuda:
        deuda_id = deuda_por_nombre(db, r.deuda[0], r.deuda[1], r.moneda, r.fecha).id
    mov = Movimiento(
        deuda_id=deuda_id,
        tipo=r.tipo, estado=EstadoMovimiento.pendiente, origen=origen, fecha=r.fecha,
        monto=r.monto, moneda=r.moneda, descripcion=descripcion[:200], texto_original=texto,
        cuotas=r.cuotas if r.cuotas and r.cuotas > 1 else None,
        categoria_id=r.categoria.id if r.categoria else None,
        medio_pago_id=r.medio.id if r.medio else None,
        cuenta_id=r.medio.cuenta_id if r.medio else None,
    )
    db.add(mov)
    db.flush()
    from app.services.fijos import absorber
    absorber(db, mov)
    if r.garantia_meses:
        from app.services.garantias import nueva, producto_de
        nueva(db, producto=producto_de(mov), fecha_compra=mov.fecha, meses=r.garantia_meses, movimiento=mov)
    return mov, r


# ---------- Validación y confirmación ----------
def resolver(db: Session, mov: Movimiento, confirmar: bool) -> None:
    """Completa la cuenta a partir del medio de pago y valida la coherencia.

    Las validaciones duras (cuenta obligatoria, monedas) solo se exigen al
    confirmar: en la bandeja puede quedar algo incompleto.
    """
    if mov.categoria_id:
        _obtener(db, Categoria, mov.categoria_id, "Categoría")
    if mov.medio_pago_id:
        medio = _obtener(db, MedioPago, mov.medio_pago_id, "Medio de pago")
        mov.cuenta_id = medio.cuenta_id

    if mov.tipo != TipoMovimiento.transferencia:
        mov.cuenta_destino_id = None

    if not confirmar:
        return

    if mov.cuenta_id is None:
        raise HTTPException(422, "Falta indicar con qué pagaste (medio de pago o cuenta).")
    cuenta = _obtener(db, Cuenta, mov.cuenta_id, "Cuenta")
    if mov.tipo == TipoMovimiento.gasto and mov.cuotas and mov.cuotas > 1 and cuenta.tipo != TipoCuenta.tarjeta_credito:
        raise HTTPException(422, f"Las compras en cuotas van con tarjeta de crédito, no con {cuenta.nombre}. "
                                 "Elegí la tarjeta (o cargala en Cuentas), o sacale las cuotas.")
    if cuenta.moneda != mov.moneda:
        raise HTTPException(422, f"La cuenta {cuenta.nombre} es en {cuenta.moneda.value} y el movimiento en {mov.moneda.value}.")

    if mov.tipo == TipoMovimiento.transferencia:
        if mov.cuenta_destino_id is None:
            raise HTTPException(422, "Una transferencia necesita cuenta de destino.")
        if mov.cuenta_destino_id == mov.cuenta_id:
            raise HTTPException(422, "Origen y destino no pueden ser la misma cuenta.")
        destino = _obtener(db, Cuenta, mov.cuenta_destino_id, "Cuenta destino")
        if destino.moneda != cuenta.moneda:
            raise HTTPException(422, "Por ahora las transferencias deben ser entre cuentas de la misma moneda.")


def confirmar(db: Session, mov: Movimiento) -> None:
    resolver(db, mov, confirmar=True)
    mov.estado = EstadoMovimiento.confirmado
    plan_desde_movimiento(db, mov)
    from app.services.fijos import al_confirmar
    al_confirmar(db, mov)


def vincular(db: Session, mov: Movimiento, archivo: Archivo, rol: RolAdjunto) -> None:
    existente = db.get(MovimientoAdjunto, (mov.id, archivo.id))
    if existente:
        existente.rol = rol
    else:
        db.add(MovimientoAdjunto(movimiento_id=mov.id, archivo_id=archivo.id, rol=rol))


def borrar(db: Session, mov: Movimiento) -> None:
    """Borra un movimiento. La garantía es de esa compra: si la compra no existía
    (error, deshacer), tampoco la garantía; si tiene comprobante propio, se queda."""
    from app.models import Garantia
    for g in db.scalars(select(Garantia).where(Garantia.movimiento_id == mov.id)):
        if g.archivo_id is None:
            db.delete(g)
    db.delete(mov)
