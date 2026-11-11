"""Datos de ejemplo para ver la app "con vida". Solo corre sobre una base cuyo
nombre contenga "demo", para no tocar nunca tus datos reales.

    DATABASE_URL=postgresql+psycopg://gyr:gyr@localhost:5432/gyrfinanzas_demo uv run python -m app.demo
"""
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import (
    Categoria,
    Cuenta,
    Deuda,
    Indexacion,
    TipoDeuda,
    EstadoMovimiento,
    MedioPago,
    EstadoResumen,
    Moneda,
    Movimiento,
    PlanCuotas,
    ResumenTarjeta,
    OrigenMovimiento,
    TipoCuenta,
    TipoMedioPago,
    TipoMovimiento,
)

# (descripción, categoría, medio, mínimo, máximo, veces por mes)
GASTOS = [
    ("Café", "Comida afuera", "mp", 2200, 3500, 14),
    ("Súper", "Súper", "debito", 28000, 95000, 6),
    ("Verdulería", "Súper", "efectivo", 6000, 15000, 5),
    ("Nafta", "Auto", "visa", 35000, 52000, 4),
    ("Delivery", "Comida afuera", "visa", 14000, 26000, 4),
    ("Uber", "Transporte", "mp", 4500, 9800, 5),
    ("Farmacia", "Salud", "debito", 9000, 28000, 2),
    ("Kiosco", "Comida afuera", "efectivo", 1500, 4200, 6),
    ("Cine", "Salidas", "visa", 9000, 16000, 1),
]
FIJOS = [  # (descripción, categoría, medio, monto, día)
    ("Alquiler", "Casa", "transf", 420000, 5),
    ("Internet", "Casa", "visa", 28990, 10),
    ("Luz", "Casa", "debito", 31500, 12),
    ("Spotify", "Suscripciones", "visa", 4999, 15),
    ("Netflix", "Suscripciones", "visa", 11999, 18),
    ("Gimnasio", "Salud", "debito", 38000, 3),
]


def main() -> None:
    if "demo" not in settings.database_url:
        sys.exit("Por seguridad, app.demo solo corre sobre una base con «demo» en el nombre.")
    rnd = random.Random(42)
    with SessionLocal() as db:
        if db.scalar(select(Cuenta).limit(1)):
            print("La base demo ya tiene datos; no agrego nada.")
            return
        cats = {c.nombre: c for c in db.scalars(select(Categoria))}
        galicia = Cuenta(nombre="Galicia", tipo=TipoCuenta.banco, saldo_inicial=Decimal("1650000"))
        mp = Cuenta(nombre="Mercado Pago", tipo=TipoCuenta.billetera, saldo_inicial=Decimal("185000"))
        efectivo = Cuenta(nombre="Efectivo", tipo=TipoCuenta.efectivo, saldo_inicial=Decimal("160000"))
        visa = Cuenta(nombre="Visa Galicia", tipo=TipoCuenta.tarjeta_credito, dia_cierre=26, dia_vencimiento=5)
        usd = Cuenta(nombre="Dólares", tipo=TipoCuenta.banco, moneda=Moneda.USD, saldo_inicial=Decimal("850"))
        db.add_all([galicia, mp, efectivo, visa, usd])
        db.flush()
        medios = {
            "debito": MedioPago(nombre="Débito Galicia", tipo=TipoMedioPago.debito, cuenta_id=galicia.id, alias="debito,galicia"),
            "transf": MedioPago(nombre="Transferencia Galicia", tipo=TipoMedioPago.transferencia, cuenta_id=galicia.id, alias="transferencia,transf"),
            "mp": MedioPago(nombre="Mercado Pago", tipo=TipoMedioPago.qr, cuenta_id=mp.id, alias="mp,mercadopago,mercado pago"),
            "efectivo": MedioPago(nombre="Efectivo", tipo=TipoMedioPago.efectivo, cuenta_id=efectivo.id, alias="efectivo,cash"),
            "visa": MedioPago(nombre="Visa Galicia", tipo=TipoMedioPago.credito, cuenta_id=visa.id, alias="visa"),
        }
        db.add_all(medios.values())
        db.flush()

        hoy = date.today()
        inicio_ant = (hoy.replace(day=1) - timedelta(days=1)).replace(day=1)

        def gasto(desc, cat, medio, monto, fecha, estado=EstadoMovimiento.confirmado, texto=None):
            md = medios[medio] if medio else None
            m = Movimiento(
                tipo=TipoMovimiento.gasto, estado=estado, fecha=fecha, monto=Decimal(monto),
                descripcion=desc, categoria_id=cats[cat].id if cat else None,
                medio_pago_id=md.id if md else None, cuenta_id=md.cuenta_id if md else None,
                origen=OrigenMovimiento.texto if texto else OrigenMovimiento.manual, texto_original=texto,
            )
            db.add(m)
            return m

        for mes_inicio in (inicio_ant, hoy.replace(day=1)):
            ultimo = hoy if mes_inicio.month == hoy.month else hoy.replace(day=1) - timedelta(days=1)
            dias = (ultimo - mes_inicio).days + 1
            total_dias = 30
            for desc, cat, medio, lo, hi, veces in GASTOS:
                n = max(0, round(veces * dias / total_dias + rnd.uniform(-0.4, 0.4)))
                for _ in range(n):
                    f = mes_inicio + timedelta(days=rnd.randrange(dias))
                    gasto(desc, cat, medio, round(rnd.uniform(lo, hi), -2), f)
            for desc, cat, medio, monto, dia in FIJOS:
                if dia <= ultimo.day:
                    if desc == "Internet" and mes_inicio.month == hoy.month:
                        monto = 32990  # aumentó este mes
                    gasto(desc, cat, medio, monto, mes_inicio.replace(day=dia))
            if 1 <= ultimo.day:
                db.add(Movimiento(
                    tipo=TipoMovimiento.ingreso, estado=EstadoMovimiento.confirmado, fecha=mes_inicio,
                    monto=Decimal("1450000"), descripcion="Sueldo", categoria_id=cats["Sueldo"].id,
                    medio_pago_id=medios["debito"].id, cuenta_id=galicia.id,
                ))

        # Pago del resumen anterior (transferencia banco → tarjeta)
        db.add(Movimiento(
            tipo=TipoMovimiento.transferencia, estado=EstadoMovimiento.confirmado,
            fecha=inicio_ant.replace(day=5), monto=Decimal("310000"), descripcion="Pago resumen Visa Galicia",
            cuenta_id=galicia.id, cuenta_destino_id=visa.id,
        ))
        # Planes de cuotas y el último resumen de la Visa
        from app.services.tarjetas import proximo_periodo, sumar_meses
        prox = proximo_periodo(visa, hoy)
        for desc, cuota, total, actual in [("Heladera", 38900, 12, 7), ("Pasajes", 52000, 12, 11),
                                           ("Zapatillas", 14500, 6, 2), ("Notebook", 47400, 9, 5)]:
            db.add(PlanCuotas(cuenta_id=visa.id, descripcion=desc, monto_cuota=Decimal(cuota), cuotas_total=total,
                              primer_periodo=sumar_meses(prox, -(actual - 1))))
        ant = sumar_meses(prox, -1)
        a, m = map(int, ant.split("-"))
        db.add(ResumenTarjeta(
            cuenta_id=visa.id, periodo=ant, estado=EstadoResumen.confirmado, metodo="reglas",
            fecha_cierre=date(a, m, 26), fecha_vencimiento=date(a + (m == 12), m % 12 + 1, 5),
            saldo_anterior=Decimal("310000"), total_ars=Decimal("498400"), pago_minimo=Decimal("74760"),
            tna=Decimal("78.5"),
        ))
        # Deudas
        db.add_all([
            Deuda(tipo=TipoDeuda.prestamo, nombre="Préstamo personal", monto_inicial=Decimal("420000"), fecha_alta=hoy,
                  tna=Decimal("45"), cuota=Decimal("35000"), cuotas_total=24, cuotas_pagadas=10, dia_vencimiento=10,
                  cuenta_id=galicia.id),
            Deuda(tipo=TipoDeuda.prestamo, nombre="Préstamo UVA", monto_inicial=Decimal("1250000"), fecha_alta=hoy,
                  tna=Decimal("9"), indexacion=Indexacion.uva, cuota=Decimal("58000"), cuotas_total=36, cuotas_pagadas=5,
                  dia_vencimiento=15, cuenta_id=galicia.id),
            Deuda(tipo=TipoDeuda.debo, nombre="Caro", monto_inicial=Decimal("60000"), fecha_alta=hoy),
            Deuda(tipo=TipoDeuda.me_deben, nombre="Juan", monto_inicial=Decimal("20000"), fecha_alta=hoy - timedelta(days=22)),
        ])
        # Cosas para que los detectores encuentren
        gasto("Uber", "Transporte", "mp", 6200, hoy)
        gasto("Uber", "Transporte", "mp", 6200, hoy)
        gasto("Mantenimiento de cuenta", "Comisiones e intereses", "debito", 4500, hoy - timedelta(days=4))
        gasto("Seguro de vida", "Comisiones e intereses", "visa", 3120, hoy - timedelta(days=6))
        # Garantías: una por vencer, una en el service, una vencida, una sin gasto y una compra sin garantía
        from app.services import garantias as svc_g
        heladera = gasto("Heladera Samsung", "Hogar", "visa", 849999, hoy - timedelta(days=343))
        notebook = gasto("Notebook Lenovo", "Otros gastos", "visa", 1190000, hoy - timedelta(days=130))
        tele = gasto("Smart TV 50", "Hogar", "debito", 620000, hoy - timedelta(days=200))
        auris = gasto("Auriculares JBL", "Otros gastos", "mp", 58000, hoy - timedelta(days=250))
        gasto("Microondas", "Hogar", "debito", 189000, hoy - timedelta(days=3))
        db.flush()
        svc_g.nueva(db, producto="Heladera Samsung", fecha_compra=heladera.fecha, meses=12, comercio="Frávega",
                    serie="RT38K5932SL", movimiento=heladera)
        svc_g.nueva(db, producto="Notebook Lenovo", fecha_compra=notebook.fecha, meses=24, comercio="Musimundo",
                    movimiento=notebook)
        tv = svc_g.nueva(db, producto="Smart TV 50", fecha_compra=tele.fecha, meses=12, comercio="Garbarino", movimiento=tele)
        tv.en_reparacion_desde = hoy - timedelta(days=6)
        tv.notas = "Se apaga sola. Service oficial, orden 44821."
        svc_g.nueva(db, producto="Auriculares JBL", fecha_compra=auris.fecha, meses=6, movimiento=auris)
        svc_g.nueva(db, producto="Aire acondicionado", fecha_compra=date(2025, 12, 15), meses=36, comercio="Megatone")
        db.flush()
        # Metas e inversiones
        from app.models import AporteMeta, Inversion, Meta, TipoInversion
        vac = Meta(nombre="Vacaciones en Brasil", emoji="🏖️", objetivo=Decimal("1800000"),
                   fecha_objetivo=date(hoy.year + (1 if hoy.month > 1 else 0), 2, 15))
        fondo = Meta(nombre="Fondo de emergencia", emoji="🛟", objetivo=Decimal("2000"), moneda=Moneda.USD,
                     aporte_mensual=Decimal("150"))
        db.add_all([vac, fondo])
        db.flush()
        vac.creado = fondo.creado = datetime.now(timezone.utc) - timedelta(days=95)
        for k, (dias, monto) in enumerate([(90, 250000), (60, 200000), (30, 150000), (3, 100000)]):
            db.add(AporteMeta(meta_id=vac.id, fecha=hoy - timedelta(days=dias), monto=Decimal(monto)))
        for dias in (88, 58, 28):
            db.add(AporteMeta(meta_id=fondo.id, fecha=hoy - timedelta(days=dias), monto=Decimal("150")))
        db.add_all([
            Inversion(nombre="Plazo fijo Galicia", tipo=TipoInversion.plazo_fijo, capital=Decimal("1500000"),
                      tna=Decimal("32"), fecha_inicio=hoy - timedelta(days=28), vence=hoy + timedelta(days=2)),
            Inversion(nombre="FCI Mercado Pago", tipo=TipoInversion.fci, capital=Decimal("600000"),
                      valor_actual=Decimal("684300"), fecha_inicio=hoy - timedelta(days=150),
                      actualizado=hoy - timedelta(days=6)),
            Inversion(nombre="Bitcoin", tipo=TipoInversion.cripto, moneda=Moneda.USD, capital=Decimal("400"),
                      valor_actual=Decimal("455"), fecha_inicio=hoy - timedelta(days=200), actualizado=hoy - timedelta(days=41)),
        ])
        # Fotos de patrimonio de meses anteriores (en la app real se van guardando solas)
        from app.models import FotoPatrimonio
        for k, neto in enumerate([980000, 1150000, 1090000, 1420000, 1610000], start=1):
            a, m = hoy.year, hoy.month - (6 - k)
            while m < 1:
                a, m = a - 1, m + 12
            db.add(FotoPatrimonio(fecha=date(a, m, 1) - timedelta(days=1), neto_ars=Decimal(neto)))
        # Respuestas del repaso de semanas anteriores
        anteriores = db.scalars(select(Movimiento).where(Movimiento.fecha < hoy - timedelta(days=15),
                                                         Movimiento.descripcion.in_(["Delivery", "Kiosco", "Café"]))).all()
        for i, m in enumerate(anteriores[:14]):
            m.valio = (m.descripcion == "Café") or i % 4 == 0
        # Bandeja: cosas por confirmar
        gasto("Regalo cumple", "Regalos", None, 25000, hoy, EstadoMovimiento.pendiente, "regalo cumple 25k")
        gasto("Ferretería", "Casa", "efectivo", 8700, hoy, EstadoMovimiento.pendiente, "ferretería 8700 efectivo")
        db.commit()
        print("Datos de demo cargados.")


if __name__ == "__main__":
    main()
