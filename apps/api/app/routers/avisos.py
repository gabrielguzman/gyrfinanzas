from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import PushSuscripcion
from app.services import avisos as svc

router = APIRouter(prefix="/avisos", tags=["avisos"])


class Preferencias(BaseModel):
    notif_hoy: bool
    notif_fijos: bool
    notif_vencimientos: bool
    notif_avisos: bool
    notif_racha: bool
    notif_hora: str


class PreferenciasPatch(BaseModel):
    notif_hoy: bool | None = None
    notif_fijos: bool | None = None
    notif_vencimientos: bool | None = None
    notif_avisos: bool | None = None
    notif_racha: bool | None = None
    notif_hora: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{1,2}$")


class EstadoAvisos(BaseModel):
    clave_publica: str
    dispositivos: int
    preferencias: Preferencias


class Claves(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class Suscripcion(BaseModel):
    endpoint: str = Field(max_length=1000, pattern=r"^https://")
    keys: Claves
    dispositivo: str = Field(default="", max_length=120)


class Baja(BaseModel):
    endpoint: str = Field(max_length=1000)


class Prueba(BaseModel):
    endpoint: str | None = None


def _estado(db: Session) -> EstadoAvisos:
    return EstadoAvisos(clave_publica=svc.clave_publica(db),
                        dispositivos=db.scalar(select(func.count()).select_from(PushSuscripcion)) or 0,
                        preferencias=Preferencias(**svc.preferencias(db)))


@router.get("", response_model=EstadoAvisos)
def estado(db: Session = Depends(get_db)):
    return _estado(db)


@router.put("/preferencias", response_model=EstadoAvisos)
def preferencias(datos: PreferenciasPatch, db: Session = Depends(get_db)):
    svc.guardar_preferencias(db, datos.model_dump(exclude_unset=True))
    db.commit()
    return _estado(db)


@router.post("/suscribir", response_model=EstadoAvisos)
def suscribir(datos: Suscripcion, db: Session = Depends(get_db)):
    s = db.scalar(select(PushSuscripcion).where(PushSuscripcion.endpoint == datos.endpoint))
    if s is None:
        s = PushSuscripcion(endpoint=datos.endpoint)
        db.add(s)
    s.p256dh, s.auth, s.dispositivo = datos.keys.p256dh, datos.keys.auth, datos.dispositivo
    db.commit()
    return _estado(db)


@router.post("/desuscribir", response_model=EstadoAvisos)
def desuscribir(datos: Baja, db: Session = Depends(get_db)):
    s = db.scalar(select(PushSuscripcion).where(PushSuscripcion.endpoint == datos.endpoint))
    if s:
        db.delete(s)
        db.commit()
    return _estado(db)


@router.post("/probar")
def probar(datos: Prueba, db: Session = Depends(get_db)):
    subs = list(db.scalars(select(PushSuscripcion).where(PushSuscripcion.endpoint == datos.endpoint))) if datos.endpoint else None
    n = svc.enviar(db, svc.Aviso("prueba", "¡Listo! 🎉", "Así te van a llegar los avisos de gyrfinanzas.", "/"), subs)
    return {"enviadas": n}
