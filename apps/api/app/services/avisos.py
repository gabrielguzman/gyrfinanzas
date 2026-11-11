"""Notificaciones en el celu (Web Push), sin depender de Telegram.

- Las claves VAPID se generan solas la primera vez y se guardan en la base.
- Un programador corre cada pocos minutos dentro de la API: genera los fijos del día y
  manda lo que corresponda. Cada aviso tiene una clave (con el día o el dato) que se anota
  antes de mandarlo, así nunca se repite.
"""
import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Ajuste, AvisoEnviado, PushSuscripcion

log = logging.getLogger("gyr.avisos")
CERO = Decimal("0")

# Preferencias (Ajuste): "1" activo, "0" apagado. Sin valor = activo.
PREFS = {
    "notif_hoy": "El número del día, a la mañana",
    "notif_fijos": "Gastos fijos el día que tocan",
    "notif_vencimientos": "Vencimientos de tarjetas y préstamos",
    "notif_avisos": "Avisos importantes (garantías, fijos sin confirmar, plazos fijos)",
}
HORA_DEFECTO = "09:00"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _get(db: Session, clave: str) -> str | None:
    a = db.get(Ajuste, clave)
    return a.valor if a else None


def _set(db: Session, clave: str, valor: str) -> None:
    a = db.get(Ajuste, clave)
    if a:
        a.valor = valor
    else:
        db.add(Ajuste(clave=clave, valor=valor))


def preferencias(db: Session) -> dict:
    return {**{k: _get(db, k) != "0" for k in PREFS}, "notif_hora": _get(db, "notif_hora") or HORA_DEFECTO}


def guardar_preferencias(db: Session, valores: dict) -> None:
    for k, v in valores.items():
        if k in PREFS and v is not None:
            _set(db, k, "1" if v else "0")
        elif k == "notif_hora" and v:
            hh, mm = str(v).split(":")[:2]
            _set(db, k, f"{max(0, min(23, int(hh))):02d}:{max(0, min(59, int(mm))):02d}")


# ───────────────────────── claves VAPID ─────────────────────────
def clave_publica(db: Session) -> str:
    pub = _get(db, "vapid_publica")
    if pub and _get(db, "vapid_privada"):
        return pub
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid02
    v = Vapid02()
    v.generate_keys()
    priv = _b64(v.private_key.private_numbers().private_value.to_bytes(32, "big"))
    pub = _b64(v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
    _set(db, "vapid_privada", priv)
    _set(db, "vapid_publica", pub)
    db.commit()
    return pub


def _vapid(db: Session):
    from py_vapid import Vapid02
    clave_publica(db)
    return Vapid02.from_raw(_get(db, "vapid_privada").encode())


# ───────────────────────── envío ─────────────────────────
@dataclass
class Aviso:
    clave: str
    titulo: str
    cuerpo: str
    url: str = "/"


def _mandar_uno(sub: PushSuscripcion, datos: str, vapid) -> int | None:
    """Devuelve el status HTTP si falló, None si salió bien."""
    from pywebpush import WebPushException, webpush
    try:
        webpush({"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}, datos,
                vapid_private_key=vapid, vapid_claims={"sub": "mailto:avisos@gyrfinanzas.app"}, ttl=12 * 3600, timeout=10)
        return None
    except WebPushException as e:
        return e.response.status_code if e.response is not None else 0
    except Exception:  # red caída, etc.
        log.exception("No pude mandar la notificación")
        return 0


def enviar(db: Session, aviso: Aviso, subs: list[PushSuscripcion] | None = None) -> int:
    """Manda a todos los dispositivos. Borra las suscripciones que ya no existen. Devuelve a cuántos llegó."""
    subs = subs if subs is not None else list(db.scalars(select(PushSuscripcion)))
    if not subs:
        return 0
    vapid = _vapid(db)
    datos = json.dumps({"titulo": aviso.titulo, "cuerpo": aviso.cuerpo, "url": aviso.url, "tag": aviso.clave.split(":")[0]}, ensure_ascii=False)
    ok = 0
    for s in subs:
        st = _mandar_uno(s, datos, vapid)
        if st is None:
            ok += 1
        elif st in (404, 410):  # el navegador la dio de baja
            db.delete(s)
    db.commit()
    return ok


# ───────────────────────── qué avisar ─────────────────────────
def _pesos(v: Decimal) -> str:
    return "$ " + f"{abs(v):,.0f}".replace(",", ".")


def _dias(n: int) -> str:
    return "1 día" if n == 1 else f"{n} días"


def calcular(db: Session, ahora: datetime) -> list[Aviso]:
    from app.services import detectores, fijos as svc_fijos, plan as svc_plan
    hoy = ahora.date()
    prefs = preferencias(db)
    hh, mm = map(int, prefs["notif_hora"].split(":"))
    desde = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
    # Nada antes de tu hora ni de noche
    if ahora < desde or ahora.hour >= 22:
        return []
    out: list[Aviso] = []

    def ya(clave: str) -> bool:
        return db.get(AvisoEnviado, clave[:200]) is not None

    # El número del día solo tiene sentido a la mañana (si la app estuvo caída, no llega a la noche)
    if prefs["notif_hoy"] and ahora - desde < timedelta(hours=4) and not ya(f"hoy:{hoy}"):
        p = svc_plan.calcular(db, hoy)
        if p.configurado:
            cobro = f", cobrás el {p.proximo_cobro:%d/%m}" if p.proximo_cobro else ""
            if p.hoy >= 0:
                out.append(Aviso(f"hoy:{hoy}", f"Hoy podés gastar {_pesos(p.hoy)}",
                                 f"Te quedan {_pesos(p.restante)} para {_dias(p.dias_restantes)}{cobro}.", "/"))
            else:
                out.append(Aviso(f"hoy:{hoy}", "Hoy conviene no gastar",
                                 f"Venís {_pesos(p.restante)} pasado del mes y faltan {_dias(p.dias_restantes)}{cobro}.", "/plan"))

    if prefs["notif_fijos"]:
        svc_fijos.generar(db, hoy)
        de_hoy = svc_fijos.de_hoy(db, hoy)
        if de_hoy and not ya(f"fijos:{hoy}"):
            total = sum((m.monto for m in de_hoy), CERO)
            nombres = " y ".join([", ".join(m.descripcion for m in de_hoy[:-1]), de_hoy[-1].descripcion]) if len(de_hoy) > 1 else de_hoy[0].descripcion
            out.append(Aviso(f"fijos:{hoy}", f"Hoy toca {nombres}",
                             f"{_pesos(total)}. Ya está en la bandeja: confirmalo con un toque cuando lo pagues.", "/"))

    if prefs["notif_vencimientos"]:
        cal = svc_plan.calendario(db, hoy, 2)
        for e in cal.eventos:
            if e.tipo not in ("tarjeta", "prestamo") or e.fecha > hoy + timedelta(days=1):
                continue
            cuando = "hoy" if e.fecha == hoy else "mañana"
            nombre = e.titulo.replace("Resumen ", "el resumen de ").replace("Cuota ", "la cuota de ")
            out.append(Aviso(f"venc:{e.titulo}:{e.fecha}", f"Vence {cuando} {nombre}",
                             f"Son {_pesos(e.monto)}{' (estimado)' if e.estimado else ''}.", "/deudas"))

    if prefs["notif_avisos"]:
        for h in detectores.hallazgos(db, hoy):
            if h.tipo in ("garantia", "fijo_atrasado", "inversion", "duplicado") and h.tono == "aviso":
                out.append(Aviso(f"h:{h.clave}", h.titulo, h.detalle, "/"))
    return out


def _marcar(db: Session, clave: str) -> bool:
    """Anota el aviso como enviado. False si ya estaba (otro proceso lo mandó)."""
    try:
        with db.begin_nested():
            db.add(AvisoEnviado(clave=clave[:200]))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def tick(db: Session, ahora: datetime | None = None) -> list[Aviso]:
    """Una pasada del programador. Devuelve lo que mandó."""
    ahora = ahora or datetime.now()
    subs = list(db.scalars(select(PushSuscripcion)))
    if not subs:
        # Sin dispositivos no hay a quién avisar, pero los fijos igual entran a la bandeja
        from app.services import fijos as svc_fijos
        svc_fijos.generar(db, ahora.date())
        return []
    enviados = []
    for a in calcular(db, ahora):
        if db.get(AvisoEnviado, a.clave[:200]) or not _marcar(db, a.clave):
            continue
        enviar(db, a, subs)
        enviados.append(a)
    # Limpieza: lo enviado hace más de 60 días ya no hace falta
    viejos = db.scalars(select(AvisoEnviado).where(AvisoEnviado.creado < datetime.now().astimezone() - timedelta(days=60)))
    for v in viejos:
        db.delete(v)
    db.commit()
    return enviados
