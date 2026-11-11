"""Migración única del propietario: ejecutada por el operador en el servidor.

python -m app.bootstrap_account EMAIL
Conserva la contraseña existente y todas las finanzas en el esquema public.
No habilita registro público ni permite reclamar datos desde la web.
"""
import sys
import uuid
from sqlalchemy import select, text
from app.accounts import EmailIn
from app.accounts_models import Usuario
from app.config import settings
from app.db import SessionLocal


def main():
    if len(sys.argv) != 2:
        sys.exit('Uso: python -m app.bootstrap_account EMAIL')
    email = EmailIn(email=sys.argv[1]).email
    if not settings.app_password_hash:
        sys.exit('Falta la contraseña anterior: no se puede migrar el propietario')
    with SessionLocal() as db:
        if db.get_bind().dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_xact_lock(74100510)'))
        existente = db.scalar(select(Usuario).where(Usuario.esquema == 'public'))
        if existente:
            if existente.email != email:
                sys.exit('El propietario ya existe con otro email')
            print('La cuenta propietaria ya está configurada')
            return
        db.add(Usuario(id=uuid.uuid4(), email=email, nombre='Gabriel', esquema='public',
                       administrador=True, activo=True, password_hash=settings.app_password_hash))
        db.commit()
    print('Propietario migrado. Conserva su contraseña actual.')


if __name__ == '__main__':
    main()
