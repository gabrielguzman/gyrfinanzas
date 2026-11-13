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
    "Kiosco": ("kiosco,kiosko,golosina,golosinas,alfajor,chicle,cigarrillos,puchos,gaseosa,coca", "kiosco", "amber"),
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


# Clásicas que no vienen por defecto: se agregan con un toque desde la pantalla de categorías.
CATALOGO_GASTOS = {
    "Delivery": ("delivery,pedidosya,rappi,pedido", "delivery", "orange"),
    "Café": ("cafe,cafecito,starbucks,havanna,medialunas", "cafe", "amber"),
    "Farmacia": ("farmacia,farmacity,remedios,ibuprofeno,perfumeria", "farmacia", "pink"),
    "Mascotas": ("veterinaria,veterinario,alimento perro,alimento gato,balanceado,mascota,petshop", "mascotas", "teal"),
    "Cuidado personal": ("peluqueria,barberia,corte de pelo,manicura,depilacion,cosmetica", "cuidado", "purple"),
    "Deportes": ("gimnasio,gym,futbol,padel,cancha,pileta,club,crossfit", "deporte", "green"),
    "Celular e internet": ("celular,personal,claro,movistar,recarga,fibertel,telecentro,internet", "celular", "blue"),
    "Servicios": ("luz,gas,agua,edenor,edesur,metrogas,aysa,ecogas", "servicios", "amber"),
    "Impuestos": ("abl,patente,monotributo,afip,arca,ganancias,bienes personales,rentas,municipal", "impuestos", "slate"),
    "Viajes": ("pasaje,vuelo,hotel,hostel,airbnb,aerolineas,flybondi,micro,excursion", "viajes", "indigo"),
    "Hijos": ("colegio,jardin,pañales,guarderia,juguete,niñera", "hijos", "pink"),
    "Tecnología": ("celular nuevo,notebook,auriculares,cargador,mouse,teclado,monitor", "tecnologia", "indigo"),
    "Juegos": ("steam,playstation,xbox,nintendo,juego", "juegos", "purple"),
    "Bebidas": ("vino,cerveza,fernet,birra,bebida,whisky", "bebidas", "red"),
    "Mantenimiento": ("plomero,electricista,gasista,arreglo,reparacion,pintura,cerrajero", "mantenimiento", "teal"),
    "Donaciones": ("donacion,donación,unicef,caritas", "donacion", "green"),
}
CATALOGO_INGRESOS = {
    "Inversiones": ("intereses,rendimiento,plazo fijo,dividendos,fci,cupon", "inversion", "green"),
    "Alquileres": ("alquiler cobrado,inquilino", "alquiler", "blue"),
    "Reintegros": ("reintegro,reembolso,devolucion,cashback", "reintegro", "teal"),
    "Regalos recibidos": ("me regalaron,regalo recibido", "regalo", "pink"),
    "Premios": ("premio,gane,sorteo,quiniela", "premio", "amber"),
}


def sembrar(db) -> None:
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
    db.flush()
    print(f"Categorías nuevas: {nuevas} · actualizadas: {completadas}")


def main() -> None:
    with SessionLocal() as db:
        sembrar(db)
        db.commit()


if __name__ == "__main__":
    main()
