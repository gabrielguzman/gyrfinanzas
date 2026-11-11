import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401  (registra las tablas)
from app.config import settings
from app.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
url = os.environ.get("ALEMBIC_DATABASE_URL", settings.database_url)


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import text, inspect
    import re
    engine = create_engine(url)
    with engine.connect() as connection:
        if connection.dialect.name != "postgresql":
            context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()
            return
        schemas = ["public"]
        # Identidades siempre en public; las finanzas de cada usuario migran por separado.
        if inspect(connection).has_table("auth_usuario", schema="public"):
            schemas += list(connection.execute(text("SELECT esquema FROM public.auth_usuario WHERE esquema <> 'public' AND activo = true")).scalars())
        connection.commit()
        for schema in schemas:
            if schema != "public" and not re.fullmatch(r"u_[0-9a-f]{32}", schema):
                raise RuntimeError("Esquema de usuario inválido")
            with connection.begin():
                connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                config.attributes["tenant_schema"] = schema
                context.configure(connection=connection, target_metadata=target_metadata,
                                  render_as_batch=True, version_table_schema=schema)
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
