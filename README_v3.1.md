# Memecoin Agent v3.1 - Sistema Autónomo de Análisis y Trading de Memecoins en Solana

**Versión**: 3.1 (Incremento desde v3.0-ultralite-fixed)
**Estado**: SAA v10.0 compliant - 100% PostgreSQL, sin Docker, sin gRPC

---

## Arquitectura v3.1

```
┌─────────────────────────────────────────────────────────────────────┐
│           Memecoin Agent v3.1 (MB: 8GB RAM)                         │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa A - Sniper Engine v3.1                 │  │
│  │  ┌────────────────────┐                                       │  │
│  │  │  Polling RPC       │                                       │  │
│  │  │  (15s Helius)      │                                       │  │
│  │  └─────────┬──────────┘                                       │  │
│  │            │                                                   │  │
│  │            ▼                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  Sniper Engine v3.1: <1s detection (mejorado)           │   │  │
│  │  │  - tx_velocity, wallets, buy_ratio, liquidity          │   │  │
│  │  │  - Caching de features (nuevo)                          │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa B - Risk Filter v3.1                  │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  Risk Score v3.1: rugcheck, creator history,           │   │  │
│  │  │  - Bloqueo con nuevas fuentes (nuevo)                   │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa C - Research Engine v3.1              │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  XGBoost Models v3.1 (IM: CPU-only, 8GB RAM)            │   │  │
│  │  │  - Transfer learning (nuevo)                            │   │  │
│  │  │  - Hipótesis LLM (TO:8080)                              │   │  │
│  │  │  - Validación cada 6h                                   │   │  │
│  │  │  - Backtest diario                                      │   │  │
│  │  │  - Modo: heuristic_only (fallback)                      │   │  │
│  │  └────────────────────┘  └────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Capa D - Execution Engine v3.1             │  │
│  │  ┌────────────────────┐  ┌────────────────────────────────┐   │  │
│  │  │  PostgreSQL DB     │  │  Circuit Breaker v3.1          │   │  │
│  │  │  - Compartido      │  │  - Stop-loss -30%              │   │  │
│  │  │  - Retention 24h   │  │  - Max 1 SOL por trade         │   │  │
│  │  └────────────────────┘  └────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                       │
│                              ▼                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Whale Tracker v3.1 (Spray)                 │  │
│  │  - Copy-trading de whales cualificadas                       │  │
│  │  - Graduation rate > 15%, rug rate < 20%                     │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Distribución de Servicios

| Servicio | Nodo | RAM | Notas |
|----------|------|-----|-------|
| Sniper Engine | MB | 2GB | Detección heurística <1s (mejorado) |
| Risk Filter | MB | 1GB | Evaluación <500ms |
| Telegram Bot | MB | 1GB | Control remoto |
| PostgreSQL DB | TO | 2GB | Base de datos compartida (localhost:5432) |
| Streaming | MB | 1GB | Polling cada 15s (Helius) |
| Research Engine | IM | 8GB | ML + Training (CPU-only, fallback) |
| LLM Access | TO | - | Gateway LiteLLM (8080) |

---

## Nuevas Características v3.1

### 1. Optimización de Latencia Sniper (<1s)
- Caching de features para reducir latencia
- Optimización de heurísticas de detección
- Reducción de latencia de RPC calls

### 2. Mejoras en Risk Filter
- Integración de más APIs de verificación
- Análisis de contrato inteligente
- Análisis de transacciones previas

### 3. Training Engine Mejorado
- Transfer learning para modelos más rápidos
- Data augmentation para mejor generalización
- Early stopping para evitar overfitting

### 4. Backtest Framework Mejorado
- Simulación de slippage
- Métricas de Sharpe Ratio
- Análisis de drawdown

---

## Requisitos

### MacBook Pro 7,1 (MB)
- **OS**: Ubuntu 24.04
- **RAM**: 8 GB
- **CPU**: Intel Core i7 (2010)

### IM (Fallback Research)
- **RAM**: 8 GB
- **CPU**: 4+ cores
- **Storage**: 50 GB SSD

### TO (Gateway)
- **LiteLLM**: Puerto 8080
- **PostgreSQL**: Puerto 5432
- **Redis**: Puerto 6379

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

# Inicializar base de datos PostgreSQL
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

### PostgreSQL (única base de datos soportada)

Todos los scripts usan `get_conn()` de `memecoins/db.py` para conectar a PostgreSQL.

---

## Estrategias

### Capa A - Sniper Engine v3.1
- Detecta tokens nuevos en <1s (mejorado desde <2s)
- Score heurístico basado en:
  - Velocidad de transacciones
  - Wallets únicas
  - Ratio compra/venta
  - Liquidez añadida
  - Progreso bonding curve
  - Caching de features (nuevo)

### Capa B - Risk Filter v3.1
- Evalúa riesgo en <500ms
- Fuentes: RugCheck API, historial creador, concentración, nuevas APIs
- Bloquea si risk_score > 0.65

### Capa C - Research Engine v3.1 (IM)
- Entrena modelos XGBoost diariamente
- Genera hipótesis semanalmente con LLM
- Validación bayesiana de hipótesis
- Transfer learning (nuevo)
- Data augmentation (nuevo)
- Modo degradado: `heuristic_only` cuando IM no disponible

### Capa D - Execution Engine v3.1
- PostgreSQL DB (única fuente de verdad)
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
- **Latencia Sniper**: < 1s (mejorado desde <2s)
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

# Inspeccionar base de datos PostgreSQL
psql postgresql://saa:saa@localhost:5432/saa -c "SELECT COUNT(*) FROM tokens;"
psql postgresql://saa:saa@localhost:5432/saa -c "SELECT model_name, precision_at_10 FROM model_performance ORDER BY created_at DESC LIMIT 5;"
```

---

## Integración con SAA v10.0

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

### Error: connection refused

**Causa**: PostgreSQL no está accesible.

**Solución**: Verificar que el SSH tunnel esté activo:
```bash
ssh -L 5432:localhost:5432 eviwork@100.68.1.180
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
- [ ] PostgreSQL (única base de datos soportada)
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
3. **Inicializar PostgreSQL** (scripts/init_db.py)
4. **Configurar variables** (config/.env)
5. **Arrancar servicios** (scripts/telegram_bot.py, agents/*.py)
6. **Validar sistema** (comandos de Telegram)

---

## Licencia

MIT