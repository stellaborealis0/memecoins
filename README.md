# Memecoin Agent v3.0-lite

Sistema Autónomo de Análisis y Trading de Memecoins en Solana

**Versión**: 3.0-lite (Optimizado para MacBook Pro 7,1 - 8GB RAM)

---

## Arquitectura v3.0-lite

```
┌─────────────────────────────────────────────────────────────────────┐
│              Memecoin Agent v3.0-lite (MB: 8GB RAM)                │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa A - Sniper Engine                     │  │
│  │  ┌────────────────────┐  ┌────────────────────────────────┐   │  │
│  │  │  Stream polling    │  │  Stream WebSocket (fallback)   │   │  │
│  │  │  (ingesta polling) │  │  (fallback)                   │   │  │
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
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  XGBoost Models (WS: 32GB RAM + 8GB VRAM)              │   │  │
│  │  │  - Pump 24h        │  │  - Hipótesis LLM (TO:8080)      │   │  │
│  │  │  - Rug 48h         │  │  - Validación cada 6h          │   │  │
│  │  │  - Survival 7d     │  │  - Backtest diario             │   │  │
│  │  └────────────────────┘  └────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa D - Execution Engine                  │  │
│  │  ┌────────────────────┐  ┌────────────────────────────────┐   │  │
│  │  │  SQLite DB         │  │  Circuit Breaker               │   │  │
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

### Distribución de Servicios

| Servicio | Nodo | RAM | Notas |
|----------|------|-----|-------|
| Sniper Engine | MB | 2GB | Detección heurística <2s |
| Risk Filter | MB | 1GB | Evaluación <500ms |
| Telegram Bot | MB | 1GB | Control remoto |
| SQLite DB | MB | 512MB | Base de datos local |
| Streaming | MB | 1GB | Polling cada 1-2s |
| Research Engine | WS | 32GB | ML + Training (32GB RAM + 8GB VRAM) |
| LLM Access | TO | - | Gateway LiteLLM (8080) |

---

## Estructura de Directorios

```
memecoins/
├── agents/                    # Módulos de las 4 capas
│   ├── sniper_engine.py      # Capa A - Detección heurística
│   ├── risk_filter.py        # Capa B - Evaluación de riesgo
│   ├── research_engine.py    # Capa C - ML + Hipótesis (WS)
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

---

## Requisitos

### MacBook Pro 7,1 (MB)
- **OS**: Ubuntu 24.04
- **RAM**: 8 GB
- **Storage**: 8 GB SSD (eMMC)
- **CPU**: Intel Core i7 (2010)

### WS (Backend Research)
- **RAM**: 32 GB
- **GPU**: 8 GB VRAM
- **Storage**: 200 GB SSD

### TO (Gateway)
- **LiteLLM**: Puerto 8080

---

## Instalación Rápida (MB - 8GB RAM)

```bash
# Clonar y configurar
git clone https://github.com/tu-usuario/memecoin-agent.git
cd memecoin-agent

# Copiar variables de entorno
cp config/.env.example config/.env
nano config/.env  # Rellenar con tus API keys y tokens

# Instalar dependencias
pip install -r requirements.txt

# Arrancar servicios
python scripts/stream_onchain_grpc.py &
python agents/sniper_engine.py &
python agents/risk_filter.py &
python agents/execution_engine.py &
python agents/whale_tracker.py &
python scripts/telegram_bot.py &
```

---

## Instalación Research Engine (WS - 32GB RAM)

```bash
# En WS (32GB RAM + 8GB VRAM)
git clone https://github.com/tu-usuario/memecoin-agent.git
cd memecoin-agent

# Copiar variables de entorno
cp config/.env.example config/.env
nano config/.env

# Instalar dependencias
pip install -r requirements.txt

# Arrancar Research Engine
python agents/research_engine.py
```

---

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

---

## Modos Operativos

- **research** (por defecto): Solo alertas y análisis. No ejecuta trades.
- **execution**: Permite trades reales con capital real.

**ADVERTENCIA**: Para activar modo execution:
1. Ejecutar `/mode execution confirm` en Telegram
2. Validar modelos con precision@top10 >= 0.60 durante 8 semanas
3. Configurar WALLET_PRIVATE_KEY con seguridad

---

## Seguridad

- Límite hard de 1 SOL por trade (nunca se puede sobrepasar)
- Stop-loss on-chain obligatorio (-30%)
- Circuit breaker tras 3 pérdidas consecutivas
- Execution PIN de 6 dígitos para activar trades reales
- NUNCA usar en producción sin validación completa

---

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

---

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

### Capa C - Research Engine (WS)
- Entrena modelos XGBoost diariamente
- Genera hipótesis semanalmente con LLM
- Validación bayesiana de hipótesis
- Requiere 32GB RAM + 8GB VRAM

### Capa D - Execution Engine
- SQLite DB (no PostgreSQL)
- Stop-loss -30%, Take-profit +50% y +100%
- Circuit breaker tras 3 pérdidas

### Whale Tracker (Spray)
- Copy-trading de whales cualificadas
- Criterios: graduation_rate > 15%, rug_rate < 20%
- Delay calculado para cada whale

---

## Métricas de Éxito

- **Precision@top10**: > 0.60 (mínimo aceptable)
- **Latencia Sniper**: < 2s
- **Latencia Risk Filter**: < 500ms
- **Uptime**: > 99.5%

---

## Logs y Monitoring

```bash
# Ver logs de todos los servicios
tail -f logs/*.log

# Ver logs de un servicio específico
tail -f logs/streaming.log
tail -f logs/sniper.log
tail -f logs/risk-filter.log

# Inspeccionar base de datos SQLite
sqlite3 data/memecoin.db
```

---

## Integración con SAA v7.2

### Enrutamiento LLM

```
Memecoin Agent (MB)
    ↓
LiteLLM Gateway (TO:8080)
    ↓
    ├─→ ws-qwen-heavy → WS:11435 (Qwen3.5) [⚠️ Ocupado COLMAP]
    ├─→ im-qwen32b    → IM:11434 (Qwen32B) [✅ Disponible]
    └─→ ew-qwen       → EW:11434 (Qwen3.5) [❌ Offline]
```

### Configuración de LiteLLM

```yaml
# litellm_config.yaml
model_list:
  - model_name: memecoin-agent
    litellm_params:
      model: openai/qwen3.5
      api_base: http://100.68.1.180:8080
      api_key: ${LITELLM_API_KEY}
```

---

## Licencia

MIT