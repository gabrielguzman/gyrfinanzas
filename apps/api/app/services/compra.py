"""¿Me lo puedo comprar? Simula la compra sin guardarla y compara antes y después.

La compra se crea de verdad dentro de un savepoint (con su plan de cuotas si es con tarjeta),
se calcula todo con la misma lógica de la app y se deshace. Mientras dura, `commit` se
reemplaza por `flush` para que nada que se llame adentro pueda dejarla guardada.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Cuenta, EstadoMovimiento, MedioPago, Moneda, Movimiento, OrigenMovimiento, TipoCuenta, TipoMovimiento
from app.services import patrimonio as svc_pat
from app.services import plan as svc_plan
from app.services import tarjetas as svc_t

CERO = Decimal("0")


@contextmanager
def sin_guardar(db: Session):
    sp = db.begin_nested()
    commit_original = db.commit
    db.commit = db.flush  # type: ignore[method-assign]
    try:
        yield
    finally:
        db.commit = commit_original  # type: ignore[method-assign]
        sp.rollback()
        db.expire_all()


@dataclass
class Foto:
    """Cómo están tus números (antes o después de la compra)."""
    hoy: Decimal | None
    por_dia: Decimal | None
    manana: Decimal | None          # por día desde mañana (lo que cambia una compra de hoy)
    restante: Decimal | None
    meses: list[svc_plan.Mes]
    rojo: tuple[date, Decimal] | None
    minimo: tuple[date, Decimal]
    liquido: Decimal
    meses_fondo: Decimal | None


def _foto(db: Session, hoy: date) -> Foto:
    p = svc_plan.calcular(db, hoy)
    cal = svc_plan.calendario(db, hoy, 90)
    pat = svc_pat.calcular(db, hoy, None, guardar_foto=False)
    return Foto(
        p.hoy if p.configurado else None, p.por_dia if p.configurado else None,
        (p.manana if p.manana is not None else p.por_dia) if p.configurado else None,
        p.restante if p.configurado else None, svc_plan.meses(db, hoy, 6),
        cal.rojo, cal.minimo, pat.liquido, pat.meses_esencial,
    )


# ───────────────────────── cuotas o contado ─────────────────────────
@dataclass
class CuotasVsContado:
    contado: Decimal
    total_cuotas: Decimal
    cuota: Decimal
    cuotas: int
    inflacion: Decimal              # mensual, en %
    valor_hoy_cuotas: Decimal       # lo que valen las cuotas en pesos de hoy
    diferencia: Decimal             # contado − valor de hoy (positivo: conviene cuotas)
    tasa_mensual: Decimal | None    # interés implícito de las cuotas vs contado (% mensual)
    conviene: str                   # cuotas | contado | igual


def tasa_implicita(contado: Decimal, cuota: Decimal, n: int, desfase: int) -> Decimal | None:
    """Tasa mensual que iguala las cuotas con el precio de contado (bisección)."""
    if cuota * n <= contado:
        return Decimal("0")

    def vp(i: float) -> float:
        return sum(float(cuota) / (1 + i) ** (desfase + k) for k in range(n))

    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if vp(mid) > float(contado):
            lo = mid
        else:
            hi = mid
    return Decimal(str(round(mid * 100, 2)))


def cuotas_vs_contado(contado: Decimal, total: Decimal, n: int, inflacion: Decimal, desfase: int) -> CuotasVsContado:
    """`desfase`: meses hasta pagar la primera cuota (con tarjeta, suele ser 1 o 2)."""
    cuota = (total / n).quantize(Decimal("0.01"))
    i = float(inflacion) / 100
    vh = Decimal(str(sum(float(cuota) / (1 + i) ** (desfase + k) for k in range(n)))).quantize(Decimal("1"))
    dif = (contado - vh).quantize(Decimal("1"))
    margen = contado * Decimal("0.01")
    conviene = "cuotas" if dif > margen else "contado" if dif < -margen else "igual"
    return CuotasVsContado(contado, total, cuota, n, inflacion, vh, dif, tasa_implicita(contado, cuota, n, desfase), conviene)


# ───────────────────────── simulación ─────────────────────────
@dataclass
class Simulacion:
    descripcion: str
    monto: Decimal
    cuotas: int
    medio: str | None
    con_tarjeta: bool
    antes: Foto
    despues: Foto
    veredicto: str                  # si | cuidado | no
    motivos: list[str] = field(default_factory=list)
    primera_cuota: date | None = None
    mejor_dia: date | None = None
    primera_cuota_mejor_dia: date | None = None
    cuotas_contado: CuotasVsContado | None = None


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def _mes(d: date, hoy: date) -> str:
    return MESES[d.month - 1] + ("" if d.year == hoy.year or d.month > hoy.month else f" {d.year}")


def _pesos(v: Decimal) -> str:
    return "$ " + f"{abs(v):,.0f}".replace(",", ".")


def simular(db: Session, *, monto: Decimal, cuotas: int = 1, medio: MedioPago | None = None, descripcion: str = "Compra",
            hoy: date | None = None, precio_contado: Decimal | None = None, total_cuotas: Decimal | None = None,
            inflacion: Decimal = Decimal("2")) -> Simulacion:
    hoy = hoy or date.today()
    cuotas = max(1, cuotas)
    cuenta = db.get(Cuenta, medio.cuenta_id) if medio else None
    if cuenta is None:
        # Sin medio de pago: sale de tu cuenta en pesos con más plata
        from app.services.saldos import saldos_por_cuenta
        from sqlalchemy import select
        saldos = saldos_por_cuenta(db)
        liquidas = db.scalars(select(Cuenta).where(Cuenta.archivada.is_(False), Cuenta.moneda == Moneda.ARS,
                                                   Cuenta.tipo != TipoCuenta.tarjeta_credito)).all()
        cuenta = max(liquidas, key=lambda c: saldos.get(c.id, CERO), default=None)
    con_tarjeta = bool(cuenta and cuenta.tipo == TipoCuenta.tarjeta_credito)
    total = total_cuotas if (total_cuotas and cuotas > 1) else monto
    antes = _foto(db, hoy)

    with sin_guardar(db):
        mov = Movimiento(
            tipo=TipoMovimiento.gasto, estado=EstadoMovimiento.confirmado, origen=OrigenMovimiento.manual,
            fecha=hoy, monto=total, moneda=Moneda.ARS, descripcion=descripcion,
            cuotas=cuotas if cuotas > 1 else None, medio_pago_id=medio.id if medio else None,
            cuenta_id=cuenta.id if cuenta else None,
        )
        db.add(mov)
        db.flush()
        svc_t.plan_desde_movimiento(db, mov)
        db.flush()
        despues = _foto(db, hoy)

    s = Simulacion(descripcion, monto, cuotas, medio.nombre if medio else None, con_tarjeta, antes, despues, "si")

    # Con tarjeta: cuándo se paga y si conviene esperar al cierre
    if con_tarjeta and cuenta:
        p = svc_t.periodo_de_compra(cuenta, hoy)
        s.primera_cuota = svc_plan.vencimiento(cuenta, p)
        md = svc_t.mejor_dia_de_compra(cuenta, hoy)
        if md != hoy and (md - hoy).days <= 20:
            s.mejor_dia = md
            s.primera_cuota_mejor_dia = svc_plan.vencimiento(cuenta, svc_t.periodo_de_compra(cuenta, md))

    if cuotas > 1:
        desfase = max(1, round((s.primera_cuota - hoy).days / 30.4)) if s.primera_cuota else 1
        s.cuotas_contado = cuotas_vs_contado(precio_contado or monto, total, cuotas, inflacion, desfase)

    # Veredicto
    m, cuidado, no = s.motivos, False, False
    if despues.restante is not None and despues.restante < 0 <= (antes.restante or 0):
        no = True
        m.append(f"Este mes te pasarías por {_pesos(despues.restante)} de lo que tenés para gastar hasta el cobro.")
    elif despues.restante is not None and antes.restante is not None and antes.restante < 0 and despues.restante < antes.restante:
        no = True
        m.append(f"Este mes ya venías pasado: quedarías {_pesos(despues.restante)} abajo de lo que tenés para gastar hasta el cobro.")
    elif despues.manana is not None and antes.manana and antes.manana > 0 and despues.manana < antes.manana * Decimal("0.5"):
        cuidado = True
        m.append(f"Desde mañana y hasta el cobro te quedarían {_pesos(despues.manana)} por día en vez de {_pesos(antes.manana)}.")
    if despues.rojo and not antes.rojo:
        no = True
        m.append(f"El {despues.rojo[0]:%d/%m} tus cuentas quedarían en −{_pesos(despues.rojo[1])}.")
    rojos = [x for x, y in zip(despues.meses, antes.meses) if x.para_gastar is not None and x.para_gastar < 0 <= (y.para_gastar or 0)]
    if rojos:
        no = True
        m.append(f"En {' y '.join(_mes(x.desde, hoy) for x in rojos[:2])} las cuotas no te dejarían plata para el día a día.")
    else:
        bajas = [(x, y) for x, y in zip(despues.meses[1:], antes.meses[1:])
                 if x.para_gastar is not None and y.para_gastar and y.para_gastar > 0 and x.para_gastar < y.para_gastar * Decimal("0.7")]
        if bajas:
            cuidado = True
            x, y = bajas[0]
            m.append(f"Desde {_mes(x.desde, hoy)} tendrías {_pesos(x.para_gastar)} por mes para gastar en vez de {_pesos(y.para_gastar)}.")
    if not con_tarjeta and antes.meses_fondo is not None and despues.meses_fondo is not None \
            and despues.meses_fondo < 1 <= antes.meses_fondo:
        cuidado = True
        m.append("Te quedarías sin fondo de emergencia: lo que tenés a mano no alcanzaría ni para lo que debés en tarjetas."
                 if despues.meses_fondo <= 0 else
                 f"Tu fondo de emergencia bajaría a {str(despues.meses_fondo).replace('.', ',')} meses de gastos fijos.")
    s.veredicto = "no" if no else "cuidado" if cuidado else "si"
    if not m:
        if antes.restante is None:
            m.append("No sé cuándo cobrás ni cuánto: miro solo tus cuentas y el calendario.")
        else:
            m.append(f"Desde mañana te quedarían {_pesos(despues.manana or CERO)} por día hasta el cobro y los meses que vienen siguen en verde.")
    if cuotas == 1 and antes.por_dia and antes.por_dia > 0 and monto >= antes.por_dia * 2:
        dias = int(monto / antes.por_dia)
        m.append(f"Son {dias} días de lo que podés gastar por día.")
    return s
