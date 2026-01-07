#!/usr/bin/env bash
# filepath: /src/slay/slay-db-update/scripts/run_flyway.sh
# Run Flyway bootstrap migration (against postgres) then main migrations (against nba)
# Reads dsn from project root config.yaml (expects 'dsn: <jdbc|postgresql uri>')

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "config.yaml not found at $CONFIG_FILE"
  exit 1
fi

# Extract DSN value using a simple awk (assumes single-line `dsn: ...`)
DSN_LINE=$(awk -F": " '/^dsn:/ {print $2; exit}' "$CONFIG_FILE")
if [ -z "$DSN_LINE" ]; then
  echo "dsn not found in $CONFIG_FILE"
  exit 1
fi

# If the DSN starts with postgresql:// convert to JDBC url for Flyway
# Flyway expects jdbc:postgresql://host:port/db
if [[ "$DSN_LINE" == postgresql://* ]]; then
  FLYWAY_URL="jdbc:${DSN_LINE}"
else
  FLYWAY_URL="$DSN_LINE"
fi

# Derive admin URL to connect to the 'postgres' database for bootstrap
# Replace the path part with /postgres
ADMIN_URL=$(echo "$FLYWAY_URL" | sed -E 's|(jdbc:postgresql://[^/]+)(/.*)|\1/postgres|')

# Location paths (relative to project root)
BOOTSTRAP_LOC="filesystem:$ROOT_DIR/sql/bootstrap"
MAIN_LOC="filesystem:$ROOT_DIR/sql/main"

# Extract user and password from DSN for Flyway CLI (naive parse)
# Expect format jdbc:postgresql://host:port/db?params or postgresql://user:pass@host:port/db?params
# We'll use environment variables FLYWAY_USER and FLYWAY_PASSWORD if present, otherwise try to parse.
if [ -n "${FLYWAY_USER-}" ] && [ -n "${FLYWAY_PASSWORD-}" ]; then
  FLYWAY_USER_OPT="$FLYWAY_USER"
  FLYWAY_PASSWORD_OPT="$FLYWAY_PASSWORD"
else
  # Try to parse user:password from DSN
  if [[ "$DSN_LINE" =~ postgresql://([^:@/]+):([^@/]+)@ ]]; then
    FLYWAY_USER_OPT="${BASH_REMATCH[1]}"
    FLYWAY_PASSWORD_OPT="${BASH_REMATCH[2]}"
  elif [[ "$FLYWAY_URL" =~ jdbc:postgresql://([^:@/]+):([^@/]+)@ ]]; then
    FLYWAY_USER_OPT="${BASH_REMATCH[1]}"
    FLYWAY_PASSWORD_OPT="${BASH_REMATCH[2]}"
  else
    echo "Could not determine DB user/password from DSN; set FLYWAY_USER and FLYWAY_PASSWORD env vars"
    exit 1
  fi
fi

# Run bootstrap migration against postgres
echo "Running bootstrap migration to create nba DB..."
cd $(echo $BOOTSTRAP_LOC | cut -d':' -f2)
cmd="flyway -url="$ADMIN_URL" -user="$FLYWAY_USER_OPT" -password="$FLYWAY_PASSWORD_OPT" migrate"
$cmd

# Run main migrations against the nba DB
echo "Running main migrations against nba DB..."
echo "flyway -locations="$MAIN_LOC" -url="$FLYWAY_URL" -user="$FLYWAY_USER_OPT" -password="$FLYWAY_PASSWORD_OPT" migrate"

echo "Migrations complete."

