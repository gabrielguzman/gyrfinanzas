"""Verifica las dos variantes 0010 que existieron antes de integrar los agentes."""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session

from app import accounts
from app.accounts_models import AuthBase, Usuario
from app.models import Cuenta

URL=os.environ.get('GYR_AUTH_TEST_URL','')
pytestmark=pytest.mark.skipif(not URL,reason='Requiere PostgreSQL descartable')
API=Path(__file__).parents[1]


def migrate(revision):
    env={**os.environ,'DATABASE_URL':URL,'ALEMBIC_DATABASE_URL':URL}
    r=subprocess.run([str(API/'.venv/bin/alembic'),'upgrade',revision],cwd=API,env=env,text=True,capture_output=True)
    assert r.returncode==0,r.stderr


@pytest.mark.parametrize('origen',['usuarios','fijos'])
def test_puente_desde_ambas_0010_preserva_datos(origen):
    e=create_engine(URL)
    assert e.url.database.endswith('_auth_test')
    with e.begin() as c:
        schemas=list(c.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'u_%'")).scalars())
        for schema in schemas:
            if schema.startswith('u_'):c.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        c.execute(text('DROP SCHEMA public CASCADE'));c.execute(text('CREATE SCHEMA public'))
    migrate('0009')
    tenant=None
    if origen=='usuarios':
        AuthBase.metadata.create_all(e)
        with e.begin() as c:c.execute(text("UPDATE alembic_version SET version_num='0010'"))
        with Session(e) as d:
            owner=Usuario(email='owner@example.com',nombre='Original',password_hash='hash-original',esquema='public',administrador=True,activo=True)
            tenant=Usuario(id=uuid.uuid4(),email='tenant@example.com',esquema='u_'+uuid.uuid4().hex,activo=False)
            d.add_all([owner,tenant]);d.flush();accounts.provisionar(d,tenant);tenant.activo=True;schema=tenant.esquema;d.commit()
        # Reproducir las tablas que tenía un usuario antes de las funciones nuevas.
        with e.begin() as c:
            c.execute(text(f'ALTER TABLE "{schema}".movimiento DROP COLUMN fijo_id CASCADE'))
            for name in ['gasto_fijo','regla_categoria','push_suscripcion','aviso_enviado']:
                c.execute(text(f'DROP TABLE "{schema}"."{name}" CASCADE'))
    else:
        # Ejecutar literalmente la migración que ya publicó Claude en main.
        source=(API/'tests/datos/legacy_0010_fijos.py').read_text()
        ns={};exec(compile(source,'migration-original','exec'),ns)
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        with e.begin() as c:
            with Operations.context(MigrationContext.configure(c)):ns['upgrade']()
            c.execute(text("UPDATE alembic_version SET version_num='0010'"))
            c.execute(text("INSERT INTO gasto_fijo (id,nombre,clave,monto,dia) VALUES (:id,'Alquiler','alquiler',100,1)"),{'id':uuid.uuid4()})
    with e.begin() as c:
        c.execute(text("INSERT INTO cuenta (id,nombre,tipo,moneda,saldo_inicial,archivada,creado) VALUES (:id,'Cuenta conservada','efectivo','ARS',123,false,now())"),{'id':uuid.uuid4()})
    migrate('head')
    with e.connect() as c:
        assert c.scalar(text('SELECT version_num FROM alembic_version'))=='0013'
        assert c.scalar(text("SELECT saldo_inicial FROM cuenta WHERE nombre='Cuenta conservada'"))==123
        for name in ['auth_usuario','auth_token','gasto_fijo','regla_categoria','push_suscripcion','aviso_enviado']:
            assert inspect(c).has_table(name,schema='public')
        if origen=='usuarios':
            assert c.scalar(text("SELECT password_hash FROM auth_usuario WHERE email='owner@example.com'"))=='hash-original'
            for name in ['gasto_fijo','regla_categoria','push_suscripcion','aviso_enviado']:
                assert inspect(c).has_table(name,schema=schema)
            assert c.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version'))=='0013'
        else: assert c.scalar(text("SELECT monto FROM gasto_fijo WHERE clave='alquiler'"))==100
    e.dispose()
