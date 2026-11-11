"""Modelo de datos de gyrfinanzas.

Ideas clave (ver docs/decisiones.md):
- Los saldos NO se guardan: se calculan sumando movimientos confirmados.
- Una tarjeta de crédito es una Cuenta con saldo negativo (= deuda).
- Un movimiento `pendiente` está en la bandeja esperando confirmación.
"""
import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum(cls: type[enum.Enum]) -> Enum:
    # native_enum=False: se guarda como VARCHAR + CHECK, fácil de migrar.
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class TipoCuenta(str, enum.Enum):
    banco = "banco"
    billetera = "billetera"
    efectivo = "efectivo"
    tarjeta_credito = "tarjeta_credito"


class Moneda(str, enum.Enum):
    ARS = "ARS"
    USD = "USD"


class TipoMedioPago(str, enum.Enum):
    debito = "debito"
    credito = "credito"
    transferencia = "transferencia"
    qr = "qr"
    efectivo = "efectivo"


class TipoCategoria(str, enum.Enum):
    gasto = "gasto"
    ingreso = "ingreso"


class TipoMovimiento(str, enum.Enum):
    gasto = "gasto"
    ingreso = "ingreso"
    transferencia = "transferencia"


class EstadoMovimiento(str, enum.Enum):
    pendiente = "pendiente"  # en la bandeja
    confirmado = "confirmado"


class OrigenMovimiento(str, enum.Enum):
    manual = "manual"
    texto = "texto"
    foto = "foto"
    pdf = "pdf"
    voz = "voz"
    telegram = "telegram"


class RolAdjunto(str, enum.Enum):
    ticket = "ticket"
    factura = "factura"
    garantia = "garantia"
    resumen = "resumen"
    otro = "otro"


class Cuenta(Base):
    __tablename__ = "cuenta"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[TipoCuenta] = mapped_column(_enum(TipoCuenta))
    moneda: Mapped[Moneda] = mapped_column(_enum(Moneda), default=Moneda.ARS)
    # Para tarjetas, un saldo inicial negativo representa deuda previa.
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    # Solo tarjetas: día del mes de cierre y de vencimiento (aprox.).
    dia_cierre: Mapped[int | None] = mapped_column(Integer)
    dia_vencimiento: Mapped[int | None] = mapped_column(Integer)
    archivada: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    medios_pago: Mapped[list["MedioPago"]] = relationship(back_populates="cuenta")


class MedioPago(Base):
    __tablename__ = "medio_pago"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[TipoMedioPago] = mapped_column(_enum(TipoMedioPago))
    cuenta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta.id", ondelete="RESTRICT"))
    # Palabras que lo identifican en texto libre, separadas por coma: "visa,galicia".
    alias: Mapped[str] = mapped_column(String(200), default="")
    archivado: Mapped[bool] = mapped_column(Boolean, default=False)

    cuenta: Mapped[Cuenta] = relationship(back_populates="medios_pago")


class Categoria(Base):
    __tablename__ = "categoria"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(60))
    tipo: Mapped[TipoCategoria] = mapped_column(_enum(TipoCategoria), default=TipoCategoria.gasto)
    # Palabras clave para autocategorizar: "nafta,ypf,shell".
    palabras: Mapped[str] = mapped_column(String(400), default="")
    # Identidad visual: clave de ícono y de color que entiende la web.
    icono: Mapped[str] = mapped_column(String(32), default="")
    color: Mapped[str] = mapped_column(String(16), default="")


class Movimiento(Base):
    __tablename__ = "movimiento"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_movimiento_monto_positivo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tipo: Mapped[TipoMovimiento] = mapped_column(_enum(TipoMovimiento))
    estado: Mapped[EstadoMovimiento] = mapped_column(
        _enum(EstadoMovimiento), default=EstadoMovimiento.pendiente, index=True
    )
    origen: Mapped[OrigenMovimiento] = mapped_column(
        _enum(OrigenMovimiento), default=OrigenMovimiento.manual
    )
    fecha: Mapped[date] = mapped_column(Date, index=True)
    # Siempre positivo: el signo lo da el tipo.
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    moneda: Mapped[Moneda] = mapped_column(_enum(Moneda), default=Moneda.ARS)
    descripcion: Mapped[str] = mapped_column(String(200), default="")
    texto_original: Mapped[str | None] = mapped_column(Text)
    # Compra en cuotas con tarjeta: al confirmar se crea su plan de cuotas.
    cuotas: Mapped[int | None] = mapped_column(Integer)
    # Repaso semanal: ¿valió la pena? (None = sin responder)
    valio: Mapped[bool | None] = mapped_column(Boolean)
    # Pago, cobro o préstamo asociado a una deuda.
    deuda_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("deuda.id", ondelete="SET NULL"), index=True)

    categoria_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categoria.id", ondelete="SET NULL"))
    medio_pago_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("medio_pago.id", ondelete="SET NULL"))
    # Cuenta de donde sale (gasto/transferencia) o a donde entra (ingreso).
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cuenta.id", ondelete="RESTRICT"), index=True)
    # Solo transferencias: cuenta que recibe.
    cuenta_destino_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cuenta.id", ondelete="RESTRICT"))

    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    actualizado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    categoria: Mapped[Categoria | None] = relationship()
    medio_pago: Mapped[MedioPago | None] = relationship()
    cuenta: Mapped[Cuenta | None] = relationship(foreign_keys=[cuenta_id])
    cuenta_destino: Mapped[Cuenta | None] = relationship(foreign_keys=[cuenta_destino_id])
    adjuntos: Mapped[list["MovimientoAdjunto"]] = relationship(
        back_populates="movimiento", cascade="all, delete-orphan"
    )
    garantias: Mapped[list["Garantia"]] = relationship(back_populates="movimiento")


class Archivo(Base):
    __tablename__ = "archivo"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre_original: Mapped[str] = mapped_column(String(255))
    ruta: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str] = mapped_column(String(100))
    tamano: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    vinculos: Mapped[list["MovimientoAdjunto"]] = relationship(back_populates="archivo")


class MovimientoAdjunto(Base):
    __tablename__ = "movimiento_adjunto"

    movimiento_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("movimiento.id", ondelete="CASCADE"), primary_key=True
    )
    archivo_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("archivo.id", ondelete="CASCADE"), primary_key=True
    )
    rol: Mapped[RolAdjunto] = mapped_column(_enum(RolAdjunto), default=RolAdjunto.ticket)
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    movimiento: Mapped[Movimiento] = relationship(back_populates="adjuntos")
    archivo: Mapped[Archivo] = relationship(back_populates="vinculos")


class TelegramChat(Base):
    """Chats de Telegram autorizados a usar el bot (vinculados con código)."""
    __tablename__ = "telegram_chat"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    nombre: Mapped[str] = mapped_column(String(120), default="")
    ultimo_semanal: Mapped[date | None] = mapped_column(Date)
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TipoLinea(str, enum.Enum):
    consumo = "consumo"
    cuota = "cuota"
    impuesto = "impuesto"
    interes = "interes"
    cargo = "cargo"
    pago = "pago"
    ajuste = "ajuste"


class AccionLinea(str, enum.Enum):
    vincular = "vincular"  # ya estaba cargado: se enlaza
    crear = "crear"        # no estaba: se crea el movimiento
    ignorar = "ignorar"


class EstadoResumen(str, enum.Enum):
    procesando = "procesando"
    revision = "revision"
    confirmado = "confirmado"
    error = "error"


class PlanCuotas(Base):
    """Una compra en cuotas. La cuota k cae en el resumen del periodo primer_periodo + (k-1)."""
    __tablename__ = "plan_cuotas"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cuenta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta.id", ondelete="CASCADE"), index=True)
    descripcion: Mapped[str] = mapped_column(String(200))
    monto_cuota: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    cuotas_total: Mapped[int] = mapped_column(Integer)
    primer_periodo: Mapped[str] = mapped_column(String(7))  # "YYYY-MM" del cierre de la 1ª cuota
    moneda: Mapped[Moneda] = mapped_column(_enum(Moneda), default=Moneda.ARS)
    movimiento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("movimiento.id", ondelete="SET NULL"))
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    cuenta: Mapped[Cuenta] = relationship()


class ResumenTarjeta(Base):
    __tablename__ = "resumen_tarjeta"
    __table_args__ = (UniqueConstraint("cuenta_id", "periodo", name="uq_resumen_cuenta_periodo"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cuenta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cuenta.id", ondelete="CASCADE"), index=True)
    periodo: Mapped[str | None] = mapped_column(String(7))
    estado: Mapped[EstadoResumen] = mapped_column(_enum(EstadoResumen), default=EstadoResumen.procesando)
    metodo: Mapped[str] = mapped_column(String(16), default="")
    error: Mapped[str | None] = mapped_column(Text)
    fecha_cierre: Mapped[date | None] = mapped_column(Date)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    saldo_anterior: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_ars: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    pago_minimo: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tna: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    archivo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("archivo.id", ondelete="SET NULL"))
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    cuenta: Mapped[Cuenta] = relationship()
    lineas: Mapped[list["ResumenLinea"]] = relationship(
        back_populates="resumen", cascade="all, delete-orphan", order_by="ResumenLinea.orden"
    )


class ResumenLinea(Base):
    __tablename__ = "resumen_linea"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    resumen_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resumen_tarjeta.id", ondelete="CASCADE"), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    fecha: Mapped[date | None] = mapped_column(Date)
    descripcion: Mapped[str] = mapped_column(String(200))
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # positivo; el tipo dice si suma o resta
    moneda: Mapped[Moneda] = mapped_column(_enum(Moneda), default=Moneda.ARS)
    tipo: Mapped[TipoLinea] = mapped_column(_enum(TipoLinea), default=TipoLinea.consumo)
    cuota_n: Mapped[int | None] = mapped_column(Integer)
    cuota_total: Mapped[int | None] = mapped_column(Integer)
    accion: Mapped[AccionLinea] = mapped_column(_enum(AccionLinea), default=AccionLinea.crear)
    movimiento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("movimiento.id", ondelete="SET NULL"))
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("plan_cuotas.id", ondelete="SET NULL"))

    resumen: Mapped[ResumenTarjeta] = relationship(back_populates="lineas")
    movimiento: Mapped["Movimiento | None"] = relationship()


class TipoDeuda(str, enum.Enum):
    prestamo = "prestamo"    # banco o financiera, con cuotas
    debo = "debo"            # le debo a alguien
    me_deben = "me_deben"    # alguien me debe


class Indexacion(str, enum.Enum):
    fija = "fija"
    uva = "uva"


class Deuda(Base):
    """El saldo NO se guarda: es monto_inicial ajustado por los movimientos vinculados."""
    __tablename__ = "deuda"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tipo: Mapped[TipoDeuda] = mapped_column(_enum(TipoDeuda))
    nombre: Mapped[str] = mapped_column(String(120))
    moneda: Mapped[Moneda] = mapped_column(_enum(Moneda), default=Moneda.ARS)
    monto_inicial: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # lo que se debía al cargarla
    fecha_alta: Mapped[date] = mapped_column(Date)
    tna: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    indexacion: Mapped[Indexacion] = mapped_column(_enum(Indexacion), default=Indexacion.fija)
    cuota: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    cuotas_total: Mapped[int | None] = mapped_column(Integer)
    cuotas_pagadas: Mapped[int] = mapped_column(Integer, default=0)  # antes de cargarla en la app
    dia_vencimiento: Mapped[int | None] = mapped_column(Integer)
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cuenta.id", ondelete="SET NULL"))
    cerrada: Mapped[bool] = mapped_column(Boolean, default=False)
    notas: Mapped[str] = mapped_column(String(400), default="")
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class HallazgoDescartado(Base):
    """Un aviso que el usuario cerró. Vuelve a aparecer si cambia (la clave incluye el dato)."""
    __tablename__ = "hallazgo_descartado"

    clave: Mapped[str] = mapped_column(String(200), primary_key=True)
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Garantia(Base):
    """Garantía de algo que compraste. `vence` se guarda (se puede corregir a mano);
    si lo mandás a reparar, los días en el service la estiran (Ley 24.240, art. 16)."""
    __tablename__ = "garantia"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    producto: Mapped[str] = mapped_column(String(120))
    comercio: Mapped[str] = mapped_column(String(120), default="")
    serie: Mapped[str] = mapped_column(String(80), default="")  # número de serie, para reclamar
    fecha_compra: Mapped[date] = mapped_column(Date)
    meses: Mapped[int] = mapped_column(Integer, default=12)
    vence: Mapped[date] = mapped_column(Date, index=True)
    en_reparacion_desde: Mapped[date | None] = mapped_column(Date)
    dias_reparacion: Mapped[int] = mapped_column(Integer, default=0)
    notas: Mapped[str] = mapped_column(String(400), default="")
    movimiento_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("movimiento.id", ondelete="SET NULL"), index=True)
    # Comprobante propio (cuando no hay gasto cargado: algo que compraste antes de usar la app)
    archivo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("archivo.id", ondelete="SET NULL"))
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    movimiento: Mapped["Movimiento | None"] = relationship(back_populates="garantias")
    archivo: Mapped["Archivo | None"] = relationship()


class Ajuste(Base):
    """Preferencias sueltas (clave → valor en texto): día de cobro, ingreso mensual, ahorro."""
    __tablename__ = "ajuste"

    clave: Mapped[str] = mapped_column(String(60), primary_key=True)
    valor: Mapped[str] = mapped_column(String(200))


class Meta(Base):
    """Meta de ahorro. Lo ahorrado sale de una cuenta aparte (si la elegís) o de los aportes que anotás."""
    __tablename__ = "meta"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(80))
    emoji: Mapped[str] = mapped_column(String(16), default="🎯")
    objetivo: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    moneda: Mapped[Moneda] = mapped_column(_enum(Moneda), default=Moneda.ARS)
    fecha_objetivo: Mapped[date | None] = mapped_column(Date)
    # Sin fecha: cuánto pensás poner por mes (con eso se estima cuándo llegás)
    aporte_mensual: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    cuenta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cuenta.id", ondelete="SET NULL"))
    archivada: Mapped[bool] = mapped_column(Boolean, default=False)
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    aportes: Mapped[list["AporteMeta"]] = relationship(
        back_populates="meta", cascade="all, delete-orphan", order_by="AporteMeta.fecha")


class AporteMeta(Base):
    __tablename__ = "aporte_meta"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    meta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meta.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # negativo = sacaste
    nota: Mapped[str] = mapped_column(String(120), default="")
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    meta: Mapped[Meta] = relationship(back_populates="aportes")


class TipoInversion(str, enum.Enum):
    plazo_fijo = "plazo_fijo"
    fci = "fci"
    cripto = "cripto"
    acciones = "acciones"
    bonos = "bonos"
    otro = "otro"


class Inversion(Base):
    """Valor = el que cargaste a mano; si no, el capital más los intereses (TNA) hasta hoy o el vencimiento."""
    __tablename__ = "inversion"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    nombre: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[TipoInversion] = mapped_column(_enum(TipoInversion), default=TipoInversion.otro)
    moneda: Mapped[Moneda] = mapped_column(_enum(Moneda), default=Moneda.ARS)
    capital: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    tna: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    vence: Mapped[date | None] = mapped_column(Date)
    valor_actual: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    actualizado: Mapped[date | None] = mapped_column(Date)
    cerrada: Mapped[bool] = mapped_column(Boolean, default=False)
    notas: Mapped[str] = mapped_column(String(200), default="")
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FotoPatrimonio(Base):
    """Una foto por día del patrimonio neto, para ver la evolución real."""
    __tablename__ = "foto_patrimonio"

    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    neto_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    neto_usd: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    cotizacion: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
