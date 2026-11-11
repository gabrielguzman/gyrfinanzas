import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Categoria
from app.routers.util import obtener
from app.schemas import CategoriaIn, CategoriaOut, CategoriaPatch

router = APIRouter(prefix="/categorias", tags=["categorías"])


@router.get("", response_model=list[CategoriaOut])
def listar(db: Session = Depends(get_db)):
    return db.scalars(select(Categoria).order_by(Categoria.tipo, Categoria.nombre)).all()


@router.post("", response_model=CategoriaOut, status_code=201)
def crear(datos: CategoriaIn, db: Session = Depends(get_db)):
    cat = Categoria(**datos.model_dump())
    db.add(cat)
    db.commit()
    return cat


@router.patch("/{categoria_id}", response_model=CategoriaOut)
def editar(categoria_id: uuid.UUID, datos: CategoriaPatch, db: Session = Depends(get_db)):
    cat = obtener(db, Categoria, categoria_id, "Categoría")
    for k, v in datos.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    return cat
