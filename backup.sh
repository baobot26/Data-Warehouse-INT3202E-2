#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
stamp="$(date +%F_%H-%M-%S)"
docker compose exec -T postgres sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  > "backups/postgres_${stamp}.sql"
find backups -type f -name 'postgres_*.sql' -mtime +7 -delete
