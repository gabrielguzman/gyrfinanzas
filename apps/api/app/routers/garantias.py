import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Archivo, Garantia, Movimiento, MovimientoAdjunto
from app.routers.util import obtener
from app.schemas import GarantiaArchivo, GarantiaIn, GarantiaOut, GarantiaPatch, ReparacionIn
from app.services import garantias as svc

router = APIRouter(prefix="/garantias", tags=["garantías"])
ORDEN = {"por_vencer": 0, "en_reparacion": 1, "vigente": 2, "vencida": 3}


def _cargar(db: Session, gid: uuid.UUID) -> Garantia:
    g = db.scalar(select(Garantia).where(Garantia.id == gid).options(
        selectinload(Garantia.archivo),
        selectinload(Garantia.movimiento).selectinload(Movimiento.adjuntos).selectinload(MovimientoAdjunto.archivo),
        selectinload(Garantia.movimiento).selectinload(Movimiento.medio_pago),
    ))
    if g is None:
        raise HTTPException(404, "Garantía no encontrada")
    return g


def _out(g: Garantia, hoy: date | None = None) -> GarantiaOut:
    e = svc.estado(g, hoy)
    archivos: list[GarantiaArchivo] = []
    if g.archivo:
        archivos.append(GarantiaArchivo(id=g.archivo.id, nombre=g.archivo.nombre_original, mime=g.archivo.mime, rol="garantia"))
    m = g.movimiento
    if m:
        # Primero el certificado de garantía, después la factura y el ticket
        prioridad = {"garantia": 0, "factura": 1, "ticket": 2}
        for a in sorted(m.adjuntos, key=lambda a: prioridad.get(a.rol.value, 9)):
            if not any(x.id == a.archivo_id for x in archivos):
                archivos.append(GarantiaArchivo(id=a.archivo_id, nombre=a.archivo.nombre_original, mime=a.archivo.mime, rol=a.rol.value))
    return GarantiaOut(
        id=g.id, producto=g.producto, comercio=g.comercio, serie=g.serie, fecha_compra=g.fecha_compra,
        meses=g.meses, vence=e.vence, estado=e.estado, dias_restantes=e.dias_restantes, progreso=e.progreso,
        en_reparacion_desde=g.en_reparacion_desde, dias_reparacion=g.dias_reparacion, notas=g.notas,
        movimiento_id=g.movimiento_id, monto=m.monto if m else None,
        medio_pago=m.medio_pago.nombre if m and m.medio_pago else None, archivos=archivos,
    )


@router.get("", response_model=list[GarantiaOut])
def listar(db: Session = Depends(get_db)):
    salida = [_out(_cargar(db, g.id)) for g in svc.activas(db)]
    return sorted(salida, key=lambda g: (ORDEN[g.estado], -g.vence.toordinal() if g.estado == "vencida" else g.vence.toordinal()))


@router.get("/{gid}", response_model=GarantiaOut)
def detalle(gid: uuid.UUID, db: Session = Depends(get_db)):
    return _out(_cargar(db, gid))


@router.post("", response_model=GarantiaOut, status_code=201)
def crear(datos: GarantiaIn, db: Session = Depends(get_db)):
    mov = obtener(db, Movimiento, datos.movimiento_id, "Movimiento") if datos.movimiento_id else None
    if mov and mov.garantias:
        raise HTTPException(409, "Esa compra ya tiene una garantía cargada")
    if datos.archivo_id:
        obtener(db, Archivo, datos.archivo_id, "Archivo")
    producto = (datos.producto or (svc.producto_de(mov) if mov else "")).strip()
    if not producto:
        raise HTTPException(422, "Decime qué producto es")
    fecha = datos.fecha_compra or (mov.fecha if mov else date.today())
    g = svc.nueva(db, producto=producto, fecha_compra=fecha, meses=datos.meses, vence=datos.vence,
                  comercio=datos.comercio, serie=datos.serie, notas=datos.notas, movimiento=mov,
                  archivo_id=datos.archivo_id)
    db.commit()
    return _out(_cargar(db, g.id))


@router.patch("/{gid}", response_model=GarantiaOut)
def editar(gid: uuid.UUID, datos: GarantiaPatch, db: Session = Depends(get_db)):
    g = obtener(db, Garantia, gid, "Garantía")
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("archivo_id"):
        obtener(db, Archivo, cambios["archivo_id"], "Archivo")
    for k, v in cambios.items():
        if v is not None or k == "archivo_id":
            setattr(g, k, v)
    if ("meses" in cambios or "fecha_compra" in cambios) and "vence" not in cambios:
        svc.recalcular(g)
    db.commit()
    return _out(_cargar(db, g.id))


@router.post("/{gid}/reparacion", response_model=GarantiaOut)
def reparacion(gid: uuid.UUID, datos: ReparacionIn, db: Session = Depends(get_db)):
    g = obtener(db, Garantia, gid, "Garantía")
    fecha = datos.fecha or date.today()
    if datos.accion == "enviar":
        svc.enviar_a_reparar(g, fecha)
    else:
        if g.en_reparacion_desde and fecha < g.en_reparacion_desde:
            raise HTTPException(422, "La fecha de vuelta es anterior a la de envío")
        svc.volvio_de_reparar(g, fecha)
    db.commit()
    return _out(_cargar(db, g.id))


@router.delete("/{gid}", status_code=204)
def borrar(gid: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(obtener(db, Garantia, gid, "Garantía"))
    db.commit()
