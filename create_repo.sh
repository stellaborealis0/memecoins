#!/bin/bash

# ============================================================
# Memecoin Agent v3.0 - Crear Subrepositorio Git
# ============================================================

set -e

echo "=== Creando Subrepositorio Git ==="

# Verificar si ya existe un repositorio
if [ -d .git ]; then
    echo "ERROR: Ya existe un repositorio git en este directorio"
    exit 1
fi

# Inicializar repositorio
git init

# Añadir archivos
git add .

# Crear commit inicial
git commit -m "feat: Initial commit - Memecoin Agent v3.0

Arquitectura de 4 capas:
- Capa A: Sniper Engine (detección heurística <2s)
- Capa B: Risk Filter (evaluación <500ms)
- Capa C: Research Engine (ML + Hipótesis)
- Capa D: Execution Engine (trades con Jito Bundles)

Características:
- Streaming on-chain con gRPC y WebSocket fallback
- Whale tracker y spray strategy
- Telegram Bot para control remoto
- Docker Compose para despliegue

Vista previa de la arquitectura:

┌─────────────────────────────────────────────────────────────────────┐
│                    Memecoin Agent v3.0                             │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa A - Sniper Engine                     │  │
│  │  ┌────────────────────┐  ┌────────────────────────────────┐   │  │
│  │  │  Stream gRPC       │  │  Stream WebSocket (fallback)   │   │  │
│  │  │  (ingesta streaming)│  │  (fallback)                   │   │  │
│  │  └─────────┬──────────┘  └────────────────────────────────┘   │  │
│  │            │                                                   │  │
│  │            ▼                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  Sniper Engine: <2s detection, score heurístico         │   │  │
│  │  │  - tx_velocity, wallets, buy_ratio, liquidity          │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa B - Risk Filter                       │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  Risk Score: rugcheck, creator history, concentration  │   │  │
│  │  │  - Bloquea si risk_score > RISK_THRESHOLD (0.65)       │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa C - Research Engine                   │  │
│  │  ┌────────────────────┐  ┌────────────────────────────────┐   │  │
│  │  │  XGBoost Models    │  │  Hipótesis LLM                 │   │  │
│  │  │  - Pump 24h        │  │  - Generación semanal          │   │  │
│  │  │  - Rug 48h         │  │  - Validación cada 6h          │   │  │
│  │  │  - Survival 7d     │  │  - Backtest diario             │   │  │
│  │  └────────────────────┘  └────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa D - Execution Engine                  │  │
│  │  ┌────────────────────┐  ┌────────────────────────────────┐   │  │
│  │  │  Jito Bundles      │  │  Circuit Breaker               │   │  │
│  │  │  - Stop-loss -30%  │  │  - Max 1 SOL por trade         │   │  │
│  │  │  - Take-profit     │  │  - Max 10 trades activos       │   │  │
│  │  └────────────────────┘  └────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Whale Tracker (Spray)                      │  │
│  │  - Copy-trading de whales cualificadas                       │  │
│  │  - Graduation rate > 15%, rug rate < 20%                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘"

echo ""
echo "=== Subrepositorio creado exitosamente ==="
echo ""
echo "Para añadir un remote y subir a GitHub:"
echo "  git remote add origin https://github.com/tu-usuario/memecoin-agent.git"
echo "  git push -u origin main"
echo ""