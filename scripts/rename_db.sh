#!/usr/bin/env bash
# scripts/rename_db.sh
# Read DSN from config.yaml, terminate connections to the DB, and rename it to <db>_old

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "config.yaml not found at $CONFIG_FILE"
  exit 1
fi

DSN_LINE=$(awk -F": " '/^dsn:/ {print $2; exit}' "$CONFIG_FILE")
if [ -z "$DSN_LINE" ]; then
  echo "dsn not found in $CONFIG_FILE"
  exit 1
fi

# Expect DSN like: postgresql://user:pass@host:port/dbname?params
if [[ "$DSN_LINE" =~ postgresql://([^:@/]+):([^@/]+)@([^:/]+):([0-9]+)/([^?]+) ]]; then
  DB_USER="${BASH_REMATCH[1]}"
  DB_PASS="${BASH_REMATCH[2]}"
  DB_HOST="${BASH_REMATCH[3]}"
  DB_PORT="${BASH_REMATCH[4]}"
  DB_NAME="${BASH_REMATCH[5]}"
else
  echo "DSN format not recognized: $DSN_LINE"
  exit 1
fi

NEW_NAME="${DB_NAME}_old"

export PGPASSWORD="$DB_PASS"

PSQL_BASE=(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -v ON_ERROR_STOP=1)

echo "Terminating other connections to database '$DB_NAME' (if any)..."
"${PSQL_BASE[@]}" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid();"

echo "Renaming database '$DB_NAME' to '$NEW_NAME'..."
"${PSQL_BASE[@]}" -d postgres -c "ALTER DATABASE \"$DB_NAME\" RENAME TO \"$NEW_NAME\";"

echo "Rename complete."

# Unset the password from environment
unset PGPASSWORD

