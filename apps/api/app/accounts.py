"""Registro e invitaciones, tokens opacos revocables y finanzas aisladas por esquema."""
import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from app import mailer
from app.accounts_models import TokenAcceso, Usuario
from app.config import settings
from app.db import Base, SessionLocal

router = APIRouter(prefix='/auth', tags=['cuentas de usuario'])
COOKIE = 'gyr_usuario'


def ahora():
    return datetime.now(timezone.utc)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def auth_db():
    with SessionLocal() as db:
        yield db


def vigente(token):
    fecha = token.vence
    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)
    return not token.usado and fecha > ahora()


def resolver(token: str | None):
    if not token or len(token) > 200:
        return None
    with SessionLocal() as db:
        t = db.get(TokenAcceso, digest(token))
        if not t or t.proposito != 'sesion' or not vigente(t):
            return None
        u = db.get(Usuario, t.usuario_id)
        if not u or not u.activo:
            return None
        db.expunge(u)
        return u


def habilitado():
    if not settings.usuarios_habilitados:
        raise HTTPException(404, 'No disponible')


def administrador(request: Request):
    habilitado()
    u = getattr(request.state, 'usuario', None)
    if not u or not u.administrador:
        raise HTTPException(403, 'Solo el administrador puede invitar personas')
    return u


def publico(u):
    return {'id': str(u.id), 'email': u.email, 'nombre': u.nombre, 'administrador': u.administrador}


def nuevo_token(db, usuario, proposito, minutos):
    raw = secrets.token_urlsafe(32)
    db.add(TokenAcceso(hash=digest(raw), usuario_id=usuario.id, proposito=proposito,
                       vence=ahora()+timedelta(minutes=minutos)))
    return raw


def enlace(raw, pagina):
    # Fragmento: el secreto no viaja al servidor ni queda en los access logs.
    return settings.app_url.rstrip('/')+'/'+pagina+'#token='+raw


def provisionar(db, u):
    if u.esquema == 'public':
        return
    if not re.fullmatch(r'u_[0-9a-f]{32}', u.esquema):
        raise ValueError('Esquema inválido')
    connection = db.connection()
    if connection.dialect.name != 'postgresql':
        raise RuntimeError('Las cuentas individuales requieren PostgreSQL')
    connection.execute(CreateSchema(u.esquema))
    # Otra conexión no participa: el DDL y la aceptación de la invitación son atómicos.
    # Copia todo el metadata para que también las FK apunten al esquema del usuario.
    from sqlalchemy import MetaData, text
    metadata = MetaData(schema=u.esquema)
    for table in Base.metadata.sorted_tables:
        table.to_metadata(metadata, schema=u.esquema, referred_schema_fn=lambda *args: u.esquema)
    metadata.create_all(connection)
    connection.execute(text(f'CREATE TABLE "{u.esquema}".alembic_version (version_num VARCHAR(32) PRIMARY KEY)'))
    connection.execute(text(f'INSERT INTO "{u.esquema}".alembic_version SELECT version_num FROM public.alembic_version'))
    from app.seed import sembrar
    with Session(bind=connection.execution_options(schema_translate_map={None:u.esquema}), expire_on_commit=False) as tenant:
        sembrar(tenant)
        tenant.flush()
    # No dejar el mapa sobre la conexión de identidades.
    connection.execution_options(schema_translate_map=None)


class EmailIn(BaseModel):
    email: str = Field(max_length=254)

    @field_validator('email')
    @classmethod
    def email_valido(cls, v):
        v = v.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", v):
            raise ValueError('Ingresá un email válido')
        local = v.split('@')[0]
        if len(local) > 64 or local.startswith('.') or local.endswith('.') or '..' in local:
            raise ValueError('Ingresá un email válido')
        return v


class LoginIn(EmailIn):
    password: str = Field(min_length=1, max_length=200)


class ActivarIn(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    nombre: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=200)

    @field_validator('nombre')
    @classmethod
    def nombre_valido(cls,v):
        if not v.strip(): raise ValueError('Ingresá tu nombre')
        return v.strip()


class RestablecerIn(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=12, max_length=200)


@router.post('/registro')
def registro(datos: EmailIn, request: Request, db: Session=Depends(auth_db)):
    """Primero verificar el correo; nombre y contraseña se eligen con el enlace."""
    habilitado()
    from app.auth import limitar, _ip
    limitar('registro-ip:'+_ip(request), 5, 3600)
    limitar('registro-email:'+datos.email, 3, 3600)
    limitar('registro-global', 30, 3600)
    if not mailer.disponible():
        raise HTTPException(503, 'El registro por correo no está disponible en este momento. Intentá más tarde.')
    respuesta = {'ok': True, 'mensaje': 'Si este email todavía no tiene una cuenta activa, vas a recibir un enlace para verificarlo y elegir tu contraseña. Revisá también la carpeta de spam. Si ya tenés cuenta, podés iniciar sesión o recuperar tu contraseña.'}
    u = db.scalar(select(Usuario).where(Usuario.email == datos.email).with_for_update())
    if u and u.activo:
        return respuesta
    if not u:
        u = Usuario(id=uuid.uuid4(), email=datos.email, esquema='u_'+uuid.uuid4().hex)
        db.add(u)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            return respuesta
    # No invalidar una invitación previa si alguien pide el registro para ese email.
    # Activar la cuenta vuelve inservibles todos los demás enlaces de activación.
    db.execute(delete(TokenAcceso).where(TokenAcceso.usuario_id == u.id,
                                        TokenAcceso.proposito == 'activar', TokenAcceso.vence < ahora()))
    raw = nuevo_token(db, u, 'activar', 24*60)
    mailer.enviar(u.email, 'Verificá tu email para crear tu cuenta de gyrfinanzas',
                  f'Confirmá tu email y elegí tu contraseña para crear tu cuenta:\n\n{enlace(raw,"activar")}\n\nEl enlace vence en 24 horas y solo puede usarse una vez. Tus finanzas serán privadas. Si no pediste esta cuenta, ignorá este correo.')
    db.commit()
    return respuesta


@router.post('/invitar')
def invitar(datos: EmailIn, request: Request, db: Session=Depends(auth_db), admin=Depends(administrador)):
    from app.auth import limitar
    limitar('invitar:'+str(admin.id), 20, 3600)
    u=db.scalar(select(Usuario).where(Usuario.email==datos.email).with_for_update())
    if u and u.activo:
        raise HTTPException(409,'Esta persona ya tiene una cuenta')
    if not u:
        u=Usuario(id=uuid.uuid4(), email=datos.email, esquema='u_'+uuid.uuid4().hex)
        db.add(u)
        try: db.flush()
        except IntegrityError:
            db.rollback(); raise HTTPException(409,'Ya hay una invitación para ese email') from None
    db.execute(delete(TokenAcceso).where(TokenAcceso.usuario_id==u.id, TokenAcceso.proposito=='activar'))
    raw=nuevo_token(db,u,'activar',48*60)
    url=enlace(raw,'activar')
    if mailer.disponible():
        mailer.enviar(u.email,'Tu invitación a gyrfinanzas',f'Te invitaron a gyrfinanzas. Elegí tu contraseña:\n\n{url}\n\nEl enlace vence en 48 horas. Si no esperabas esta invitación, ignorá este correo.')
    db.commit()
    # Con SMTP se entrega por correo; sin SMTP solo el administrador recibe el enlace.
    return {'ok':True,'enviado':mailer.disponible(), **({'enlace':url} if not mailer.disponible() else {})}


@router.post('/aceptar')
def aceptar(datos: ActivarIn, db: Session=Depends(auth_db)):
    habilitado()
    t=db.scalar(select(TokenAcceso).where(TokenAcceso.hash==digest(datos.token)).with_for_update())
    if not t or t.proposito!='activar' or not vigente(t):
        raise HTTPException(400,'El enlace venció o ya fue utilizado. Solicitá otro desde registro o pedí una nueva invitación.')
    u=db.scalar(select(Usuario).where(Usuario.id==t.usuario_id).with_for_update())
    if u.activo: raise HTTPException(400,'La cuenta ya está activa')
    from app.auth import generar_hash
    provisionar(db,u)
    u.nombre=datos.nombre;u.password_hash=generar_hash(datos.password);u.activo=True;t.usado=True
    db.commit()
    return {'ok':True}


@router.post('/recuperar')
def recuperar(datos: EmailIn, request: Request, db: Session=Depends(auth_db)):
    habilitado()
    from app.auth import limitar, _ip
    limitar('recuperar-ip:'+_ip(request),10,900)
    limitar('recuperar-email:'+datos.email,3,900)
    if not mailer.disponible():
        raise HTTPException(503,'La recuperación por correo todavía no está configurada. Contactá al administrador.')
    u=db.scalar(select(Usuario).where(Usuario.email==datos.email,Usuario.activo.is_(True)).with_for_update())
    if u:
        db.execute(delete(TokenAcceso).where(TokenAcceso.usuario_id==u.id,TokenAcceso.proposito=='recuperar'))
        raw=nuevo_token(db,u,'recuperar',30)
        mailer.enviar(u.email,'Restablecé tu contraseña de gyrfinanzas',f'Elegí una nueva contraseña:\n\n{enlace(raw,"recuperar")}\n\nEste enlace vence en 30 minutos y se puede usar una sola vez. Si no lo pediste, ignoralo.')
        db.commit()
    return {'ok':True,'mensaje':'Si el email tiene una cuenta activa, vas a recibir un enlace para restablecer tu contraseña.'}


@router.post('/restablecer')
def restablecer(datos: RestablecerIn, db: Session=Depends(auth_db)):
    habilitado()
    t=db.scalar(select(TokenAcceso).where(TokenAcceso.hash==digest(datos.token)).with_for_update())
    if not t or t.proposito!='recuperar' or not vigente(t):
        raise HTTPException(400,'El enlace venció o ya fue utilizado. Solicitá otro.')
    u=db.scalar(select(Usuario).where(Usuario.id==t.usuario_id).with_for_update())
    if not u.activo: raise HTTPException(400,'Cuenta no disponible')
    from app.auth import generar_hash
    u.password_hash=generar_hash(datos.password)
    db.execute(delete(TokenAcceso).where(TokenAcceso.usuario_id==u.id))
    db.commit()
    return {'ok':True}


def login(datos,request,response,db):
    from app.auth import _ip, _bloqueado, _fallos, verificar, generar_hash
    import time
    ip='login-ip:'+_ip(request);email='login-email:'+datos.email;now=time.time()
    if _bloqueado(ip,now) or _bloqueado(email,now):
        raise HTTPException(429,'Demasiados intentos. Esperá unos minutos.')
    u=db.scalar(select(Usuario).where(Usuario.email==datos.email).with_for_update())
    # Misma función costosa para emails inexistentes.
    h=u.password_hash if u and u.password_hash else DUMMY_HASH
    valido=verificar(datos.password,h)
    if not u or not u.activo or not valido:
        _fallos[ip].append(now);_fallos[email].append(now)
        raise HTTPException(401,'Email o contraseña incorrectos')
    _fallos.pop(ip,None);_fallos.pop(email,None)
    db.execute(delete(TokenAcceso).where(TokenAcceso.usuario_id==u.id,TokenAcceso.vence<ahora()))
    raw=nuevo_token(db,u,'sesion',settings.sesion_dias*24*60)
    db.commit()
    response.set_cookie(COOKIE,raw,max_age=settings.sesion_dias*86400,httponly=True,secure=settings.cookie_secure,samesite='lax',path='/')
    return {'ok':True,'usuario':publico(u)}


# Hash scrypt válido y público, usado únicamente para igualar trabajo en login inválido.
DUMMY_HASH='scrypt:16384:8:1:AAAAAAAAAAAAAAAAAAAAAA:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'

class CambiarIn(BaseModel):
    actual: str = Field(min_length=1, max_length=200)
    nueva: str = Field(min_length=12, max_length=200)


@router.post('/cambiar-password')
def cambiar_password(datos: CambiarIn, request: Request, db: Session=Depends(auth_db)):
    habilitado()
    usuario = getattr(request.state, 'usuario', None)
    if not usuario:
        raise HTTPException(401, 'Iniciá sesión')
    from app.auth import limitar, verificar, generar_hash
    limitar('cambiar:'+str(usuario.id),5,900)
    u=db.scalar(select(Usuario).where(Usuario.id==usuario.id).with_for_update())
    if not verificar(datos.actual,u.password_hash):
        raise HTTPException(401,'La contraseña actual no es correcta')
    u.password_hash=generar_hash(datos.nueva)
    db.execute(delete(TokenAcceso).where(TokenAcceso.usuario_id==u.id))
    db.commit()
    return {'ok':True}
