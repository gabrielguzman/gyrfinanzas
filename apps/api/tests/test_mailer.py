import ssl
import pytest
from fastapi import HTTPException
from app import mailer
from app.config import settings


@pytest.mark.parametrize('port',[465,587])
def test_smtp_verifica_tls(monkeypatch,port):
    llamadas=[]
    class SMTP:
        def __init__(self,*args,**kwargs): llamadas.append(('conexion',args,kwargs))
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def starttls(self,context): llamadas.append(('tls',context))
        def login(self,*args): llamadas.append(('login',))
        def send_message(self,msg): llamadas.append(('mensaje',msg))
    for k,v in dict(smtp_host='smtp.test',smtp_port=port,smtp_from='finanzas@example.com',smtp_user='user',smtp_password='secret').items():
        monkeypatch.setattr(settings,k,v)
    monkeypatch.setattr(mailer.smtplib,'SMTP_SSL',SMTP)
    monkeypatch.setattr(mailer.smtplib,'SMTP',SMTP)
    mailer.enviar('usuario@example.com','Invitación','Contenido')
    context=llamadas[0][2]['context'] if port==465 else llamadas[1][1]
    assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname
    assert llamadas[-1][1]['To']=='usuario@example.com'


def test_sin_smtp_no_finge_envio(monkeypatch):
    monkeypatch.setattr(settings,'smtp_host','')
    with pytest.raises(HTTPException) as e: mailer.enviar('user@example.com','Asunto','Texto')
    assert e.value.status_code==503
