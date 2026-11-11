#!/bin/sh
# Lo corre GitHub Actions en el servidor (ver .github/workflows/deploy.yml). Solo toca ~/apps/gyrfinanzas.
# La primera vez clona el proyecto y crea deploy/.env con secretos generados acá mismo.
set -eu
DIR="$HOME/apps/gyrfinanzas"
API_IMAGE="ghcr.io/gabrielguzman/gyrfinanzas-api:latest"

if [ ! -d "$DIR/.git" ]; then
  echo "▸ Primera vez: clono el proyecto en $DIR"
  mkdir -p "$HOME/apps"
  git clone --quiet https://github.com/gabrielguzman/gyrfinanzas "$DIR"
fi
cd "$DIR"
git fetch --quiet origin main
git reset --quiet --hard origin/main
cd deploy

if [ ! -f .env ]; then
  echo "▸ Primera vez: creo deploy/.env"
  : "${DOMINIO:?Falta la variable DOMINIO en GitHub (Settings → Secrets and variables → Actions → Variables)}"
  if [ -n "${APP_PASSWORD_HASH:-}" ]; then
    HASH="$APP_PASSWORD_HASH"
  elif [ -n "${APP_PASSWORD:-}" ]; then
    docker pull --quiet "$API_IMAGE" >/dev/null
    HASH=$(docker run --rm -e GYR_PASSWORD="$APP_PASSWORD" "$API_IMAGE" python -m app.auth)
  else
    echo "Falta el secreto APP_PASSWORD (o APP_PASSWORD_HASH) en GitHub" >&2; exit 1
  fi
  umask 077
  sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" \
      -e "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" \
      -e "s|^APP_PASSWORD_HASH=.*|APP_PASSWORD_HASH=$HASH|" \
      -e "s|^DOMINIO=.*|DOMINIO=$DOMINIO|" \
      .env.example > .env
  if [ -n "${TELEGRAM_TOKEN:-}" ]; then
    sed -i -e "s|^TELEGRAM_TOKEN=.*|TELEGRAM_TOKEN=$TELEGRAM_TOKEN|" -e "s|^# COMPOSE_PROFILES=bot|COMPOSE_PROFILES=bot|" .env
  fi
fi

# Si cambiaste el dominio en GitHub, se actualiza
if [ -n "${DOMINIO:-}" ] && ! grep -q "^DOMINIO=$DOMINIO\$" .env; then
  sed -i "s|^DOMINIO=.*|DOMINIO=$DOMINIO|" .env
fi

echo "▸ Bajando imágenes y actualizando"
docker compose pull --quiet
docker compose up -d --remove-orphans

echo "▸ Esperando que la API esté sana"
i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' gyrfinanzas-api-1 2>/dev/null)" = "healthy" ]; do
  i=$((i+1)); [ $i -gt 30 ] && { docker compose logs --tail 40 api; echo "La API no arrancó" >&2; exit 1; }
  sleep 4
done
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
PUERTO=$(grep -E '^WEB_PORT=' .env | cut -d= -f2); PUERTO=${PUERTO:-3410}
echo "▸ Web local:   $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PUERTO/entrar")"
DOM=$(grep -E '^DOMINIO=' .env | cut -d= -f2)
echo "▸ Por dominio: $(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOM/api/salud" || echo 'todavía no (DNS o certificado)')"
