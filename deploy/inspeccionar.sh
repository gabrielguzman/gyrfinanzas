#!/bin/sh
# Inspección de SOLO LECTURA del servidor: no cambia nada.
# Correlo en el servidor y pegá la salida:   sh inspeccionar.sh
echo "== Sistema";            uname -srm; . /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
echo "== Memoria y disco";    free -h | head -2; df -h / | tail -1
echo "== Docker";             docker version --format '{{.Server.Version}}' 2>&1; docker compose version 2>&1 | head -1
echo "== Contenedores (nombre | imagen | puertos)"
docker ps --format '{{.Names}} | {{.Image}} | {{.Ports}}' 2>&1
echo "== Redes de Docker";    docker network ls --format '{{.Name}} ({{.Driver}})' 2>&1
echo "== Puertos en uso";     (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | awk 'NR>1{print $4}' | sort -u | tr '\n' ' '; echo
echo "== Proxy / gestor de proyectos"
for x in nginx caddy traefik apache2 httpd dokku caprover coolify dokploy; do command -v "$x" >/dev/null 2>&1 && echo "comando: $x"; done
docker ps --format '{{.Image}}' 2>/dev/null | grep -iE 'traefik|caddy|nginx|proxy|coolify|dokploy|caprover|portainer|npm' | sort -u | sed 's/^/contenedor: /'
ls /etc/nginx/sites-enabled 2>/dev/null | sed 's/^/nginx sitio: /'
echo "== Carpeta de este usuario"; ls -la ~ | awk 'NR>1{print $1, $NF}'
