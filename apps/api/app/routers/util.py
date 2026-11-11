import uuid
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

T = TypeVar("T")


def obtener(db: Session, modelo: type[T], id_: uuid.UUID, nombre: str) -> T:
    obj = db.get(modelo, id_)
    if obj is None:
        raise HTTPException(404, f"{nombre} no encontrado/a")
    return obj
