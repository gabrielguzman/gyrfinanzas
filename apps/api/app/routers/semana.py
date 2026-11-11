import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import HallazgoDescartado, Movimiento
from app.routers.movimientos import _cargar, serializar
from app.routers.util import obtener
from app.schemas import (
    ArrepentimientoOut,
    DescartarIn,
    HallazgoOut,
    MovimientoOut,
    SemanaOut,
    TopCategoria,
    ValioIn,
    VencimientoOut,
)
from app.services import detectores, semanal

router = APIRouter(tags=["semana"])


def _h(h: detectores.Hallazgo) -> HallazgoOut:
    return HallazgoOut(**{k: v for k, v in asdict(h).items() if k != "orden"})


@router.get("/hallazgos", response_model=list[HallazgoOut])
def hallazgos(db: Session = Depends(get_db)):
    return [_h(h) for h in detectores.hallazgos(db)]


@router.post("/hallazgos/descartar", status_code=204)
def descartar(datos: DescartarIn, db: Session = Depends(get_db)):
    if db.get(HallazgoDescartado, datos.clave) is None:
        db.add(HallazgoDescartado(clave=datos.clave))
        db.commit()


@router.post("/hallazgos/restaurar", status_code=204)
def restaurar(datos: DescartarIn, db: Session = Depends(get_db)):
    h = db.get(HallazgoDescartado, datos.clave)
    if h:
        db.delete(h)
        db.commit()


@router.get("/repaso", response_model=list[MovimientoOut])
def repaso(db: Session = Depends(get_db)):
    return [serializar(_cargar(db, m.id)) for m in semanal.para_repasar(db)]


@router.post("/movimientos/{mov_id}/valio", response_model=MovimientoOut)
def valio(mov_id: uuid.UUID, datos: ValioIn, db: Session = Depends(get_db)):
    m = obtener(db, Movimiento, mov_id, "Movimiento")
    m.valio = datos.valio
    db.commit()
    return serializar(_cargar(db, mov_id))


@router.get("/repaso/arrepentimientos", response_model=list[ArrepentimientoOut])
def arrepentimientos(db: Session = Depends(get_db)):
    return [ArrepentimientoOut(**asdict(a)) for a in semanal.arrepentimientos(db)]


@router.get("/semana", response_model=SemanaOut)
def semana(db: Session = Depends(get_db)):
    s = semanal.armar(db)
    return SemanaOut(
        desde=s.desde, hasta=s.hasta, gastos=s.gastos, gastos_anterior=s.gastos_anterior, cantidad=s.cantidad,
        fijos=s.fijos, variables=s.variables, variables_anterior=s.variables_anterior,
        top=[TopCategoria(nombre=n, icono=i, color=c, total=t) for n, i, c, t in s.top],
        mayor={"descripcion": s.mayor[0], "monto": s.mayor[1], "fecha": s.mayor[2]} if s.mayor else None,
        pendientes=s.pendientes,
        vencimientos=[VencimientoOut(**asdict(v)) for v in s.vencimientos],
        hallazgos=[_h(h) for h in s.hallazgos],
        repaso=[serializar(_cargar(db, m.id)) for m in s.repaso],
        arrepentimientos=[ArrepentimientoOut(**asdict(a)) for a in semanal.arrepentimientos(db)],
    )
