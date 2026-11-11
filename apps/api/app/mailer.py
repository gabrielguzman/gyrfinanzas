"""Envío SMTP con TLS. Los enlaces nunca se escriben en logs."""
import smtplib
import ssl
from email.message import EmailMessage

from fastapi import HTTPException
from app.config import settings


def disponible() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def enviar(destino: str, asunto: str, texto: str) -> None:
    if not disponible():
        raise HTTPException(503, "El envío de correos todavía no está configurado. Contactá al administrador.")
    msg = EmailMessage()
    msg['From'] = settings.smtp_from
    msg['To'] = destino
    msg['Subject'] = asunto
    msg.set_content(texto)
    try:
        cls = smtplib.SMTP_SSL if settings.smtp_port == 465 else smtplib.SMTP
        opciones = {"context": ssl.create_default_context()} if settings.smtp_port == 465 else {}
        with cls(settings.smtp_host, settings.smtp_port, timeout=15, **opciones) as smtp:
            if settings.smtp_port != 465:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        raise HTTPException(503, "No pudimos enviar el correo. Intentá de nuevo más tarde.") from None
