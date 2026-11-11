# gyrfinanzas

App de finanzas personales: cargar en segundos, ordenar después.

## Estructura

```
apps/api   FastAPI + PostgreSQL + SQLAlchemy 2.0 + Alembic
apps/web   Next.js (PWA)
docs/      Decisiones de producto y modelo de datos
```

## Levantar en local

**Lo fácil:** doble clic en `levantar.command` (Mac). Levanta Postgres, la API y la web, elige puertos libres y abre el navegador.

**A mano:**

```bash
# 1. Base de datos
docker compose up -d db

# 2. API
cd apps/api
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run python -m app.seed          # categorías por defecto
uv run uvicorn app.main:app --reload
# Docs interactivas en http://localhost:8000/docs

# Tests (usan SQLite en memoria, no necesitan Postgres)
uv run pytest

# 3. Web (en otra terminal)
cd apps/web
npm install
npm run dev
# http://localhost:3000
```

### Usarla desde el celu

1. Celu y compu en la misma red WiFi.
2. Corré `./levantar.command` (o doble clic en Finder): levanta todo y te muestra la dirección para el celu.
3. Abrila en el celu y Compartir → *Agregar a pantalla de inicio*.

La web reenvía `/api/*` a la API, así que el celu solo necesita llegar a la web.

La instalación completa como PWA (con modo sin conexión) funciona en producción (`npm run build && npm start`) o desplegada con HTTPS.

## Acceso y cuentas individuales

En producción se entra con email y contraseña. Podés registrarte desde la pantalla de acceso y verificar tu email para elegir
tu contraseña. El administrador también puede invitar personas desde **Tu cuenta**; cada persona tiene sus propias finanzas privadas.
El invitado recibe un enlace para elegir una contraseña de al menos 12 caracteres.
También se puede cambiar la contraseña desde la cuenta o recuperarla por email.
Ver [configuración y migración de producción](deploy/DEPLOY.md).

## Bot de Telegram

Cargá gastos escribiéndole a tu bot: `nafta 40k visa`, una foto del ticket, `/saldo`, `/bandeja`.

1. En Telegram, hablale a **@BotFather** → `/newbot` → elegí nombre → te da un token.
2. Corré `levantar.command`: la primera vez te pide el token (o ponelo en `apps/api/.env` → `TELEGRAM_TOKEN`).
3. La Terminal muestra un código: mandale a tu bot `/vincular CÓDIGO`. Solo los chats vinculados pueden usarlo.

Funciona con *long polling*: no hace falta URL pública, solo que la compu esté prendida.

## Resúmenes de tarjeta

En la tarjeta (Cuentas → tocá la tarjeta) subí el PDF del resumen como lo descargás del banco. La app lo lee, verifica que la suma dé el total y te muestra qué ya tenías cargado y qué falta.

- **Sin configurar nada** se lee con reglas: anda con los formatos típicos (fecha, detalle, monto, `C.03/12`).
- **Con IA** entiende cualquier banco y PDFs raros: poné tu clave en `apps/api/.env` → `ANTHROPIC_API_KEY=...`. El PDF se manda a la API de Anthropic para leerlo.

## Detectores y tu semana

La app revisa sola tus movimientos y avisa en Inicio («Para mirar») y en **Tu semana**: cargas duplicadas, fijos que subieron, comisiones e intereses, gastos hormiga y categorías que se dispararon. Cada aviso se puede descartar. Los lunes a las 9 el bot de Telegram manda el resumen de la semana con un repaso rápido.

## Hoja de ruta

- **v1 (ahora):** cuentas y medios de pago, carga por texto libre, bandeja, movimientos, comprobantes adjuntos, PWA.
- Después: bot de Telegram → tarjetas y resumen PDF → préstamos y deudas → detectores → garantías.

Regla: no se empieza una fase hasta haber usado la anterior una semana.
