# Decisiones

- **Captura primero.** Todo entra crudo a una bandeja (movimientos con `estado = pendiente`) y se confirma con un toque.
- **Saldos calculados al vuelo**, nunca guardados: `saldo_inicial + entradas − salidas` sobre movimientos confirmados.
- **La tarjeta de crédito es una cuenta** (`tipo = tarjeta_credito`). Comprar con crédito aumenta su deuda (saldo negativo) y no toca el banco. Pagar el resumen es una **transferencia** banco → tarjeta.
- **Medio de pago → cuenta.** Cada movimiento guarda el medio con el que se pagó; la cuenta afectada sale del medio.
- **Comprobantes muchos-a-muchos** (`movimiento_adjunto`, con `rol`): un ticket puede respaldar un gasto y un resumen PDF muchos consumos. Los archivos se deduplican por SHA-256.
- **Montos en `Numeric(14,2)`**, nunca float.
- **PWA primero**; Capacitor si algún día hace falta nativo.
- **Bot de Telegram con long polling** (sin URL pública ni webhooks). Solo responde a chats privados vinculados con un código que se genera en cada arranque; 5 intentos fallidos bloquean ese chat hasta reiniciar.
- **La lógica de carga vive en `services/registro.py`** y la comparten la API y el bot: lo que escribís en uno se interpreta igual en el otro.
- **Fotos en el bot:** con texto → gasto nuevo con comprobante; sin texto y con un gasto cargado hace menos de 15 min → se adjunta a ese (con botón "No, es de otro"); si no, pregunta de qué gasto es.
- **Compras en cuotas = un movimiento por el total + un plan.** La deuda de la tarjeta sube por el total el día de la compra (es lo que debés); el plan dice cuánto cae en cada resumen. Al confirmar «heladera 466k 12 cuotas visa» el plan se crea solo.
- **Periodo de un resumen = mes en que cierra.** Una compra entra en el resumen del mes si es hasta el día de cierre; si no, en el siguiente. Sin día de cierre se usa el 25.
- **El resumen PDF se lee con IA si hay `ANTHROPIC_API_KEY`, y con reglas si no.** Siempre se revisa: la verificación compara saldo anterior + cargos − pagos contra el total del PDF, y la conciliación propone vincular (ya cargado), crear o ignorar (pagos) cada línea.
- **Cuotas 2/N o más de una compra que no está en la app → solo se crea el plan** (se asume que su deuda ya estaba en el saldo inicial de la tarjeta). La cuota 1/N sin compra cargada crea el movimiento por el total y su plan.
- **Un resumen por tarjeta y por mes.** El PDF queda adjunto (rol «resumen») a cada movimiento que respalda.
- **Deudas: tres tipos** (préstamo con cuotas, le debo a alguien, me deben). El saldo no se guarda: es lo que se debía al cargarla ± los movimientos vinculados (`movimiento.deuda_id`). En préstamos cada pago cubre primero el interés del mes (sistema francés).
- **Prestar o pedir prestado no es gastar ni ganar:** esos movimientos no cuentan en el resumen del mes. Pagar cuotas o devolver sí (categoría «Deudas y préstamos»).
- **Carga por texto de préstamos entre personas:** «le presté 20 lucas a juan», «caro me prestó 60k», «le devolví 10k a caro», «juan me devolvió 5 lucas». Se agrupa por persona (sin importar tildes).
- **Simulador avalancha vs bola de nieve:** presupuesto = cuotas + extra; lo que se libera al terminar una deuda pasa a la siguiente. Con inflación esperada, avalancha ordena por tasa real (un UVA ya es tasa real). Las tarjetas entran solo si el usuario dice que las financia.
- **Detectores sobre los últimos 30 días** (gastos confirmados en pesos, sin préstamos entre personas): duplicados (mismo concepto y monto en ≤1 día), aumentos de fijos (>5%), comisiones/intereses/impuestos, gastos hormiga (≥6 gastos chicos —menos del 1,5% del mes— que suman ≥3%), desvíos por categoría (>40% sobre el promedio de 3 meses a la misma altura) y total de fijos. Un fijo = mismo concepto, ~1 vez por mes (≥20 días entre pagos), montos parecidos.
- **Descartar un aviso guarda su clave**, que incluye el dato que lo disparó: si cambia (otro aumento, otro duplicado), vuelve a aparecer.
- **Tu semana compara sin fijos:** el alquiler no dice nada de cómo gastaste la semana.
- **Repaso «¿valió la pena?»:** 5 gastos de la semana, elegidos al azar pero fijos durante la semana, sin fijos ni salud ni deudas. Con 4+ respuestas por categoría se muestra dónde te arrepentís más.
- **Resumen semanal por Telegram** los lunes desde las 9 (una vez por chat), más `/semana` a pedido; incluye 3 gastos para el repaso con botones 👍/👎.

## Garantías (fase 7)
- Una garantía es de una compra (`movimiento_id`) o suelta, con comprobante propio (`archivo_id`), para lo comprado antes de usar la app.
- `vence` se guarda: se puede corregir a mano. Los días en el service se suman al volver (Ley 24.240, art. 16); mientras está en reparación no corre.
- Carga por texto: «garantía 1 año», «con garantía de 6 meses», «garantía» sola = 12 meses. El número del plazo nunca se toma como monto.
- Borrar la compra borra su garantía (error o «deshacer»), salvo que tenga comprobante propio.
- Avisos: «vence en N días» desde 30 días antes (Inicio, Tu semana, Telegram) y «¿tiene garantía?» para compras de $100.000 o más en Hogar/Otros o en 3+ cuotas.
- Los modales se montan en `<body>` con un portal: dentro de una página animada, `fixed` quedaba relativo a la página.

## Hoy podés gastar y calendario (fase 8)
- Ciclo = de cobro a cobro. Día y monto del cobro: los que configures o, si no, el último sueldo cargado (o el ingreso más grande de ~3 meses).
- Para gastar = ingreso (el esperado o lo cobrado, lo que sea mayor) − fijos detectados − cuotas de los resúmenes que vencen en el ciclo − cuotas de préstamos − ahorro.
- Gasto variable: gastos en pesos, también los de la bandeja; sin fijos, sin compras en cuotas (cuentan por cuota) y sin pagos de deudas.
- Hoy = (lo que queda + lo gastado hoy) / días que faltan − lo gastado hoy: el número solo se mueve en el día por lo que gastás.
- Calendario: saldo de cuentas en pesos (sin tarjetas), proyectado 60 días con cobros, resúmenes (el total del PDF si está, si no lo cargado más las cuotas), cuotas de préstamos y fijos, y el gasto diario que propone el plan. Avisa el primer día en negativo.

## Metas y patrimonio (fase 9)
- Meta: objetivo en pesos o dólares; con fecha (pide falta/meses por mes) o sin fecha con aporte mensual (estima cuándo llegás). Lo ahorrado sale del saldo de una cuenta elegida o de aportes anotados (web o Telegram: «aparté 50k para vacaciones», que se reconoce solo si el texto empieza con el nombre de la meta).
- Lo que piden las metas por mes se descuenta de «Hoy podés gastar»; «ahorro extra» queda como ajuste aparte. Avisos: meta atrasada (lo que pusiste en los últimos 3 meses < 80% de lo necesario) y meta cumplida.
- Patrimonio neto = cuentas (USD a la cotización elegida) + inversiones + lo que te deben − tarjetas − préstamos − lo que debés. Las metas con aportes anotados no suman aparte: es la misma plata.
- Cotización: DolarAPI (MEP por defecto), cache 3 h, reintento cada 15 min si falla, última conocida o una manual.
- Inversiones: valor manual (FCI, cripto, acciones) o capital + interés simple por TNA hasta hoy o el vencimiento (plazo fijo). Aviso 3 días antes del vencimiento y si el valor tiene más de 30 días.
- Evolución: una foto diaria al mirar el patrimonio; antes de la primera foto, estimación con saldos a fin de mes, solo desde que existen las cuentas en la app.
- Fondo de emergencia = (cuentas + inversiones líquidas − tarjetas) / (fijos + cuotas).

## ¿Me lo puedo comprar? (fase 10)
- La compra se simula creándola de verdad dentro de un savepoint (con su plan de cuotas si es con tarjeta) y deshaciéndola; mientras dura, `commit` es `flush`. Así usa exactamente la misma lógica que la app.
- Compara antes y después: hoy podés gastar, por día hasta el cobro, los próximos 6 ciclos (cobro − fijos − cuotas − metas − ahorro), lo más bajo del calendario a 90 días y el fondo de emergencia.
- Veredicto: «mejor no» si te pasás del mes, si el calendario queda en rojo o si algún mes las cuotas no dejan plata; «con cuidado» si el día a día baja a menos de la mitad, algún mes baja más de 30% o el fondo de emergencia baja de 1 mes.
- Cuotas o contado: valor actual de las cuotas descontado por la inflación mensual (2% por defecto, editable), desde el mes en que se paga la primera; si hay recargo, tasa implícita mensual.
- Con tarjeta: cuándo se paga la primera cuota y, si el próximo cierre está a 20 días o menos, cuánto se corre si esperás al día siguiente del cierre.
- Fondo de emergencia: de las tarjetas solo se resta lo que no son cuotas de resúmenes futuros.
- Un gasto cargado a mano en cuotas con tarjeta ahora también crea su plan de cuotas.
