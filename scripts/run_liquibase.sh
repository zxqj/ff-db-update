#!/usr/bin/env bash
# scripts/run_liquibase.sh
# Run Liquibase bootstrap (create 'nba' DB) and then main changelogs to create tables.
# Reads DSN from project root config.yaml (expects a top-level `dsn: postgresql://...`)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$ROOT_DIR/config.yaml"
LB_DIR="lb"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "config.yaml not found at $CONFIG_FILE"
  exit 1
fi

DSN_LINE=$(awk -F": " '/^dsn:/ {print $2; exit}' "$CONFIG_FILE")
if [ -z "$DSN_LINE" ]; then
  echo "dsn not found in $CONFIG_FILE"
  exit 1
fi

# Build JDBC URL for Liquibase: jdbc:postgresql://host:port/db?params
if [[ "$DSN_LINE" == postgresql://* ]]; then
  # parse postgresql://user:pass@host:port/dbname?params
  if [[ "$DSN_LINE" =~ postgresql://([^:@/]+):([^@/]+)@([^:/?]+)(:([0-9]+))?/([^?]+)(\?(.*))? ]]; then
    LB_USER_PARSED="${BASH_REMATCH[1]}"
    LB_PASS_PARSED="${BASH_REMATCH[2]}"
    DB_HOST_PARSED="${BASH_REMATCH[3]}"
    DB_PORT_PARSED="${BASH_REMATCH[5]}"
    DB_NAME_PARSED="${BASH_REMATCH[6]}"
    DSN_PARAMS="${BASH_REMATCH[8]}"
    if [ -z "$DB_PORT_PARSED" ]; then
      DB_PORT_PARSED=5432
    fi
    JDBC_URL="jdbc:postgresql://$DB_HOST_PARSED:$DB_PORT_PARSED/$DB_NAME_PARSED"
    if [ -n "$DSN_PARAMS" ]; then
      JDBC_URL="$JDBC_URL?$DSN_PARAMS"
    fi
    # If LB_USER wasn't set from env, use parsed user/pass
    if [ -z "${LB_USER-}" ]; then LB_USER="$LB_USER_PARSED"; fi
    if [ -z "${LB_PASS-}" ]; then LB_PASS="$LB_PASS_PARSED"; fi
  else
    # fallback: just prefix jdbc: and hope for the best
    JDBC_URL="jdbc:${DSN_LINE}"
  fi
else
  JDBC_URL="$DSN_LINE"
fi

# Derive admin (postgres) JDBC URL to create the database
# We want jdbc:postgresql://host:port/postgres plus any params
if [[ "$JDBC_URL" =~ jdbc:postgresql://([^:/?]+)(:([0-9]+))?(/[^?]+)?(\?(.*))? ]]; then
  ADMIN_HOST="${BASH_REMATCH[1]}"
  ADMIN_PORT="${BASH_REMATCH[3]}"
  ADMIN_PARAMS="${BASH_REMATCH[5]}"
  if [ -z "$ADMIN_PORT" ]; then ADMIN_PORT=5432; fi
  ADMIN_JDBC_URL="jdbc:postgresql://$ADMIN_HOST:$ADMIN_PORT/postgres"
  if [ -n "$ADMIN_PARAMS" ]; then
    ADMIN_JDBC_URL="$ADMIN_JDBC_URL?${ADMIN_PARAMS#?}"
  fi
else
  # fallback to sed replacement
  ADMIN_JDBC_URL=$(echo "$JDBC_URL" | sed -E 's|(jdbc:postgresql://[^/]+)(/.*)|\1/postgres|')
fi

# Ensure liquibase is available
if ! command -v liquibase >/dev/null 2>&1; then
  echo "liquibase not found on PATH. Please install Liquibase CLI (https://www.liquibase.org/)."
  exit 1
fi

# install packages listed in liquibase.json
# NOTE:
#   Peculiarly, 'liquibase lpm install' exits erroneously if the packages are already installed
#   so we use 'upgrade' instead.
cd $LB_DIR
liquibase lpm upgrade

# Run bootstrap changelog against postgres DB to create nba
echo "Running Liquibase bootstrap to create 'nba' database against postgres..."
liquibase \
  --changeLogFile="conf/bootstrap/changelog.xml" \
  --url="$ADMIN_JDBC_URL" \
  --username="$LB_USER" \
  --password="$LB_PASS" \
  update

# Run main changelog against the newly created nba DB
echo "Running Liquibase main changelog against nba DB..."
liquibase \
  --changeLogFile="conf/main/changelog.xml" \
  --url="$JDBC_URL" \
  --username="$LB_USER" \
  --password="$LB_PASS" \
  update

echo "Liquibase migrations complete."
