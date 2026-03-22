# Memecoin Agent v3.0

Sistema Autónomo de Análisis y Trading de Memecoins en Solana

## Arquitectura v3.0

```
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
└─────────────────────────────────────────────────────────────────────┘
```

## Estructura de Directorios

```
memecoins/
├── agents/                    # Módulos de las 4 capas
│   ├── sniper_engine.py      # Capa A - Detección heurística
│   ├── risk_filter.py        # Capa B - Evaluación de riesgo
│   ├── research_engine.py    # Capa C - ML + Hipótesis
│   ├── execution_engine.py   # Capa D - Ejecución de trades
│   └── whale_tracker.py      # Estrategia spray
├── scripts/                   # Scripts de ETL y ML
│   ├── stream_onchain_grpc.py
│   ├── stream_onchain_ws.py
│   ├── collect_onchain.py
│   ├── compute_features.py
│   ├── label_targets.py
│   ├── train_models_all.py
│   ├── generate_hypotheses_llm.py
│   ├── validate_hypotheses.py
│   ├── backtest_report.py
│   └── telegram_bot.py
├── config/
│   ├── .env.example
│   └── hermes-memecoin.toml
├── sql/
│   └── schema_v3.0.sql
├── models/                    # Modelos entrenados (.pkl)
├── logs/                      # Logs de ejecución
├── docker-compose.yml
├── Dockerfile
├── docker-entrypoint.sh
├── requirements.txt
└── README.md
```

## Requisitos

- Python 3.11+
- PostgreSQL 16 + TimescaleDB
- Docker y Docker Compose (opcional)

## Instalación Rápida (Docker)

```bash
# Clonar y configurar
git clone https://github.com/tu-usuario/memecoin-agent.git
cd memecoin-agent

# Copiar variables de entorno
cp config/.env.example config/.env
nano config/.env  # Rellenar con tus API keys y tokens

# Arrancar
docker compose up -d

# Ver logs
docker compose logs -f stream-grpc
```

## Instalación Nativa

```bash
# Instalar PostgreSQL + TimescaleDB
brew install postgresql@16
brew install timescaledb

# Crear base de datos
createdb memecoin_db
createuser memecoin_user
psql -d memecoin_db -f sql/schema_v3.0.sql

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
export DATABASE_URL=postgresql://memecoin_user:password@localhost:5432/memecoin_db
export TELEGRAM_BOT_TOKEN=tu_token
export TELEGRAM_ALLOWED_USERS=tu_user_id

# Arrancar
python scripts/stream_onchain_grpc.py
python agents/risk_filter.py
python agents/research_engine.py
```

## Comandos de Telegram

- `/start` - Ayuda
- `/status` - Estado general
- `/top_pump` - Top 10 tokens por prob. pump
- `/top_rug` - Top 10 tokens por riesgo rug
- `/hypotheses` - Top 5 hipótesis activas
- `/backtest` - Métricas de modelos
- `/mode` - Ver/cambiar modo operativo
- `/pause` - Pausar agente
- `/resume` - Reanudar agente
- `/ping` - Verificar estado

## Modos Operativos

- **research** (por defecto): Solo alertas y análisis. No ejecuta trades.
- **execution**: Permite trades reales con capital real.

**ADVERTENCIA**: Para activar modo execution:
1. Ejecutar `/mode execution confirm` en Telegram
2. Validar modelos con precision@top10 >= 0.60 durante 8 semanas
3. Configurar WALLET_PRIVATE_KEY con seguridad

## Seguridad

- Límite hard de 1 SOL por trade (nunca se puede sobrepasar)
- Stop-loss on-chain obligatorio (-30%)
- Circuit breaker tras 3 pérdidas consecutivas
- Execution PIN de 6 dígitos para activar trades reales
- NUNCA usar en producción sin validación completa

## Arquitectura de Datos

### Tablas Principales

- `tokens`: Metadatos de tokens y predicciones
- `launches`: Series temporales de micro-ventanas (TimescaleDB)
- `token_features`: Features versionadas para ML
- `token_hypotheses`: Hipótesis falsables con validación bayesiana
- `model_performance`: Métricas de modelos (precision@top_k)
- `pending_trades`: Señales pendientes de ejecución
- `trades`: Historial de trades ejecutados
- `risk_events`: Eventos de evaluación de riesgo
- `tracked_wallets`: Wallets monitoreadas (whales, creators)

## Estrategias

### Capa A - Sniper Engine
- Detecta tokens nuevos en <2s
- Score heurístico basado en:
  - Velocidad de transacciones
  - Wallets únicas
  - Ratio compra/venta
  - Liquidez añadida
  - Progreso bonding curve

### Capa B - Risk Filter
- Evalúa riesgo en <500ms
- Fuentes: RugCheck API, historial creador, concentración
- Bloquea si risk_score > 0.65

### Capa C - Research Engine
- Entrena modelos XGBoost diariamente
- Genera hipótesis semanalmente con LLM
- Validación bayesiana de hipótesis

### Capa D - Execution Engine
- Jito Bundles para MEV protection
- Stop-loss -30%, Take-profit +50% y +100%
- Circuit breaker tras 3 pérdidas

### Whale Tracker (Spray)
- Copy-trading de whales cualificadas
- Criterios: graduation_rate > 15%, rug_rate < 20%
- Delay calculado para cada whale

## Métricas de Éxito

- **Precision@top10**: > 0.60 (mínimo aceptable)
- **Latencia Sniper**: < 2s
- **Latencia Risk Filter**: < 500ms
- **Uptime**: > 99.5%

## Logs y Monitoring

```bash
# Ver logs de todos los servicios
docker compose logs -f

# Ver logs de un servicio específico
docker compose logs -f stream-grpc
docker compose logs -f sniper
docker compose logs -f risk-filter

# Inspeccionar base de datos
docker compose exec postgres psql -U memecoin_user -d memecoin_db
```

## Licencia

MIT