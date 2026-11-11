from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import AjustesPlanIn, CalendarioOut, EventoOut, ItemMonto, PresupuestoOut, PuntoOut
from app.services import plan as svc

router = APIRouter(prefix="/plan", tags=["plan"])


def plan_out(p: svc.Plan) -> PresupuestoOut:
    return PresupuestoOut(
        configurado=p.configurado, dia_cobro=p.cobro.dia, ingreso_esperado=p.cobro.monto,
        cobro_detectado=p.cobro.detectado, ahorro=p.ahorro, desde=p.desde, hasta=p.hasta,
        proximo_cobro=p.proximo_cobro, dias_restantes=p.dias_restantes, dias_total=p.dias_total,
        ingreso=p.ingreso, fijos=p.fijos, cuotas_tarjetas=p.cuotas_tarjetas, cuotas_prestamos=p.cuotas_prestamos, metas=p.metas,
        para_gastar=p.para_gastar, gastado=p.gastado, gastado_hoy=p.gastado_hoy, restante=p.restante,
        por_dia=p.por_dia, hoy=p.hoy, manana=p.manana, proyeccion_fin=p.proyeccion_fin, estado=p.estado,
        detalle_fijos=[ItemMonto(nombre=n, monto=v) for n, v in p.detalle_fijos],
        detalle_cuotas=[ItemMonto(nombre=n, monto=v) for n, v in p.detalle_cuotas],
        detalle_metas=[ItemMonto(nombre=n, monto=v) for n, v in p.detalle_metas],
    )


@router.get("", response_model=PresupuestoOut)
def ver(hoy: date | None = None, db: Session = Depends(get_db)):
    return plan_out(svc.calcular(db, hoy))


@router.put("/ajustes", response_model=PresupuestoOut)
def ajustar(datos: AjustesPlanIn, db: Session = Depends(get_db)):
    svc.guardar_ajustes(db, {k: (str(v) if v is not None else None) for k, v in datos.model_dump(exclude_unset=True).items()})
    db.commit()
    return plan_out(svc.calcular(db))


@router.get("/calendario", response_model=CalendarioOut)
def calendario(dias: int = 60, hoy: date | None = None, db: Session = Depends(get_db)):
    c = svc.calendario(db, hoy, min(max(dias, 7), 120))
    return CalendarioOut(
        saldo_hoy=c.saldo_hoy, gasto_diario=c.gasto_diario,
        eventos=[EventoOut(**e.__dict__) for e in c.eventos],
        serie=[PuntoOut(fecha=f, saldo=s) for f, s in c.serie],
        rojo=PuntoOut(fecha=c.rojo[0], saldo=c.rojo[1]) if c.rojo else None,
        minimo=PuntoOut(fecha=c.minimo[0], saldo=c.minimo[1]),
    )
