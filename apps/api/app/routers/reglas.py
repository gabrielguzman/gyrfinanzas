import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria, Movimiento, ReglaCategoria, TipoMovimiento
from app.routers.util import obtener
from app.services import reglas as svc

router = APIRouter(tags=["reglas"])


class ReglaOut(BaseModel):
    id: uuid.UUID
    texto: str
    categoria_id: uuid.UUID
    categoria: str
    categoria_icono: str
    categoria_color: str


class ReglaIn(BaseModel):
    texto: str = Field(min_length=2, max_length=80)
    categoria_id: uuid.UUID
    aplicar: bool = True  # también a lo que ya cargaste


class ReglaCreada(BaseModel):
    regla: ReglaOut
    cambiados: int


class PreviaIn(BaseModel):
    texto: str = Field(min_length=1, max_length=80)
    categoria_id: uuid.UUID | None = None


class PreviaOut(BaseModel):
    texto: str
    total: int
    a_cambiar: int
    ejemplos: list[str]


class SugerenciaOut(BaseModel):
    texto: str | None
    total: int = 0          # otros movimientos con ese texto
    a_cambiar: int = 0      # de esos, cuántos tienen otra categoría
    existe: bool = False    # ya hay una regla con ese texto


class LoteIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    categoria_id: uuid.UUID | None


class LoteOut(BaseModel):
    actualizados: int


def _out(r: ReglaCategoria) -> ReglaOut:
    c = r.categoria
    return ReglaOut(id=r.id, texto=r.texto, categoria_id=c.id, categoria=c.nombre, categoria_icono=c.icono, categoria_color=c.color)


@router.get("/reglas", response_model=list[ReglaOut])
def listar(db: Session = Depends(get_db)):
    return [_out(r) for r in sorted(svc.todas(db), key=lambda r: r.texto)]


@router.post("/reglas/previa", response_model=PreviaOut)
def previa(datos: PreviaIn, db: Session = Depends(get_db)):
    return PreviaOut(**svc.previa(db, datos.texto, datos.categoria_id).__dict__)


@router.post("/reglas", response_model=ReglaCreada, status_code=201)
def crear(datos: ReglaIn, db: Session = Depends(get_db)):
    obtener(db, Categoria, datos.categoria_id, "Categoría")
    if len(svc.limpiar(datos.texto)) < 2:
        raise HTTPException(422, "Escribí al menos dos letras.")
    r, n = svc.crear(db, datos.texto, datos.categoria_id, datos.aplicar)
    db.commit()
    db.refresh(r)
    return ReglaCreada(regla=_out(r), cambiados=n)


@router.delete("/reglas/{regla_id}", status_code=204)
def borrar(regla_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(obtener(db, ReglaCategoria, regla_id, "Regla"))
    db.commit()


@router.get("/reglas/sugerencia/{mov_id}", response_model=SugerenciaOut)
def sugerencia(mov_id: uuid.UUID, db: Session = Depends(get_db)):
    """Después de cambiarle la categoría a un movimiento: ¿armo una regla?"""
    m = obtener(db, Movimiento, mov_id, "Movimiento")
    texto = svc.sugerir_texto(m.descripcion) if m.tipo != TipoMovimiento.transferencia and not m.deuda_id else None
    if not texto or not m.categoria_id:
        return SugerenciaOut(texto=None)
    existe = db.scalar(select(ReglaCategoria).where(ReglaCategoria.texto == texto, ReglaCategoria.categoria_id == m.categoria_id))
    p = svc.previa(db, texto, m.categoria_id)
    return SugerenciaOut(texto=texto, total=max(0, p.total - 1), a_cambiar=p.a_cambiar, existe=existe is not None)


@router.post("/movimientos/lote/categoria", response_model=LoteOut)
def recategorizar(datos: LoteIn, db: Session = Depends(get_db)):
    if datos.categoria_id:
        obtener(db, Categoria, datos.categoria_id, "Categoría")
    movs = db.scalars(select(Movimiento).where(Movimiento.id.in_(datos.ids))).all()
    n = 0
    for m in movs:
        if m.tipo != TipoMovimiento.transferencia and m.categoria_id != datos.categoria_id:
            m.categoria_id = datos.categoria_id
            n += 1
    db.commit()
    return LoteOut(actualizados=n)
