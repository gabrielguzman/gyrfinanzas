from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from fastapi import Request, HTTPException

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    usuario = getattr(request.state, "usuario", None)
    if settings.usuarios_habilitados and usuario is None:
        raise HTTPException(401, "Iniciá sesión")
    bind = engine
    if usuario is not None:
        bind = engine.execution_options(schema_translate_map={None: usuario.esquema})
    db = Session(bind=bind, autoflush=False, expire_on_commit=False)
    try:
        yield db
    finally:
        db.close()
