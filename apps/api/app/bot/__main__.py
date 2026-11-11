"""Corre el bot de Telegram con long polling (no necesita URL pública).

    TELEGRAM_TOKEN=... TELEGRAM_CODIGO=... uv run python -m app.bot
"""
import logging
import secrets
import sys
import time
from datetime import datetime

from app.bot.cliente import TelegramCliente, TelegramError
from app.bot.logica import Bot
from app.config import settings
from app.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # sus logs incluyen la URL con el token
log = logging.getLogger("gyr.bot")


def main() -> None:
    token = settings.telegram_token.strip()
    if not token:
        sys.exit("Falta TELEGRAM_TOKEN en apps/api/.env (pedíselo a @BotFather en Telegram).")
    codigo = settings.telegram_codigo.strip() or secrets.token_hex(4).upper()

    cliente = TelegramCliente(token)
    bot = Bot(cliente=cliente, sesiones=SessionLocal, codigo=codigo)
    try:
        cliente.configurar_comandos()
    except Exception as e:
        log.warning("No pude configurar los comandos: %s", e)

    log.info("Bot corriendo. Código de vinculación: %s", codigo)
    offset = None
    espera = 1
    while True:
        try:
            bot.semanal_si_toca(datetime.now())
            updates = cliente.get_updates(offset)
            espera = 1
            for u in updates:
                offset = u["update_id"] + 1
                bot.procesar(u)
        except TelegramError as e:
            if "Unauthorized" in str(e):
                sys.exit("El token de Telegram no es válido. Revisá TELEGRAM_TOKEN en apps/api/.env")
            log.warning("Telegram: %s (reintento en %ss)", e, espera)
            time.sleep(espera)
            espera = min(espera * 2, 60)
        except Exception as e:  # red caída, etc.
            log.warning("Sin conexión con Telegram: %s (reintento en %ss)", type(e).__name__, espera)
            time.sleep(espera)
            espera = min(espera * 2, 60)


if __name__ == "__main__":
    main()
