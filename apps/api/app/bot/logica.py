"""Qué hace el bot con cada mensaje. No sabe nada de HTTP: recibe un cliente
(real o falso, para tests) y una fábrica de sesiones de base de datos."""
import base64
import html
import hmac
import io
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from fastapi import HTTPException, UploadFile
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.bot.cliente import Botones
from app.models import (
    TipoMedioPago,
    Archivo,
    Cuenta,
    EstadoMovimiento,
    MedioPago,
    Movimiento,
    MovimientoAdjunto,
    OrigenMovimiento,
    RolAdjunto,
    TelegramChat,
    TipoCuenta,
    TipoMovimiento,
)
from app.services import archivos as svc_archivos
from app.services import garantias as svc_garantias
from app.services import plan as svc_plan
from app.services import compra as svc_compra
from app.services.registro import interpretar_texto
from app.services import cotizacion as svc_cot, metas as svc_metas, patrimonio as svc_patrimonio
from app.services.registro import SinMonto, borrar as borrar_mov, confirmar, crear_desde_texto, vincular
from app.services.saldos import saldos_por_cuenta
from app.services.tarjetas import deuda_corriente
from app.services import semanal

log = logging.getLogger("gyr.bot")

VENTANA_ADJUNTO = 15 * 60  # una foto sin texto va al último gasto si es de hace menos de 15 min
MAX_INTENTOS = 5

AYUDA = (
    "<b>Escribime lo que gastaste como te salga:</b>\n"
    "• <code>nafta 40k visa</code>\n"
    "• <code>café 2500 mp</code>\n"
    "• <code>ayer farmacia 18.900 efectivo</code>\n"
    "• <code>cobré el sueldo 1.45M</code>\n\n"
    "📎 Mandame la <b>foto del ticket</b> o un PDF y lo guardo con el gasto.\n"
    "🎯 Para tus metas: <code>aparté 50k para vacaciones</code>\n"
    "🛡 Si tiene garantía, agregalo: <code>heladera 850k visa garantía 1 año</code>\n\n"
    "/hoy · /puedo · /saldo · /bandeja · /ultimos · /semana · /metas · /patrimonio · /garantias"
)


# ---------- utilidades ----------
def corto(u: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(u.bytes).decode().rstrip("=")


def largo(s: str) -> uuid.UUID:
    return uuid.UUID(bytes=base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)))


def pesos(valor: Decimal | float | int, moneda: str = "ARS") -> str:
    v = Decimal(valor).quantize(Decimal("0.01"))
    entero, dec = f"{abs(v):,.2f}".split(".")
    entero = entero.replace(",", ".")
    texto = entero if dec == "00" else f"{entero},{dec}"
    signo = "−" if v < 0 else ""
    return f"{signo}{'USD' if moneda == 'USD' else '$'} {texto}"


def esc(s: str | None) -> str:
    return html.escape(s or "")


class Cliente(Protocol):
    def enviar(self, chat_id: int, texto: str, botones: Botones | None = None) -> int: ...
    def editar(self, chat_id: int, message_id: int, texto: str, botones: Botones | None = None) -> None: ...
    def responder_boton(self, callback_id: str, texto: str | None = None) -> None: ...
    def descargar(self, file_id: str) -> bytes: ...


@dataclass
class EstadoChat:
    ultimo_mov: uuid.UUID | None = None
    ultimo_en: float = 0.0
    archivo_pendiente: uuid.UUID | None = None
    intentos: int = 0


@dataclass
class Bot:
    cliente: Cliente
    sesiones: Callable[[], Session]
    codigo: str
    reloj: Callable[[], float] = time.time
    estados: dict[int, EstadoChat] = field(default_factory=dict)

    # ---------- entrada ----------
    def procesar(self, update: dict) -> None:
        try:
            if "callback_query" in update:
                self._boton(update["callback_query"])
            elif "message" in update:
                self._mensaje(update["message"])
        except Exception:
            log.exception("Error procesando update %s", update.get("update_id"))
            chat = (update.get("message") or update.get("callback_query", {}).get("message") or {}).get("chat", {})
            if chat.get("id"):
                try:
                    self.cliente.enviar(chat["id"], "Uy, algo falló de mi lado. Probá de nuevo en un rato.")
                except Exception:
                    pass

    def _estado(self, chat_id: int) -> EstadoChat:
        return self.estados.setdefault(chat_id, EstadoChat())

    def _autorizado(self, db: Session, chat_id: int) -> bool:
        return db.get(TelegramChat, chat_id) is not None

    # ---------- mensajes ----------
    def _mensaje(self, msg: dict) -> None:
        chat = msg["chat"]
        chat_id = chat["id"]
        if chat.get("type") != "private":
            return  # solo chats privados
        texto = (msg.get("text") or msg.get("caption") or "").strip()

        with self.sesiones() as db:
            if not self._autorizado(db, chat_id):
                self._vincular(db, chat, texto)
                return

            comando = texto.split()[0].split("@")[0].lower() if texto.startswith("/") else None
            if comando in ("/start", "/ayuda", "/help"):
                self.cliente.enviar(chat_id, AYUDA)
            elif comando == "/saldo":
                self.cliente.enviar(chat_id, self._texto_saldo(db))
            elif comando == "/bandeja":
                self._bandeja(db, chat_id)
            elif comando == "/semana":
                self.enviar_semanal(db, chat_id)
            elif comando == "/ultimos":
                self._ultimos(db, chat_id)
            elif comando == "/hoy":
                self.cliente.enviar(chat_id, self._texto_hoy(db))
            elif comando == "/puedo":
                self.cliente.enviar(chat_id, self._texto_puedo(db, texto.partition(" ")[2].strip()))
            elif comando == "/metas":
                self.cliente.enviar(chat_id, self._texto_metas(db))
            elif comando == "/patrimonio":
                self.cliente.enviar(chat_id, self._texto_patrimonio(db))
            elif comando == "/garantias":
                self.cliente.enviar(chat_id, self._texto_garantias(db))
            elif comando:
                self.cliente.enviar(chat_id, "No conozco ese comando. " + AYUDA)
            elif "photo" in msg or "document" in msg:
                self._archivo(db, chat_id, msg, texto)
            elif texto:
                self._texto(db, chat_id, texto)

    def _vincular(self, db: Session, chat: dict, texto: str) -> None:
        chat_id = chat["id"]
        est = self._estado(chat_id)
        partes = texto.split()
        if len(partes) == 2 and partes[0].lower() in ("/vincular", "/start"):
            if est.intentos >= MAX_INTENTOS:
                self.cliente.enviar(chat_id, "Demasiados intentos. Reiniciá gyrfinanzas para obtener un código nuevo.")
                return
            if self.codigo and hmac.compare_digest(partes[1].strip().upper(), self.codigo.upper()):
                nombre = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])) or chat.get("username", "")
                db.add(TelegramChat(chat_id=chat_id, nombre=nombre[:120]))
                db.commit()
                est.intentos = 0
                self.cliente.enviar(chat_id, f"¡Listo{', ' + esc(chat.get('first_name')) if chat.get('first_name') else ''}! Ya estamos vinculados. 🎉\n\n" + AYUDA)
                return
            est.intentos += 1
            self.cliente.enviar(chat_id, "Ese código no es. Revisalo en la Terminal donde corre gyrfinanzas.")
            return
        self.cliente.enviar(
            chat_id,
            "Hola 👋 Este bot es privado.\nSi es tuyo, mandame <code>/vincular CÓDIGO</code> "
            "con el código que aparece en la Terminal de gyrfinanzas.",
        )

    # ---------- carga por texto ----------
    def _texto(self, db: Session, chat_id: int, texto: str) -> None:
        est = self._estado(chat_id)
        aporte = svc_metas.interpretar_aporte(db, texto)
        if aporte:
            self._aportar(db, chat_id, *aporte)
            return
        try:
            mov, interpretado = crear_desde_texto(db, texto, OrigenMovimiento.telegram)
        except SinMonto as e:
            self.cliente.enviar(chat_id, f"🤔 {esc(str(e))}")
            return

        adjuntado = None
        if est.archivo_pendiente:
            archivo = db.get(Archivo, est.archivo_pendiente)
            if archivo:
                vincular(db, mov, archivo, RolAdjunto.ticket)
                adjuntado = archivo
            est.archivo_pendiente = None

        if mov.medio_pago_id:
            try:
                confirmar(db, mov)
            except HTTPException:
                pass  # queda pendiente (por ejemplo, moneda distinta a la cuenta)
        db.commit()
        est.ultimo_mov, est.ultimo_en = mov.id, self.reloj()
        texto_resp, botones = self._tarjeta(db, mov)
        if adjuntado:
            texto_resp += "\n📎 Con el comprobante que me mandaste"
        if interpretado.aviso:
            texto_resp += f"\n⚠️ {esc(interpretado.aviso)}"
        self.cliente.enviar(chat_id, texto_resp, botones)

    def _tarjeta(self, db: Session, mov: Movimiento) -> tuple[str, Botones]:
        db.refresh(mov)
        signo = "+" if mov.tipo == TipoMovimiento.ingreso else "−"
        valor = pesos(mov.monto, mov.moneda.value).lstrip("−")
        linea = f"<b>{esc(mov.descripcion)}</b> · {signo} {valor}"
        detalles = [mov.categoria.nombre if mov.categoria else "Sin categoría"]
        if mov.medio_pago:
            detalles.append(mov.medio_pago.nombre)
        if mov.fecha != date.today():
            detalles.append(mov.fecha.strftime("%d/%m"))
        clip = " 📎" if mov.adjuntos else ""
        if mov.garantias:
            detalles.append(f"garantía hasta {svc_garantias.estado(mov.garantias[0]).vence:%m/%Y}")
        m = corto(mov.id)

        if mov.estado == EstadoMovimiento.confirmado:
            texto = f"✅ {linea}{clip}\n{esc(' · '.join(detalles))}"
            if mov.tipo == TipoMovimiento.gasto:
                texto += self._linea_hoy(db)
            return texto, [[("Cambiar medio", f"cm|{m}"), ("Deshacer", f"u|{m}")]]

        pregunta = "¿Con qué pagaste?" if mov.tipo != TipoMovimiento.ingreso else "¿Dónde entró?"
        texto = f"📥 {linea}{clip}\n{esc(' · '.join(detalles))}\n<b>{pregunta}</b>"
        return texto, self._botones_medios(db, mov) + [[("Dejar en la bandeja", f"b|{m}"), ("Borrar", f"u|{m}")]]

    def _botones_medios(self, db: Session, mov: Movimiento) -> Botones:
        medios = db.scalars(select(MedioPago).where(MedioPago.archivado.is_(False)).order_by(MedioPago.nombre)).all()
        if mov.cuotas and mov.cuotas > 1:  # en cuotas: solo tarjetas de crédito
            medios = [md for md in medios if md.tipo == TipoMedioPago.credito]
        m = corto(mov.id)
        botones = [(md.nombre, f"m|{m}|{corto(md.id)}") for md in medios]
        return [botones[i:i + 2] for i in range(0, len(botones), 2)]

    # ---------- comprobantes ----------
    def _archivo(self, db: Session, chat_id: int, msg: dict, texto: str) -> None:
        est = self._estado(chat_id)
        if "photo" in msg:
            foto = max(msg["photo"], key=lambda p: p.get("file_size", 0))
            file_id, nombre, mime = foto["file_id"], f"foto_{msg['message_id']}.jpg", "image/jpeg"
        else:
            doc = msg["document"]
            file_id, nombre, mime = doc["file_id"], doc.get("file_name") or "archivo", (doc.get("mime_type") or "")
        if mime not in svc_archivos.TIPOS_PERMITIDOS:
            self.cliente.enviar(chat_id, "Solo guardo fotos y PDFs.")
            return

        contenido = self.cliente.descargar(file_id)
        try:
            archivo = svc_archivos.guardar(db, UploadFile(file=io.BytesIO(contenido), filename=nombre,
                                                          headers={"content-type": mime}))
        except HTTPException as e:
            self.cliente.enviar(chat_id, f"No pude guardarlo: {esc(e.detail)}")
            return

        # 1) Con texto: es un gasto nuevo con su comprobante.
        if texto:
            est.archivo_pendiente = archivo.id
            db.commit()
            self._texto(db, chat_id, texto)
            return

        # 2) Sin texto y hay un gasto recién cargado sin comprobante: va ahí.
        if est.ultimo_mov and self.reloj() - est.ultimo_en < VENTANA_ADJUNTO:
            mov = db.get(Movimiento, est.ultimo_mov)
            if mov and not mov.adjuntos:
                vincular(db, mov, archivo, RolAdjunto.ticket)
                db.commit()
                est.ultimo_mov = None
                self.cliente.enviar(
                    chat_id,
                    f"📎 Lo adjunté a <b>{esc(mov.descripcion)}</b> · {pesos(mov.monto, mov.moneda.value)}",
                    [[("No, es de otro", f"x|{corto(mov.id)}|{corto(archivo.id)}")]],
                )
                return

        # 3) Si no, preguntamos de qué es.
        db.commit()
        self._preguntar_destino(db, chat_id, archivo)

    def _preguntar_destino(self, db: Session, chat_id: int, archivo: Archivo, message_id: int | None = None) -> None:
        self._estado(chat_id).archivo_pendiente = archivo.id
        recientes = db.scalars(
            select(Movimiento)
            .where(Movimiento.tipo != TipoMovimiento.transferencia,
                   ~exists().where(MovimientoAdjunto.movimiento_id == Movimiento.id))
            .order_by(Movimiento.fecha.desc(), Movimiento.creado.desc())
            .limit(5)
        ).all()
        a = corto(archivo.id)
        botones: Botones = [[(f"{m.descripcion} · {pesos(m.monto, m.moneda.value)}"[:60], f"a|{corto(m.id)}|{a}")] for m in recientes]
        texto = ("Guardé el comprobante. <b>¿De qué gasto es?</b>\n"
                 "Elegilo abajo o escribime el gasto y lo adjunto ahí.")
        if message_id:
            self.cliente.editar(chat_id, message_id, texto, botones)
        else:
            self.cliente.enviar(chat_id, texto, botones)

    # ---------- botones ----------
    def _boton(self, cb: dict) -> None:
        chat_id = cb["message"]["chat"]["id"]
        message_id = cb["message"]["message_id"]
        partes = (cb.get("data") or "").split("|")
        with self.sesiones() as db:
            if not self._autorizado(db, chat_id):
                self.cliente.responder_boton(cb["id"], "No autorizado")
                return
            try:
                ids = [largo(p) for p in (partes[1:2] if partes[0] == "v" else partes[1:])]
            except Exception:
                self.cliente.responder_boton(cb["id"], "Botón vencido")
                return
            mov = db.get(Movimiento, ids[0]) if ids else None
            if ids and mov is None and partes[0] != "x":
                self.cliente.responder_boton(cb["id"], "Ese movimiento ya no existe")
                self.cliente.editar(chat_id, message_id, "Ese movimiento ya no existe.")
                return

            accion = partes[0]
            aviso = None
            if accion == "m":  # elegir medio y confirmar
                medio = db.get(MedioPago, ids[1])
                mov.medio_pago_id = medio.id if medio else None
                try:
                    confirmar(db, mov)
                    aviso = "Guardado"
                except HTTPException as e:
                    aviso = str(e.detail)[:190]
                    mov.medio_pago_id, mov.cuenta_id = None, None  # queda en la bandeja, sin ese medio
                db.commit()
                self.cliente.editar(chat_id, message_id, *self._tarjeta(db, mov))
            elif accion == "cm":  # mostrar medios
                texto, _ = self._tarjeta(db, mov)
                m = corto(mov.id)
                self.cliente.editar(chat_id, message_id, texto + "\n<b>¿Con qué pagaste?</b>",
                                    self._botones_medios(db, mov) + [[("Cancelar", f"k|{m}")]])
            elif accion == "k":  # cancelar edición
                self.cliente.editar(chat_id, message_id, *self._tarjeta(db, mov))
            elif accion == "b":  # dejar en bandeja
                texto, _ = self._tarjeta(db, mov)
                self.cliente.editar(chat_id, message_id, texto.rsplit("\n", 1)[0] + "\nQuedó en la bandeja.")
            elif accion == "u":  # deshacer / borrar
                resumen = f"{esc(mov.descripcion)} · {pesos(mov.monto, mov.moneda.value)}"
                borrar_mov(db, mov)
                db.commit()
                self.cliente.editar(chat_id, message_id, f"↩️ <s>{resumen}</s>\nBorrado.")
                aviso = "Borrado"
            elif accion == "a":  # adjuntar archivo a un movimiento
                archivo = db.get(Archivo, ids[1])
                if archivo is None:
                    aviso = "No encontré el archivo"
                else:
                    vincular(db, mov, archivo, RolAdjunto.ticket)
                    db.commit()
                    self._estado(chat_id).archivo_pendiente = None
                    self.cliente.editar(chat_id, message_id,
                                        f"📎 Adjuntado a <b>{esc(mov.descripcion)}</b> · {pesos(mov.monto, mov.moneda.value)}")
                    aviso = "Adjuntado"
            elif accion == "v":  # repaso: ¿valió la pena?
                mov.valio = partes[2] == "1"
                db.commit()
                self.cliente.editar(chat_id, message_id, f"{'👍' if mov.valio else '👎'} {esc(mov.descripcion)} · {pesos(mov.monto, mov.moneda.value)}")
                aviso = "Anotado"
            elif accion == "x":  # no era de ese movimiento
                archivo = db.get(Archivo, ids[1])
                vinc = db.get(MovimientoAdjunto, (ids[0], ids[1]))
                if vinc:
                    db.delete(vinc)
                    db.commit()
                if archivo:
                    self._preguntar_destino(db, chat_id, archivo, message_id)
            self.cliente.responder_boton(cb["id"], aviso)

    # ---------- consultas ----------
    def _texto_saldo(self, db: Session) -> str:
        saldos = saldos_por_cuenta(db)
        cuentas = db.scalars(select(Cuenta).where(Cuenta.archivada.is_(False)).order_by(Cuenta.creado)).all()
        if not cuentas:
            return "Todavía no cargaste cuentas. Hacelo desde la app, en Cuentas."
        lineas: list[str] = []
        for moneda in ("ARS", "USD"):
            de_moneda = [c for c in cuentas if c.moneda.value == moneda]
            if not de_moneda:
                continue
            plata = sum((saldos.get(c.id, Decimal(0)) for c in de_moneda if c.tipo != TipoCuenta.tarjeta_credito), Decimal(0))
            tarjetas = {c.id: deuda_corriente(db, c, saldos.get(c.id, Decimal(0)))
                        for c in de_moneda if c.tipo == TipoCuenta.tarjeta_credito}
            deuda = sum((a for a, _ in tarjetas.values()), Decimal(0))
            lineas.append(f"<b>Disponible{' en USD' if moneda == 'USD' else ''}: {pesos(plata - deuda, moneda)}</b>")
            for c in de_moneda:
                s = saldos.get(c.id, Decimal(0))
                if c.tipo == TipoCuenta.tarjeta_credito:
                    ahora, futuras = tarjetas[c.id]
                    extra = f" (+ {pesos(futuras, moneda)} en cuotas que vienen)" if futuras > 0 else ""
                    lineas.append(f"  💳 {esc(c.nombre)}: a pagar {pesos(ahora, moneda)}{extra}")
                else:
                    lineas.append(f"  • {esc(c.nombre)}: {pesos(s, moneda)}")
            lineas.append("")
        return "\n".join(lineas).strip()

    def _bandeja(self, db: Session, chat_id: int) -> None:
        pendientes = db.scalars(
            select(Movimiento).where(Movimiento.estado == EstadoMovimiento.pendiente)
            .order_by(Movimiento.creado.desc()).limit(5)
        ).all()
        if not pendientes:
            self.cliente.enviar(chat_id, "✨ Bandeja vacía: todo al día.")
            return
        for mov in pendientes:
            self.cliente.enviar(chat_id, *self._tarjeta(db, mov))

    def _ultimos(self, db: Session, chat_id: int) -> None:
        movs = db.scalars(
            select(Movimiento).where(Movimiento.estado == EstadoMovimiento.confirmado)
            .order_by(Movimiento.fecha.desc(), Movimiento.creado.desc()).limit(10)
        ).all()
        if not movs:
            self.cliente.enviar(chat_id, "Todavía no hay movimientos confirmados.")
            return
        lineas = []
        for m in movs:
            signo = "+" if m.tipo == TipoMovimiento.ingreso else ("⇄" if m.tipo == TipoMovimiento.transferencia else "−")
            clip = " 📎" if m.adjuntos else ""
            lineas.append(f"{m.fecha:%d/%m}  {signo} {pesos(m.monto, m.moneda.value).lstrip('−')}  {esc(m.descripcion)}{clip}")
        self.cliente.enviar(chat_id, "<b>Últimos movimientos</b>\n<code>" + "\n".join(lineas) + "</code>")


    def _linea_hoy(self, db: Session) -> str:
        p = svc_plan.calcular(db)
        if not p.configurado:
            return ""
        if p.hoy >= 0:
            return f"\nHoy te quedan <b>{pesos(p.hoy)}</b>"
        return f"\nHoy te pasaste {pesos(-p.hoy)}" + (f"; mañana tenés {pesos(p.manana)}" if p.manana and p.manana > 0 else "")

    def _texto_hoy(self, db: Session) -> str:
        p = svc_plan.calcular(db)
        if not p.configurado:
            return ("Para decirte cuánto podés gastar necesito saber cuándo cobrás y cuánto.\n"
                    "Cargá tu sueldo (<code>cobré el sueldo 1.2M</code>) o configuralo en la web, en Plan.")
        l = []
        if p.hoy >= 0:
            l.append(f"Hoy podés gastar <b>{pesos(p.hoy)}</b>")
        else:
            l.append(f"Hoy te pasaste <b>{pesos(-p.hoy)}</b>")
        if p.restante >= 0:
            l.append(f"Te quedan {pesos(p.restante)} para {p.dias_restantes} días, hasta el cobro del {p.proximo_cobro:%d/%m}.")
        else:
            l.append(f"Ya gastaste {pesos(-p.restante)} más de lo que daba el mes, y faltan {p.dias_restantes} días para cobrar.")
        if p.manana is not None and p.manana > 0 and p.gastado_hoy > 0:
            l.append(f"Si hoy no gastás más, mañana tenés {pesos(p.manana)}.")
        return "\n".join(l)

    def _aportar(self, db: Session, chat_id: int, meta, monto: Decimal) -> None:
        from app.models import AporteMeta
        if meta.cuenta_id:
            self.cliente.enviar(chat_id, f"{esc(meta.nombre)} sigue el saldo de su cuenta: transferí ahí y se actualiza sola.")
            return
        db.add(AporteMeta(meta_id=meta.id, fecha=date.today(), monto=monto, nota="Desde Telegram"))
        db.commit()
        db.refresh(meta)
        e = svc_metas.estado(db, meta, date.today(), svc_cot.obtener(db) if meta.moneda.value == "USD" else None)
        mon = meta.moneda.value
        verbo = "Sumé" if monto > 0 else "Saqué"
        l = [f"🎯 {verbo} {pesos(abs(monto), mon)} {'a' if monto > 0 else 'de'} <b>{esc(meta.emoji)} {esc(meta.nombre)}</b>",
             f"Llevás {pesos(e.ahorrado, mon)} de {pesos(meta.objetivo, mon)} ({round(e.progreso * 100)}%)."]
        if e.cumplida:
            l.append("¡Llegaste! 🎉")
        elif e.por_mes:
            l.append(f"Para llegar: {pesos(e.por_mes, mon)} por mes.")
        self.cliente.enviar(chat_id, "\n".join(l))

    def _texto_puedo(self, db: Session, compra: str) -> str:
        if not compra:
            return "Decime qué querés comprar: <code>/puedo notebook 1.2M en 12 cuotas visa</code>"
        r = interpretar_texto(db, compra)
        if not r.monto:
            return "No encontré el precio. Probá: <code>/puedo zapatillas 120k debito</code>"
        s = svc_compra.simular(db, monto=r.monto, cuotas=r.cuotas or 1, medio=r.medio, descripcion=r.descripcion)
        cabeza = {"si": "✅ <b>Sí, tranqui</b>", "cuidado": "⚠️ <b>Con cuidado</b>", "no": "⛔ <b>Mejor no ahora</b>"}[s.veredicto]
        detalle = f"{esc(s.descripcion)} · {pesos(s.monto)}" + (f" en {s.cuotas} cuotas" if s.cuotas > 1 else "")
        l = [cabeza, detalle, ""] + [f"• {esc(m)}" for m in s.motivos]
        if s.antes.hoy is not None and s.despues.hoy is not None and s.despues.hoy != s.antes.hoy:
            l.append(f"• Hoy podrías gastar {pesos(max(s.despues.hoy, Decimal(0)))} en vez de {pesos(max(s.antes.hoy, Decimal(0)))}.")
        if s.mejor_dia and s.primera_cuota_mejor_dia:
            l.append(f"• Si esperás al {s.mejor_dia:%d/%m}, la primera cuota se paga el {s.primera_cuota_mejor_dia:%d/%m} en vez del {s.primera_cuota:%d/%m}.")
        c = s.cuotas_contado
        if c and c.conviene == "cuotas":
            l.append(f"• Sin interés y con 2% de inflación, las cuotas valen {pesos(c.valor_hoy_cuotas)} en plata de hoy: te conviene en cuotas.")
        l.append("\nNo guardé nada. Si lo comprás, cargalo como siempre.")
        return "\n".join(l)

    def _texto_metas(self, db: Session) -> str:
        metas = svc_metas.activas(db)
        if not metas:
            return "No tenés metas de ahorro. Creá una en la app, en Metas."
        cot = svc_cot.obtener(db) if svc_metas.hay_en_dolares(db) else None
        l = ["<b>Tus metas</b>"]
        for m in metas:
            e = svc_metas.estado(db, m, date.today(), cot)
            mon = m.moneda.value
            extra = " ✅" if e.cumplida else (f" · {pesos(e.por_mes, mon)}/mes" if e.por_mes else "")
            l.append(f"{esc(m.emoji)} {esc(m.nombre)}: {pesos(e.ahorrado, mon)} de {pesos(m.objetivo, mon)} ({round(e.progreso * 100)}%){extra}")
        l.append("\nPara sumar: <code>aparté 50k para " + esc(metas[0].nombre.lower()) + "</code>")
        return "\n".join(l)

    def _texto_patrimonio(self, db: Session) -> str:
        cot = svc_cot.obtener(db)
        p = svc_patrimonio.calcular(db, None, cot, guardar_foto=False)
        l = [f"<b>Patrimonio neto: {pesos(p.neto)}</b>"]
        if p.neto_usd is not None and cot:
            l.append(f"Son USD {p.neto_usd:,.0f} al {cot.nombre} ({pesos(cot.valor)})".replace(",", "."))
        l.append(f"Tenés {pesos(p.activos)} y debés {pesos(p.pasivos)}.")
        if p.meses_esencial is not None:
            l.append(f"Con lo líquido cubrís {p.meses_esencial} meses de gastos fijos.".replace(".0 ", " "))
        return "\n".join(l)

    def _texto_garantias(self, db: Session) -> str:
        hoy = date.today()
        vivas = [(g, svc_garantias.estado(g, hoy)) for g in svc_garantias.activas(db)]
        vivas = [(g, e) for g, e in vivas if e.estado != "vencida"]
        if not vivas:
            return ("No tenés garantías vigentes cargadas.\n"
                    "Agregá «garantía 1 año» cuando cargues una compra y te aviso antes de que venza.")
        l = ["<b>Tus garantías</b>"]
        for g, e in sorted(vivas, key=lambda x: x[1].vence):
            if e.estado == "en_reparacion":
                cuando = "en reparación (no corre)"
            elif e.dias_restantes <= 60:
                cuando = f"vence en {e.dias_restantes} días" if e.dias_restantes > 1 else "vence ya"
            else:
                cuando = f"hasta {e.vence:%m/%Y}"
            alerta = "⚠️ " if e.estado == "por_vencer" else "• "
            l.append(f"{alerta}{esc(g.producto)}: {cuando}")
        return "\n".join(l)

    # ---------- resumen semanal ----------
    def enviar_semanal(self, db: Session, chat_id: int) -> None:
        s = semanal.armar(db)
        self.cliente.enviar(chat_id, semanal.texto_telegram(s))
        if s.repaso:
            self.cliente.enviar(chat_id, "<b>Repaso rápido:</b> ¿valió la pena?")
            for m in s.repaso[:3]:
                c = corto(m.id)
                self.cliente.enviar(
                    chat_id, f"{esc(m.descripcion)} · {pesos(m.monto, m.moneda.value)} · {m.fecha:%d/%m}",
                    [[("👍 Sí", f"v|{c}|1"), ("👎 No", f"v|{c}|0")]],
                )

    def semanal_si_toca(self, ahora: "datetime") -> int:
        """Los lunes desde las 9, una vez por chat. Devuelve a cuántos chats se envió."""
        if ahora.weekday() != 0 or ahora.hour < 9:
            return 0
        enviados = 0
        with self.sesiones() as db:
            for chat in db.scalars(select(TelegramChat)):
                if chat.ultimo_semanal == ahora.date():
                    continue
                try:
                    self.enviar_semanal(db, chat.chat_id)
                    chat.ultimo_semanal = ahora.date()
                    db.commit()
                    enviados += 1
                except Exception:
                    log.exception("No pude enviar el resumen semanal")
        return enviados
