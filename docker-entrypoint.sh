#!/bin/bash

set -e

echo "=== Memecoin Agent v3.0 ==="
echo "Iniciando en modo: ${EXECUTION_MODE:-research}"

# Esperar a que PostgreSQL esté listo
echo "Esperando PostgreSQL..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
    sleep 2
done

echo "PostgreSQL listo."

# Inicializar schema si no existe
echo "Inicializando schema..."
PGPASSWORD=$POSTGRES_PASSWORD psql \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -f /app/sql/schema_v3.0.sql \
    --on-error-stop 2>/dev/null || echo "Schema ya existe, continuando."

# Ejecutar backfill si la DB está vacía
TOKEN_COUNT=$(PGPASSWORD=$POSTGRES_PASSWORD psql \
    -h "$POSTGRES_HOST" \
    -p "$POSTGRES_PORT" \
    -U "$POSTGRES_USER" \
    -d "$POSTGRES_DB" \
    -tAc "SELECT COUNT(*) FROM tokens;" 2>/dev/null || echo "0")

if [ "$TOKEN_COUNT" -lt "100" ]; then
    echo "DB vacía (${TOKEN_COUNT} tokens). Iniciando backfill histórico..."
    python scripts/backfill_historical.py
else
    echo "DB ya tiene ${TOKEN_COUNT} tokens. Saltando backfill."
fi

# Iniciar Telegram bot en background
echo "Iniciando Telegram bot..."
python scripts/telegram_bot.py &
TELEGRAM_PID=$!

# Iniciar stream gRPC en background (si no está deshabilitado)
if [ "${STREAM_SOURCE:-grpc}" = "grpc" ]; then
    echo "Iniciando stream gRPC..."
    python scripts/stream_onchain_grpc.py &
    STREAM_PID=$!
fi

# Iniciar risk filter en background
echo "Iniciando risk filter..."
python agents/risk_filter.py &
RISK_PID=$!

# Iniciar research engine en background
echo "Iniciando research engine..."
python agents/research_engine.py &
RESEARCH_PID=$!

# Si execution_mode = execution, iniciar execution engine
if [ "${EXECUTION_MODE:-research}" = "execution" ]; then
    echo "Iniciando execution engine..."
    python agents/execution_engine.py &
    EXECUTION_PID=$!
fi

# Esperar a todos los procesos
wait