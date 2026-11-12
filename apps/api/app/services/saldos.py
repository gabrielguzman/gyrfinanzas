"""Saldos calculados al vuelo a partir de movimientos confirmados."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import Cuenta, EstadoMovimiento, Movimiento, TipoMovimiento

CERO = Decimal("0")


def saldos_por_cuenta(db: Session, hasta: date | None = None) -> dict[uuid.UUID, Decimal]:
    """Devuelve {cuenta_id: saldo} para todas las cuentas (al final del día `hasta`, si se pide)."""
    # Lo marcado «ya estaba descontado del saldo» no mueve el saldo
    confirmado = (Movimiento.estado == EstadoMovimiento.confirmado) & Movimiento.fuera_de_saldo.is_(False)
    if hasta is not None:
        confirmado = confirmado & (Movimiento.fecha <= hasta)

    # Efecto sobre la cuenta origen: ingreso suma; gasto y transferencia restan.
    signo = case(
        (Movimiento.tipo == TipoMovimiento.ingreso, Movimiento.monto),
        else_=-Movimiento.monto,
    )
    origen = dict(
        db.execute(
            select(Movimiento.cuenta_id, func.sum(signo))
            .where(confirmado, Movimiento.cuenta_id.is_not(None))
            .group_by(Movimiento.cuenta_id)
        ).all()
    )
    # Transferencias: suman en la cuenta destino.
    destino = dict(
        db.execute(
            select(Movimiento.cuenta_destino_id, func.sum(Movimiento.monto))
            .where(
                confirmado,
                Movimiento.tipo == TipoMovimiento.transferencia,
                Movimiento.cuenta_destino_id.is_not(None),
            )
            .group_by(Movimiento.cuenta_destino_id)
        ).all()
    )

    resultado: dict[uuid.UUID, Decimal] = {}
    for cuenta_id, saldo_inicial in db.execute(select(Cuenta.id, Cuenta.saldo_inicial)).all():
        total = Decimal(saldo_inicial or 0) + Decimal(origen.get(cuenta_id) or 0) + Decimal(destino.get(cuenta_id) or 0)
        resultado[cuenta_id] = total.quantize(Decimal("0.01"))
    return resultado
