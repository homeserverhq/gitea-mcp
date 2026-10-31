#!/usr/bin/env sh
#
# Remove or check Gitea "action" rows that reference repositories which no
# longer exist. Gitea retains these rows when a repository is deleted, and they
# can make user activity feeds render "(non-existing-repo)" or return HTTP 500.
#
# Uses the standard PostgreSQL environment variables:
#   PGHOST, PGPORT, PGUSER, PGDATABASE, PGPASSWORD
#
# Usage:
#   scripts/cleanup_orphaned_actions.sh          # delete orphaned rows
#   scripts/cleanup_orphaned_actions.sh --check  # exit non-zero if any exist
#
# Example inside the Gitea database container:
#   docker exec -e PGPASSWORD="$GITEA_DB_PASSWORD" gitea-db \
#     sh /path/to/cleanup_orphaned_actions.sh
#
set -eu

: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
export PGHOST PGPORT

ORPHAN_COUNT_SQL="
SELECT count(*)
FROM action a
LEFT JOIN repository r ON a.repo_id = r.id
WHERE a.repo_id IS NOT NULL AND r.id IS NULL;
"

DELETE_SQL="
DELETE FROM action a
WHERE a.repo_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM repository r WHERE r.id = a.repo_id
  );
"

if [ "${1:-}" = "--check" ]; then
    count=$(psql -tAc "$ORPHAN_COUNT_SQL")
    echo "orphaned actions: $count"
    if [ "$count" -eq 0 ]; then
        exit 0
    fi
    exit 1
fi

psql -v ON_ERROR_STOP=1 -c "$DELETE_SQL"
count=$(psql -tAc "$ORPHAN_COUNT_SQL")
echo "orphaned actions after cleanup: $count"
[ "$count" -eq 0 ]
