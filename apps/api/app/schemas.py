from typing import Literal
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    EstadoMovimiento,
    Moneda,
    OrigenMovimiento,
    RolAdjunto,
    TipoCategoria,
    TipoCuenta,
    TipoMedioPago,
    TipoMovimiento,
)


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Cuentas ----------
class CuentaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: TipoCuenta
    moneda: Moneda = Moneda.ARS
    saldo_inicial: Decimal = Decimal("0")
    dia_cierre: int | None = Field(default=None, ge=1, le=31)
    dia_vencimiento: int | None = Field(default=None, ge=1, le=31)


class CuentaPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    saldo_inicial: Decimal | None = None
    dia_cierre: int | None = Field(default=None, ge=1, le=31)
    dia_vencimiento: int | None = Field(default=None, ge=1, le=31)
    archivada: bool | None = None


class CuentaOut(_Out):
    id: uuid.UUID
    nombre: str
    tipo: TipoCuenta
    moneda: Moneda
    saldo_inicial: Decimal
    dia_cierre: int | None
    dia_vencimiento: int | None
    archivada: bool
    saldo: Decimal = Decimal("0")


# ---------- Medios de pago ----------
class MedioPagoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: TipoMedioPago
    cuenta_id: uuid.UUID
    alias: str = ""


class MedioPagoPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    cuenta_id: uuid.UUID | None = None
    alias: str | None = None
    archivado: bool | None = None


class MedioPagoOut(_Out):
    id: uuid.UUID
    nombre: str
    tipo: TipoMedioPago
    cuenta_id: uuid.UUID
    alias: str
    archivado: bool


# ---------- Categorías ----------
class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    tipo: TipoCategoria = TipoCategoria.gasto
    palabras: str = ""
    icono: str = Field(default="", max_length=32)
    color: str = Field(default="", max_length=16)


class CategoriaPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    palabras: str | None = None
    icono: str | None = Field(default=None, max_length=32)
    color: str | None = Field(default=None, max_length=16)


class CategoriaOut(_Out):
    id: uuid.UUID
    nombre: str
    tipo: TipoCategoria
    palabras: str
    icono: str
    color: str


# ---------- Archivos ----------
class ArchivoOut(_Out):
    id: uuid.UUID
    nombre_original: str
    mime: str
    tamano: int
    creado: datetime


class ArchivoConVinculosOut(ArchivoOut):
    movimientos: list[uuid.UUID] = []
    garantia: str | None = None  # producto, si es el comprobante de una garantía suelta


class AdjuntoIn(BaseModel):
    archivo_id: uuid.UUID
    rol: RolAdjunto = RolAdjunto.ticket


class AdjuntoOut(BaseModel):
    archivo_id: uuid.UUID
    nombre: str
    mime: str
    rol: RolAdjunto


# ---------- Movimientos ----------
class MovimientoIn(BaseModel):
    tipo: TipoMovimiento
    fecha: date
    monto: Decimal = Field(gt=0)
    moneda: Moneda = Moneda.ARS
    descripcion: str = Field(default="", max_length=200)
    categoria_id: uuid.UUID | None = None
    medio_pago_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    cuenta_destino_id: uuid.UUID | None = None
    cuotas: int | None = Field(default=None, ge=1, le=72)
    etiquetas: list[str] | None = Field(default=None, max_length=20)
    # Lo cargado a mano entra confirmado; la captura automática entra pendiente.
    estado: EstadoMovimiento = EstadoMovimiento.confirmado


class MovimientoPatch(BaseModel):
    tipo: TipoMovimiento | None = None
    fecha: date | None = None
    monto: Decimal | None = Field(default=None, gt=0)
    moneda: Moneda | None = None
    descripcion: str | None = Field(default=None, max_length=200)
    categoria_id: uuid.UUID | None = None
    medio_pago_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    cuenta_destino_id: uuid.UUID | None = None
    cuotas: int | None = Field(default=None, ge=1, le=72)
    etiquetas: list[str] | None = Field(default=None, max_length=20)


class MovimientoOut(BaseModel):
    id: uuid.UUID
    tipo: TipoMovimiento
    estado: EstadoMovimiento
    origen: OrigenMovimiento
    fecha: date
    monto: Decimal
    moneda: Moneda
    descripcion: str
    texto_original: str | None
    categoria_id: uuid.UUID | None
    categoria: str | None
    categoria_icono: str | None = None
    categoria_color: str | None = None
    medio_pago_id: uuid.UUID | None
    medio_pago: str | None
    cuenta_id: uuid.UUID | None
    cuenta: str | None
    cuenta_destino_id: uuid.UUID | None
    cuenta_destino: str | None
    adjuntos: list[AdjuntoOut]
    tiene_comprobante: bool
    valio: bool | None = None
    deuda_id: uuid.UUID | None = None
    cuotas: int | None = None
    fijo_id: uuid.UUID | None = None
    etiquetas: list[str] = []
    garantia: "GarantiaMini | None" = None
    creado: datetime


class GarantiaMini(BaseModel):
    id: uuid.UUID
    vence: date
    estado: str
    dias_restantes: int


# ---------- Captura ----------
class Parte(BaseModel):
    inicio: int
    fin: int
    tipo: str  # monto | medio | categoria | fecha | cuotas | moneda | garantia


class Frecuente(BaseModel):
    texto: str
    descripcion: str
    monto: Decimal
    medio_pago: str | None
    categoria_icono: str | None
    categoria_color: str | None
    veces: int

class CapturaIn(BaseModel):
    texto: str = Field(min_length=1, max_length=500)
    origen: OrigenMovimiento = OrigenMovimiento.texto


class Interpretacion(BaseModel):
    tipo: TipoMovimiento
    monto: Decimal | None
    moneda: Moneda
    descripcion: str
    fecha: date
    medio_pago_id: uuid.UUID | None
    medio_pago: str | None
    cuenta_id: uuid.UUID | None
    categoria_id: uuid.UUID | None
    categoria: str | None
    cuotas: int | None
    categoria_icono: str | None = None
    categoria_color: str | None = None
    deuda_tipo: str | None = None
    deuda_nombre: str | None = None
    garantia_meses: int | None = None
    aviso: str | None = None
    etiquetas: list[str] = []
    # Partes del texto reconocidas, para resaltarlas mientras escribís.
    partes: list["Parte"] = []
    # Por qué se eligió el medio de pago ("dijiste «visa»"), para mostrar en la UI.
    motivo_medio: str | None
    faltantes: list[str]


# ---------- Resumen del mes ----------
class CategoriaTotal(BaseModel):
    categoria_id: uuid.UUID | None
    nombre: str
    icono: str
    color: str
    total: Decimal
    cantidad: int


class PuntoDiario(BaseModel):
    dia: int
    acumulado: Decimal


class ResumenMes(BaseModel):
    mes: str
    dias_mes: int
    dia_hoy: int | None  # None si el mes no es el actual
    gastos: Decimal
    ingresos: Decimal
    gastos_anterior_a_la_fecha: Decimal
    gastos_anterior_total: Decimal
    por_categoria: list[CategoriaTotal]
    diario: list[PuntoDiario]
    diario_anterior: list[PuntoDiario]


# ---------- Inicio ----------
class TotalMoneda(BaseModel):
    moneda: Moneda
    en_cuentas: Decimal
    deuda_tarjetas: Decimal      # lo que vence (resumen cerrado + el abierto)
    cuotas_futuras: Decimal = Decimal("0")  # cuotas de resúmenes siguientes: deuda, pero no sale ahora
    disponible: Decimal


class InicioOut(BaseModel):
    totales: list[TotalMoneda]
    pendientes: int
    sin_comprobante_mes: int


# ---------- Tarjetas ----------
class PlanOut(BaseModel):
    id: uuid.UUID
    cuenta_id: uuid.UUID
    descripcion: str
    monto_cuota: Decimal
    cuotas_total: int
    primer_periodo: str
    moneda: Moneda
    cuota_actual: int | None
    restantes: int
    ultimo_periodo: str
    movimiento_id: uuid.UUID | None


class PlanIn(BaseModel):
    descripcion: str = Field(min_length=1, max_length=200)
    monto_cuota: Decimal = Field(gt=0)
    cuotas_total: int = Field(ge=2, le=72)
    cuota_actual: int = Field(default=1, ge=1, le=72, description="Qué cuota cae en el próximo resumen")
    moneda: Moneda = Moneda.ARS


class CompromisoOut(BaseModel):
    periodo: str
    total: Decimal
    planes: int


class LiberacionOut(BaseModel):
    periodo: str
    monto: Decimal
    planes_que_terminan: int


class ResumenCorto(BaseModel):
    id: uuid.UUID
    periodo: str | None
    estado: str
    fecha_cierre: date | None
    fecha_vencimiento: date | None
    total_ars: Decimal | None
    total_usd: Decimal | None
    pago_minimo: Decimal | None
    tna: Decimal | None
    interes_si_minimo: Decimal | None


class TarjetaOut(BaseModel):
    cuenta_id: uuid.UUID
    nombre: str
    deuda: Decimal
    dia_cierre: int | None
    dia_vencimiento: int | None
    proximo_periodo: str
    mejor_dia_compra: date
    ultimo_resumen: ResumenCorto | None
    pendiente_revision: uuid.UUID | None = None
    planes: list[PlanOut]
    compromisos: list[CompromisoOut]
    liberacion: LiberacionOut | None


class LineaOut(BaseModel):
    id: uuid.UUID
    fecha: date | None
    descripcion: str
    monto: Decimal
    moneda: Moneda
    tipo: str
    cuota_n: int | None
    cuota_total: int | None
    accion: str
    movimiento_id: uuid.UUID | None
    movimiento: str | None
    plan_id: uuid.UUID | None


class LineaPatch(BaseModel):
    accion: str | None = None
    tipo: str | None = None
    moneda: Moneda | None = None


class ResumenOut(ResumenCorto):
    cuenta_id: uuid.UUID
    cuenta: str
    metodo: str
    error: str | None
    saldo_anterior: Decimal | None
    archivo_id: uuid.UUID | None
    verificacion: dict | None
    lineas: list[LineaOut]


class ResumenPatch(BaseModel):
    fecha_cierre: date | None = None
    fecha_vencimiento: date | None = None
    saldo_anterior: Decimal | None = None
    total_ars: Decimal | None = None
    pago_minimo: Decimal | None = None


# ---------- Deudas ----------
class DeudaIn(BaseModel):
    tipo: str = Field(pattern="^(prestamo|debo|me_deben)$")
    nombre: str = Field(min_length=1, max_length=120)
    moneda: Moneda = Moneda.ARS
    monto_inicial: Decimal = Field(ge=0, description="Lo que se debe hoy")
    fecha_alta: date | None = None
    tna: Decimal | None = Field(default=None, ge=0, le=1000)
    indexacion: str = Field(default="fija", pattern="^(fija|uva)$")
    cuota: Decimal | None = Field(default=None, gt=0)
    cuotas_total: int | None = Field(default=None, ge=1, le=600)
    cuotas_pagadas: int = Field(default=0, ge=0, le=600)
    dia_vencimiento: int | None = Field(default=None, ge=1, le=31)
    cuenta_id: uuid.UUID | None = None
    notas: str = Field(default="", max_length=400)


class DeudaPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    monto_inicial: Decimal | None = Field(default=None, ge=0)
    tna: Decimal | None = Field(default=None, ge=0, le=1000)
    indexacion: str | None = Field(default=None, pattern="^(fija|uva)$")
    cuota: Decimal | None = Field(default=None, gt=0)
    cuotas_total: int | None = Field(default=None, ge=1, le=600)
    cuotas_pagadas: int | None = Field(default=None, ge=0, le=600)
    dia_vencimiento: int | None = Field(default=None, ge=1, le=31)
    cuenta_id: uuid.UUID | None = None
    cerrada: bool | None = None
    notas: str | None = Field(default=None, max_length=400)


class DeudaOut(BaseModel):
    id: uuid.UUID
    tipo: str
    nombre: str
    moneda: Moneda
    monto_inicial: Decimal
    fecha_alta: date
    tna: Decimal | None
    indexacion: str
    cuota: Decimal | None
    cuotas_total: int | None
    dia_vencimiento: int | None
    cuenta_id: uuid.UUID | None
    cerrada: bool
    notas: str
    saldo: Decimal
    pagado: Decimal
    intereses_pagados: Decimal
    pagos: int
    cuotas_pagadas: int | None
    cuotas_restantes: int | None
    proximo_vencimiento: date | None
    cuota_sugerida: Decimal | None


class DeudaDetalle(DeudaOut):
    movimientos: list[MovimientoOut]


class DeudaMovimientoIn(BaseModel):
    accion: str = Field(pattern="^(pago|aumento)$", description="pago = achica la deuda; aumento = la agranda")
    monto: Decimal | None = Field(default=None, gt=0)
    fecha: date | None = None
    medio_pago_id: uuid.UUID | None = None


class SimularIn(BaseModel):
    extra_mensual: Decimal = Field(default=Decimal("0"), ge=0)
    inflacion_mensual: Decimal | None = Field(default=None, ge=0, le=100, description="% mensual esperado")
    tarjetas: list[uuid.UUID] = []


class DeudaSimOut(BaseModel):
    id: str
    nombre: str
    tipo: str
    saldo: Decimal
    tasa_anual: Decimal
    tasa_real_anual: Decimal | None
    minimo: Decimal


class PasoOut(BaseModel):
    id: str
    nombre: str
    mes: int
    fecha: date


class EstrategiaOut(BaseModel):
    estrategia: str
    meses: int | None
    fecha_fin: date | None
    intereses: Decimal
    orden: list[PasoOut]
    serie: list[Decimal]


class SimularOut(BaseModel):
    deudas: list[DeudaSimOut]
    presupuesto_mensual: Decimal
    avalancha: EstrategiaOut
    bola_de_nieve: EstrategiaOut


# ---------- Detectores y semana ----------
class HallazgoOut(BaseModel):
    clave: str
    tipo: str
    tono: str
    titulo: str
    detalle: str
    monto: Decimal | None
    accion: dict | None
    movimientos: list[str]


class DescartarIn(BaseModel):
    clave: str = Field(min_length=1, max_length=200)


class ValioIn(BaseModel):
    valio: bool | None


class ArrepentimientoOut(BaseModel):
    categoria: str
    respondidos: int
    no: int


class VencimientoOut(BaseModel):
    fecha: date
    que: str
    monto: Decimal


class TopCategoria(BaseModel):
    nombre: str
    icono: str
    color: str
    total: Decimal


class SemanaOut(BaseModel):
    desde: date
    hasta: date
    gastos: Decimal
    gastos_anterior: Decimal
    cantidad: int
    fijos: Decimal
    variables: Decimal
    variables_anterior: Decimal
    top: list[TopCategoria]
    mayor: dict | None
    pendientes: int
    vencimientos: list[VencimientoOut]
    hallazgos: list[HallazgoOut]
    repaso: list[MovimientoOut]
    arrepentimientos: list[ArrepentimientoOut]


# ---------- Garantías ----------
class GarantiaArchivo(BaseModel):
    id: uuid.UUID
    nombre: str
    mime: str
    rol: str


class GarantiaOut(BaseModel):
    id: uuid.UUID
    producto: str
    comercio: str
    serie: str
    fecha_compra: date
    meses: int
    vence: date
    estado: str
    dias_restantes: int
    progreso: float
    en_reparacion_desde: date | None
    dias_reparacion: int
    notas: str
    movimiento_id: uuid.UUID | None
    monto: Decimal | None
    medio_pago: str | None
    archivos: list[GarantiaArchivo]


class GarantiaIn(BaseModel):
    producto: str | None = Field(default=None, max_length=120)
    comercio: str = Field(default="", max_length=120)
    serie: str = Field(default="", max_length=80)
    fecha_compra: date | None = None
    meses: int | None = Field(default=None, ge=1, le=240)
    vence: date | None = None
    notas: str = Field(default="", max_length=400)
    movimiento_id: uuid.UUID | None = None
    archivo_id: uuid.UUID | None = None


class GarantiaPatch(BaseModel):
    producto: str | None = Field(default=None, min_length=1, max_length=120)
    comercio: str | None = Field(default=None, max_length=120)
    serie: str | None = Field(default=None, max_length=80)
    fecha_compra: date | None = None
    meses: int | None = Field(default=None, ge=1, le=240)
    vence: date | None = None
    notas: str | None = Field(default=None, max_length=400)
    archivo_id: uuid.UUID | None = None


class ReparacionIn(BaseModel):
    accion: Literal["enviar", "volvio"]
    fecha: date | None = None


# ---------- Plan ----------
class ItemMonto(BaseModel):
    nombre: str
    monto: Decimal


class PresupuestoOut(BaseModel):
    configurado: bool
    dia_cobro: int | None
    ingreso_esperado: Decimal | None
    cobro_detectado: bool
    ahorro: Decimal
    desde: date | None
    hasta: date | None
    proximo_cobro: date | None
    dias_restantes: int
    dias_total: int
    ingreso: Decimal
    fijos: Decimal
    cuotas_tarjetas: Decimal
    cuotas_prestamos: Decimal
    metas: Decimal
    para_gastar: Decimal
    gastado: Decimal
    gastado_hoy: Decimal
    restante: Decimal
    por_dia: Decimal
    hoy: Decimal
    manana: Decimal | None
    proyeccion_fin: Decimal | None
    estado: str
    detalle_fijos: list[ItemMonto]
    detalle_cuotas: list[ItemMonto]
    detalle_metas: list[ItemMonto]


class AjustesPlanIn(BaseModel):
    dia_cobro: int | None = Field(default=None, ge=1, le=31)
    ingreso_mensual: Decimal | None = Field(default=None, ge=0)
    ahorro_mensual: Decimal | None = Field(default=None, ge=0)


class EventoOut(BaseModel):
    fecha: date
    tipo: str
    titulo: str
    monto: Decimal
    estimado: bool


class PuntoOut(BaseModel):
    fecha: date
    saldo: Decimal


class CalendarioOut(BaseModel):
    saldo_hoy: Decimal
    gasto_diario: Decimal
    eventos: list[EventoOut]
    serie: list[PuntoOut]
    rojo: PuntoOut | None
    minimo: PuntoOut




# ---------- Metas ----------
class AporteOut(BaseModel):
    id: uuid.UUID
    fecha: date
    monto: Decimal
    nota: str


class MetaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    emoji: str
    objetivo: Decimal
    moneda: Moneda
    fecha_objetivo: date | None
    aporte_mensual: Decimal | None
    cuenta_id: uuid.UUID | None
    cuenta: str | None
    ahorrado: Decimal
    falta: Decimal
    progreso: float
    cumplida: bool
    por_mes: Decimal | None
    por_mes_ars: Decimal | None
    meses_restantes: int | None
    fecha_estimada: date | None
    ritmo: Decimal | None
    en_camino: bool | None
    aportes: list[AporteOut] = []


class MetaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    emoji: str = Field(default="🎯", max_length=16)
    objetivo: Decimal = Field(gt=0)
    moneda: Moneda = Moneda.ARS
    fecha_objetivo: date | None = None
    aporte_mensual: Decimal | None = Field(default=None, gt=0)
    cuenta_id: uuid.UUID | None = None
    ya_tengo: Decimal | None = Field(default=None, ge=0)  # lo que ya juntaste (primer aporte)


class MetaPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    emoji: str | None = Field(default=None, max_length=16)
    objetivo: Decimal | None = Field(default=None, gt=0)
    fecha_objetivo: date | None = None
    aporte_mensual: Decimal | None = None
    cuenta_id: uuid.UUID | None = None
    archivada: bool | None = None


class AporteIn(BaseModel):
    monto: Decimal  # negativo = sacaste
    fecha: date | None = None
    nota: str = Field(default="", max_length=120)


# ---------- Patrimonio ----------
class InversionOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    moneda: Moneda
    capital: Decimal
    tna: Decimal | None
    fecha_inicio: date
    vence: date | None
    valor_actual: Decimal | None
    actualizado: date | None
    cerrada: bool
    notas: str
    valor: Decimal
    ganancia: Decimal
    valor_ars: Decimal | None


class InversionIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: Literal["plazo_fijo", "fci", "cripto", "acciones", "bonos", "otro"] = "otro"
    moneda: Moneda = Moneda.ARS
    capital: Decimal = Field(gt=0)
    tna: Decimal | None = Field(default=None, ge=0, le=1000)
    fecha_inicio: date | None = None
    vence: date | None = None
    valor_actual: Decimal | None = Field(default=None, ge=0)
    notas: str = Field(default="", max_length=200)


class InversionPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    capital: Decimal | None = Field(default=None, gt=0)
    tna: Decimal | None = None
    vence: date | None = None
    valor_actual: Decimal | None = Field(default=None, ge=0)
    cerrada: bool | None = None
    notas: str | None = Field(default=None, max_length=200)


class CotizacionOut(BaseModel):
    valor: Decimal | None
    casa: str
    nombre: str
    fecha: datetime | None
    vieja: bool
    manual: bool
    casas: dict[str, str]


class CotizacionIn(BaseModel):
    casa: str | None = None
    manual: Decimal | None = Field(default=None, gt=0)
    borrar_manual: bool = False


class ItemPatrimonioOut(BaseModel):
    grupo: str
    nombre: str
    moneda: Moneda
    monto: Decimal
    ars: Decimal | None
    activo: bool
    ref: str


class PuntoPatrimonioOut(BaseModel):
    fecha: date
    neto: Decimal
    estimado: bool


class PatrimonioOut(BaseModel):
    items: list[ItemPatrimonioOut]
    activos: Decimal
    pasivos: Decimal
    neto: Decimal
    neto_usd: Decimal | None
    cotizacion: CotizacionOut
    sin_convertir: bool
    liquido: Decimal
    gasto_esencial: Decimal
    gasto_mensual: Decimal
    meses_esencial: Decimal | None
    meses_total: Decimal | None
    serie: list[PuntoPatrimonioOut]




# ---------- ¿Me lo puedo comprar? ----------
class CompraIn(BaseModel):
    texto: str | None = Field(default=None, max_length=300)
    monto: Decimal | None = Field(default=None, gt=0)
    cuotas: int | None = Field(default=None, ge=1, le=72)
    medio_pago_id: uuid.UUID | None = None
    descripcion: str | None = Field(default=None, max_length=120)
    precio_contado: Decimal | None = Field(default=None, gt=0)
    total_cuotas: Decimal | None = Field(default=None, gt=0)
    inflacion: Decimal = Field(default=Decimal("2"), ge=0, le=50)


class MesOut(BaseModel):
    desde: date
    para_gastar: Decimal | None
    cuotas: Decimal


class FotoOut(BaseModel):
    hoy: Decimal | None
    por_dia: Decimal | None
    manana: Decimal | None
    restante: Decimal | None
    meses: list[MesOut]
    rojo: PuntoOut | None
    minimo: PuntoOut
    liquido: Decimal
    meses_fondo: Decimal | None


class CuotasContadoOut(BaseModel):
    contado: Decimal
    total_cuotas: Decimal
    cuota: Decimal
    cuotas: int
    inflacion: Decimal
    valor_hoy_cuotas: Decimal
    diferencia: Decimal
    tasa_mensual: Decimal | None
    conviene: str


class SimulacionOut(BaseModel):
    descripcion: str
    monto: Decimal
    cuotas: int
    medio_pago_id: uuid.UUID | None
    medio: str | None
    con_tarjeta: bool
    antes: FotoOut
    despues: FotoOut
    veredicto: str
    motivos: list[str]
    primera_cuota: date | None
    mejor_dia: date | None
    primera_cuota_mejor_dia: date | None
    cuotas_contado: CuotasContadoOut | None


MovimientoOut.model_rebuild()


# ---------- Gastos fijos ----------
class FijoOut(BaseModel):
    id: uuid.UUID
    nombre: str
    clave: str
    monto: Decimal
    dia: int
    cada_meses: int
    mes_inicio: int | None
    por_mes: Decimal
    activo: bool
    categoria_id: uuid.UUID | None
    categoria: str | None
    categoria_icono: str | None
    categoria_color: str | None
    medio_pago_id: uuid.UUID | None
    medio_pago: str | None
    proxima: date
    # Este mes: pagado (confirmado) | en_bandeja (generado, sin confirmar) | por_venir
    este_mes: Literal["pagado", "en_bandeja", "por_venir"]
    movimiento_id: uuid.UUID | None


class FijoSugerido(BaseModel):
    clave: str
    nombre: str
    monto: Decimal
    dia: int
    meses: int
    categoria: str | None


class FijosOut(BaseModel):
    fijos: list[FijoOut]
    sugeridos: list[FijoSugerido]
    total_mensual: Decimal          # lo que hay que apartar por mes (los no mensuales, prorrateados)
    este_mes_total: Decimal         # lo que toca pagar este mes
    pagado_mes: Decimal


class FijoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    monto: Decimal = Field(gt=0)
    dia: int = Field(ge=1, le=31)
    cada_meses: Literal[1, 2, 3, 4, 6, 12] = 1
    mes_inicio: int | None = Field(default=None, ge=1, le=12)
    categoria_id: uuid.UUID | None = None
    medio_pago_id: uuid.UUID | None = None


class FijoPatch(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    monto: Decimal | None = Field(default=None, gt=0)
    dia: int | None = Field(default=None, ge=1, le=31)
    cada_meses: Literal[1, 2, 3, 4, 6, 12] | None = None
    mes_inicio: int | None = Field(default=None, ge=1, le=12)
    categoria_id: uuid.UUID | None = None
    medio_pago_id: uuid.UUID | None = None
    activo: bool | None = None


class FijoDecision(BaseModel):
    clave: str = Field(min_length=1, max_length=160)
    activo: bool = True  # False: «no es un fijo»
