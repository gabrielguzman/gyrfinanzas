import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria, GastoFijo, Movimiento, ReglaCategoria, TipoCategoria
from app.routers.util import obtener
from app.schemas import CategoriaIn, CategoriaOut, CategoriaPatch
from app.services.captura import normalizar

router = APIRouter(prefix="/categorias", tags=["categorías"])


class CategoriaUso(CategoriaOut):
    cantidad: int = 0


class Sugerida(BaseModel):
    nombre: str
    tipo: TipoCategoria
    palabras: str
    icono: str
    color: str


class AgregarIn(BaseModel):
    nombres: list[str] = Field(min_length=1, max_length=40)


def _clave(nombre: str) -> str:
    return normalizar(nombre).strip()


def _existe(db: Session, nombre: str, tipo: TipoCategoria, salvo: uuid.UUID | None = None) -> bool:
    for c in db.scalars(select(Categoria).where(Categoria.tipo == tipo)):
        if c.id != salvo and _clave(c.nombre) == _clave(nombre):
            return True
    return False


@router.get("", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db)):
    return db.scalars(select(Categoria).order_by(Categoria.tipo, Categoria.nombre)).all()


@router.get("/uso", response_model=list[CategoriaUso])
def con_uso(db: Session = Depends(get_db)):
    """Las categorías con cuántos movimientos tiene cada una (para administrarlas)."""
    cuenta = dict(db.execute(select(Movimiento.categoria_id, func.count()).group_by(Movimiento.categoria_id)).all())
    return [CategoriaUso(**CategoriaOut.model_validate(c).model_dump(), cantidad=cuenta.get(c.id, 0))
            for c in db.scalars(select(Categoria).order_by(Categoria.tipo, Categoria.nombre))]


@router.get("/sugeridas", response_model=list[Sugerida])
def sugeridas(db: Session = Depends(get_db)):
    """Clásicas que todavía no tenés (Delivery, Farmacia, Mascotas…)."""
    from app.seed import CATALOGO_GASTOS, CATALOGO_INGRESOS, GASTOS, INGRESOS
    tenes = {(_clave(c.nombre), c.tipo) for c in db.scalars(select(Categoria))}
    out = []
    for tipo, cat in ((TipoCategoria.gasto, {**GASTOS, **CATALOGO_GASTOS}), (TipoCategoria.ingreso, {**INGRESOS, **CATALOGO_INGRESOS})):
        for nombre, (palabras, icono, color) in cat.items():
            if (_clave(nombre), tipo) not in tenes:
                out.append(Sugerida(nombre=nombre, tipo=tipo, palabras=palabras, icono=icono, color=color))
    return out


@router.post("/sugeridas", response_model=list[CategoriaOut], status_code=201)
def agregar_sugeridas(datos: AgregarIn, db: Session = Depends(get_db)):
    disponibles = {(s.nombre): s for s in sugeridas(db)}
    nuevas = []
    for n in datos.nombres:
        s = disponibles.get(n)
        if s:
            c = Categoria(nombre=s.nombre, tipo=s.tipo, palabras=s.palabras, icono=s.icono, color=s.color)
            db.add(c)
            nuevas.append(c)
    db.commit()
    return nuevas


@router.post("", response_model=CategoriaOut, status_code=201)
def crear(datos: CategoriaIn, db: Session = Depends(get_db)):
    if _existe(db, datos.nombre, datos.tipo):
        raise HTTPException(409, f"Ya tenés una categoría «{datos.nombre.strip()}».")
    cat = Categoria(**{**datos.model_dump(), "nombre": datos.nombre.strip()})
    db.add(cat)
    db.commit()
    return cat


@router.patch("/{categoria_id}", response_model=CategoriaOut)
def editar(categoria_id: uuid.UUID, datos: CategoriaPatch, db: Session = Depends(get_db)):
    cat = obtener(db, Categoria, categoria_id, "Categoría")
    cambios = datos.model_dump(exclude_unset=True)
    if cambios.get("nombre") and _existe(db, cambios["nombre"], cat.tipo, salvo=cat.id):
        raise HTTPException(409, f"Ya tenés una categoría «{cambios['nombre'].strip()}».")
    for k, v in cambios.items():
        setattr(cat, k, v.strip() if k == "nombre" and v else v)
    db.commit()
    return cat


@router.delete("/{categoria_id}", status_code=204)
def borrar(categoria_id: uuid.UUID, mover_a: uuid.UUID | None = Query(default=None), db: Session = Depends(get_db)):
    """Borra la categoría. Sus movimientos (y fijos y reglas) pasan a `mover_a`, o quedan sin categoría."""
    cat = obtener(db, Categoria, categoria_id, "Categoría")
    if mover_a:
        destino = obtener(db, Categoria, mover_a, "Categoría destino")
        if destino.id == cat.id or destino.tipo != cat.tipo:
            raise HTTPException(422, "Elegí otra categoría del mismo tipo.")
    db.execute(update(Movimiento).where(Movimiento.categoria_id == cat.id).values(categoria_id=mover_a))
    db.execute(update(GastoFijo).where(GastoFijo.categoria_id == cat.id).values(categoria_id=mover_a))
    if mover_a:
        db.execute(update(ReglaCategoria).where(ReglaCategoria.categoria_id == cat.id).values(categoria_id=mover_a))
        # Sus palabras clave pasan a la otra, así lo que se cargue después se sigue reconociendo
        extra = [p for p in cat.palabras.split(",") if p.strip() and p not in destino.palabras.split(",")]
        if extra:
            destino.palabras = ",".join([x for x in destino.palabras.split(",") if x] + extra)[:400]
    else:
        db.execute(ReglaCategoria.__table__.delete().where(ReglaCategoria.categoria_id == cat.id))
    db.delete(cat)
    db.commit()
