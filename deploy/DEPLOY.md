# Poner gyrfinanzas en producción

## Instalación del 11 de noviembre de 2026

Servidor: `deploy@64.23.196.133`. Carpeta: `/home/deploy/apps/gyrfinanzas`.
Dirección inicial: https://finanzas.64.23.196.133.sslip.io.
Dominio definitivo: https://gyrfinanzas.com (también funciona `www`). El DNS
en Hostinger apunta a `64.23.196.133`; HTTPS se emite con Let's Encrypt.

Se construyen las imágenes desde el código local (`gyrfinanzas-api:20261111-register1` y
`gyrfinanzas-web:20261111-register1`). GitHub Actions conserva el flujo de publicación del repositorio; esta instalación manual usa imágenes locales fijadas en `.env`.
El archivo privado `deploy/.env` selecciona las imágenes y activa
`COMPOSE_FILE=docker-compose.yml:compose.proxy.yml`. El proxy Traefik existente
detecta las etiquetas de la web en la red `coolify`; no requiere reiniciarse.
En `.env`, `APP_DOMAIN` define el dominio (debe resolver a la IP del servidor).

Las contraseñas de las cuentas se guardan como hashes; la contraseña inicial
compartida quedó reemplazada por la cuenta del propietario. Los datos y
comprobantes usan volúmenes propios.
Los backups quedan en `deploy/backups`, con retención de 14 días.

### Cuentas individuales

La instalación usa `USUARIOS_HABILITADOS=true`. El propietario migra desde la
contraseña compartida mediante un comando de operador (nunca desde la web):

```sh
docker compose exec api python -m app.bootstrap_account tu@email.com
```

Se conserva su contraseña y sus datos en `public`. Las sesiones antiguas de la
contraseña compartida ya no sirven al activar este modo. Cada invitado tiene
sus finanzas en un esquema PostgreSQL propio `u_<uuid>`; las consultas y tareas
en segundo plano usan ese esquema explícitamente. Los comprobantes nuevos se
guardan en un subdirectorio del mismo usuario. El registro público está disponible en `/registro`: se verifica el email antes
de elegir la contraseña o crear el esquema de finanzas. No hay espacios
familiares compartidos en esta versión. El bot existente opera solo
sobre las finanzas del propietario; no ofrece vinculación para otros usuarios.

El registro público envía un enlace de verificación de un solo uso, válido por
24 horas. Tiene límites por IP, email y un límite global de envíos por hora.
El registro no permite reclamar una cuenta activa ni modificar su contraseña.
Desde **Tu cuenta**, el administrador también invita personas por email. El enlace
vence en 48 horas. Sin SMTP puede compartir un enlace privado manualmente;
tener ese enlace permite activar la cuenta invitada. Con SMTP se entrega por
correo. La recuperación vence en 30 minutos y requiere SMTP. Los enlaces son
de un solo uso; sus secretos se guardan como hashes. Cambiar o restablecer la
contraseña revoca todas las sesiones del usuario. La contraseña nueva tiene
un mínimo de 12 caracteres.

El envío se configura en `.env` con `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASSWORD`, `SMTP_FROM` y `APP_URL`. Gmail usa `smtp.gmail.com:465` y una
contraseña de aplicación. El archivo debe conservar permisos `600`. Nunca
copiar sus secretos a documentación o git. SMTP fue autenticado con TLS;
la entrega final de mensajes depende del proveedor y del destinatario.

`alembic upgrade head` migra primero `public` y después los esquemas de usuarios
activos. El backup completo de PostgreSQL incluye identidades y todos los
esquemas. Para volver al acceso anterior, restaurar la configuración privada
`.env.pre-usuarios` y recrear solo API/web con sus imágenes anteriores; no borrar
los esquemas ni los volúmenes. Esa reversión desactiva temporalmente las cuentas
de invitados. El respaldo previo está en `deploy/backups/`.

Pruebas de aislamiento (usar una base descartable cuyo nombre termine en
`_auth_test`, nunca la de producción):

```sh
cd apps/api
DATABASE_URL="$GYR_AUTH_TEST_URL" uv run alembic upgrade head
uv run pytest -q
```

Si `GYR_AUTH_TEST_URL` está definida, las pruebas borran y recrean los datos
de esa base de prueba. Sin ella, se omiten las pruebas PostgreSQL de cuentas.

Para operar esta instalación:

```sh
cd /home/deploy/apps/gyrfinanzas/deploy
docker compose ps
docker compose logs --tail=100 api web backup
docker compose exec backup sh /backup.sh ahora
```

## Flujo del repositorio con GitHub Actions

El deploy lo hace GitHub Actions: en cada push a `main` corre los tests, construye las imágenes
(`ghcr.io/gabrielguzman/gyrfinanzas-api` y `-web`) y, si están los secretos, entra al servidor y
actualiza **solo** `~/apps/gyrfinanzas`. Todo corre con su propio proyecto de Docker Compose
(`gyrfinanzas`), su propia red y sus volúmenes. Solo la web se suma a la red `coolify` con etiquetas
de Traefik, así el proxy de Coolify publica `DOMINIO` con HTTPS (igual que tus otros proyectos de Compose).

## Opción A: todo desde GitHub (sin tocar el servidor)

`deploy/servidor.sh` lo corre GitHub Actions por SSH: la primera vez clona el proyecto y crea
`deploy/.env` **en el servidor** (genera ahí la contraseña de la base y SECRET_KEY). Solo necesita:

- Secretos: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_KEY` y `APP_PASSWORD` (tu contraseña de login;
  en el servidor se guarda solo el hash). Opcional: `TELEGRAM_TOKEN`.
- Variable: `DOMINIO` (por ejemplo `finanzas.tudominio.com`).

Después, Actions → «Tests, imágenes y deploy» → Run workflow (o cualquier push a `main`).

## Opción B: a mano, en el servidor

```sh
# 1. Traer el proyecto
mkdir -p ~/apps && git clone https://github.com/gabrielguzman/gyrfinanzas ~/apps/gyrfinanzas
cd ~/apps/gyrfinanzas/deploy && cp .env.example .env

# 2. Completar .env
openssl rand -hex 24   # → POSTGRES_PASSWORD
openssl rand -hex 32   # → SECRET_KEY
docker run --rm ghcr.io/gabrielguzman/gyrfinanzas-api:latest python -m app.auth "tu contraseña"   # → APP_PASSWORD_HASH
nano .env

# 3. Arrancar
docker compose up -d && docker compose ps
```

Antes, creá el registro DNS **A** de `DOMINIO` apuntando a la IP del servidor. Traefik saca el
certificado solo la primera vez que alguien entra. Para probar desde el servidor sin dominio:
`curl -I http://127.0.0.1:3410/entrar`.

## Deploy automático (GitHub → servidor)

```sh
# En el servidor: una llave solo para el deploy
ssh-keygen -t ed25519 -N "" -f ~/.ssh/gyr_deploy -C gyr-deploy
cat ~/.ssh/gyr_deploy.pub >> ~/.ssh/authorized_keys
cat ~/.ssh/gyr_deploy      # copiá esto (privada) al secreto DEPLOY_KEY
```

En GitHub → Settings → Secrets and variables → Actions:
`DEPLOY_HOST` (IP), `DEPLOY_USER` (deploy), `DEPLOY_KEY` (la llave privada), y `DEPLOY_PORT` si no es 22.

Si el servidor no puede bajar las imágenes, en GitHub → tu perfil → Packages poné
`gyrfinanzas-api` y `gyrfinanzas-web` como públicas (el repo ya es público).

## Backups

Todos los días a las `BACKUP_HORA` quedan en `deploy/backups/`: `base-*.dump` y
`comprobantes-*.tar.gz` (se guardan `BACKUP_DIAS` días). Backup manual:

```sh
docker compose exec backup sh /backup.sh ahora
```

Restaurar (pisa la base actual):

```sh
docker compose stop api bot web
docker compose exec -T db pg_restore -U gyr -d gyrfinanzas --clean --if-exists < backups/base-AAAAMMDD-HHMM.dump
docker compose run --rm -v "$PWD/backups:/b" --entrypoint sh api -c "tar -xzf /b/comprobantes-AAAAMMDD-HHMM.tar.gz -C /data/uploads"
docker compose up -d
```

Conviene copiar `deploy/backups/` fuera del servidor de vez en cuando (por ejemplo con `rsync` a tu compu).

## Útiles

```sh
docker compose logs -f api        # ver qué pasa
docker compose restart api        # reiniciar solo la API
docker compose down               # apagar gyrfinanzas (no toca nada más del servidor)
```
