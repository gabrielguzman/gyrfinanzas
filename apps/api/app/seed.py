"""Carga categorías por defecto y completa ícono/color de las existentes.
Se puede correr varias veces: no duplica ni pisa lo que cambiaste.

    uv run python -m app.seed
"""
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Categoria, TipoCategoria

# nombre: (palabras clave, ícono, color)
GASTOS = {
    "Súper": ("super,supermercado,chino,almacen,verduleria,carniceria,vea,carrefour,coto", "carrito", "green"),
    "Comida afuera": ("cafe,resto,restaurante,delivery,pedidosya,rappi,bar,helado,birra,cena,almuerzo", "comida", "orange"),
    "Auto": ("nafta,ypf,shell,axion,peaje,estacionamiento,mecanico,gomeria,seguro auto,patente", "auto", "red"),
    "Transporte": ("uber,cabify,didi,taxi,remis,colectivo,sube,bondi", "transporte", "amber"),
    "Casa": ("alquiler,expensas,luz,gas,agua,internet,ferreteria", "casa", "blue"),
    "Salud": ("farmacia,medico,dentista,prepaga,obra social,remedios", "salud", "pink"),
    "Suscripciones": ("netflix,spotify,disney,max,youtube,icloud,chatgpt,claude,suscripcion", "suscripcion", "purple"),
    "Ropa": ("ropa,zapatillas,remera,campera,pantalon", "ropa", "indigo"),
    "Hogar": ("heladera,lavarropas,mueble,colchon,electro", "hogar", "teal"),
    "Salidas": ("cine,recital,entrada,boliche,salida", "salidas", "pink"),
    "Regalos": ("regalo,cumple", "regalo", "red"),
    "Educación": ("curso,libro,facultad,cuota colegio", "educacion", "indigo"),
    "Comisiones e intereses": ("comision,mantenimiento,interes,intereses,punitorio,iva,percepcion", "comision", "slate"),
    "Deudas y préstamos": ("cuota prestamo,prestamo personal", "deuda", "amber"),
    "Otros gastos": ("", "otros", "slate"),
}
INGRESOS = {
    "Sueldo": ("sueldo,aguinaldo,salario", "sueldo", "green"),
    "Trabajos": ("cliente,factura,freelance,trabajo,proyecto", "trabajo", "teal"),
    "Ventas": ("vendi,venta", "venta", "amber"),
    "Otros ingresos": ("reintegro,devolucion,regalo", "ingreso", "blue"),
}


def main() -> None:
    with SessionLocal() as db:
        existentes = {(c.nombre, c.tipo): c for c in db.scalars(select(Categoria))}
        nuevas = completadas = 0
        for tipo, catalogo in ((TipoCategoria.gasto, GASTOS), (TipoCategoria.ingreso, INGRESOS)):
            for nombre, (palabras, icono, color) in catalogo.items():
                cat = existentes.get((nombre, tipo))
                if cat is None:
                    db.add(Categoria(nombre=nombre, tipo=tipo, palabras=palabras, icono=icono, color=color))
                    nuevas += 1
                elif not cat.icono or not cat.color:
                    cat.icono = cat.icono or icono
                    cat.color = cat.color or color
                    completadas += 1
        db.commit()
        print(f"Categorías nuevas: {nuevas} · actualizadas: {completadas}")


if __name__ == "__main__":
    main()
