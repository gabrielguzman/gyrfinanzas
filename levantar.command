#!/bin/zsh
# Levanta gyrfinanzas completo: Postgres (Docker/OrbStack) + API + web.
# Doble clic desde Finder o ./levantar.command. Ctrl+C para apagar todo.

cd "$(dirname "$0")"
RAIZ="$(pwd)"
mkdir -p .logs

# Una sola a la vez: si abrís el archivo dos veces, la segunda se pisa con la primera (migraciones, puertos).
LOCK=.logs/levantar.pid
if ! ( set -o noclobber; echo $$ > $LOCK ) 2>/dev/null; then
  if kill -0 "$(cat $LOCK 2>/dev/null)" 2>/dev/null; then
    print -P "%F{yellow}gyrfinanzas ya está corriendo en otra ventana.%f Esta se cierra sola."
    sleep 4; exit 0
  fi
  echo $$ >| $LOCK  # quedó de una vez que se cortó
fi

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.homebrew/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

paso() { print -P "\n%F{blue}▸ $1%f"; }
ok()   { print -P "  %F{green}✓ $1%f"; }
mal()  { print -P "  %F{red}✗ $1%f"; echo; echo "Apretá Enter para cerrar."; read; exit 1; }

paso "Revisando herramientas"
command -v node >/dev/null || mal "No encuentro Node.js. Instalalo (nvm install --lts) y volvé a correr esto."
ok "Node $(node -v)"
if ! command -v uv >/dev/null; then
  echo "  uv no está instalado; lo instalo (gestor de Python de Astral)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || mal "No pude instalar uv."
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv $(uv --version | cut -d' ' -f2)"

if ! docker info >/dev/null 2>&1; then
  echo "  Docker no responde; abro OrbStack…"
  open -a OrbStack 2>/dev/null || open -a Docker 2>/dev/null
  for i in {1..60}; do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || mal "Docker no arrancó. Abrí OrbStack a mano y volvé a correr esto."
fi
ok "Docker listo"

paso "Base de datos"
docker compose up -d db >/dev/null 2>&1 || mal "No pude levantar Postgres (¿el puerto 5432 está ocupado?)."
for i in {1..30}; do docker compose exec -T db pg_isready -U gyr >/dev/null 2>&1 && break; sleep 1; done
ok "Postgres en localhost:5432"

libre() { local p=$1; while lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; do p=$((p+1)); done; echo $p; }
API_PORT=$(libre 8000)
WEB_PORT=$(libre 3000)
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)
export CORS_ORIGINS="http://localhost:$WEB_PORT${IP:+,http://$IP:$WEB_PORT}"
export API_PORT

paso "API"
cd "$RAIZ/apps/api"
[ -f .env ] || cp .env.example .env
uv sync --quiet || mal "Falló la instalación de dependencias de Python (ver arriba)."
uv run alembic upgrade head >/dev/null 2>&1 || mal "Fallaron las migraciones."
uv run python -m app.seed >/dev/null
uv run uvicorn app.main:app --host 0.0.0.0 --port $API_PORT --reload > "$RAIZ/.logs/api.log" 2>&1 &
API_PID=$!
for i in {1..30}; do curl -sf localhost:$API_PORT/salud >/dev/null && break; sleep 1; done
curl -sf localhost:$API_PORT/salud >/dev/null || mal "La API no arrancó. Mirá .logs/api.log"
ok "API en http://localhost:$API_PORT  (docs: /docs)"

paso "Bot de Telegram"
grep -q '^TELEGRAM_TOKEN=' .env || echo "TELEGRAM_TOKEN=" >> .env
TOKEN=$(grep '^TELEGRAM_TOKEN=' .env | head -1 | cut -d= -f2- | tr -d '"'"'"' ')
if [ -z "$TOKEN" ] && ! grep -q '^TELEGRAM_OMITIR=1' .env; then
  echo "  Para cargar gastos desde Telegram, creá un bot con @BotFather (/newbot)"
  echo "  y pegá acá el token que te da. Escribí «no» para no preguntar más."
  echo "  (Si no respondés en 60 s, sigo sin bot y te pregunto la próxima vez.)"
  printf "  Token: "
  if read -r -t 60 TOKEN; then
    TOKEN=$(echo "$TOKEN" | tr -d ' ')
    if [ "$TOKEN" = "no" ]; then
      echo "TELEGRAM_OMITIR=1" >> .env; TOKEN=""
    elif [ -n "$TOKEN" ]; then
      sed -i '' "s|^TELEGRAM_TOKEN=.*|TELEGRAM_TOKEN=$TOKEN|" .env
    fi
  else
    echo; TOKEN=""
  fi
fi
if [ -n "$TOKEN" ]; then
  CODIGO=$(openssl rand -hex 4 | tr 'a-f' 'A-F')
  TELEGRAM_CODIGO=$CODIGO uv run python -m app.bot > "$RAIZ/.logs/bot.log" 2>&1 &
  BOT_PID=$!
  sleep 4
  if kill -0 $BOT_PID 2>/dev/null; then
    ok "Bot corriendo"
  else
    print -P "  %F{yellow}! El bot no arrancó: $(tail -1 "$RAIZ/.logs/bot.log")%f"
    BOT_PID=""; CODIGO=""
  fi
else
  echo "  Sin token: el bot queda apagado (agregalo en apps/api/.env → TELEGRAM_TOKEN)."
fi

paso "Web"
cd "$RAIZ/apps/web"
if [ ! -d node_modules ] || [ package.json -nt node_modules/.package-lock.json ]; then
  echo "  Instalando dependencias…"
  npm install --no-audit --no-fund --loglevel=error || mal "Falló npm install."
fi
npm run dev -- -H 0.0.0.0 -p $WEB_PORT > "$RAIZ/.logs/web.log" 2>&1 &
WEB_PID=$!
for i in {1..60}; do curl -sf -o /dev/null localhost:$WEB_PORT && break; sleep 1; done
curl -sf -o /dev/null localhost:$WEB_PORT || mal "La web no arrancó. Mirá .logs/web.log"
ok "Web en http://localhost:$WEB_PORT"

trap 'echo; echo "Apagando…"; kill $API_PID $WEB_PID $BOT_PID 2>/dev/null; rm -f "$RAIZ/$LOCK"; exit 0' INT TERM HUP

print -P "\n%F{green}%B¡Listo! gyrfinanzas está corriendo.%b%f"
echo "  En esta compu:  http://localhost:$WEB_PORT"
[ -n "$IP" ] && echo "  Desde el celu (misma WiFi):  http://$IP:$WEB_PORT"
[ -n "$CODIGO" ] && echo "  Telegram: si todavía no lo vinculaste, mandale al bot  /vincular $CODIGO"
echo "  Logs en .logs/   ·   Ctrl+C (o cerrar esta ventana) para apagar todo"
open http://localhost:$WEB_PORT
wait
