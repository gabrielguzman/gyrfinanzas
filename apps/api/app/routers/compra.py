from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import MedioPago
from app.routers.util import obtener
from app.schemas import CompraIn, CuotasContadoOut, FotoOut, MesOut, PuntoOut, SimulacionOut
from app.services import compra as svc
from app.services.registro import interpretar_texto

router = APIRouter(prefix="/compra", tags=["¿me lo puedo comprar?"])


def _foto(f: svc.Foto) -> FotoOut:
    return FotoOut(
        hoy=f.hoy, por_dia=f.por_dia, manana=f.manana, restante=f.restante,
        meses=[MesOut(desde=m.desde, para_gastar=m.para_gastar, cuotas=m.cuotas_tarjetas + m.cuotas_prestamos) for m in f.meses],
        rojo=PuntoOut(fecha=f.rojo[0], saldo=f.rojo[1]) if f.rojo else None,
        minimo=PuntoOut(fecha=f.minimo[0], saldo=f.minimo[1]), liquido=f.liquido, meses_fondo=f.meses_fondo,
    )


@router.post("/simular", response_model=SimulacionOut)
def simular(datos: CompraIn, db: Session = Depends(get_db)):
    monto, cuotas, medio, desc = datos.monto, datos.cuotas, None, datos.descripcion
    if datos.texto:
        r = interpretar_texto(db, datos.texto)
        monto = monto or r.monto
        cuotas = cuotas or r.cuotas
        medio = r.medio
        desc = desc or r.descripcion
    if datos.medio_pago_id:
        medio = obtener(db, MedioPago, datos.medio_pago_id, "Medio de pago")
    if not monto:
        raise HTTPException(422, "Decime cuánto sale. Por ejemplo: «notebook 1.2M en 12 cuotas visa».")
    s = svc.simular(db, monto=monto, cuotas=cuotas or 1, medio=medio, descripcion=desc or "Compra",
                    precio_contado=datos.precio_contado, total_cuotas=datos.total_cuotas, inflacion=datos.inflacion)
    return SimulacionOut(
        descripcion=s.descripcion, monto=s.monto, cuotas=s.cuotas, medio_pago_id=medio.id if medio else None,
        medio=s.medio, con_tarjeta=s.con_tarjeta, antes=_foto(s.antes), despues=_foto(s.despues),
        veredicto=s.veredicto, motivos=s.motivos, primera_cuota=s.primera_cuota, mejor_dia=s.mejor_dia,
        primera_cuota_mejor_dia=s.primera_cuota_mejor_dia,
        cuotas_contado=CuotasContadoOut(**s.cuotas_contado.__dict__) if s.cuotas_contado else None,
    )
