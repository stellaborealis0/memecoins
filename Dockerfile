FROM python:3.11-slim

# Dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY scripts/ ./scripts/
COPY agents/ ./agents/
COPY config/  ./config/
COPY sql/     ./sql/

# Directorios de datos y logs
RUN mkdir -p /data/models /data/checkpoints /app/logs

# Variables de entorno por defecto
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV MODELS_DIR=/data/models

# Script de entrada
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]