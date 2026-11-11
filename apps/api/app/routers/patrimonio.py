import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Inversion, TipoInversion
from app.routers.util import obtener
from app.schemas import (
    CotizacionIn,
    CotizacionOut,
    InversionIn,
    InversionOut,
    InversionPatch,
    ItemPatrimonioOut,
    PatrimonioOut,
    PuntoPatrimonioOut,
)
from app.services import cotizacion as svc_cot
from app.services import patrimonio as svc
from app.services.cotizacion import a_pesos

router = APIRouter(tags=["patrimonio"])


def _cot_out(db: Session, cot) -> CotizacionOut:
    return CotizacionOut(
        valor=cot.valor if cot else None, casa=cot.casa if cot else svc_cot.casa_elegida(db),
        nombre=cot.nombre if cot else svc_cot.CASAS.get(svc_cot.casa_elegida(db), ""),
        fecha=cot.fecha if cot else None, vieja=cot.vieja if cot else False,
        manual=bool(cot and cot.casa == "manual"), casas=svc_cot.CASAS,
    )


def _inv_out(i: Inversion, cot) -> InversionOut:
    v = svc.valor_inversion(i, date.today())
    return InversionOut(
        id=i.id, nombre=i.nombre, tipo=i.tipo.value, moneda=i.moneda, capital=i.capital, tna=i.tna,
        fecha_inicio=i.fecha_inicio, vence=i.vence, valor_actual=i.valor_actual, actualizado=i.actualizado,
        cerrada=i.cerrada, notas=i.notas, valor=v, ganancia=v - i.capital, valor_ars=a_pesos(v, i.moneda.value, cot),
    )


@router.get("/patrimonio", response_model=PatrimonioOut)
def patrimonio(db: Session = Depends(get_db)):
    cot = svc_cot.obtener(db)
    p = svc.calcular(db, None, cot)
    return PatrimonioOut(
        items=[ItemPatrimonioOut(**i.__dict__) for i in p.items], activos=p.activos, pasivos=p.pasivos,
        neto=p.neto, neto_usd=p.neto_usd, cotizacion=_cot_out(db, cot), sin_convertir=p.sin_convertir,
        liquido=p.liquido, gasto_esencial=p.gasto_esencial, gasto_mensual=p.gasto_mensual,
        meses_esencial=p.meses_esencial, meses_total=p.meses_total,
        serie=[PuntoPatrimonioOut(fecha=f, neto=n, estimado=e) for f, n, e in p.serie],
    )


@router.get("/cotizacion", response_model=CotizacionOut)
def cotizacion(db: Session = Depends(get_db)):
    return _cot_out(db, svc_cot.obtener(db))


@router.put("/cotizacion", response_model=CotizacionOut)
def configurar_cotizacion(datos: CotizacionIn, db: Session = Depends(get_db)):
    if datos.casa and datos.casa not in svc_cot.CASAS:
        raise HTTPException(422, "Cotización desconocida")
    svc_cot.configurar(db, datos.casa, datos.manual, datos.borrar_manual)
    db.commit()
    return _cot_out(db, svc_cot.obtener(db))


@router.get("/inversiones", response_model=list[InversionOut])
def listar(incluir_cerradas: bool = False, db: Session = Depends(get_db)):
    q = select(Inversion).order_by(Inversion.cerrada, Inversion.fecha_inicio.desc())
    if not incluir_cerradas:
        q = q.where(Inversion.cerrada.is_(False))
    cot = svc_cot.obtener(db)
    return [_inv_out(i, cot) for i in db.scalars(q)]


@router.post("/inversiones", response_model=InversionOut, status_code=201)
def crear(datos: InversionIn, db: Session = Depends(get_db)):
    d = datos.model_dump()
    d["tipo"] = TipoInversion(d["tipo"])
    d["fecha_inicio"] = d["fecha_inicio"] or date.today()
    if d["vence"] and d["vence"] < d["fecha_inicio"]:
        raise HTTPException(422, "El vencimiento es anterior al inicio")
    i = Inversion(**d, actualizado=date.today() if d["valor_actual"] is not None else None)
    db.add(i)
    db.commit()
    return _inv_out(i, svc_cot.obtener(db))


@router.patch("/inversiones/{iid}", response_model=InversionOut)
def editar(iid: uuid.UUID, datos: InversionPatch, db: Session = Depends(get_db)):
    i = obtener(db, Inversion, iid, "Inversión")
    cambios = datos.model_dump(exclude_unset=True)
    for k, v in cambios.items():
        if v is not None or k in ("tna", "vence", "valor_actual"):
            setattr(i, k, v)
    if "valor_actual" in cambios:
        i.actualizado = date.today() if cambios["valor_actual"] is not None else None
    db.commit()
    return _inv_out(i, svc_cot.obtener(db))


@router.delete("/inversiones/{iid}", status_code=204)
def borrar(iid: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(obtener(db, Inversion, iid, "Inversión"))
    db.commit()
