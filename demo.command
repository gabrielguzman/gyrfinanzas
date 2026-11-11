#!/bin/zsh
# Abre gyrfinanzas con DATOS DE EJEMPLO, en una base aparte (gyrfinanzas_demo).
# Tus datos reales no se tocan. Corre al lado de la app real, en otros puertos.
# Ctrl+C o cerrar la ventana para apagarla.

cd "$(dirname "$0")"
RAIZ="$(pwd)"
mkdir -p .logs
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.homebrew/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

ok()  { print -P "  %F{green}✓ $1%f"; }
mal() { print -P "  %F{red}✗ $1%f"; echo "Apretá Enter para cerrar."; read; exit 1; }

print -P "%F{blue}▸ gyrfinanzas DEMO (datos de ejemplo)%f"
docker info >/dev/null 2>&1 || { open -a OrbStack 2>/dev/null || open -a Docker; for i in {1..60}; do docker info >/dev/null 2>&1 && break; sleep 2; done; }
docker compose up -d db >/dev/null 2>&1 || mal "No pude levantar Postgres."
for i in {1..30}; do docker compose exec -T db pg_isready -U gyr >/dev/null 2>&1 && break; sleep 1; done
docker compose exec -T db psql -U gyr -d gyrfinanzas -tAc "SELECT 1 FROM pg_database WHERE datname='gyrfinanzas_demo'" | grep -q 1 \
  || docker compose exec -T db createdb -U gyr gyrfinanzas_demo || mal "No pude crear la base demo."
ok "Base demo lista"

libre() { local p=$1; while lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; do p=$((p+1)); done; echo $p; }
API_PORT=$(libre 8100); WEB_PORT=$(libre 3100)

cd "$RAIZ/apps/api"
export DATABASE_URL="postgresql+psycopg://gyr:gyr@localhost:5432/gyrfinanzas_demo"
export UPLOAD_DIR="./uploads-demo" TELEGRAM_TOKEN=""
uv sync --quiet || mal "Falló uv sync."
uv run alembic upgrade head >/dev/null 2>&1 || mal "Fallaron las migraciones."
uv run python -m app.seed >/dev/null && uv run python -m app.demo
uv run uvicorn app.main:app --host 0.0.0.0 --port $API_PORT --reload > "$RAIZ/.logs/demo-api.log" 2>&1 &
API_PID=$!
for i in {1..30}; do curl -sf localhost:$API_PORT/salud >/dev/null && break; sleep 1; done
ok "API demo en :$API_PORT"

cd "$RAIZ/apps/web"
{ [ -d node_modules ] && [ ! package.json -nt node_modules/.package-lock.json ]; } || npm install --no-audit --no-fund --loglevel=error
NEXT_DIST_DIR=.next-demo API_PORT=$API_PORT npm run dev -- -H 0.0.0.0 -p $WEB_PORT > "$RAIZ/.logs/demo-web.log" 2>&1 &
WEB_PID=$!
for i in {1..60}; do curl -sf -o /dev/null localhost:$WEB_PORT && break; sleep 1; done
ok "Web demo en http://localhost:$WEB_PORT"

trap 'echo; echo "Apagando demo…"; kill $API_PID $WEB_PID 2>/dev/null; exit 0' INT TERM HUP
print -P "\n%F{green}%BDemo corriendo:%b http://localhost:$WEB_PORT%f   (tus datos reales siguen en :3000)"
open http://localhost:$WEB_PORT
wait
