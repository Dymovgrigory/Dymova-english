#!/usr/bin/env bash
# Бэкап SQLite-базы бота с ротацией (храним 14 последних копий).
#
# Использование:
#   ./scripts/backup_db.sh [путь_к_bot.db] [каталог_бэкапов]
#
# По умолчанию: ./data/bot.db -> ./data/backups/
# Cron (ежедневно в 04:00):
#   0 4 * * * /opt/foxinburg/bot/scripts/backup_db.sh /opt/foxinburg/data/bot.db /opt/foxinburg/data/backups
set -euo pipefail

DB_PATH="${1:-./data/bot.db}"
BACKUP_DIR="${2:-./data/backups}"
KEEP=14

if [ ! -f "$DB_PATH" ]; then
  echo "backup_db: база $DB_PATH не найдена" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$BACKUP_DIR/bot-$STAMP.db"

# .backup — онлайн-бэкап SQLite: снимок согласованный даже при работающем боте.
sqlite3 "$DB_PATH" ".backup '$DEST'"
chmod 600 "$DEST"

# Ротация: удаляем всё старше KEEP последних файлов.
ls -1t "$BACKUP_DIR"/bot-*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

echo "backup_db: $DEST ($(du -h "$DEST" | cut -f1)), копий: $(ls -1 "$BACKUP_DIR"/bot-*.db | wc -l | tr -d ' ')"
