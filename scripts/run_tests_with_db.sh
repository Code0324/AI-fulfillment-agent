#!/usr/bin/env bash
#
# Runs the full backend test suite (existing + MCP + pricing-provider tests)
# against a real, disposable PostgreSQL instance.
#
# Why a DISPOSABLE container instead of `docker compose up postgres`
# ---------------------------------------------------------------------------
# docker-compose.yml's `postgres` service is meant for local dev/prod — it
# has a named, persistent volume (amazon_fulfillment_postgres_data). The
# test suite is NOT safe to point at that: several test files call
# order_service.clear() / inventory_service.clear() / etc. as an autouse
# fixture, which issue a real `DELETE FROM ...` against every row in those
# tables. Running that against your dev database would destroy real data.
# So this script starts its own throwaway container instead — its own
# name, its own port, an anonymous volume, and `docker run --rm` (removed
# on stop) — so it can never collide with or affect the docker-compose.yml
# stack, and there is nothing left to "clean up" afterward.
#
# Usage
# ---------------------------------------------------------------------------
#   ./scripts/run_tests_with_db.sh              # run the full suite
#   ./scripts/run_tests_with_db.sh tests/test_pricing_providers.py -v
#   (any extra arguments are passed through to `pytest`)
#
# Requires: Docker (with the daemon reachable from this shell) and a Python
# interpreter with this repo's requirements.txt installed (see PYTHON_BIN
# selection below — on WSL, plain `python` can silently resolve to a
# Windows App Execution Alias stub that does nothing and exits 0, which
# would make this script falsely appear to pass with zero tests run; that
# is exactly the failure mode the check below exists to catch loudly
# instead of silently).
set -euo pipefail

# Prefer python3 (the portable, unambiguous choice on Linux/WSL); allow an
# explicit override via PYTHON_BIN=... for a venv interpreter. Then verify
# it's a real interpreter with pytest installed — fail loudly rather than
# silently "succeeding" with zero tests run (see note above).
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
if [ -z "${PYTHON_BIN}" ] || ! "${PYTHON_BIN}" -c "import pytest, alembic" >/dev/null 2>&1; then
  echo "ERROR: '${PYTHON_BIN:-python3/python}' is not a working interpreter with" >&2
  echo "this repo's dependencies installed (pytest, alembic). On WSL, 'python'" >&2
  echo "can silently resolve to a Windows App Execution Alias stub instead of a" >&2
  echo "real interpreter. Activate your venv first, or set PYTHON_BIN=/path/to/python." >&2
  exit 1
fi
echo "Using Python interpreter: ${PYTHON_BIN}"

CONTAINER_NAME="amazon-fulfillment-test-postgres"
TEST_DB_PORT="55432"  # deliberately not 5432/5434 — never collides with a dev instance
POSTGRES_USER="test_user"
POSTGRES_PASSWORD="test_password"
POSTGRES_DB="amazon_fulfillment_test"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${SCRIPT_DIR}/../backend"

cleanup() {
  echo "Stopping and removing ${CONTAINER_NAME}..."
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting disposable Postgres container (${CONTAINER_NAME}) on port ${TEST_DB_PORT}..."
docker run -d --rm \
  --name "${CONTAINER_NAME}" \
  -e POSTGRES_USER="${POSTGRES_USER}" \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
  -e POSTGRES_DB="${POSTGRES_DB}" \
  -p "${TEST_DB_PORT}:5432" \
  postgres:16-alpine >/dev/null

echo "Waiting for Postgres to accept connections..."
for _ in $(seq 1 30); do
  if docker exec "${CONTAINER_NAME}" pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! docker exec "${CONTAINER_NAME}" pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" >/dev/null 2>&1; then
  echo "Postgres did not become ready in time." >&2
  exit 1
fi

export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${TEST_DB_PORT}/${POSTGRES_DB}"
echo "DATABASE_URL=${DATABASE_URL}"

echo "Running Alembic migrations..."
(cd "${BACKEND_DIR}" && "${PYTHON_BIN}" -m alembic upgrade head)

echo "Running the full test suite..."
(cd "${BACKEND_DIR}" && "${PYTHON_BIN}" -m pytest "$@")
