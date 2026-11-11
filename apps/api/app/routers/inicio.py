from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Cuenta, EstadoMovimiento, Movimiento, MovimientoAdjunto, TipoCuenta, TipoMovimiento
from app.schemas import InicioOut, TotalMoneda
from app.services.saldos import saldos_por_cuenta
from app.services.tarjetas import deuda_corriente

router = APIRouter(prefix="/inicio", tags=["inicio"])


@router.get("", response_model=InicioOut)
def inicio(db: Session = Depends(get_db)):
    saldos = saldos_por_cuenta(db)
    por_moneda: dict = {}
    for c in db.scalars(select(Cuenta).where(Cuenta.archivada.is_(False))):
        t = por_moneda.setdefault(c.moneda, {"en_cuentas": Decimal("0"), "deuda": Decimal("0"), "futuras": Decimal("0")})
        saldo = saldos.get(c.id, Decimal("0"))
        if c.tipo == TipoCuenta.tarjeta_credito:
            # Una compra en cuotas no se paga toda ahora: solo resta lo que vence en el resumen abierto
            ahora, futuras = deuda_corriente(db, c, saldo)
            t["deuda"] += ahora
            t["futuras"] += futuras
        else:
            t["en_cuentas"] += saldo
    totales = [
        TotalMoneda(moneda=m, en_cuentas=v["en_cuentas"], deuda_tarjetas=v["deuda"], cuotas_futuras=v["futuras"],
                    disponible=v["en_cuentas"] - v["deuda"])
        for m, v in sorted(por_moneda.items(), key=lambda kv: kv[0].value)
    ]

    pendientes = db.scalar(
        select(func.count()).select_from(Movimiento).where(Movimiento.estado == EstadoMovimiento.pendiente)
    )
    hoy = date.today()
    sin_comprobante = db.scalar(
        select(func.count()).select_from(Movimiento).where(
            Movimiento.estado == EstadoMovimiento.confirmado,
            Movimiento.tipo == TipoMovimiento.gasto,
            Movimiento.fecha >= hoy.replace(day=1),
            ~exists().where(MovimientoAdjunto.movimiento_id == Movimiento.id),
        )
    )
    return InicioOut(totales=totales, pendientes=pendientes or 0, sin_comprobante_mes=sin_comprobante or 0)
