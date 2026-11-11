from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.bot.logica import Bot, corto, largo, pesos
from app.config import settings
from app.db import Base
from app.models import (
    Categoria,
    Cuenta,
    EstadoMovimiento,
    MedioPago,
    Movimiento,
    TipoCategoria,
    TipoCuenta,
    TipoMedioPago,
)
from app.services.saldos import saldos_por_cuenta

YO = 111
EXTRANO = 999


class FakeCliente:
    def __init__(self):
        self.enviados: list[tuple[int, str, list | None]] = []
        self.editados: list[tuple[int, int, str, list | None]] = []
        self.respuestas: list[str | None] = []
        self.archivos: dict[str, bytes] = {}

    def enviar(self, chat_id, texto, botones=None):
        self.enviados.append((chat_id, texto, botones))
        return len(self.enviados)

    def editar(self, chat_id, message_id, texto, botones=None):
        self.editados.append((chat_id, message_id, texto, botones))

    def responder_boton(self, callback_id, texto=None):
        self.respuestas.append(texto)

    def descargar(self, file_id):
        return self.archivos[file_id]

    @property
    def ultimo(self):
        return self.enviados[-1]


@pytest.fixture()
def entorno(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sesion = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Sesion() as db:
        galicia = Cuenta(nombre="Galicia", tipo=TipoCuenta.banco, saldo_inicial=Decimal("100000"))
        visa = Cuenta(nombre="Visa", tipo=TipoCuenta.tarjeta_credito)
        db.add_all([galicia, visa])
        db.flush()
        db.add_all([
            MedioPago(nombre="Débito Galicia", tipo=TipoMedioPago.debito, cuenta_id=galicia.id, alias="debito"),
            MedioPago(nombre="Visa", tipo=TipoMedioPago.credito, cuenta_id=visa.id, alias="visa"),
            Categoria(nombre="Auto", tipo=TipoCategoria.gasto, palabras="nafta"),
        ])
        db.commit()
    original = settings.upload_dir
    settings.upload_dir = str(tmp_path / "uploads")
    reloj = {"t": 1000.0}
    cli = FakeCliente()
    bot = Bot(cliente=cli, sesiones=Sesion, codigo="AB12CD34", reloj=lambda: reloj["t"])
    yield bot, cli, Sesion, reloj
    settings.upload_dir = original


_uid = iter(range(1, 10_000))


def msg(chat_id, texto=None, **extra):
    m = {"message_id": next(_uid), "chat": {"id": chat_id, "type": "private", "first_name": "Gabriel"}}
    if texto is not None:
        m["text"] = texto
    m.update(extra)
    return {"update_id": next(_uid), "message": m}


def boton(chat_id, data, message_id=1):
    return {"update_id": next(_uid), "callback_query": {
        "id": str(next(_uid)), "data": data, "message": {"message_id": message_id, "chat": {"id": chat_id}}}}


def vincular(bot):
    bot.procesar(msg(YO, "/vincular ab12cd34"))


def test_utilidades():
    import uuid
    u = uuid.uuid4()
    assert largo(corto(u)) == u and len(corto(u)) == 22
    assert pesos(Decimal("40000")) == "$ 40.000"
    assert pesos(Decimal("1234.5")) == "$ 1.234,50"
    assert pesos(Decimal("-500"), "USD") == "−USD 500"


def test_chat_no_vinculado_no_puede_cargar(entorno):
    bot, cli, Sesion, _ = entorno
    bot.procesar(msg(EXTRANO, "nafta 40k visa"))
    assert "privado" in cli.ultimo[1]
    with Sesion() as db:
        assert db.scalars(select(Movimiento)).all() == []


def test_codigo_incorrecto_y_bloqueo(entorno):
    bot, cli, _, _ = entorno
    for _ in range(5):
        bot.procesar(msg(EXTRANO, "/vincular NOPE"))
    bot.procesar(msg(EXTRANO, "/vincular AB12CD34"))
    assert "Demasiados intentos" in cli.ultimo[1]


def test_vincular_y_cargar_con_medio_confirma(entorno):
    bot, cli, Sesion, _ = entorno
    vincular(bot)
    assert "vinculados" in cli.ultimo[1]
    bot.procesar(msg(YO, "nafta 40k visa"))
    texto, botones = cli.ultimo[1], cli.ultimo[2]
    assert texto.startswith("✅") and "Nafta" in texto and "40.000" in texto
    assert botones[0][1][0] == "Deshacer"
    with Sesion() as db:
        mov = db.scalars(select(Movimiento)).one()
        assert mov.estado == EstadoMovimiento.confirmado and mov.origen.value == "telegram"
        visa = db.scalars(select(Cuenta).where(Cuenta.nombre == "Visa")).one()
        assert saldos_por_cuenta(db)[visa.id] == Decimal("-40000")


def test_sin_medio_pregunta_y_boton_confirma(entorno):
    bot, cli, Sesion, _ = entorno
    vincular(bot)
    bot.procesar(msg(YO, "regalo 5000"))
    texto, botones = cli.ultimo[1], cli.ultimo[2]
    assert texto.startswith("📥") and "¿Con qué pagaste?" in texto
    data_debito = next(d for fila in botones for t, d in fila if t == "Débito Galicia")
    bot.procesar(boton(YO, data_debito))
    assert cli.editados[-1][2].startswith("✅")
    with Sesion() as db:
        mov = db.scalars(select(Movimiento)).one()
        assert mov.estado == EstadoMovimiento.confirmado and mov.medio_pago.nombre == "Débito Galicia"


def test_deshacer_borra(entorno):
    bot, cli, Sesion, _ = entorno
    vincular(bot)
    bot.procesar(msg(YO, "nafta 40k visa"))
    data = cli.ultimo[2][0][1][1]
    bot.procesar(boton(YO, data))
    assert "Borrado" in cli.editados[-1][2]
    with Sesion() as db:
        assert db.scalars(select(Movimiento)).all() == []


def test_sin_monto(entorno):
    bot, cli, _, _ = entorno
    vincular(bot)
    bot.procesar(msg(YO, "nafta visa"))
    assert "monto" in cli.ultimo[1]


def test_foto_sin_texto_va_al_ultimo_gasto(entorno):
    bot, cli, Sesion, reloj = entorno
    vincular(bot)
    bot.procesar(msg(YO, "nafta 40k visa"))
    cli.archivos["F1"] = b"\xff\xd8 jpeg falso"
    reloj["t"] += 60
    bot.procesar(msg(YO, photo=[{"file_id": "F1", "file_size": 10}]))
    assert "Lo adjunté a <b>Nafta</b>" in cli.ultimo[1]
    with Sesion() as db:
        assert len(db.scalars(select(Movimiento)).one().adjuntos) == 1


def test_foto_tardia_pregunta_de_que_es_y_se_adjunta(entorno):
    bot, cli, Sesion, reloj = entorno
    vincular(bot)
    bot.procesar(msg(YO, "nafta 40k visa"))
    reloj["t"] += 3600
    cli.archivos["F2"] = b"\xff\xd8 otro jpeg"
    bot.procesar(msg(YO, photo=[{"file_id": "F2", "file_size": 10}]))
    assert "¿De qué gasto es?" in cli.ultimo[1]
    data = cli.ultimo[2][0][0][1]
    bot.procesar(boton(YO, data))
    assert "Adjuntado" in cli.editados[-1][2]
    with Sesion() as db:
        assert len(db.scalars(select(Movimiento)).one().adjuntos) == 1


def test_foto_con_texto_crea_gasto_con_comprobante(entorno):
    bot, cli, Sesion, _ = entorno
    vincular(bot)
    cli.archivos["F3"] = b"%PDF factura"
    bot.procesar(msg(YO, caption="super 63280 debito",
                     document={"file_id": "F3", "file_name": "ticket.pdf", "mime_type": "application/pdf"}))
    assert "Con el comprobante" in cli.ultimo[1]
    with Sesion() as db:
        mov = db.scalars(select(Movimiento)).one()
        assert mov.monto == Decimal("63280") and len(mov.adjuntos) == 1


def test_foto_y_despues_texto(entorno):
    bot, cli, Sesion, _ = entorno
    vincular(bot)
    cli.archivos["F4"] = b"\xff\xd8 jpeg 4"
    bot.procesar(msg(YO, photo=[{"file_id": "F4", "file_size": 10}]))
    bot.procesar(msg(YO, "farmacia 18900 debito"))
    assert "Con el comprobante" in cli.ultimo[1]


def test_saldo(entorno):
    bot, cli, _, _ = entorno
    vincular(bot)
    bot.procesar(msg(YO, "nafta 40k visa"))
    bot.procesar(msg(YO, "/saldo"))
    t = cli.ultimo[1]
    assert "Disponible: $ 60.000" in t and "debés $ 40.000" in t


def test_grupos_ignorados(entorno):
    bot, cli, _, _ = entorno
    u = msg(YO, "/vincular AB12CD34")
    u["message"]["chat"]["type"] = "group"
    bot.procesar(u)
    assert cli.enviados == []


def test_hoy_y_cuanto_queda_al_cargar(entorno):
    bot, cli, Sesion, _ = entorno
    vincular(bot)
    bot.procesar(msg(YO, "/hoy"))
    assert "cuándo cobrás" in cli.ultimo[1]
    from app.services.plan import guardar_ajustes
    with Sesion() as db:
        guardar_ajustes(db, {"dia_cobro": "1", "ingreso_mensual": "900000"})
        db.commit()
    bot.procesar(msg(YO, "/hoy"))
    assert cli.ultimo[1].startswith("Hoy podés gastar <b>$ ")
    bot.procesar(msg(YO, "nafta 40k visa"))
    assert "Hoy te quedan" in cli.ultimo[1] or "Hoy te pasaste" in cli.ultimo[1]


def test_puedo(entorno):
    bot, cli, Sesion, _ = entorno
    vincular(bot)
    bot.procesar(msg(YO, "/puedo"))
    assert "Decime qué querés comprar" in cli.ultimo[1]
    bot.procesar(msg(YO, "/puedo zapatillas 120k visa"))
    assert cli.ultimo[1].split("\n")[0] in ("✅ <b>Sí, tranqui</b>", "⚠️ <b>Con cuidado</b>", "⛔ <b>Mejor no ahora</b>")
    assert "No guardé nada" in cli.ultimo[1]
    with Sesion() as db:
        assert db.scalars(select(Movimiento)).all() == []
