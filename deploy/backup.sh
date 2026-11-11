#!/bin/sh
# Backup de gyrfinanzas: base (pg_dump comprimido) + comprobantes (tar).
# Corre una vez al arrancar si no hay backup de hoy, y después todos los días a las BACKUP_HORA.
# Uso manual:  docker compose exec backup sh /backup.sh ahora
set -eu

hacer() {
  f=$(date +%Y%m%d-%H%M)
  pg_dump --no-owner --format=custom --file="/backups/base-$f.dump"
  tar -czf "/backups/comprobantes-$f.tar.gz" -C /uploads .
  find /backups -name 'base-*.dump' -mtime +"$BACKUP_DIAS" -delete
  find /backups -name 'comprobantes-*.tar.gz' -mtime +"$BACKUP_DIAS" -delete
  echo "$(date '+%F %T') backup listo: base-$f.dump y comprobantes-$f.tar.gz"
}

if [ "${1:-}" = "ahora" ]; then hacer; exit 0; fi

ultimo=""
while true; do
  hoy=$(date +%F)
  if [ "$ultimo" != "$hoy" ] && { [ "$(date +%H)" = "$BACKUP_HORA" ] || ! ls /backups/base-"$(date +%Y%m%d)"-*.dump >/dev/null 2>&1; }; then
    if hacer; then ultimo=$hoy; else echo "$(date '+%F %T') el backup falló, reintento en una hora"; fi
  fi
  sleep 3600
done
