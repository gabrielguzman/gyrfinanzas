"""Login de un solo usuario: una contraseña (guardada como hash scrypt) y una sesión firmada en cookie.

Sin APP_PASSWORD_HASH la app queda abierta, como en tu red local. En producción se configura
el hash y SECRET_KEY, y todo pide sesión salvo /salud y /auth/*.
"""
import base64
import hashlib
import hmac
import os
import sys
import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings

COOKIE = "gyr_sesion"
LIBRES = ("/salud", "/auth/")
N, R, P = 2**14, 8, 1


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def generar_hash(password: str) -> str:
    sal = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=sal, n=N, r=R, p=P, dklen=32)
    # «:» como separador: «$» lo interpretaría Docker Compose en los .env
    return f"scrypt:{N}:{R}:{P}:{_b64(sal)}:{_b64(h)}"


def verificar(password: str, guardado: str) -> bool:
    try:
        alg, n, r, p, sal, h = guardado.replace("$", ":").split(":")
        if alg != "scrypt":
            return False
        calc = hashlib.scrypt(password.encode(), salt=_unb64(sal), n=int(n), r=int(r), p=int(p), dklen=len(_unb64(h)))
        return hmac.compare_digest(calc, _unb64(h))
    except (ValueError, TypeError):
        return False


def activo() -> bool:
    return bool(settings.app_password_hash)


def _firma(datos: str) -> str:
    return _b64(hmac.new(settings.secret_key.encode(), datos.encode(), hashlib.sha256).digest())


def crear_sesion(ahora: float | None = None) -> str:
    vence = int((time.time() if ahora is None else ahora) + settings.sesion_dias * 86400)
    return f"{vence}.{_firma(str(vence))}"


def sesion_valida(token: str | None, ahora: float | None = None) -> bool:
    if not token or "." not in token or not settings.secret_key:
        return False
    vence, firma = token.split(".", 1)
    return vence.isdigit() and hmac.compare_digest(firma, _firma(vence)) and int(vence) > (time.time() if ahora is None else ahora)


# ───────────── límite de intentos: 5 fallidos cada 15 minutos por IP ─────────────
_fallos: dict[str, deque] = defaultdict(deque)
VENTANA, MAX_FALLOS = 15 * 60, 5


def _ip(request: Request) -> str:
    reenviada = request.headers.get("x-forwarded-for", "")
    return reenviada.split(",")[0].strip() or (request.client.host if request.client else "?")


def _bloqueado(ip: str, ahora: float) -> bool:
    q = _fallos[ip]
    while q and ahora - q[0] > VENTANA:
        q.popleft()
    return len(q) >= MAX_FALLOS


async def middleware(request: Request, call_next):
    if not activo() or request.method == "OPTIONS" or request.url.path.startswith(LIBRES):
        return await call_next(request)
    if not sesion_valida(request.cookies.get(COOKIE)):
        return JSONResponse({"detail": "Tenés que entrar con tu contraseña"}, status_code=401)
    return await call_next(request)


router = APIRouter(prefix="/auth", tags=["sistema"])


class LoginIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.get("/estado")
def estado(request: Request):
    return {"requiere": activo(), "ok": (not activo()) or sesion_valida(request.cookies.get(COOKIE))}


@router.post("/login")
def login(datos: LoginIn, request: Request, response: Response):
    if not activo():
        return {"ok": True}
    if not settings.secret_key:
        raise HTTPException(500, "Falta configurar SECRET_KEY en el servidor")
    ip, ahora = _ip(request), time.time()
    if _bloqueado(ip, ahora):
        raise HTTPException(429, "Demasiados intentos. Esperá unos minutos.")
    if not verificar(datos.password, settings.app_password_hash):
        _fallos[ip].append(ahora)
        raise HTTPException(401, "Contraseña incorrecta")
    _fallos.pop(ip, None)
    response.set_cookie(COOKIE, crear_sesion(ahora), max_age=settings.sesion_dias * 86400, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/")
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('Uso: python -m app.auth "tu contraseña"')
        sys.exit(1)
    print(generar_hash(sys.argv[1]))
