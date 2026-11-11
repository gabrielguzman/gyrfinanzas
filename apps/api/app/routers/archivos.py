import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Archivo, Garantia
from app.routers.util import obtener
from app.schemas import ArchivoConVinculosOut
from app.services import archivos as svc

router = APIRouter(prefix="/archivos", tags=["comprobantes"])


def _out(a: Archivo, garantias: dict | None = None) -> ArchivoConVinculosOut:
    out = ArchivoConVinculosOut.model_validate(a)
    out.movimientos = [v.movimiento_id for v in a.vinculos]
    out.garantia = (garantias or {}).get(a.id)
    return out


@router.post("", response_model=ArchivoConVinculosOut, status_code=201)
def subir(archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    guardado = svc.guardar(db, archivo)
    db.commit()
    db.refresh(guardado)
    return _out(guardado)


@router.get("", response_model=list[ArchivoConVinculosOut])
def listar(sin_vincular: bool = False, db: Session = Depends(get_db)):
    archivos = db.scalars(select(Archivo).options(selectinload(Archivo.vinculos)).order_by(Archivo.creado.desc()))
    garantias = {g.archivo_id: g.producto for g in db.scalars(select(Garantia).where(Garantia.archivo_id.is_not(None)))}
    return [_out(a, garantias) for a in archivos if not (sin_vincular and (a.vinculos or a.id in garantias))]


@router.get("/{archivo_id}", response_model=ArchivoConVinculosOut)
def detalle(archivo_id: uuid.UUID, db: Session = Depends(get_db)):
    return _out(obtener(db, Archivo, archivo_id, "Archivo"))


@router.get("/{archivo_id}/contenido")
def contenido(archivo_id: uuid.UUID, db: Session = Depends(get_db)):
    archivo = obtener(db, Archivo, archivo_id, "Archivo")
    ruta = svc.ruta_absoluta(archivo)
    if not ruta.exists():
        raise HTTPException(410, "El archivo ya no está en el almacenamiento")
    return FileResponse(ruta, media_type=archivo.mime, filename=archivo.nombre_original)
