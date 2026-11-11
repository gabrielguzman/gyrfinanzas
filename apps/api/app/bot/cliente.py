"""Cliente mínimo de la API de bots de Telegram (long polling, sin dependencias extra)."""
import json
from typing import Any

import httpx

Botones = list[list[tuple[str, str]]]  # filas de (texto, callback_data)


def teclado(botones: Botones | None) -> dict | None:
    if not botones:
        return None
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in fila] for fila in botones]}


class TelegramError(RuntimeError):
    pass


class TelegramCliente:
    def __init__(self, token: str, timeout: float = 40.0):
        self._base = f"https://api.telegram.org/bot{token}"
        self._archivos = f"https://api.telegram.org/file/bot{token}"
        self._http = httpx.Client(timeout=timeout)

    def _llamar(self, metodo: str, **params: Any) -> Any:
        datos = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items() if v is not None}
        r = self._http.post(f"{self._base}/{metodo}", data=datos)
        cuerpo = r.json()
        if not cuerpo.get("ok"):
            # No incluimos la URL: contiene el token.
            raise TelegramError(f"{metodo}: {cuerpo.get('description', r.status_code)}")
        return cuerpo["result"]

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        return self._llamar("getUpdates", offset=offset, timeout=timeout,
                            allowed_updates=["message", "callback_query"])

    def enviar(self, chat_id: int, texto: str, botones: Botones | None = None) -> int:
        msg = self._llamar("sendMessage", chat_id=chat_id, text=texto, parse_mode="HTML",
                           reply_markup=teclado(botones), disable_web_page_preview=True)
        return msg["message_id"]

    def editar(self, chat_id: int, message_id: int, texto: str, botones: Botones | None = None) -> None:
        try:
            self._llamar("editMessageText", chat_id=chat_id, message_id=message_id, text=texto,
                         parse_mode="HTML", reply_markup=teclado(botones) or {"inline_keyboard": []})
        except TelegramError as e:
            if "not modified" not in str(e):
                raise

    def responder_boton(self, callback_id: str, texto: str | None = None) -> None:
        self._llamar("answerCallbackQuery", callback_query_id=callback_id, text=texto)

    def descargar(self, file_id: str) -> bytes:
        info = self._llamar("getFile", file_id=file_id)
        r = self._http.get(f"{self._archivos}/{info['file_path']}")
        r.raise_for_status()
        return r.content

    def configurar_comandos(self) -> None:
        self._llamar("setMyCommands", commands=[
            {"command": "hoy", "description": "Cuánto podés gastar hoy"},
            {"command": "puedo", "description": "¿Me lo puedo comprar? /puedo notebook 1.2M 12 cuotas visa"},
            {"command": "saldo", "description": "Cuánto tenés disponible"},
            {"command": "bandeja", "description": "Lo que falta confirmar"},
            {"command": "ultimos", "description": "Últimos movimientos"},
            {"command": "semana", "description": "Resumen de la semana pasada"},
            {"command": "metas", "description": "Cómo vienen tus metas de ahorro"},
            {"command": "patrimonio", "description": "Cuánto tenés en total"},
            {"command": "garantias", "description": "Qué garantías tenés y cuándo vencen"},
            {"command": "ayuda", "description": "Cómo cargar"},
        ])
