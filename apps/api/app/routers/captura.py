"""Carga rápida: texto libre → movimiento pendiente en la bandeja."""
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import EstadoMovimiento, Movimiento, TipoMovimiento

from app.db import get_db
from app.routers.movimientos import _cargar, serializar
from app.schemas import CapturaIn, Frecuente, Interpretacion, MovimientoOut, Parte
from app.services.captura import Resultado
from app.services.registro import SinMonto, crear_desde_texto, interpretar_texto

router = APIRouter(prefix="/captura", tags=["captura"])


def _a_schema(r: Resultado) -> Interpretacion:
    return Interpretacion(
        tipo=r.tipo, monto=r.monto, moneda=r.moneda, descripcion=r.descripcion, fecha=r.fecha,
        medio_pago_id=r.medio.id if r.medio else None,
        medio_pago=r.medio.nombre if r.medio else None,
        cuenta_id=r.medio.cuenta_id if r.medio else None,
        categoria_id=r.categoria.id if r.categoria else None,
        categoria=r.categoria.nombre if r.categoria else None,
        cuotas=r.cuotas, motivo_medio=r.motivo_medio, faltantes=r.faltantes,
        categoria_icono=r.categoria.icono if r.categoria else None,
        categoria_color=r.categoria.color if r.categoria else None,
        partes=[Parte(inicio=a, fin=b, tipo=t) for a, b, t in r.partes],
        deuda_tipo=r.deuda[0] if r.deuda else None,
        deuda_nombre=r.deuda[1] if r.deuda else None,
        garantia_meses=r.garantia_meses,
        aviso=r.aviso,
    )


@router.post("/previsualizar", response_model=Interpretacion)
def previsualizar(datos: CapturaIn, db: Session = Depends(get_db)):
    """Lo que la app entendió, sin guardar nada (para mostrar mientras escribís)."""
    return _a_schema(interpretar_texto(db, datos.texto))


@router.post("", response_model=MovimientoOut, status_code=201)
def capturar(datos: CapturaIn, db: Session = Depends(get_db)):
    """Interpreta el texto y lo deja en la bandeja como movimiento pendiente."""
    try:
        mov, _ = crear_desde_texto(db, datos.texto, datos.origen)
    except SinMonto as e:
        raise HTTPException(422, str(e))
    db.commit()
    return serializar(_cargar(db, mov.id))


@router.get("/frecuentes", response_model=list[Frecuente])
def frecuentes(db: Session = Depends(get_db)):
    """Lo que más cargás (últimos 90 días), listo para repetir con un toque."""
    desde = date.today() - timedelta(days=90)
    movs = db.scalars(
        select(Movimiento)
        .options(selectinload(Movimiento.medio_pago), selectinload(Movimiento.categoria))
        .where(Movimiento.estado == EstadoMovimiento.confirmado,
               Movimiento.tipo == TipoMovimiento.gasto, Movimiento.fecha >= desde)
        .order_by(Movimiento.fecha.desc(), Movimiento.creado.desc())
    ).all()
    veces = Counter(m.descripcion.strip().lower() for m in movs)
    vistos: set[str] = set()
    salida: list[Frecuente] = []
    for m in movs:  # el más reciente de cada concepto define monto y medio
        clave = m.descripcion.strip().lower()
        if clave in vistos or veces[clave] < 2 or "cuotas" in clave:
            continue
        vistos.add(clave)
        alias = ""
        if m.medio_pago:
            alias = (m.medio_pago.alias.split(",")[0].strip() or m.medio_pago.nombre).lower()
        monto = int(m.monto) if m.monto == int(m.monto) else m.monto
        salida.append(Frecuente(
            texto=" ".join(filter(None, [clave, str(monto), alias])),
            descripcion=m.descripcion, monto=m.monto,
            medio_pago=m.medio_pago.nombre if m.medio_pago else None,
            categoria_icono=m.categoria.icono if m.categoria else None,
            categoria_color=m.categoria.color if m.categoria else None,
            veces=veces[clave],
        ))
    salida.sort(key=lambda f: -f.veces)
    return salida[:6]
