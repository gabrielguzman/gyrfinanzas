"""Integración PostgreSQL. GYR_AUTH_TEST_URL debe apuntar a una DB terminada en _auth_test."""
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text, inspect
from sqlalchemy.orm import sessionmaker
from app import accounts, auth, db as dbmod, mailer, models
from app.accounts_models import AuthBase, Usuario, TokenAcceso
from app.config import settings
from app.db import Base
from app.main import app

URL = os.environ.get('GYR_AUTH_TEST_URL', '')
pytestmark = pytest.mark.skipif(not URL, reason='Requiere PostgreSQL de prueba')
PASS = 'una frase de prueba segura'

@pytest.fixture()
def multi(monkeypatch, tmp_path):
    e = create_engine(URL, pool_pre_ping=True)
    assert e.url.database.endswith('_auth_test')
    with e.begin() as c:
        for schema in c.execute(text("SELECT esquema FROM public.auth_usuario WHERE esquema <> 'public'")).scalars():
            c.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    AuthBase.metadata.drop_all(e); AuthBase.metadata.create_all(e)
    Base.metadata.drop_all(e); Base.metadata.create_all(e)
    factory = sessionmaker(bind=e, expire_on_commit=False)
    monkeypatch.setattr(dbmod, 'engine', e)
    monkeypatch.setattr(dbmod, 'SessionLocal', factory)
    monkeypatch.setattr(accounts, 'SessionLocal', factory)
    for key,value in dict(usuarios_habilitados=True,upload_dir=str(tmp_path),app_url='https://finanzas.test',cookie_secure=False,smtp_host='',smtp_from='').items():
        monkeypatch.setattr(settings,key,value)
    auth._fallos.clear()
    with factory() as d:
        d.add(Usuario(email='owner@example.com',nombre='Propietario',password_hash=auth.generar_hash(PASS),esquema='public',administrador=True,activo=True))
        d.add(models.Cuenta(nombre='Cuenta anterior',tipo=models.TipoCuenta.efectivo));d.commit()
    with TestClient(app) as client:
        assert client.post('/auth/login',json={'email':'owner@example.com','password':PASS}).status_code==200
        yield client,factory,e
    e.dispose()

def invite(c,email='nuevo@example.com'):
    r=c.post('/auth/invitar',json={'email':email});assert r.status_code==200,r.text
    return parse_qs(urlparse(r.json()['enlace']).fragment)['token'][0]

def signin(c,email='nuevo@example.com',password=PASS):
    c.cookies.clear();r=c.post('/auth/login',json={'email':email,'password':password});assert r.status_code==200,r.text

def test_aislamiento_completo(multi):
    c,factory,e=multi
    owner=c.get('/cuentas').json()[0]
    archivo=c.post('/archivos',files={'archivo':('ticket.pdf',b'%PDF prueba','application/pdf')}).json()
    token=invite(c)
    r=c.post('/auth/aceptar',json={'token':token,'nombre':'Nuevo','password':PASS});assert r.status_code==200,r.text
    assert c.post('/auth/aceptar',json={'token':token,'nombre':'Otro','password':PASS}).status_code==400
    signin(c)
    assert c.get('/cuentas').json()==[]
    assert len(c.get('/categorias').json())==19
    assert c.get('/cuentas/'+owner['id']).status_code==404
    assert c.get('/archivos/'+archivo['id']+'/contenido').status_code==404
    assert c.get('/archivos').json()==[]
    assert c.post('/medios-pago',json={'nombre':'Ajeno','tipo':'efectivo','cuenta_id':owner['id']}).status_code==404
    nueva=c.post('/cuentas',json={'nombre':'Privada','tipo':'efectivo'}).json()
    r=c.post('/archivos',files={'archivo':('ticket.pdf',b'%PDF prueba','application/pdf')});assert r.status_code==201,r.text
    assert r.json()['id']!=archivo['id']
    with factory() as d:
        u=d.scalar(select(Usuario).where(Usuario.email=='nuevo@example.com'))
        assert (Path(settings.upload_dir)/u.esquema).exists()
    assert c.post('/auth/invitar',json={'email':'tercero@example.com'}).status_code==403
    signin(c,'owner@example.com')
    assert [x['id'] for x in c.get('/cuentas').json()]==[owner['id']]
    assert c.get('/cuentas/'+nueva['id']).status_code==404

def test_logout_expiracion_cookie_legacy(multi):
    c,factory,e=multi
    session=c.cookies.get(accounts.COOKIE)
    assert c.post('/auth/logout').status_code==200
    c.cookies.set(accounts.COOKIE,session);assert c.get('/cuentas').status_code==401
    c.cookies.clear();c.cookies.set(auth.COOKIE,auth.crear_sesion());assert c.get('/cuentas').status_code==401
    signin(c,'owner@example.com')
    with factory() as d:
        t=d.get(TokenAcceso,accounts.digest(c.cookies.get(accounts.COOKIE)));t.vence=accounts.ahora()-timedelta(seconds=1);d.commit()
    assert c.get('/cuentas').status_code==401

def test_recuperacion_uniforme_y_revocacion(multi,monkeypatch):
    c,factory,e=multi;sent=[]
    monkeypatch.setattr(mailer,'disponible',lambda:True)
    monkeypatch.setattr(mailer,'enviar',lambda *args:sent.append(args))
    known=c.post('/auth/recuperar',json={'email':'owner@example.com'})
    unknown=c.post('/auth/recuperar',json={'email':'nadie@example.com'})
    assert known.json()==unknown.json() and known.status_code==200
    raw=sent[0][2].split('#token=')[1].split()[0]
    assert c.post('/auth/restablecer',json={'token':raw,'password':'corta'}).status_code==422
    r=c.post('/auth/restablecer',json={'token':raw,'password':'mi nueva frase segura'});assert r.status_code==200,r.text
    assert c.get('/cuentas').status_code==401
    assert c.post('/auth/restablecer',json={'token':raw,'password':PASS}).status_code==400
    c.cookies.clear();assert c.post('/auth/login',json={'email':'owner@example.com','password':PASS}).status_code==401
    signin(c,'owner@example.com','mi nueva frase segura')

def test_reinvitar_y_vencidos(multi):
    c,factory,e=multi;old=invite(c);new=invite(c)
    assert c.post('/auth/aceptar',json={'token':old,'nombre':'A','password':PASS}).status_code==400
    with factory() as d:
        t=d.get(TokenAcceso,accounts.digest(new));t.vence=accounts.ahora()-timedelta(seconds=1);d.commit()
    assert c.post('/auth/aceptar',json={'token':new,'nombre':'A','password':PASS}).status_code==400
    with factory() as d:
        u=d.scalar(select(Usuario).where(Usuario.email=='nuevo@example.com'));assert not u.activo
        assert not inspect(e).has_schema(u.esquema)

def test_correo_error_y_csrf(multi,monkeypatch):
    c,factory,e=multi
    assert c.post('/auth/invitar',json={'email':'otro@example.com'},headers={'Origin':'https://malicioso.test'}).status_code==403
    monkeypatch.setattr(mailer,'disponible',lambda:True)
    def fallo(*args):
        from fastapi import HTTPException
        raise HTTPException(503,'No se pudo enviar')
    monkeypatch.setattr(mailer,'enviar',fallo)
    assert c.post('/auth/invitar',json={'email':'otro@example.com'}).status_code==503
    with factory() as d: assert d.scalar(select(Usuario).where(Usuario.email=='otro@example.com')) is None

def test_validacion_roles_limites(multi):
    c,factory,e=multi
    assert c.post('/auth/invitar',json={'email':'no es un mail'}).status_code==422
    c.cookies.clear()
    assert c.post('/auth/invitar',json={'email':'intruso@example.com'}).status_code==403
    assert c.post('/auth/registro',json={'email':'intruso@example.com'}).status_code==503
    for _ in range(5): assert c.post('/auth/login',json={'email':'owner@example.com','password':'incorrecta'}).status_code==401
    assert c.post('/auth/login',json={'email':'owner@example.com','password':PASS}).status_code==429

def test_cambio_password_y_pestana_anterior(multi):
    c,factory,e=multi
    assert c.post('/cuentas',json={'nombre':'No crear','tipo':'efectivo'},headers={'X-Gyr-Usuario':'otro-id'}).status_code==409
    assert len(c.get('/cuentas').json())==1
    assert c.post('/auth/cambiar-password',json={'actual':'incorrecta','nueva':'mi nueva frase segura'}).status_code==401
    assert c.post('/auth/cambiar-password',json={'actual':PASS,'nueva':'mi nueva frase segura'}).status_code==200
    assert c.get('/cuentas').status_code==401
    signin(c,'owner@example.com','mi nueva frase segura')


def test_migraciones_y_background(multi):
    import subprocess
    from app.routers.tarjetas import _procesar
    c,factory,e=multi
    token=invite(c)
    r=c.post('/auth/aceptar',json={'token':token,'nombre':'Nuevo','password':PASS});assert r.status_code==200,r.text
    with factory() as d:
        u=d.scalar(select(Usuario).where(Usuario.email=='nuevo@example.com'));schema=u.esquema
    env={**os.environ,'DATABASE_URL':URL,'ALEMBIC_DATABASE_URL':URL}
    r=subprocess.run([str(Path(__file__).parents[1]/'.venv/bin/alembic'),'upgrade','head'],env=env,capture_output=True,text=True,cwd=Path(__file__).parents[1])
    assert r.returncode==0,r.stderr
    bind=e.execution_options(schema_translate_map={None:schema})
    with factory(bind=bind) as d:
        card=models.Cuenta(nombre='Visa privada',tipo=models.TipoCuenta.tarjeta_credito);d.add(card);d.flush()
        summary=models.ResumenTarjeta(cuenta_id=card.id);d.add(summary);d.commit();sid=summary.id
    _procesar(sid,b'PDF no valido',bind)
    with factory(bind=bind) as d: assert d.get(models.ResumenTarjeta,sid).estado==models.EstadoResumen.error
    with factory() as d: assert d.get(models.ResumenTarjeta,sid) is None


def test_registro_publico_verifica_email_y_aisla_datos(multi,monkeypatch):
    c,factory,e=multi;enviados=[]
    monkeypatch.setattr(mailer,'disponible',lambda:True)
    monkeypatch.setattr(mailer,'enviar',lambda *args:enviados.append(args))
    owner=c.get('/cuentas').json()[0]
    c.cookies.clear()
    r=c.post('/auth/registro',json={'email':'  Persona@Example.com '})
    assert r.status_code==200 and 'enlace' not in r.json()
    assert enviados[0][0]=='persona@example.com'
    token=enviados[0][2].split('#token=')[1].split()[0]
    with factory() as d:
        u=d.scalar(select(Usuario).where(Usuario.email=='persona@example.com'))
        assert not u.activo and not u.administrador and not u.password_hash
        assert not inspect(e).has_schema(u.esquema)
    assert c.post('/auth/login',json={'email':'persona@example.com','password':PASS}).status_code==401
    r=c.post('/auth/aceptar',json={'token':token,'nombre':'Persona','password':PASS});assert r.status_code==200,r.text
    assert c.post('/auth/aceptar',json={'token':token,'nombre':'Otra','password':PASS}).status_code==400
    signin(c,'persona@example.com')
    assert c.get('/cuentas').json()==[] and len(c.get('/categorias').json())==19
    assert c.get('/cuentas/'+owner['id']).status_code==404
    assert c.get('/auth/estado').json()['usuario']['administrador'] is False
    assert c.post('/auth/invitar',json={'email':'otro@example.com'}).status_code==403


def test_registro_existente_no_cambia_password_y_no_invalida_invitacion(multi,monkeypatch):
    c,factory,e=multi;enviados=[]
    invitacion=invite(c,'pendiente@example.com')
    monkeypatch.setattr(mailer,'disponible',lambda:True)
    monkeypatch.setattr(mailer,'enviar',lambda *args:enviados.append(args))
    c.cookies.clear()
    nuevo=c.post('/auth/registro',json={'email':'pendiente@example.com'})
    existente=c.post('/auth/registro',json={'email':'owner@example.com'})
    assert nuevo.json()==existente.json() and nuevo.status_code==200
    assert len(enviados)==1
    assert c.post('/auth/aceptar',json={'token':invitacion,'nombre':'Invitado','password':PASS}).status_code==200
    signin(c,'owner@example.com')


def test_registro_correo_fallido_validacion_y_limites(multi,monkeypatch):
    from fastapi import HTTPException
    c,factory,e=multi
    monkeypatch.setattr(mailer,'disponible',lambda:True)
    def fallo(*args): raise HTTPException(503,'No se pudo enviar')
    monkeypatch.setattr(mailer,'enviar',fallo)
    c.cookies.clear()
    assert c.post('/auth/registro',json={'email':'invalido'}).status_code==422
    assert c.post('/auth/registro',json={'email':'nuevo@example.com'}).status_code==503
    with factory() as d: assert d.scalar(select(Usuario).where(Usuario.email=='nuevo@example.com')) is None
    monkeypatch.setattr(mailer,'enviar',lambda *args:None)
    for _ in range(2): assert c.post('/auth/registro',json={'email':'nuevo@example.com'}).status_code==200
    assert c.post('/auth/registro',json={'email':'nuevo@example.com'}).status_code==429


def test_fijos_programados_y_exportacion_separados_por_usuario(multi):
    from app.main import _pasada
    from app.models import GastoFijo
    c,factory,e=multi
    token=invite(c)
    assert c.post('/auth/aceptar',json={'token':token,'nombre':'Nuevo','password':PASS}).status_code==200
    with factory() as d:
        schema=d.scalar(select(Usuario.esquema).where(Usuario.email=='nuevo@example.com'))
        d.add(GastoFijo(nombre='Fijo del propietario',clave='mismo-nombre',monto=100,dia=1));d.commit()
    with factory(bind=e.execution_options(schema_translate_map={None:schema})) as d:
        d.add(GastoFijo(nombre='Fijo privado',clave='mismo-nombre',monto=200,dia=1));d.commit()
    _pasada()
    assert [m['descripcion'] for m in c.get('/movimientos').json()]==['Fijo del propietario']
    export=c.get('/exportar?formato=csv');assert export.status_code==200 and 'Fijo privado' not in export.text
    signin(c)
    assert [m['descripcion'] for m in c.get('/movimientos').json()]==['Fijo privado']
    export=c.get('/exportar?formato=csv');assert export.status_code==200 and 'Fijo del propietario' not in export.text
