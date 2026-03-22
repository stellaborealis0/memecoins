#!/bin/bash

# ============================================================
# Memecoin Agent v3.0 - Script de Inicialización
# ============================================================

set -e

echo "=== Memecoin Agent v3.0 - Inicialización ==="

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker no está instalado"
    exit 1
fi

# Verificar docker-compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose no está instalado"
    exit 1
fi

# Crear directorios necesarios
mkdir -p models logs data

# Copiar .env.example si no existe
if [ ! -f config/.env ]; then
    echo "Copiando config/.env.example a config/.env..."
    cp config/.env.example config/.env
    echo "Por favor, edita config/.env con tus valores antes de arrancar"
fi

# Arrancar
echo "Arrancando Memecoin Agent v3.0..."
docker compose up -d

echo ""
echo "=== Inicialización completada ==="
echo ""
echo "Comandos útiles:"
echo "  docker compose ps              - Ver estado de servicios"
echo "  docker compose logs -f         - Ver logs en tiempo real"
echo "  docker compose down            - Detener servicios"
echo "  docker compose down -v         - Detener y borrar datos"
echo ""
echo "Para ver los logs de un servicio específico:"
echo "  docker compose logs -f stream-grpc"
echo "  docker compose logs -f sniper"
echo "  docker compose logs -f risk-filter"
echo ""