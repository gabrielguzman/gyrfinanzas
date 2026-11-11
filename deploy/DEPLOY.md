# Poner gyrfinanzas en producción

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
