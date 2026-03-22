# Memecoin Agent v3.0-ultralite

Sistema Autónomo de Análisis y Trading de Memecoins en Solana

**Versión**: 3.0-ultralite (Optimizado para MacBook Pro 7,1 - 8GB RAM)

**Estado**: SAA v7.2 compliant - 100% SQLite, sin Docker, sin gRPC

---

## Arquitectura v3.0-ultralite

```
┌─────────────────────────────────────────────────────────────────────┐
│           Memecoin Agent v3.0-ultralite (MB: 8GB RAM)              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa A - Sniper Engine                     │  │
│  │  ┌────────────────────┐                                       │  │
│  │  │  Polling RPC       │                                       │  │
│  │  │  (15s Helius)      │                                       │  │
│  │  └─────────┬──────────┘                                       │  │
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
│  │  │  XGBoost Models (IM: CPU-only, 8GB RAM)                │   │  │
│  │  │  - Pump 24h        │  │  - Hipótesis LLM (TO:8080)      │   │  │
│  │  │  - Rug 48h         │  │  - Validación cada 6h          │   │  │
│  │  │  - Survival 7d     │  │  - Backtest diario             │   │  │
│  │  │  - Modo: heuristic_only (fallback)                     │   │  │
│  │  └────────────────────┘  └────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa D - Execution Engine                  │  │
│  │  ┌────────────────────┐  ┌────────────────────────────────┐   │  │
│  │  │  SQLite DB         │  │  Circuit Breaker               │   │  │
│  │  │  - WAL Mode        │  │  - Stop-loss -30%              │   │  │
│  │  │  - Retention 24h   │  │  - Max 1 SOL por trade         │   │  │
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
| SQLite DB | MB | 512MB | Base de datos local (WAL Mode) |
| Streaming | MB | 1GB | Polling cada 15s (Helius) |
| Research Engine | IM | 8GB | ML + Training (CPU-only, fallback) |
| LLM Access | TO | - | Gateway LiteLLM (8080) |

---

## Requisitos

### MacBook Pro 7,1 (MB)
- **OS**: Ubuntu 24.04
- **RAM**: 8 GB
- **Storage**: 8 GB SSD (eMMC) - **CRÍTICO**
- **CPU**: Intel Core i7 (2010)

**⚠️ Importante**: El SSD de 8GB se llenará rápidamente. Implementar:
- Retención de datos: 24h máximo (configurable en agent_config)
- Rotación de logs: 10MB máximo por archivo
- Limpieza automática cada 6h

### IM (Fallback Research)
- **RAM**: 8 GB
- **CPU**: 4+ cores
- **Storage**: 50 GB SSD

### TO (Gateway)
- **LiteLLM**: Puerto 8080

---

## Instalación Rápida (MB - 8GB RAM)

```bash
# Clonar y configurar
git clone https://github.com/tu-usuario/memecoin-agent.git
cd memecoins

# Copiar variables de entorno
cp config/.env.example config/.env
nano config/.env  # Rellenar con tus API keys y tokens

# Instalar dependencias (ultralite: ~200MB)
pip install -r requirements.txt

# Inicializar base de datos SQLite con WAL mode
python scripts/init_db.py

# Arrancar servicios (sin Docker)
python scripts/stream_onchain_polling.py &
python agents/sniper_engine.py &
python agents/risk_filter.py &
python agents/execution_engine.py &
python agents/whale_tracker.py &
python scripts/telegram_bot.py &
```

---

## Instalación Research Engine (IM - 8GB RAM)

```bash
# En IM (fallback)
git clone https://github.com/tu-usuario/memecoin-agent.git
cd memecoins

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
- `launches`: Series temporales de micro-ventanas
- `token_features`: Features versionadas para ML
- `token_hypotheses`: Hipótesis falsables con validación bayesiana
- `model_performance`: Métricas de modelos (precision@top_k)
- `pending_trades`: Señales pendientes de ejecución
- `trades`: Historial de trades ejecutados
- `risk_events`: Eventos de evaluación de riesgo
- `tracked_wallets`: Wallets monitoreadas (whales, creators)

### SQLite WAL Mode (Obligatorio)

Todos los scripts deben ejecutar al conectar:

```python
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA busy_timeout=5000;")
conn.execute("PRAGMA synchronous=NORMAL;")
conn.execute("PRAGMA cache_size=-100000;")
```

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

### Capa C - Research Engine (IM)
- Entrena modelos XGBoost diariamente
- Genera hipótesis semanalmente con LLM
- Validación bayesiana de hipótesis
- Modo degradado: `heuristic_only` cuando IM no disponible

### Capa D - Execution Engine
- SQLite DB (WAL Mode)
- Retención: 24h máximo (configurable)
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
sqlite3 data/memecoin.db "SELECT COUNT(*) FROM tokens;"
sqlite3 data/memecoin.db "SELECT model_name, precision_at_10 FROM model_performance ORDER BY created_at DESC LIMIT 5;"
```

---

## Integración con SAA v7.2

### Enrutamiento LLM

```
Memecoin Agent (MB)
    ↓
LiteLLM Gateway (TO:8080)
    ↓
    ├─→ im-qwen32b    → IM:11434 (Qwen32B) [✅ Disponible]
    └─→ ew-qwen       → EW:11434 (Qwen3.5) [❌ Offline - ignorar]
```

**Nota**: WS está ocupado con COLMAP y no se usa. Research Engine va a IM.

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

### RPC Solana Free Tier (Sin coste)

| RPC | Coste | Límite | Notas |
|-----|-------|--------|-------|
| Helius Free Tier | $0 | 100k req/mes | Sin API key necesaria |
| QuickNode Free Tier | $0 | 100 req/día | Sin API key necesaria |
| RPC Pool | $0 | 100 req/día | Sin API key necesaria |

**Recomendación**: Usar Helius Free Tier (100k req/mes) o RPC público para MVP.

### APIs Públicas (Sin coste)

| API | Coste | Notas |
|-----|-------|-------|
| DexScreener API | $0 | Sin auth necesaria |
| CoinGecko API | $0 | Sin auth necesaria |
| SolanaFM API | $0 | Sin auth necesaria |
| RugCheck API | $0 | API pública de Solana |

---

## Costes Estimados (Free Tier)

| Componente | Coste Mensual | Notas |
|------------|---------------|-------|
| RPC Solana | **$0** | Helius Free Tier (100k req/mes) |
| DexScreener API | **$0** | Sin auth necesaria |
| CoinGecko API | **$0** | Sin auth necesaria |
| RugCheck API | **$0** | API pública de Solana |
| **Total Estimado** | **$0/mes** | Free tier suficiente para MVP |

---

## Troubleshooting

### Error: database is locked

**Causa**: SQLite sin WAL mode o múltiples escritores simultáneos.

**Solución**: Asegurar que todos los scripts ejecuten:
```python
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA busy_timeout=5000;")
```

### Error: No space left on device

**Causa**: SSD de 8GB lleno por logs y datos.

**Solución**:
1. Limpieza automática cada 6h (configurable)
2. Rotación de logs: 10MB máximo
3. Retención de datos: 24h máximo

### Error: Research Engine no responde

**Causa**: IM está ocupado o no disponible.

**Solución**: El sistema opera en modo `heuristic_only` automáticamente.

---

## Checklist de Validación Pre-Producción

### Hardware
- [ ] MB: 8GB RAM, 8GB SSD (eMMC)
- [ ] IM: 8GB RAM, 4+ cores
- [ ] TO: LiteLLM Gateway en puerto 8080

### Software
- [ ] SQLite con WAL mode
- [ ] Python 3.11+
- [ ] Dependencias instaladas (requirements.txt)
- [ ] Variables de entorno configuradas

### Red
- [ ] Tailscale conectado
- [ ] Acceso a LiteLLM Gateway
- [ ] Acceso a RPC Solana (Helius)

### Seguridad
- [ ] Límite hard 1 SOL por trade
- [ ] Stop-loss -30%
- [ ] Circuit breaker configurado
- [ ] Execution PIN configurado

---

## Próximos Pasos

1. **Validar hardware** (MB 8GB + IM 8GB)
2. **Instalar dependencias** (pip install -r requirements.txt)
3. **Inicializar SQLite** (scripts/init_db.py)
4. **Configurar variables** (config/.env)
5. **Arrancar servicios** (scripts/telegram_bot.py, agents/*.py)
6. **Validar sistema** (comandos de Telegram)

---

## Licencia

MIT