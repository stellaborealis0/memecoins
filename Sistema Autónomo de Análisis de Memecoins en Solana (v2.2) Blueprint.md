# **Sistema Autónomo de Análisis de Memecoins en Solana (v2.2)**

## **Blueprint de Arquitectura e Implementación — Retroanálisis First**

**Fecha:** Marzo 2026
**Versión:** 2.2 (corrección de errores de numeración y formato)

---

### **Índice**

* Capítulo 0 — Principio fundamental v2.2: retroanálisis de 90 días obligatorio antes de producción
* Capítulo 1 — Objetivos, principios de diseño y stack técnico
* Capítulo 2 — Fuentes de datos históricos (90 días) (Helius, Bitquery, DexScreener, HuggingFace, CoinGecko) + prevención de leakage y survivorship bias
* Capítulo 3 — Arquitectura del sistema v2.2 completa con diagrama, flujo de datos y config de Hermes
* Capítulo 4 — Esquema de base de datos completo. Schema SQL completo (8 tablas, TimescaleDB, índices, versionado)
* Capítulo 5 — Scripts Python: especificación completa: backfill_historical.py, collect_onchain.py, label_targets.py, compute_features.py, train_models_all.py
* Capítulo 6 — Modelos ML: entrenamiento y métricas
* Capítulo 7 — Generación y validación de hipótesis. generate_hypotheses_llm.py, validate_hypotheses.py, backtest_report
* Capítulo 8 — Telegram Bot y control desde iOS. telegram_bot.py completo con todos los comandos + sistema de alertas automáticas
* Capítulo 9 — Docker Compose y despliegue. Dockerfile, entrypoint, requirements.txt, instalación nativa macOS
* Capítulo 10 — Plan de implementación para Cline. 7 prompts exactos para Cline (fase a fase) + checklist de validación pre-producción

---

## **CAPÍTULO 0 — Principio fundamental v2.2**

"No esperamos 3 meses. Tenemos 3 meses de historia disponible ahora mismo."

Pump.fun lleva operativo desde 2024. Existen fuentes públicas y RPC histórico que permiten reconstruir el historial completo de lanzamientos, precios, wallets y liquidez de los últimos 90+ días SIN necesidad de esperar producción.

Secuencia de arranque:

1. Fase 0 — Ingesta histórica (días 1–7): descarga y procesa 90 días de datos reales.
2. Fase 1 — Etiquetado y features (días 7–9): los outcomes ya ocurrieron, se etiquetan directamente.
3. Fase 2 — Entrenamiento inicial (días 9–11): modelos A/B/C entrenados con datos reales.
4. Fase 3 — Producción (día 11+): el sistema opera con modelos ya validados.

Dos modos operativos (obligatorio respetar el orden):

* **Modo Research/Defense:** análisis, alertas, paper trading. ACTIVO por defecto.
* **Modo Execution:** trades reales. DESACTIVADO hasta validación demostrada (mínimo 8 semanas consecutivas con precision@top10 >= 0.60 en datos vivos, no backtest).

Advertencia sobre el Modo Execution:

* Memecoins en Pump.fun son entorno adversarial. Bots MEV operan en milisegundos.
* Nunca operar con más del 1% del capital total por trade en producción inicial.
* Stop-loss on-chain obligatorio desde el primer trade real.
* El sistema NO ejecuta trades reales hasta que el usuario lo active explícitamente con `/mode execution confirm`.

---

## **CAPÍTULO 1 — Objetivos y principios de diseño**

### **1.1 Objetivo del sistema**

* Recoger automáticamente datos on-chain de tokens nuevos en Pump.fun / Solana.
* Predecir con tres modelos independientes:
  * **Modelo A:** pump ≥100% en primeras 24 h.
  * **Modelo B:** rug-pull en ≤48 h.
  * **Modelo C:** token todavía activo a los 7 días.
* Generar y refinar hipótesis falsables basadas en patrones on-chain reales (nunca inventadas por el LLM sin contraste empírico).
* Ejecutar en macOS / Ubuntu 24/7 (SAA v7.2: nodo MB o IM).
* Control remoto desde iOS vía SSH + Telegram.

### **1.2 Principios de diseño**

| Principio | Descripción |
| :--- | :--- |
| Retroanálisis first | Los modelos se entrenan con 90 días de historia antes de ver un solo token nuevo en producción. |
| On-chain > Social | 70% features on-chain, 20% microestructura, 10% social ligero máximo. |
| Hermes = orquestador | Hermes llama scripts Python. Nunca hace scraping masivo ni parsing HTML directo. |
| Versionado estricto | feature_version + model_version en cada fila. Sin esto no hay reproducibilidad ni comparación de experimentos. |
| Métricas de trading | precision@top_k como métrica principal. Accuracy es engañosa en clases muy desbalanceadas. |
| Modelos separados | Nunca mezclar pump, rug y survival en un único label ni en un único modelo. |
| LLM fuera del loop rápido | LLM solo para análisis offline semanal y generación de hipótesis. Nunca en la ruta crítica de decisión en tiempo real. |
| Defense first | El sistema es más valioso evitando rugs que encontrando pumps. El edge principal es preservación de capital. |

### **1.3 Stack técnico**

| Componente | Tecnología | Justificación |
| :--- | :--- | :--- |
| Agente orquestador | Hermes (Nous Research) | Open-source, MIT, loop de tareas nativo, Telegram integrado, compatible macOS/Linux. |
| LLM razonamiento | LiteLLM Gateway (TO:8080) → Qwen3.5 / phi local | Sin dependencia cloud obligatoria. Fallback local siempre disponible. |
| LLM auxiliar | Ollama + Llama-3-8B / Mistral-7B cuantizado | Para tareas baratas y pruebas de prompts sin consumir cuota. |
| On-chain / ETL | Python + requests + solana.py + RPC | Scraper robusto, sin dependencia de UI web. |
| Base de datos | PostgreSQL 16 + TimescaleDB | Series temporales financieras + versionado de features + índices ricos. |
| ML / estadística | XGBoost + sklearn + pandas | Ligero, CPU suficiente, métricas correctas. |
| Control remoto | SSH + Telegram bot (python-telegram-bot) | Comandos y alertas desde iOS, sin coste adicional. |

---

## **CAPÍTULO 2 — Fuentes de datos históricos (90 días)**

Este es el cambio estructural clave de v2.2: el sistema NO arranca en blanco.

### **2.1 Prioridad de fuentes**

| Prioridad | Fuente | Tipo | Coste | Uso principal |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Dump CSV/Parquet comunitario (Hugging Face) | Bulk descarga | Gratis | Backfill masivo inicial, miles de tokens de una vez |
| 2 | Bitquery GraphQL API | REST/GraphQL | Free tier suficiente | Tokens nuevos + primeras horas de actividad por rango de fechas |
| 3 | Helius RPC histórico | JSON-RPC | Free tier ~100k req/mes | Transacciones, wallets y liquidez por token individual |
| 4 | DexScreener API | REST | Sin auth necesaria | Precios y volumen histórico por token |
| 5 | CoinGecko API | REST | Sin auth necesaria | Contexto BTC histórico (precio, dominancia, volumen) |

### **2.2 Endpoints y ejemplos de llamada**

#### DexScreener — precio y volumen histórico por token

```bash
GET https://api.dexscreener.com/latest/dex/tokens/{token_address}
# Sin API key. Devuelve precio actual, volumen 24h, liquidez, variación.
```

#### CoinGecko — BTC últimos 90 días

```bash
GET https://api.coingecko.com/api/v3/coins/bitcoin/market_chart \
    ?vs_currency=usd&days=90&interval=hourly
# Sin API key. Devuelve array de [timestamp, price_usd].
```

#### Helius — transacciones históricas del programa Pump.fun

```json
POST https://mainnet.helius-rpc.com/?api-key=TU_KEY
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "getSignaturesForAddress",
  "params": [
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
    {"limit": 1000, "before": "ULTIMA_FIRMA_PAGINACION"}
  ]
}
# La dirección es el programa oficial de Pump.fun en Solana mainnet.
# Paginar hacia atrás hasta cubrir 90 días.
```

#### Bitquery — tokens nuevos en Pump.fun por rango de fechas

```graphql
POST https://graphql.bitquery.io/
Header: X-API-KEY: TU_KEY

query {
  solana {
    instructions(
      programId: {is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}
      date: {between: ["2025-12-22", "2026-03-22"]}
      instruction: {callPath: {is: "create"}}
    ) {
      block { timestamp { time } }
      accounts { address }
      transaction { signature }
    }
  }
}
```

#### Hugging Face — dump comunitario de Pump.fun

```bash
# Buscar en: https://huggingface.co/datasets?search=pump.fun
# Datasets relevantes disponibles: pump-fun-tokens, solana-memecoin-launches
# Descarga directa en parquet, sin auth para datasets públicos.
pip install datasets
from datasets import load_dataset
ds = load_dataset("nombre/pump-fun-tokens")
```

### **2.3 Etiquetado automático con datos históricos**

Con 90 días de historia el outcome ya ocurrió. El etiquetado es determinista:

```python
# Modelo A — pump en 24h
pump_100pc_24h = (price_at_t24h / price_initial) >= 2.0

# Modelo B — rug pull en 48h
rug_pull_48h = (
    (liquidity_withdrawn_pct_at_t48h > 0.80)
    or (volume_at_t48h == 0 and volume_at_t2h > 0)
    or (top_10_wallets_sold_pct_at_t48h > 0.90)
)

# Modelo C — supervivencia 7 días
still_active_7d = (
    liquidity_pool_at_t7d > LIQUIDITY_MIN_THRESHOLD
    and volume_at_t7d > percentile_25_all_tokens
)
```

### **2.4 Prevención de sesgo de supervivencia**

**Problema:** los tokens que "ganaron" en el pasado son visibles precisamente porque sobrevivieron. Los miles que murieron en minutos tienen datos escasos.

**Solución obligatoria:**

* Incluir TODOS los tokens descubiertos en el backfill, no solo los que tienen datos completos. Los tokens con datos incompletos tras t+2h se etiquetan como `rug_pull_48h = True` por defecto (heurística conservadora).
* Registrar en `backfill_log` cuántos tokens se descartaron y por qué.
* Nunca filtrar tokens por "tienen suficientes datos" antes del etiquetado.
* El modelo debe aprender también de los casos con señal mínima.

### **2.5 Prevención de leakage temporal**

**Problema:** features calculadas en ventanas largas (60 min, 4h) pueden contener información del outcome si el pump ocurrió dentro de esa ventana.

**Regla estricta:**

* **Modelo A (pump 24h):** usar SOLO features de ventana 0–30 min.
* **Modelo B (rug 48h):** usar SOLO features de ventana 0–2h.
* **Modelo C (survival 7d):** puede usar features hasta 4h, nunca más.
* En `token_features`: columna `max_feature_window_minutes` documenta la ventana máxima usada para cada fila.
* El split train/test es SIEMPRE temporal (nunca aleatorio):
  * Train: tokens lanzados antes de fecha de corte.
  * Test: tokens lanzados después de fecha de corte.

---

## **CAPÍTULO 3 — Arquitectura del sistema v2.2**

### **3.1 Diagrama general**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    macOS / Ubuntu 24/7 — SAA v7.2                      │
│                                                                         │
│  ┌─────────────────────────┐   ┌─────────────────────────────────────┐  │
│  │    Hermes Agent         │   │   Python ETL + ML Scripts           │  │
│  │    (orquestador)        │   │                                     │  │
│  │                         │   │  scripts/                           │  │
│  │  tasks:                 │   │  ├── backfill_historical.py         │  │
│  │  - backfill    (1x)     │   │  ├── collect_onchain.py             │  │
│  │  - collect     (*/15m)  │   │  ├── compute_features.py            │  │
│  │  - features    (*/1h)   │   │  ├── label_targets.py               │  │
│  │  - label       (*/1h)   │   │  ├── train_models_all.py            │  │
│  │  - train       (3am)    │   │  ├── generate_hypotheses_llm.py     │  │
│  │  - hypotheses  (MON)    │   │  ├── validate_hypotheses.py         │  │
│  │  - validate    (*/6h)   │   │  ├── backtest_report.py             │  │
│  │  - backtest    (*/24h)  │   │  └── telegram_bot.py                │  │
│  └──────────┬──────────────┘   └──────────────┬────────────────────┘   │
│             │                                  │                        │
│             └──────────────┬───────────────────┘                        │
│                            │                                            │
│           ┌────────────────▼────────────────────────────────────────┐   │
│           │           PostgreSQL 16 + TimescaleDB                   │   │
│           │                                                         │   │
│           │  tokens              token_features (versionado)        │   │
│           │  launches            token_hypotheses                   │   │
│           │  btc_context         model_performance                  │   │
│           │  backfill_log        agent_execution_log                │   │
│           └─────────────────────────────────────────────────────────┘   │
│                            │                                            │
│           ┌────────────────▼────────────────────────────────────────┐   │
│           │   Telegram Bot — control iOS                            │   │
│           │   /status /top_pump /top_rug /hypotheses                │   │
│           │   /backtest_report /pause /resume /mode                 │   │
│           └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┬──────────────────┐
          │                  │                  │                  │
     ┌────▼─────┐   ┌────────▼────────┐  ┌─────▼──────┐  ┌───────▼──────┐
     │  iOS     │   │  LiteLLM        │  │ Helius RPC │  │ DexScreener  │
     │  SSH +   │   │  Gateway        │  │ Bitquery   │  │ CoinGecko    │
     │ Telegram │   │  TO:8080        │  │ Solana FM  │  │ HuggingFace  │
     └──────────┘   │  Qwen/phi local │  └────────────┘  └──────────────┘
                    └─────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│  WORKSTATION (exploración e inferencia local)                      │
│  - Jupyter para EDA de datos históricos                            │
│  - Ollama + Llama-3-8B / Mistral-7B para pruebas de prompts        │
│  - XGBoost / sklearn en CPU (sin GPU necesaria para MVP)           │
└────────────────────────────────────────────────────────────────────┘
```

### **3.2 Flujo de datos completo**

```
FASE 0 — BACKFILL (una sola vez)
────────────────────────────────
backfill_historical.py
  │
  ├── Descarga dump CSV/Parquet de HuggingFace (si existe)
  ├── Query Bitquery: todos los tokens Pump.fun en rango -90d a hoy
  ├── Para cada token: Helius RPC → txs, wallets, liquidez por ventana
  ├── DexScreener → precio histórico por token
  ├── CoinGecko → BTC context por hora
  │
  ├── INSERT INTO tokens (data_source='backfill_historical')
  ├── INSERT INTO launches (ventanas 0-5m, 5-60m, 60-240m)
  ├── INSERT INTO btc_context
  └── Registra progreso en backfill_log cada 500 tokens

          │
          ▼

label_targets.py
  └── Para cada token con datos suficientes:
      - pump_100pc_24h  → precio t+24h / precio_inicial >= 2.0
      - rug_pull_48h    → heurísticas de liquidez + wallets
      - still_active_7d → liquidez y volumen en t+7d
      - UPDATE tokens SET pump_100pc_24h=..., rug_pull_48h=..., still_active_7d=...

          │
          ▼

compute_features.py
  └── Para cada token etiquetado:
      - Calcula features desde launches + btc_context
      - INSERT INTO token_features (feature_version='v1-onchain-minimal')

          │
          ▼

train_models_all.py
  └── Split temporal (nunca aleatorio):
      - Train: tokens creados antes de fecha_corte
      - Test:  tokens creados después de fecha_corte
      - Entrena modelo A, B, C con XGBoost
      - Evalúa precision@top_10, precision@top_20, AUC, F1
      - INSERT INTO model_performance

FASE 1 — PRODUCCIÓN (continua, cada 15 min)
────────────────────────────────────────────
collect_onchain.py (*/15m)
  └── Nuevos tokens en Pump.fun → INSERT INTO tokens (data_source='live_rpc')
      └── Muestras en t+5m, t+15m, t+60m, t+4h → INSERT INTO launches

compute_features.py (*/1h)
  └── Calcula features para tokens nuevos sin features todavía

label_targets.py (*/1h)
  └── Etiqueta tokens con suficiente historia (>24h, >48h, >7d)

train_models_all.py (3am diario)
  └── Reentrenamiento incremental con datos nuevos

generate_hypotheses_llm.py (lunes 4am)
  └── Top 20 winners + top 20 losers → LLM → hipótesis → token_hypotheses

validate_hypotheses.py (*/6h)
  └── Contrasta hipótesis activas con tokens nuevos → actualiza posterior_probability

backtest_report.py (*/24h)
  └── Genera informe de precision@top_k en últimas 24h → alerta Telegram
```

### **3.3 Hermes: configuración de tareas**

```toml
# config/hermes-memecoin.toml

[agent]
name = "memecoin-analyst"
model = "http://100.68.1.180:8080/v1"   # LiteLLM Gateway SAA
model_id = "qwen3.5"
temperature = 0.4
max_tokens = 2000

[memory]
type = "sqlite"
path = "/data/hermes/memory.db"

[tasks.backfill]
run = "python scripts/backfill_historical.py"
schedule = "once"
on_startup_if_empty = true

[tasks.collect]
run = "python scripts/collect_onchain.py"
schedule = "*/15 * * * *"

[tasks.features]
run = "python scripts/compute_features.py --version v1-onchain-minimal"
schedule = "0 * * * *"

[tasks.label]
run = "python scripts/label_targets.py"
schedule = "30 * * * *"

[tasks.train]
run = "python scripts/train_models_all.py"
schedule = "0 3 * * *"

[tasks.hypotheses]
run = "python scripts/generate_hypotheses_llm.py"
schedule = "0 4 * * MON"

[tasks.validate]
run = "python scripts/validate_hypotheses.py"
schedule = "0 */6 * * *"

[tasks.backtest]
run = "python scripts/backtest_report.py"
schedule = "0 8 * * *"

[telegram]
enabled = true
token_env = "TELEGRAM_BOT_TOKEN"
allowed_users_env = "TELEGRAM_ALLOWED_USERS"
```

### **3.4 Variables de entorno requeridas**

```bash
# config/.env

# Base de datos
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=memecoin_db
POSTGRES_USER=memecoin_user
POSTGRES_PASSWORD=TU_PASSWORD

# RPC y APIs on-chain
HELIUS_API_KEY=TU_KEY
BITQUERY_API_KEY=TU_KEY
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=${HELIUS_API_KEY}

# LLM
LITELLM_ENDPOINT=http://100.68.1.180:8080/v1
LITELLM_MODEL=qwen3.5
LITELLM_API_KEY=TU_KEY_LOCAL

# Telegram
TELEGRAM_BOT_TOKEN=TU_TOKEN
TELEGRAM_ALLOWED_USERS=TU_USER_ID

# Modo operativo
EXECUTION_MODE=research   # 'research' | 'execution'
MAX_POSITION_SOL=0.5      # solo activo si EXECUTION_MODE=execution
```

---

## **CAPÍTULO 4 — Esquema de base de datos completo**

### **4.1 tokens**

```sql
CREATE TABLE tokens (
  id                  SERIAL PRIMARY KEY,
  address             VARCHAR(255) UNIQUE NOT NULL,
  name                VARCHAR(255),
  symbol              VARCHAR(50),
  chain               VARCHAR(50) DEFAULT 'solana',
  creator_address     VARCHAR(255),
  created_at          TIMESTAMP NOT NULL,

  -- Datos iniciales del lanzamiento
  initial_liquidity   BIGINT,
  initial_market_cap  BIGINT,
  initial_holders     INTEGER,
  initial_price_usd   FLOAT,

  -- Origen del dato
  data_source         VARCHAR(50),
  -- valores: 'backfill_historical' | 'live_rpc'

  -- Targets (rellenados por label_targets.py)
  pump_100pc_24h      BOOLEAN,
  rug_pull_48h        BOOLEAN,
  still_active_7d     BOOLEAN,

  -- Predicciones actuales de los modelos
  prob_pump_24h       FLOAT,
  prob_rug_48h        FLOAT,
  prob_survival_7d    FLOAT,

  -- Versiones de modelo usadas en la última predicción
  model_A_version     VARCHAR(50),
  model_B_version     VARCHAR(50),
  model_C_version     VARCHAR(50),

  -- Control
  label_completed     BOOLEAN DEFAULT FALSE,
  features_computed   BOOLEAN DEFAULT FALSE,
  predicted_at        TIMESTAMP
);

CREATE INDEX idx_tokens_created_at  ON tokens (created_at DESC);
CREATE INDEX idx_tokens_source      ON tokens (data_source);
CREATE INDEX idx_tokens_probs       ON tokens (prob_pump_24h DESC, prob_rug_48h ASC);
CREATE INDEX idx_tokens_unlabeled   ON tokens (label_completed) WHERE label_completed = FALSE;
```

### **4.2 launches (TimescaleDB hypertable)**

```sql
CREATE TABLE launches (
  time                        TIMESTAMP NOT NULL,
  token_id                    INTEGER   NOT NULL REFERENCES tokens(id),

  -- Precio en el momento de la muestra
  price_usd                   FLOAT,

  -- Volumen acumulado desde lanzamiento hasta t
  volume_5m                   BIGINT,
  volume_15m                  BIGINT,
  volume_60m                  BIGINT,
  volume_240m                 BIGINT,

  -- Transacciones por ventana
  txs_0_5m                    INTEGER,
  txs_5_60m                   INTEGER,
  txs_60_240m                 INTEGER,

  -- Wallets únicas acumuladas
  unique_wallets_0_10m        INTEGER,
  unique_wallets_0_60m        INTEGER,

  -- Dirección del flujo
  buy_tx_0_30m                INTEGER,
  sell_tx_0_30m               INTEGER,

  -- Estado de liquidez
  liquidity_pool_before       BIGINT,
  liquidity_pool_after        BIGINT,
  is_liquidity_removed        BOOLEAN DEFAULT FALSE,

  -- Concentración de holders
  top_10_wallets_pct_0_1h     FLOAT,
  gini_concentration_0_1h     FLOAT,

  PRIMARY KEY (time, token_id)
);

SELECT create_hypertable('launches', 'time', if_not_exists => TRUE);

CREATE INDEX idx_launches_token ON launches (token_id, time DESC);
```

### **4.3 btc_context**

```sql
CREATE TABLE btc_context (
  time                TIMESTAMP PRIMARY KEY,
  price_usd           FLOAT,
  volume_24h          BIGINT,
  change_pct_1h       FLOAT,
  change_pct_6h       FLOAT,
  change_pct_24h      FLOAT,
  dominance_pct       FLOAT
);

SELECT create_hypertable('btc_context', 'time', if_not_exists => TRUE);
```

### **4.4 token_features (versionado)**

```sql
CREATE TABLE token_features (
  id                          SERIAL PRIMARY KEY,
  token_id                    INTEGER NOT NULL REFERENCES tokens(id),

  -- Versionado obligatorio
  feature_version             VARCHAR(50) NOT NULL,
  -- valores: 'v1-onchain-minimal' | 'v2-onchain-plus' | 'v3-micro'
  model_version               VARCHAR(50),

  -- Ventana máxima usada (para detectar leakage)
  max_feature_window_minutes  INTEGER,

  -- 1. Velocidad de transacciones
  tx_velocity_0_5m            FLOAT,   -- txs / 5 min
  tx_velocity_5_60m           FLOAT,   -- txs / 55 min
  tx_velocity_60_240m         FLOAT,   -- txs / 180 min

  -- 2. Wallets únicas
  unique_wallets_0_10m        INTEGER,
  unique_wallets_0_60m        INTEGER,

  -- 3. Ratio compra/venta
  buy_tx_ratio_0_30m          FLOAT,   -- buy_tx / (buy_tx + sell_tx), ventana 0-30 min

  -- 4. Liquidez
  liquidity_add_0_10m         BOOLEAN,
  liquidity_remove_0_2h       BOOLEAN,
  liquidity_drop_1_2h_pct     FLOAT,   -- (liq_t1h - liq_t2h) / liq_t1h

  -- 5. Concentración de holders
  top_10_wallets_pct_0_1h     FLOAT,
  gini_concentration_0_1h     FLOAT,

  -- 6. Contexto BTC en el momento del lanzamiento
  btc_change_pct_6h           FLOAT,
  btc_dominance_pct           FLOAT,

  -- 7. Timing del lanzamiento
  launch_hour_utc             INTEGER,   -- 0-23
  launch_day_of_week          INTEGER,   -- 0=lunes, 6=domingo

  -- 8. Microestructura (v2 en adelante)
  avg_trade_size_0_30m        FLOAT,     -- SOL por trade medio
  slippage_0_30m              FLOAT,

  created_at                  TIMESTAMP DEFAULT NOW(),
  updated_at                  TIMESTAMP DEFAULT NOW(),

  UNIQUE (token_id, feature_version)
);

CREATE INDEX idx_tf_version ON token_features (feature_version);
CREATE INDEX idx_tf_core    ON token_features (
  feature_version,
  tx_velocity_0_5m DESC,
  unique_wallets_0_10m DESC
);
```

### **4.5 token_hypotheses**

```sql
CREATE TABLE token_hypotheses (
  id                      SERIAL PRIMARY KEY,

  hypothesis_text         TEXT NOT NULL,

  -- Condiciones estructuradas para validación automática
  conditions_json         JSONB,
  -- Ejemplo:
  -- [
  --   {"feature": "tx_velocity_0_5m",    "op": ">",  "threshold": 5.0},
  --   {"feature": "buy_tx_ratio_0_30m",  "op": ">",  "threshold": 0.70},
  --   {"feature": "liquidity_remove_0_2h","op": "=", "threshold": false}
  -- ]

  target_model            VARCHAR(20),
  -- valores: 'pump' | 'rug' | 'survival'

  feature_version         VARCHAR(50),
  model_version           VARCHAR(50),

  -- Probabilidad estimada por el LLM al generar
  estimated_probability   FLOAT,
  confidence_interval     FLOAT,

  -- Actualización bayesiana (Beta distribution)
  prior_probability       FLOAT DEFAULT 0.5,
  posterior_probability   FLOAT DEFAULT 0.5,
  bayes_factor            FLOAT,

  -- Validación empírica acumulada
  total_tested            INTEGER DEFAULT 0,
  validated_count         INTEGER DEFAULT 0,
  refuted_count           INTEGER DEFAULT 0,

  -- Origen de la hipótesis
  generated_by            VARCHAR(50),
  -- valores: 'llm-qwen' | 'llm-phi' | 'manual'
  generated_on_data       VARCHAR(50),
  -- valores: 'backfill-90d' | 'live-week-N'

  -- Estado
  active                  BOOLEAN DEFAULT TRUE,

  created_at              TIMESTAMP DEFAULT NOW(),
  last_updated            TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_hyp_prob     ON token_hypotheses (posterior_probability DESC);
CREATE INDEX idx_hyp_model    ON token_hypotheses (target_model);
CREATE INDEX idx_hyp_active   ON token_hypotheses (active) WHERE active = TRUE;
CREATE INDEX idx_hyp_versions ON token_hypotheses (feature_version, model_version);
```

### **4.6 model_performance**

```sql
CREATE TABLE model_performance (
  id                  SERIAL PRIMARY KEY,

  model_name          VARCHAR(50) NOT NULL,
  -- valores: 'model-A-pump' | 'model-B-rug' | 'model-C-survival'

  feature_version     VARCHAR(50),
  model_version       VARCHAR(50),

  -- Rango de datos usado
  train_start         DATE,
  train_end           DATE,
  test_start          DATE,
  test_end            DATE,
  n_tokens_train      INTEGER,
  n_tokens_test       INTEGER,
  pct_positive        FLOAT,   -- % de clase positiva (para detectar desbalance)

  -- Métricas principales
  precision_at_10     FLOAT,
  precision_at_20     FLOAT,
  recall_at_10        FLOAT,
  auc_roc             FLOAT,
  f1_score            FLOAT,
  log_loss            FLOAT,

  -- Ruta del modelo serializado
  model_file_path     VARCHAR(500),

  experiment_notes    TEXT,
  created_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_mp_model   ON model_performance (model_name, model_version);
CREATE INDEX idx_mp_created ON model_performance (created_at DESC);
```

### **4.7 backfill_log**

```sql
CREATE TABLE backfill_log (
  id                  SERIAL PRIMARY KEY,
  source              VARCHAR(50),
  -- valores: 'huggingface' | 'bitquery' | 'helius' | 'dexscreener'

  date_range_from     DATE,
  date_range_to       DATE,

  tokens_discovered   INTEGER DEFAULT 0,
  tokens_stored       INTEGER DEFAULT 0,
  tokens_skipped      INTEGER DEFAULT 0,
  launches_stored     INTEGER DEFAULT 0,

  last_checkpoint     VARCHAR(255),
  -- firma o cursor para reanudar si se interrumpe

  status              VARCHAR(20) DEFAULT 'running',
  -- valores: 'running' | 'completed' | 'failed' | 'partial'

  error_message       TEXT,
  started_at          TIMESTAMP DEFAULT NOW(),
  ended_at            TIMESTAMP
);
```

### **4.8 agent_execution_log**

```sql
CREATE TABLE agent_execution_log (
  id                    SERIAL PRIMARY KEY,
  task_name             VARCHAR(255),
  status                VARCHAR(50),
  -- valores: 'success' | 'failed' | 'partial'

  error_message         TEXT,
  started_at            TIMESTAMP,
  ended_at              TIMESTAMP,

  tokens_processed      INTEGER DEFAULT 0,
  data_points_collected INTEGER DEFAULT 0,

  extra_json            JSONB   -- para métricas adicionales específicas de cada tarea
);

CREATE INDEX idx_ael_task    ON agent_execution_log (task_name, started_at DESC);
CREATE INDEX idx_ael_status  ON agent_execution_log (status);
```

### **4.9 Script de inicialización completo**

```bash
# Ejecutar una sola vez para crear toda la estructura
psql -U memecoin_user -d memecoin_db -f schema_v2.2.sql

# Verificar que TimescaleDB está activo
psql -U memecoin_user -d memecoin_db -c "SELECT extname FROM pg_extension;"
# Debe mostrar: timescaledb

# Verificar hypertables
psql -U memecoin_user -d memecoin_db -c "SELECT * FROM timescaledb_information.hypertables;"
# Debe mostrar: launches, btc_context
```

---

## **CAPÍTULO 5 — Scripts Python: especificación completa**

### **5.1 scripts/backfill_historical.py**

```python
"""
backfill_historical.py

Descarga y almacena 90 días de historia de tokens Pump.fun.

Se ejecuta UNA SOLA VEZ. Idempotente: ON CONFLICT DO NOTHING en todos los inserts.

Reanuda desde el último checkpoint si se interrumpe.
"""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import Optional
import requests
import psycopg2
from solana.rpc.api import Client

# --- Configuración ---

BACKFILL_DAYS         = 90
BACKFILL_BATCH_SIZE   = 500
PUMP_PROGRAM_ADDRESS  = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
HELIUS_API_KEY        = os.getenv("HELIUS_API_KEY")
BITQUERY_API_KEY      = os.getenv("BITQUERY_API_KEY")
SOLANA_RPC_URL        = os.getenv("SOLANA_RPC_URL")
DB_DSN                = os.getenv("DATABASE_URL")

DATE_FROM = datetime.utcnow() - timedelta(days=BACKFILL_DAYS)
DATE_TO   = datetime.utcnow()

# --- Lógica principal ---

def main():
    conn = psycopg2.connect(DB_DSN)

    # 1. Verificar si ya hay un backfill completado
    if backfill_already_completed(conn):
        logging.info("Backfill ya completado. Saliendo.")
        return

    # 2. Obtener último checkpoint
    checkpoint = get_last_checkpoint(conn)

    # 3. Intentar fuentes en orden de prioridad
    sources = ["huggingface", "bitquery", "helius"]
    for source in sources:
        try:
            logging.info(f"Intentando fuente: {source}")
            if source == "huggingface":
                tokens = fetch_from_huggingface()
            elif source == "bitquery":
                tokens = fetch_from_bitquery(DATE_FROM, DATE_TO, checkpoint)
            elif source == "helius":
                tokens = fetch_from_helius(checkpoint)

            if tokens:
                process_tokens(conn, tokens, source)
                break
        except Exception as e:
            logging.error(f"Fuente {source} falló: {e}")
            continue

    # 4. Finalizar
    mark_backfill_completed(conn)
    conn.close()
    logging.info("Backfill completado.")


def fetch_from_huggingface() -> list:
    """
    Intenta cargar dataset público de Pump.fun desde HuggingFace.

    Buscar: huggingface.co/datasets?search=pump.fun

    Devuelve lista de dicts con campos: address, name, symbol,
    created_at, initial_liquidity, initial_price_usd.
    """
    from datasets import load_dataset
    ds = load_dataset("datasets/pump-fun-tokens", split="train")
    return [dict(row) for row in ds]


def fetch_from_bitquery(date_from: datetime, date_to: datetime,
                        checkpoint: Optional[str]) -> list:
    """
    Query GraphQL a Bitquery para obtener tokens nuevos en Pump.fun
    en el rango de fechas dado.
    """
    query = """
    query($from: ISO8601DateTime, $to: ISO8601DateTime) {
      solana {
        instructions(
          programId: {is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}
          date: {between: [$from, $to]}
          instruction: {callPath: {is: "create"}}
          options: {limit: 5000}
        ) {
          block { timestamp { time } }
          accounts { address isWritable isSigner }
          transaction { signature }
        }
      }
    }
    """

    variables = {
        "from": date_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to":   date_to.strftime("%Y-%m-%dT%H:%M:%SZ")
    }

    resp = requests.post(
        "https://graphql.bitquery.io/",
        json={"query": query, "variables": variables},
        headers={"X-API-KEY": BITQUERY_API_KEY},
        timeout=60
    )
    resp.raise_for_status()
    instructions = resp.json()["data"]["solana"]["instructions"]
    return parse_bitquery_instructions(instructions)


def fetch_from_helius(checkpoint: Optional[str]) -> list:
    """
    Pagina hacia atrás en las firmas del programa Pump.fun
    usando Helius RPC hasta cubrir BACKFILL_DAYS días.
    """
    client = Client(SOLANA_RPC_URL)
    tokens = []
    before = checkpoint
    cutoff = datetime.utcnow() - timedelta(days=BACKFILL_DAYS)

    while True:
        params = {"limit": 1000}
        if before:
            params["before"] = before

        resp = client.get_signatures_for_address(PUMP_PROGRAM_ADDRESS, **params)
        sigs = resp.value

        if not sigs:
            break

        for sig in sigs:
            block_time = datetime.utcfromtimestamp(sig.block_time)
            if block_time < cutoff:
                return tokens

            tokens.append({
                "signature": str(sig.signature),
                "block_time": block_time
            })

        before = str(sigs[-1].signature)
        time.sleep(0.1)  # respetar rate limit

    return tokens


def process_tokens(conn, tokens: list, source: str):
    """
    Para cada token:
    1. INSERT INTO tokens (ON CONFLICT DO NOTHING)
    2. Enriquecer con DexScreener (precio histórico)
    3. INSERT INTO launches
    4. Guardar checkpoint cada BACKFILL_BATCH_SIZE tokens
    """
    cursor = conn.cursor()
    for i, token in enumerate(tokens):
        try:
            # Enriquecer con DexScreener
            price_data = fetch_dexscreener(token.get("address", ""))

            cursor.execute("""
                INSERT INTO tokens
                  (address, name, symbol, created_at, data_source,
                   initial_price_usd, initial_liquidity)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (address) DO NOTHING
            """, (
                token.get("address"),
                token.get("name"),
                token.get("symbol"),
                token.get("created_at"),
                source,
                price_data.get("initial_price_usd"),
                price_data.get("initial_liquidity")
            ))

            # Guardar checkpoint periódicamente
            if i % BACKFILL_BATCH_SIZE == 0:
                conn.commit()
                save_checkpoint(conn, token.get("signature", ""), source, i)
                logging.info(f"Checkpoint: {i} tokens procesados")
        except Exception as e:
            logging.error(f"Error procesando token {token}: {e}")
            continue

    conn.commit()


def fetch_dexscreener(address: str) -> dict:
    """
    Obtiene precio y liquidez actuales/históricos de DexScreener.
    Sin API key requerida.
    """
    if not address:
        return {}

    try:
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{address}",
            timeout=10
        )
        resp.raise_for_status()
        pairs = resp.json().get("pairs", [])
        if not pairs:
            return {}

        p = pairs[0]
        return {
            "initial_price_usd": float(p.get("priceUsd", 0) or 0),
            "initial_liquidity": int(p.get("liquidity", {}).get("usd", 0) or 0)
        }
    except Exception:
        return {}


def backfill_already_completed(conn) -> bool:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM backfill_log
        WHERE status = 'completed'
        LIMIT 1
    """)
    return cursor.fetchone() is not None


def get_last_checkpoint(conn) -> Optional[str]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT last_checkpoint FROM backfill_log
        WHERE status IN ('running', 'partial')
        ORDER BY started_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    return row[0] if row else None


def save_checkpoint(conn, checkpoint: str, source: str, count: int):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO backfill_log
          (source, date_range_from, date_range_to,
           tokens_stored, last_checkpoint, status)
        VALUES (%s, %s, %s, %s, %s, 'running')
        ON CONFLICT DO NOTHING
    """, (source, DATE_FROM.date(), DATE_TO.date(), count, checkpoint))
    conn.commit()


def mark_backfill_completed(conn):
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE backfill_log SET status = 'completed', ended_at = NOW()
        WHERE status = 'running'
    """)
    conn.commit()


def parse_bitquery_instructions(instructions: list) -> list:
    tokens = []
    for instr in instructions:
        accounts = instr.get("accounts", [])
        token_addr = next(
            (a["address"] for a in accounts if a.get("isWritable")), None
        )
        tokens.append({
            "address":    token_addr,
            "created_at": instr["block"]["timestamp"]["time"],
            "signature":  instr["transaction"]["signature"]
        })
    return tokens


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

### **5.2 scripts/collect_onchain.py**

```python
"""
collect_onchain.py

Monitoriza nuevos tokens en Pump.fun en tiempo real.

Frecuencia: cada 15 minutos via Hermes/cron.
"""

import os
import logging
from datetime import datetime, timedelta
import psycopg2
from solana.rpc.api import Client

PUMP_PROGRAM_ADDRESS = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
SOLANA_RPC_URL       = os.getenv("SOLANA_RPC_URL")
DB_DSN               = os.getenv("DATABASE_URL")
LOOKBACK_MINUTES     = 20  # margen extra sobre los 15 min del cron


def main():
    conn   = psycopg2.connect(DB_DSN)
    client = Client(SOLANA_RPC_URL)
    cutoff = datetime.utcnow() - timedelta(minutes=LOOKBACK_MINUTES)

    new_tokens = fetch_new_tokens(client, cutoff)
    stored     = 0

    for token in new_tokens:
        if insert_token(conn, token):
            stored += 1

    log_execution(conn, "collect_onchain", stored)
    conn.commit()
    conn.close()
    logging.info(f"collect_onchain: {stored} tokens nuevos almacenados")


def fetch_new_tokens(client: Client, cutoff: datetime) -> list:
    tokens = []
    resp   = client.get_signatures_for_address(PUMP_PROGRAM_ADDRESS, limit=200)

    for sig in resp.value:
        block_time = datetime.utcfromtimestamp(sig.block_time)
        if block_time < cutoff:
            break
        tokens.append({
            "signature":  str(sig.signature),
            "created_at": block_time
        })
    return tokens


def insert_token(conn, token: dict) -> bool:
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tokens (address, created_at, data_source)
        VALUES (%s, %s, 'live_rpc')
        ON CONFLICT (address) DO NOTHING
        RETURNING id
    """, (token["signature"], token["created_at"]))
    return cursor.fetchone() is not None


def log_execution(conn, task: str, count: int):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO agent_execution_log
          (task_name, status, started_at, ended_at, tokens_processed)
        VALUES (%s, 'success', NOW(), NOW(), %s)
    """, (task, count))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

### **5.3 scripts/label_targets.py**

```python
"""
label_targets.py

Etiqueta tokens con suficiente historia.

Frecuencia: cada hora via Hermes/cron.
"""

import os
import logging
import psycopg2

DB_DSN                   = os.getenv("DATABASE_URL")
LIQUIDITY_MIN_THRESHOLD  = 500    # USD mínimo para considerar activo
RUG_LIQUIDITY_WITHDRAWN  = 0.80   # % liquidez retirada = rug
PUMP_MULTIPLIER          = 2.0    # 2x = pump 100%


def main():
    conn   = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    # Tokens sin etiquetar con más de 24h de historia
    cursor.execute("""
        SELECT id, created_at, initial_price_usd
        FROM tokens
        WHERE label_completed = FALSE
          AND created_at < NOW() - INTERVAL '24 hours'
    """)
    tokens = cursor.fetchall()

    labeled = 0
    for token_id, created_at, initial_price in tokens:
        pump  = compute_pump(cursor, token_id, initial_price)
        rug   = compute_rug(cursor, token_id, created_at)
        surv  = compute_survival(cursor, token_id, created_at)

        cursor.execute("""
            UPDATE tokens SET
              pump_100pc_24h  = %s,
              rug_pull_48h    = %s,
              still_active_7d = %s,
              label_completed = TRUE
            WHERE id = %s
        """, (pump, rug, surv, token_id))
        labeled += 1

    conn.commit()
    conn.close()
    logging.info(f"label_targets: {labeled} tokens etiquetados")


def compute_pump(cursor, token_id: int, initial_price: float) -> bool:
    if not initial_price or initial_price == 0:
        return False

    cursor.execute("""
        SELECT price_usd FROM launches
        WHERE token_id = %s
          AND time >= (SELECT created_at FROM tokens WHERE id = %s)
                    + INTERVAL '23 hours'
          AND time <= (SELECT created_at FROM tokens WHERE id = %s)
                    + INTERVAL '25 hours'
        ORDER BY time DESC
        LIMIT 1
    """, (token_id, token_id, token_id))

    row = cursor.fetchone()
    if not row or not row[0]:
        return False
    return (row[0] / initial_price) >= PUMP_MULTIPLIER


def compute_rug(cursor, token_id: int, created_at) -> bool:
    # Condición 1: liquidez retirada >80% en 48h
    cursor.execute("""
        SELECT liquidity_pool_before, liquidity_pool_after
        FROM launches
        WHERE token_id = %s
          AND time <= %s + INTERVAL '48 hours'
          AND is_liquidity_removed = TRUE
        LIMIT 1
    """, (token_id, created_at))

    row = cursor.fetchone()
    if row and row[0] and row[0] > 0:
        withdrawn_pct = 1.0 - (row[1] or 0) / row[0]
        if withdrawn_pct >= RUG_LIQUIDITY_WITHDRAWN:
            return True

    # Condición 2: volumen colapsa a 0 tras pico inicial
    cursor.execute("""
        SELECT volume_60m FROM launches
        WHERE token_id = %s
        ORDER BY time ASC
        LIMIT 1
    """, (token_id,))
    row_first = cursor.fetchone()

    cursor.execute("""
        SELECT volume_60m FROM launches
        WHERE token_id = %s
          AND time BETWEEN %s + INTERVAL '24 hours'
                       AND %s + INTERVAL '48 hours'
        ORDER BY time DESC
        LIMIT 1
    """, (token_id, created_at, created_at))
    row_last = cursor.fetchone()

    if row_first and row_last:
        if (row_first[0] or 0) > 0 and (row_last[0] or 0) == 0:
            return True

    return False


def compute_survival(cursor, token_id: int, created_at) -> bool:
    # Solo para tokens con más de 7 días de historia
    cursor.execute("""
        SELECT NOW() > %s + INTERVAL '7 days'
    """, (created_at,))
    has_7d = cursor.fetchone()[0]

    if not has_7d:
        return None  # todavía no se puede etiquetar

    cursor.execute("""
        SELECT liquidity_pool_after, volume_240m
        FROM launches
        WHERE token_id = %s
          AND time BETWEEN %s + INTERVAL '6 days 20 hours'
                       AND %s + INTERVAL '7 days 4 hours'
        ORDER BY time DESC
        LIMIT 1
    """, (token_id, created_at, created_at))

    row = cursor.fetchone()
    if not row:
        return False

    liquidity_ok = (row[0] or 0) >= LIQUIDITY_MIN_THRESHOLD
    return liquidity_ok


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

### **5.4 scripts/compute_features.py**

```python
"""
compute_features.py

Calcula token_features desde launches + btc_context.

Frecuencia: cada hora via Hermes/cron.

Feature version actual: v1-onchain-minimal
"""

import os
import logging
import psycopg2

DB_DSN          = os.getenv("DATABASE_URL")
FEATURE_VERSION = os.getenv("FEATURE_VERSION", "v1-onchain-minimal")


def main():
    conn   = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    # Tokens etiquetados sin features todavía
    cursor.execute("""
        SELECT t.id, t.created_at
        FROM tokens t
        LEFT JOIN token_features tf
          ON tf.token_id = t.id AND tf.feature_version = %s
        WHERE t.label_completed = TRUE
          AND tf.id IS NULL
    """, (FEATURE_VERSION,))

    tokens = cursor.fetchall()
    computed = 0

    for token_id, created_at in tokens:
        features = compute_all_features(cursor, token_id, created_at)
        if features:
            insert_features(cursor, token_id, features)
            computed += 1

    conn.commit()
    conn.close()
    logging.info(f"compute_features: {computed} tokens con features calculadas")


def compute_all_features(cursor, token_id: int, created_at) -> dict:
    launches = get_launches(cursor, token_id)
    if not launches:
        return None

    btc = get_btc_context(cursor, created_at)

    # 1. Velocidad de transacciones
    tx_velocity_0_5m    = safe_div(launches.get("txs_0_5m", 0),    5.0)
    tx_velocity_5_60m   = safe_div(launches.get("txs_5_60m", 0),   55.0)
    tx_velocity_60_240m = safe_div(launches.get("txs_60_240m", 0), 180.0)

    # 2. Wallets únicas
    unique_wallets_0_10m = launches.get("unique_wallets_0_10m", 0)
    unique_wallets_0_60m = launches.get("unique_wallets_0_60m", 0)

    # 3. Ratio compra/venta (ventana 0-30 min)
    buy  = launches.get("buy_tx_0_30m", 0) or 0
    sell = launches.get("sell_tx_0_30m", 0) or 0
    buy_tx_ratio_0_30m = safe_div(buy, buy + sell)

    # 4. Liquidez
    liq_before = launches.get("liquidity_pool_before", 0) or 0
    liq_after  = launches.get("liquidity_pool_after", 0) or 0
    liq_t1h    = launches.get("liq_t1h", 0) or 0
    liq_t2h    = launches.get("liq_t2h", 0) or 0

    liquidity_add_0_10m     = liq_after > liq_before
    liquidity_remove_0_2h   = launches.get("is_liquidity_removed", False)
    liquidity_drop_1_2h_pct = safe_div(liq_t1h - liq_t2h, liq_t1h)

    # 5. Concentración
    top_10_wallets_pct_0_1h  = launches.get("top_10_wallets_pct_0_1h", None)
    gini_concentration_0_1h  = launches.get("gini_concentration_0_1h", None)

    # 6. Contexto BTC
    btc_change_pct_6h  = btc.get("change_pct_6h", None)
    btc_dominance_pct  = btc.get("dominance_pct", None)

    # 7. Timing
    launch_hour_utc    = created_at.hour
    launch_day_of_week = created_at.weekday()

    return {
        "feature_version":           FEATURE_VERSION,
        "max_feature_window_minutes": 30,
        "tx_velocity_0_5m":          tx_velocity_0_5m,
        "tx_velocity_5_60m":         tx_velocity_5_60m,
        "tx_velocity_60_240m":       tx_velocity_60_240m,
        "unique_wallets_0_10m":      unique_wallets_0_10m,
        "unique_wallets_0_60m":      unique_wallets_0_60m,
        "buy_tx_ratio_0_30m":        buy_tx_ratio_0_30m,
        "liquidity_add_0_10m":       liquidity_add_0_10m,
        "liquidity_remove_0_2h":     liquidity_remove_0_2h,
        "liquidity_drop_1_2h_pct":   liquidity_drop_1_2h_pct,
        "top_10_wallets_pct_0_1h":   top_10_wallets_pct_0_1h,
        "gini_concentration_0_1h":   gini_concentration_0_1h,
        "btc_change_pct_6h":         btc_change_pct_6h,
        "btc_dominance_pct":         btc_dominance_pct,
        "launch_hour_utc":           launch_hour_utc,
        "launch_day_of_week":        launch_day_of_week,
    }


def get_launches(cursor, token_id: int) -> dict:
    cursor.execute("""
        SELECT
          MAX(txs_0_5m)               AS txs_0_5m,
          MAX(txs_5_60m)              AS txs_5_60m,
          MAX(txs_60_240m)            AS txs_60_240m,
          MAX(unique_wallets_0_10m)   AS unique_wallets_0_10m,
          MAX(unique_wallets_0_60m)   AS unique_wallets_0_60m,
          MAX(buy_tx_0_30m)           AS buy_tx_0_30m,
          MAX(sell_tx_0_30m)          AS sell_tx_0_30m,
          MAX(liquidity_pool_before)  AS liquidity_pool_before,
          MAX(liquidity_pool_after)   AS liquidity_pool_after,
          MAX(top_10_wallets_pct_0_1h) AS top_10_wallets_pct_0_1h,
          MAX(gini_concentration_0_1h) AS gini_concentration_0_1h,
          BOOL_OR(is_liquidity_removed) AS is_liquidity_removed
        FROM launches
        WHERE token_id = %s
    """, (token_id,))

    row = cursor.fetchone()
    if not row:
        return {}

    cols = [
        "txs_0_5m","txs_5_60m","txs_60_240m",
        "unique_wallets_0_10m","unique_wallets_0_60m",
        "buy_tx_0_30m","sell_tx_0_30m",
        "liquidity_pool_before","liquidity_pool_after",
        "top_10_wallets_pct_0_1h","gini_concentration_0_1h",
        "is_liquidity_removed"
    ]
    return dict(zip(cols, row))


def get_btc_context(cursor, created_at) -> dict:
    cursor.execute("""
        SELECT change_pct_6h, dominance_pct
        FROM btc_context
        WHERE time <= %s
        ORDER BY time DESC
        LIMIT 1
    """, (created_at,))

    row = cursor.fetchone()
    if not row:
        return {}
    return {"change_pct_6h": row[0], "dominance_pct": row[1]}


def insert_features(cursor, token_id: int, f: dict):
    cursor.execute("""
        INSERT INTO token_features (
          token_id, feature_version, max_feature_window_minutes,
          tx_velocity_0_5m, tx_velocity_5_60m, tx_velocity_60_240m,
          unique_wallets_0_10m, unique_wallets_0_60m,
          buy_tx_ratio_0_30m,
          liquidity_add_0_10m, liquidity_remove_0_2h, liquidity_drop_1_2h_pct,
          top_10_wallets_pct_0_1h, gini_concentration_0_1h,
          btc_change_pct_6h, btc_dominance_pct,
          launch_hour_utc, launch_day_of_week
        ) VALUES (
          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        ON CONFLICT (token_id, feature_version) DO UPDATE SET
          updated_at = NOW()
    """, (
        token_id,
        f["feature_version"],
        f["max_feature_window_minutes"],
        f["tx_velocity_0_5m"],
        f["tx_velocity_5_60m"],
        f["tx_velocity_60_240m"],
        f["unique_wallets_0_10m"],
        f["unique_wallets_0_60m"],
        f["buy_tx_ratio_0_30m"],
        f["liquidity_add_0_10m"],
        f["liquidity_remove_0_2h"],
        f["liquidity_drop_1_2h_pct"],
        f["top_10_wallets_pct_0_1h"],
        f["gini_concentration_0_1h"],
        f["btc_change_pct_6h"],
        f["btc_dominance_pct"],
        f["launch_hour_utc"],
        f["launch_day_of_week"],
    ))


def safe_div(a, b) -> float:
    if not b or b == 0:
        return 0.0
    return float(a or 0) / float(b)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

### **5.5 scripts/train_models_all.py**

```python
"""
train_models_all.py

Entrena los tres modelos (A, B, C) con split temporal estricto.

Frecuencia: cada noche a las 3am via Hermes/cron.
"""

import os
import pickle
import logging
import numpy as np
import pandas as pd
import psycopg2
from datetime import datetime, timedelta
from sklearn.metrics import roc_auc_score, f1_score, log_loss
from xgboost import XGBClassifier

DB_DSN          = os.getenv("DATABASE_URL")
FEATURE_VERSION = os.getenv("FEATURE_VERSION", "v1-onchain-minimal")
MODELS_DIR      = os.getenv("MODELS_DIR", "/data/models")
TEST_DAYS       = 14  # últimos 14 días como test, resto como train

FEATURE_COLS = [
    "tx_velocity_0_5m",
    "tx_velocity_5_60m",
    "tx_velocity_60_240m",
    "unique_wallets_0_10m",
    "unique_wallets_0_60m",
    "buy_tx_ratio_0_30m",
    "liquidity_add_0_10m",
    "liquidity_remove_0_2h",
    "liquidity_drop_1_2h_pct",
    "top_10_wallets_pct_0_1h",
    "gini_concentration_0_1h",
    "btc_change_pct_6h",
    "btc_dominance_pct",
    "launch_hour_utc",
    "launch_day_of_week",
]

MODELS_CONFIG = [
    {
        "name":        "model-A-pump",
        "target_col":  "pump_100pc_24h",
        "description": "pump >= 100% en 24h",
    },
    {
        "name":        "model-B-rug",
        "target_col":  "rug_pull_48h",
        "description": "rug pull en <= 48h",
    },
    {
        "name":        "model-C-survival",
        "target_col":  "still_active_7d",
        "description": "token activo a los 7 dias",
    },
]


def main():
    conn = psycopg2.connect(DB_DSN)
    df   = load_dataset(conn)

    if df.empty or len(df) < 100:
        logging.warning("Datos insuficientes para entrenar. Minimo 100 tokens.")
        conn.close()
        return

    cutoff_date = datetime.utcnow() - timedelta(days=TEST_DAYS)
    df_train    = df[df["created_at"] < cutoff_date].copy()
    df_test     = df[df["created_at"] >= cutoff_date].copy()

    logging.info(f"Train: {len(df_train)} tokens | Test: {len(df_test)} tokens")

    os.makedirs(MODELS_DIR, exist_ok=True)
    for cfg in MODELS_CONFIG:
        train_model(conn, df_train, df_test, cfg)

    conn.close()


def load_dataset(conn) -> pd.DataFrame:
    query = """
        SELECT
            t.id,
            t.created_at,
            t.pump_100pc_24h,
            t.rug_pull_48h,
            t.still_active_7d,
            tf.tx_velocity_0_5m,
            tf.tx_velocity_5_60m,
            tf.tx_velocity_60_240m,
            tf.unique_wallets_0_10m,
            tf.unique_wallets_0_60m,
            tf.buy_tx_ratio_0_30m,
            tf.liquidity_add_0_10m,
            tf.liquidity_remove_0_2h,
            tf.liquidity_drop_1_2h_pct,
            tf.top_10_wallets_pct_0_1h,
            tf.gini_concentration_0_1h,
            tf.btc_change_pct_6h,
            tf.btc_dominance_pct,
            tf.launch_hour_utc,
            tf.launch_day_of_week
        FROM tokens t
        INNER JOIN token_features tf
            ON tf.token_id = t.id
            AND tf.feature_version = %s
        WHERE t.label_completed = TRUE
          AND t.pump_100pc_24h IS NOT NULL
          AND t.rug_pull_48h IS NOT NULL
        ORDER BY t.created_at ASC
    """

    df = pd.read_sql(query, conn, params=(FEATURE_VERSION,))
    df["liquidity_add_0_10m"]   = df["liquidity_add_0_10m"].astype(float)
    df["liquidity_remove_0_2h"] = df["liquidity_remove_0_2h"].astype(float)
    return df


def train_model(conn, df_train: pd.DataFrame, df_test: pd.DataFrame, cfg: dict):
    name       = cfg["name"]
    target_col = cfg["target_col"]

    # Eliminar filas sin target
    train = df_train[df_train[target_col].notna()].copy()
    test  = df_test[df_test[target_col].notna()].copy()

    if len(train) < 50:
        logging.warning(f"{name}: datos insuficientes ({len(train)} train). Saltando.")
        return

    X_train = train[FEATURE_COLS].fillna(0)
    y_train = train[target_col].astype(int)
    X_test  = test[FEATURE_COLS].fillna(0)
    y_test  = test[target_col].astype(int)

    # Manejar desbalance de clases
    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=pos_weight,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    # --- Métricas ---
    probs = model.predict_proba(X_test)[:, 1]
    precision_at_10 = compute_precision_at_k(y_test.values, probs, k=10)
    precision_at_20 = compute_precision_at_k(y_test.values, probs, k=20)
    recall_at_10    = compute_recall_at_k(y_test.values, probs, k=10)
    auc             = roc_auc_score(y_test, probs) if y_test.nunique() > 1 else 0.0
    f1              = f1_score(y_test, (probs >= 0.5).astype(int), zero_division=0)
    ll              = log_loss(y_test, probs) if y_test.nunique() > 1 else 0.0

    logging.info(
        f"{name} | P@10={precision_at_10:.3f} P@20={precision_at_20:.3f} "
        f"AUC={auc:.3f} F1={f1:.3f} LogLoss={ll:.3f}"
    )

    # --- Guardar modelo ---
    timestamp     = datetime.utcnow().strftime("%Y%m%d_%H%M")
    model_version = f"{name}-{FEATURE_VERSION}-{timestamp}"
    model_path    = os.path.join(MODELS_DIR, f"{model_version}.pkl")

    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    # --- Guardar métricas en DB ---
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO model_performance (
            model_name, feature_version, model_version,
            train_start, train_end, test_start, test_end,
            n_tokens_train, n_tokens_test, pct_positive,
            precision_at_10, precision_at_20, recall_at_10,
            auc_roc, f1_score, log_loss,
            model_file_path
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
    """, (
        name,
        FEATURE_VERSION,
        model_version,
        df_train["created_at"].min().date(),
        df_train["created_at"].max().date(),
        df_test["created_at"].min().date() if len(df_test) > 0 else None,
        df_test["created_at"].max().date() if len(df_test) > 0 else None,
        len(train),
        len(test),
        float(y_train.mean()),
        precision_at_10,
        precision_at_20,
        recall_at_10,
        auc,
        f1,
        ll,
        model_path,
    ))
    conn.commit()

    # --- Actualizar predicciones en tabla tokens ---
    update_predictions(conn, model, model_version, name, target_col)


def update_predictions(conn, model, model_version: str,
                        model_name: str, target_col: str):
    """
    Recalcula probabilidades para todos los tokens con features disponibles
    y actualiza la columna correspondiente en tokens.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.id, tf.tx_velocity_0_5m, tf.tx_velocity_5_60m,
               tf.tx_velocity_60_240m, tf.unique_wallets_0_10m,
               tf.unique_wallets_0_60m, tf.buy_tx_ratio_0_30m,
               tf.liquidity_add_0_10m, tf.liquidity_remove_0_2h,
               tf.liquidity_drop_1_2h_pct, tf.top_10_wallets_pct_0_1h,
               tf.gini_concentration_0_1h, tf.btc_change_pct_6h,
               tf.btc_dominance_pct, tf.launch_hour_utc,
               tf.launch_day_of_week
        FROM tokens t
        INNER JOIN token_features tf ON tf.token_id = t.id
          AND tf.feature_version = %s
    """, (FEATURE_VERSION,))

    rows = cursor.fetchall()
    if not rows:
        return

    ids = [r[0] for r in rows]
    X   = pd.DataFrame(
        [r[1:] for r in rows],
        columns=FEATURE_COLS
    ).fillna(0)

    probs = model.predict_proba(X)[:, 1]

    prob_col_map = {
        "model-A-pump":     "prob_pump_24h",
        "model-B-rug":      "prob_rug_48h",
        "model-C-survival": "prob_survival_7d",
    }
    prob_col      = prob_col_map.get(model_name, "prob_pump_24h")
    version_col   = {
        "model-A-pump":     "model_A_version",
        "model-B-rug":      "model_B_version",
        "model-C-survival": "model_C_version"
    }.get(model_name)

    for token_id, prob in zip(ids, probs):
        cursor.execute(f"""
            UPDATE tokens
            SET {prob_col} = %s,
                {version_col} = %s,
                predicted_at = NOW()
            WHERE id = %s
        """, (float(prob), model_version, token_id))

    conn.commit()
    logging.info(f"update_predictions: {len(ids)} tokens actualizados con {model_name}")


def compute_precision_at_k(y_true: np.ndarray,
                            probs: np.ndarray, k: int) -> float:
    if len(probs) < k:
        k = len(probs)
    top_k_idx    = np.argsort(probs)[::-1][:k]
    y_top_k      = y_true[top_k_idx]
    return float(y_top_k.sum()) / k


def compute_recall_at_k(y_true: np.ndarray,
                         probs: np.ndarray, k: int) -> float:
    total_positive = y_true.sum()
    if total_positive == 0:
        return 0.0
    if len(probs) < k:
        k = len(probs)
    top_k_idx = np.argsort(probs)[::-1][:k]
    y_top_k   = y_true[top_k_idx]
    return float(y_top_k.sum()) / float(total_positive)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

## **CAPÍTULO 6 — Modelos ML: entrenamiento y métricas**

### **6.1 Diseño de los tres modelos**

| Modelo | Nombre | Target | Horizonte de features | Horizonte de outcome |
| :--- | :--- | :--- | :--- | :--- |
| **A** | **model-A-pump** | **pump_100pc_24h** | **0–30 min** | **24 h** |
| **B** | **model-B-rug** | **rug_pull_48h** | **0–2 h** | **48 h** |
| **C** | **model-C-survival** | **still_active_7d** | **0–4 h** | **7 días** |

### **Regla estricta de ventanas:**

* **Modelo A usa SOLO features con max_feature_window_minutes <= 30.**
* **Modelo B usa SOLO features con max_feature_window_minutes <= 120.**
* **Modelo C puede usar features hasta 240 min.**
* Esta regla previene leakage temporal y se verifica en `train_models_all.py` filtrando por `max_feature_window_minutes` antes de entrenar.

---

### **6.2 Features por modelo**

#### **Modelo A — Pump (ventana máx 30 min)**

```python
FEATURES_MODEL_A = [
    "tx_velocity_0_5m",
    "unique_wallets_0_10m",
    "buy_tx_ratio_0_30m",
    "liquidity_add_0_10m",
    "top_10_wallets_pct_0_1h",   # calculada en t+10m, no t+1h real
    "btc_change_pct_6h",
    "btc_dominance_pct",
    "launch_hour_utc",
    "launch_day_of_week",
]
```

#### **Modelo B — Rug (ventana máx 120 min)**

```python
FEATURES_MODEL_B = [
    "tx_velocity_0_5m",
    "tx_velocity_5_60m",
    "unique_wallets_0_10m",
    "unique_wallets_0_60m",
    "buy_tx_ratio_0_30m",
    "liquidity_add_0_10m",
    "liquidity_remove_0_2h",
    "liquidity_drop_1_2h_pct",
    "top_10_wallets_pct_0_1h",
    "gini_concentration_0_1h",
    "btc_change_pct_6h",
    "launch_hour_utc",
]
```

#### **Modelo C — Survival (ventana máx 240 min)**

```python
FEATURES_MODEL_C = [
    "tx_velocity_0_5m",
    "tx_velocity_5_60m",
    "tx_velocity_60_240m",
    "unique_wallets_0_10m",
    "unique_wallets_0_60m",
    "buy_tx_ratio_0_30m",
    "liquidity_add_0_10m",
    "liquidity_remove_0_2h",
    "liquidity_drop_1_2h_pct",
    "top_10_wallets_pct_0_1h",
    "gini_concentration_0_1h",
    "btc_change_pct_6h",
    "btc_dominance_pct",
    "launch_hour_utc",
    "launch_day_of_week",
]
```

---

### **6.3 Split temporal estricto**

```
Timeline de datos disponibles tras backfill de 90 días:

|←────────────── 90 días ──────────────────→|
|←── 76 días TRAIN ──→|←── 14 días TEST ──→|
                       ↑
                  cutoff_date =
                  hoy - TEST_DAYS (14)
```

**Reglas:**

* NUNCA split aleatorio (train_test_split con shuffle=False obligatorio).
* NUNCA usar datos del futuro para entrenar.
* El test set representa siempre los últimos N días.
* En producción, el test set avanza con el tiempo (walk-forward).

```python
# En train_models_all.py
TEST_DAYS   = 14
cutoff_date = datetime.utcnow() - timedelta(days=TEST_DAYS)

df_train = df[df["created_at"] <  cutoff_date]
df_test  = df[df["created_at"] >= cutoff_date]

# Verificación anti-leakage
assert df_train["created_at"].max() < df_test["created_at"].min(), \
    "ERROR: leakage temporal detectado en el split"
```

---

### **6.4 Configuración XGBoost por modelo**

```python
# Parámetros base (iguales para los tres modelos en v1)
BASE_PARAMS = {
    "n_estimators":      300,
    "max_depth":         4,
    "learning_rate":     0.05,
    "subsample":         0.8,
    "colsample_bytree":  0.8,
    "use_label_encoder": False,
    "eval_metric":       "logloss",
    "random_state":      42,
    "n_jobs":            -1,
}

# Ajuste de desbalance de clases
# Pump.fun: ~5-10% de tokens hacen pump real
# ~80-90% de tokens son rug o mueren rápido
# scale_pos_weight = n_negativos / n_positivos
pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

model = XGBClassifier(**BASE_PARAMS, scale_pos_weight=pos_weight)

model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=False,
)
```

---

### **6.5 Métricas: definición y cálculo**

#### **Métrica principal: precision@top_k**

**¿Qué mide?**
> De los K tokens con mayor probabilidad predicha, cuántos realmente cumplieron el outcome.

**¿Por qué es la métrica correcta?**
> En trading no te importa clasificar bien todos los tokens. Te importa que cuando el modelo dice "este es interesante", tenga razón la mayor parte de las veces.

**Ejemplo real:**
* Hay 1000 tokens en el test set.
* Solo 50 hacen pump real (5%).
* El modelo ordena los 1000 por probabilidad descendente.
* Tomamos los top 10.
* Si 6 de esos 10 hicieron pump real → precision@10 = 0.60.
* Random baseline: precision@10 ≈ 0.05 (5% de la clase).
* Un modelo con precision@10 = 0.60 es 12x mejor que random.

```python
def compute_precision_at_k(y_true: np.ndarray,
                            probs: np.ndarray,
                            k: int) -> float:
    """
    Fracción de aciertos entre los k tokens
    con mayor probabilidad predicha.
    """
    k       = min(k, len(probs))
    top_idx = np.argsort(probs)[::-1][:k]
    return float(y_true[top_idx].sum()) / k


def compute_recall_at_k(y_true: np.ndarray,
                         probs: np.ndarray,
                         k: int) -> float:
    """
    Fracción de positivos reales capturados
    en los top k tokens predichos.
    """
    total_pos = y_true.sum()
    if total_pos == 0:
        return 0.0
    k       = min(k, len(probs))
    top_idx = np.argsort(probs)[::-1][:k]
    return float(y_true[top_idx].sum()) / float(total_pos)
```

#### **Métricas secundarias**

```python
from sklearn.metrics import roc_auc_score, f1_score, log_loss

# AUC-ROC: mide la capacidad de ranking general del modelo
# Útil para comparar versiones de modelo entre sí
auc = roc_auc_score(y_test, probs) if y_test.nunique() > 1 else 0.0

# F1: balance entre precision y recall en threshold 0.5
# Útil para detectar si el modelo está sesgado a una clase
f1 = f1_score(y_test, (probs >= 0.5).astype(int), zero_division=0)

# LogLoss: mide calibración de probabilidades
# Un modelo bien calibrado tiene logloss bajo
ll = log_loss(y_test, probs) if y_test.nunique() > 1 else 0.0
```

#### **Umbrales de aceptación mínimos (v1)**

```python
# Si un modelo no supera estos umbrales en test temporal,
# NO se despliega y se registra en model_performance con nota.

MINIMUM_THRESHOLDS = {
    "model-A-pump":     {"precision_at_10": 0.40, "auc_roc": 0.60},
    "model-B-rug":      {"precision_at_10": 0.50, "auc_roc": 0.65},
    "model-C-survival": {"precision_at_10": 0.45, "auc_roc": 0.60},
}

def model_passes_threshold(model_name: str,
                            precision_at_10: float,
                            auc_roc: float) -> bool:
    thresholds = MINIMUM_THRESHOLDS.get(model_name, {})
    return (
        precision_at_10 >= thresholds.get("precision_at_10", 0.0)
        and auc_roc     >= thresholds.get("auc_roc", 0.0)
    )
```

---

### **6.6 Feature importance y diagnóstico**

```python
def log_feature_importance(model: XGBClassifier,
                            feature_cols: list,
                            model_name: str):
    """
    Registra las features más importantes después de entrenar.
    Útil para detectar si el modelo depende de features inesperadas
    (posible señal de leakage o sobreajuste).
    """
    importances = model.feature_importances_
    ranked = sorted(
        zip(feature_cols, importances),
        key=lambda x: x[1],
        reverse=True
    )

    logging.info(f"\n=== Feature importance: {model_name} ===")
    for feat, imp in ranked:
        bar = "█" * int(imp * 50)
        logging.info(f"  {feat:<35} {imp:.4f} {bar}")

    # Alerta si una sola feature domina demasiado
    top_importance = ranked[0][1] if ranked else 0
    if top_importance > 0.40:
        logging.warning(
            f"ALERTA: '{ranked[0][0]}' tiene importancia {top_importance:.2f}. "
            "Posible leakage o feature dominante. Revisar."
        )
```

---

### **6.7 Versionado de modelos**

**Esquema de nombres de versión:**
> `{model_name}-{feature_version}-{timestamp}`

**Ejemplo:**
> `model-A-pump-v1-onchain-minimal-20260322_0300`

**Fichero en disco:**
> `/data/models/model-A-pump-v1-onchain-minimal-20260322_0300.pkl`

**Registro en model_performance:**
```
model_name    = "model-A-pump"
feature_version = "v1-onchain-minimal"
model_version = "model-A-pump-v1-onchain-minimal-20260322_0300"
model_file_path = "/data/models/model-A-pump-v1-onchain-minimal-20260322_0300.pkl"
```

**Política de retención:**
* Mantener los últimos 5 modelos por cada model_name.
* Borrar automáticamente los más antiguos.
* NUNCA borrar un modelo si es el único con precision_at_10 >= 0.40.

```python
def cleanup_old_models(models_dir: str,
                        model_name: str,
                        keep_last: int = 5):
    """
    Borra modelos antiguos manteniendo los últimos keep_last.
    """
    import glob
    pattern = os.path.join(models_dir, f"{model_name}-*.pkl")
    files   = sorted(glob.glob(pattern))

    if len(files) <= keep_last:
        return

    to_delete = files[:-keep_last]
    for f in to_delete:
        os.remove(f)
        logging.info(f"Modelo antiguo borrado: {f}")
```

---

### **6.8 Walk-forward validation (para producción)**

Una vez el sistema está en producción, el reentrenamiento diario implementa automáticamente una walk-forward validation:

```
Semana 1:  Train=[días 1-76]  Test=[días 77-90]
Semana 2:  Train=[días 1-77]  Test=[días 78-91]
Semana 3:  Train=[días 1-78]  Test=[días 79-92]
...
```

**Cada día que pasa:**
* El train set crece en 1 día.
* El test set avanza en 1 día.
* precision@top_k se recalcula sobre datos siempre frescos.
* model_performance acumula el histórico de métricas.

```python
# Visualizar evolución de precision@10 en el tiempo
# (query para ejecutar en psql o Jupyter)
SELECT
    DATE(created_at)    AS fecha,
    model_name,
    precision_at_10,
    auc_roc
FROM model_performance
WHERE model_name = 'model-A-pump'
ORDER BY created_at ASC;
```

---

## **CAPÍTULO 7 — Generación y validación de hipótesis**

### **7.1 scripts/generate_hypotheses_llm.py**

```python
"""
generate_hypotheses_llm.py

Genera hipótesis falsables comparando top-20 winners vs top-20 losers.

Frecuencia: lunes a las 4am via Hermes/cron.

El LLM recibe datos BRUTOS (no promedios) para evitar correlaciones inventadas.
"""

import os
import json
import logging
import psycopg2
import requests
from datetime import datetime

DB_DSN           = os.getenv("DATABASE_URL")
LITELLM_ENDPOINT = os.getenv("LITELLM_ENDPOINT", "http://100.68.1.180:8080/v1")
LITELLM_MODEL    = os.getenv("LITELLM_MODEL", "qwen3.5")
LITELLM_API_KEY  = os.getenv("LITELLM_API_KEY", "local")
FEATURE_VERSION  = os.getenv("FEATURE_VERSION", "v1-onchain-minimal")
TOP_N            = 20  # winners y losers a comparar


def main():
    conn = psycopg2.connect(DB_DSN)

    for target_model, target_col in [
        ("pump",     "pump_100pc_24h"),
        ("rug",      "rug_pull_48h"),
        ("survival", "still_active_7d"),
    ]:
        logging.info(f"Generando hipótesis para modelo: {target_model}")
        winners = fetch_top_n(conn, target_col, True,  TOP_N)
        losers  = fetch_top_n(conn, target_col, False, TOP_N)

        if len(winners) < 5 or len(losers) < 5:
            logging.warning(f"Datos insuficientes para {target_model}. Saltando.")
            continue

        hypotheses = call_llm(winners, losers, target_model)
        for h in hypotheses:
            insert_hypothesis(conn, h, target_model)

        logging.info(f"{target_model}: {len(hypotheses)} hipótesis generadas")

    conn.close()


def fetch_top_n(conn, target_col: str,
                is_winner: bool, n: int) -> list:
    """
    Devuelve los N tokens con mayor/menor probabilidad
    junto a sus features completas (filas brutas, no promedios).
    """
    prob_col = {
        "pump_100pc_24h":  "prob_pump_24h",
        "rug_pull_48h":    "prob_rug_48h",
        "still_active_7d": "prob_survival_7d",
    }[target_col]

    order = "DESC" if is_winner else "ASC"
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT
            t.address,
            t.created_at,
            t.{target_col},
            t.{prob_col},
            tf.tx_velocity_0_5m,
            tf.tx_velocity_5_60m,
            tf.tx_velocity_60_240m,
            tf.unique_wallets_0_10m,
            tf.unique_wallets_0_60m,
            tf.buy_tx_ratio_0_30m,
            tf.liquidity_add_0_10m,
            tf.liquidity_remove_0_2h,
            tf.liquidity_drop_1_2h_pct,
            tf.top_10_wallets_pct_0_1h,
            tf.gini_concentration_0_1h,
            tf.btc_change_pct_6h,
            tf.btc_dominance_pct,
            tf.launch_hour_utc,
            tf.launch_day_of_week
        FROM tokens t
        INNER JOIN token_features tf
            ON tf.token_id = t.id
            AND tf.feature_version = %s
        WHERE t.{target_col} = %s
          AND t.label_completed = TRUE
        ORDER BY t.{prob_col} {order}
        LIMIT %s
    """, (FEATURE_VERSION, is_winner, n))

    cols = [
        "address", "created_at", "target", "probability",
        "tx_velocity_0_5m", "tx_velocity_5_60m", "tx_velocity_60_240m",
        "unique_wallets_0_10m", "unique_wallets_0_60m",
        "buy_tx_ratio_0_30m",
        "liquidity_add_0_10m", "liquidity_remove_0_2h",
        "liquidity_drop_1_2h_pct",
        "top_10_wallets_pct_0_1h", "gini_concentration_0_1h",
        "btc_change_pct_6h", "btc_dominance_pct",
        "launch_hour_utc", "launch_day_of_week",
    ]

    rows = cursor.fetchall()
    return [dict(zip(cols, row)) for row in rows]


def call_llm(winners: list, losers: list, target_model: str) -> list:
    """
    Llama al LLM con datos brutos de winners y losers.
    Devuelve lista de hipótesis estructuradas.
    """
    winners_csv = rows_to_csv(winners)
    losers_csv  = rows_to_csv(losers)

    prompt = f"""Eres un analista cuantitativo especializado en memecoins de Solana.

Tienes dos grupos de tokens reales de Pump.fun:

=== WINNERS ({target_model}) ===
{winners_csv}

=== LOSERS ({target_model}) ===
{losers_csv}

INSTRUCCIONES ESTRICTAS:

1. Analiza los datos brutos. NO inventes correlaciones genéricas.
2. Busca patrones DIFERENCIALES concretos entre winners y losers.
3. Genera exactamente 5 hipótesis falsables.
4. Cada hipótesis DEBE tener este formato JSON exacto:
{{
  "hypothesis_text": "Si [condicion A] Y [condicion B], entonces [outcome] con probabilidad aproximada X%.",
  "conditions": [
    {{"feature": "nombre_feature", "op": ">", "threshold": valor_numerico}},
    {{"feature": "nombre_feature", "op": "<", "threshold": valor_numerico}}
  ],
  "estimated_probability": 0.XX,
  "confidence_interval": 0.XX,
  "reasoning": "Explicacion breve basada en los datos observados"
}}
5. Operadores válidos en conditions: ">", "<", ">=", "<=", "==", "!="
6. Features válidas: tx_velocity_0_5m, tx_velocity_5_60m, tx_velocity_60_240m,
   unique_wallets_0_10m, unique_wallets_0_60m, buy_tx_ratio_0_30m,
   liquidity_add_0_10m, liquidity_remove_0_2h, liquidity_drop_1_2h_pct,
   top_10_wallets_pct_0_1h, gini_concentration_0_1h,
   btc_change_pct_6h, btc_dominance_pct, launch_hour_utc, launch_day_of_week
7. NO menciones Twitter, sentiment ni noticias. Solo features on-chain.
8. Devuelve SOLO un array JSON con las 5 hipótesis. Sin texto adicional.
"""

    response = requests.post(
        f"{LITELLM_ENDPOINT}/chat/completions",
        headers={
            "Authorization": f"Bearer {LITELLM_API_KEY}",
            "Content-Type":  "application/json",
        },
        json={
            "model":       LITELLM_MODEL,
            "temperature": 0.3,
            "max_tokens":  2000,
            "messages": [
                {"role": "system", "content":
                    "Eres un analista cuantitativo. Respondes SOLO con JSON válido."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=120,
    )

    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"].strip()
    return parse_llm_response(content)


def parse_llm_response(content: str) -> list:
    """
    Parsea la respuesta del LLM y valida estructura mínima.
    Tolerante a markdown code blocks.
    """
    # Limpiar posibles ```json ... ```
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    try:
        hypotheses = json.loads(content.strip())
        if not isinstance(hypotheses, list):
            hypotheses = [hypotheses]
    except json.JSONDecodeError as e:
        logging.error(f"Error parseando JSON del LLM: {e}\\nContenido: {content}")
        return []

    valid = []
    for h in hypotheses:
        if all(k in h for k in [
            "hypothesis_text", "conditions",
            "estimated_probability", "confidence_interval"
        ]):
            valid.append(h)
        else:
            logging.warning(f"Hipótesis incompleta ignorada: {h}")

    return valid


def insert_hypothesis(conn, h: dict, target_model: str):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO token_hypotheses (
            hypothesis_text,
            conditions_json,
            target_model,
            feature_version,
            estimated_probability,
            confidence_interval,
            prior_probability,
            posterior_probability,
            generated_by,
            generated_on_data,
            active
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE
        )
    """, (
        h["hypothesis_text"],
        json.dumps(h["conditions"]),
        target_model,
        FEATURE_VERSION,
        h["estimated_probability"],
        h["confidence_interval"],
        h["estimated_probability"],   # prior = estimación inicial del LLM
        h["estimated_probability"],   # posterior arranca igual que prior
        f"llm-{LITELLM_MODEL}",
        f"backfill-90d" if is_backfill_mode() else f"live-{get_week_label()}",
    ))
    conn.commit()


def rows_to_csv(rows: list) -> str:
    """
    Convierte lista de dicts a formato CSV legible para el LLM.
    """
    if not rows:
        return "(sin datos)"

    headers = [k for k in rows[0].keys() if k not in ("address", "created_at")]
    lines   = [",".join(headers)]

    for row in rows:
        values = [str(round(row[h], 4) if isinstance(row[h], float)
                      else row[h]) for h in headers]
        lines.append(",".join(values))

    return "\\n".join(lines)


def is_backfill_mode() -> bool:
    return os.getenv("BACKFILL_MODE", "false").lower() == "true"


def get_week_label() -> str:
    now = datetime.utcnow()
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

### **7.2 scripts/validate_hypotheses.py**

```python
"""
validate_hypotheses.py

Contrasta hipótesis activas con tokens nuevos etiquetados.

Actualiza posterior_probability con actualización bayesiana simple (Beta).

Frecuencia: cada 6h via Hermes/cron.
"""

import os
import json
import logging
import psycopg2
from datetime import datetime, timedelta

DB_DSN = os.getenv("DATABASE_URL")

# Parámetros Beta prior iniciales
BETA_ALPHA_INIT = 1.0
BETA_BETA_INIT  = 1.0


def main():
    conn   = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    # Hipótesis activas
    cursor.execute("""
        SELECT id, conditions_json, target_model,
               prior_probability, total_tested,
               validated_count, refuted_count
        FROM token_hypotheses
        WHERE active = TRUE
    """)
    hypotheses = cursor.fetchall()

    # Tokens etiquetados en las últimas 6h (ventana de validación)
    cursor.execute("""
        SELECT
            t.id, t.pump_100pc_24h, t.rug_pull_48h, t.still_active_7d,
            tf.tx_velocity_0_5m, tf.tx_velocity_5_60m,
            tf.tx_velocity_60_240m, tf.unique_wallets_0_10m,
            tf.unique_wallets_0_60m, tf.buy_tx_ratio_0_30m,
            tf.liquidity_add_0_10m, tf.liquidity_remove_0_2h,
            tf.liquidity_drop_1_2h_pct, tf.top_10_wallets_pct_0_1h,
            tf.gini_concentration_0_1h, tf.btc_change_pct_6h,
            tf.btc_dominance_pct, tf.launch_hour_utc,
            tf.launch_day_of_week
        FROM tokens t
        INNER JOIN token_features tf ON tf.token_id = t.id
        WHERE t.label_completed = TRUE
          AND t.predicted_at >= NOW() - INTERVAL '6 hours'
    """)

    cols = [
        "id", "pump_100pc_24h", "rug_pull_48h", "still_active_7d",
        "tx_velocity_0_5m", "tx_velocity_5_60m", "tx_velocity_60_240m",
        "unique_wallets_0_10m", "unique_wallets_0_60m",
        "buy_tx_ratio_0_30m", "liquidity_add_0_10m",
        "liquidity_remove_0_2h", "liquidity_drop_1_2h_pct",
        "top_10_wallets_pct_0_1h", "gini_concentration_0_1h",
        "btc_change_pct_6h", "btc_dominance_pct",
        "launch_hour_utc", "launch_day_of_week",
    ]

    tokens = [dict(zip(cols, row)) for row in cursor.fetchall()]

    if not tokens:
        logging.info("validate_hypotheses: sin tokens nuevos en ventana.")
        conn.close()
        return

    target_col_map = {
        "pump":     "pump_100pc_24h",
        "rug":      "rug_pull_48h",
        "survival": "still_active_7d",
    }

    updated = 0
    for hyp in hypotheses:
        hyp_id, conditions_json, target_model, prior, total, validated, refuted = hyp
        conditions = json.loads(conditions_json) if conditions_json else []
        target_col = target_col_map.get(target_model)

        if not target_col:
            continue

        new_tested    = 0
        new_validated = 0
        new_refuted   = 0

        for token in tokens:
            if not token_matches_conditions(token, conditions):
                continue

            new_tested += 1
            outcome = token.get(target_col)

            if outcome is True:
                new_validated += 1
            elif outcome is False:
                new_refuted += 1

        if new_tested == 0:
            continue

        # Actualización bayesiana Beta-Binomial
        alpha = BETA_ALPHA_INIT + (validated + new_validated)
        beta  = BETA_BETA_INIT  + (refuted  + new_refuted)
        posterior = alpha / (alpha + beta)

        # Bayes factor simple
        bayes_factor = (
            posterior / max(prior, 0.01)
            if posterior > prior
            else prior / max(posterior, 0.01) * -1
        )

        cursor.execute("""
            UPDATE token_hypotheses SET
                total_tested       = total_tested     + %s,
                validated_count    = validated_count  + %s,
                refuted_count      = refuted_count    + %s,
                posterior_probability = %s,
                bayes_factor          = %s,
                last_updated          = NOW()
            WHERE id = %s
        """, (
            new_tested, new_validated, new_refuted,
            posterior, bayes_factor, hyp_id
        ))
        updated += 1

    conn.commit()
    conn.close()
    logging.info(f"validate_hypotheses: {updated} hipótesis actualizadas "
                 f"con {len(tokens)} tokens nuevos")


def token_matches_conditions(token: dict, conditions: list) -> bool:
    """
    Evalúa si un token cumple TODAS las condiciones de una hipótesis.
    """
    for cond in conditions:
        feature   = cond.get("feature")
        op        = cond.get("op")
        threshold = cond.get("threshold")
        value = token.get(feature)

        if value is None:
            return False

        # Normalizar booleanos
        if isinstance(value, bool):
            value = float(value)
        if isinstance(threshold, bool):
            threshold = float(threshold)

        try:
            value     = float(value)
            threshold = float(threshold)
        except (TypeError, ValueError):
            return False

        if op == ">"  and not (value >  threshold): return False
        if op == "<"  and not (value <  threshold): return False
        if op == ">=" and not (value >= threshold): return False
        if op == "<=" and not (value <= threshold): return False
        if op == "==" and not (value == threshold): return False
        if op == "!=" and not (value != threshold): return False

    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

### **7.3 scripts/backtest_report.py**

```python
"""
backtest_report.py

Genera informe diario de precision@top_k en datos recientes.

Envía resumen por Telegram.

Frecuencia: cada dia a las 8am via Hermes/cron.
"""

import os
import logging
import psycopg2
import requests
from datetime import datetime, timedelta

DB_DSN               = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED     = os.getenv("TELEGRAM_ALLOWED_USERS", "")


def main():
    conn   = psycopg2.connect(DB_DSN)
    report = build_report(conn)
    conn.close()
    send_telegram(report)
    logging.info("backtest_report: informe enviado")


def build_report(conn) -> str:
    cursor = conn.cursor()

    # Últimas métricas de cada modelo
    cursor.execute("""
        SELECT DISTINCT ON (model_name)
            model_name, model_version,
            precision_at_10, precision_at_20,
            auc_roc, f1_score,
            n_tokens_train, n_tokens_test,
            created_at
        FROM model_performance
        ORDER BY model_name, created_at DESC
    """)
    models = cursor.fetchall()

    # Hipótesis con mayor posterior_probability
    cursor.execute("""
        SELECT target_model, hypothesis_text,
               posterior_probability, total_tested,
               validated_count, refuted_count
        FROM token_hypotheses
        WHERE active = TRUE
        ORDER BY posterior_probability DESC
        LIMIT 5
    """)
    top_hyp = cursor.fetchall()

    # Tokens de hoy con mayor prob de pump y menor de rug
    cursor.execute("""
        SELECT symbol, address,
               prob_pump_24h, prob_rug_48h, prob_survival_7d,
               created_at
        FROM tokens
        WHERE created_at >= NOW() - INTERVAL '24 hours'
          AND prob_pump_24h IS NOT NULL
          AND prob_rug_48h IS NOT NULL
        ORDER BY (prob_pump_24h - prob_rug_48h) DESC
        LIMIT 5
    """)
    top_tokens = cursor.fetchall()

    # Construir mensaje
    lines = [
        f"📊 *Informe diario — {datetime.utcnow().strftime('%Y-%m-%d')}*",
        "",
        "*Modelos activos:*",
    ]

    for m in models:
        name, version, p10, p20, auc, f1, n_train, n_test, ts = m
        lines.append(
            f"• `{name}` | P@10={p10:.2f} P@20={p20:.2f} "
            f"AUC={auc:.2f} F1={f1:.2f} "
            f"(train={n_train} test={n_test})"
        )

    lines += ["", "*Top 5 hipótesis activas:*"]

    for h in top_hyp:
        model, text, posterior, tested, val, ref = h
        short_text = text[:80] + "..." if len(text) > 80 else text
        lines.append(
            f"• [{model}] P={posterior:.2f} "
            f"({val}/{tested} validadas) — {short_text}"
        )

    lines += ["", "*Top 5 tokens 24h (pump - rug score):*"]

    for t in top_tokens:
        symbol, addr, p_pump, p_rug, p_surv, created = t
        short_addr = addr[:8] + "..." if addr else "?"
        lines.append(
            f"• `{symbol or short_addr}` "
            f"pump={p_pump:.2f} rug={p_rug:.2f} surv={p_surv:.2f} "
            f"@ {created.strftime('%H:%M')} UTC"
        )

    return "\\n".join(lines)


def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN:
        logging.warning("Sin TELEGRAM_BOT_TOKEN. Informe no enviado.")
        return

    for user_id in TELEGRAM_ALLOWED.split(","):
        user_id = user_id.strip()
        if not user_id:
            continue

        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id":    user_id,
                    "text":       message,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
        except Exception as e:
            logging.error(f"Error enviando Telegram a {user_id}: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

## **CAPÍTULO 8 — Telegram Bot y control desde iOS**

### **8.1 scripts/telegram_bot.py**

```python
"""
telegram_bot.py

Bot de Telegram para control remoto del sistema desde iOS.

Comandos disponibles:

  /start          — ayuda
  /status         — estado general del sistema
  /top_pump       — top 10 tokens con mayor prob de pump
  /top_rug        — top 10 tokens con mayor prob de rug
  /hypotheses     — top 5 hipótesis con mayor posterior
  /backtest       — últimas métricas de los modelos
  /mode           — ver modo operativo actual
  /mode research  — activar modo research (solo alertas)
  /mode execution — activar modo execution (trades reales)
  /pause          — pausar todas las tareas del agente
  /resume         — reanudar tareas del agente
  /ping           — verificar que el bot responde
"""

import os
import logging
import psycopg2
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

DB_DSN               = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_ALLOWED     = os.getenv("TELEGRAM_ALLOWED_USERS", "")
PAUSE_FILE           = "/tmp/agent.pause"
MODE_FILE            = "/tmp/agent.mode"

ALLOWED_USER_IDS = set(
    int(x.strip()) for x in TELEGRAM_ALLOWED.split(",") if x.strip()
)


# --- Decorador de seguridad ---

def restricted(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USER_IDS:
            await update.message.reply_text("⛔ No autorizado.")
            logging.warning(f"Acceso denegado: user_id={user_id}")
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# --- Comandos ---

@restricted
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *Memecoin Agent v2.2*\\n\\n"
        "Comandos disponibles:\\n"
        "/status — estado general\\n"
        "/top\\_pump — top 10 tokens pump\\n"
        "/top\\_rug — top 10 tokens rug risk\\n"
        "/hypotheses — top 5 hipótesis activas\\n"
        "/backtest — métricas de modelos\\n"
        "/mode — ver/cambiar modo operativo\\n"
        "/pause — pausar agente\\n"
        "/resume — reanudar agente\\n"
        "/ping — verificar estado\\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@restricted
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    paused = os.path.exists(PAUSE_FILE)
    mode   = read_mode()
    await update.message.reply_text(
        f"✅ Bot activo — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\\n"
        f"Modo: `{mode}` | Agente: {'⏸ pausado' if paused else '▶️ activo'}",
        parse_mode="Markdown"
    )


@restricted
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn   = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    # Total tokens
    cursor.execute("SELECT COUNT(*) FROM tokens")
    total_tokens = cursor.fetchone()[0]

    # Tokens últimas 24h
    cursor.execute("""
        SELECT COUNT(*) FROM tokens
        WHERE created_at >= NOW() - INTERVAL '24 hours'
    """)
    tokens_24h = cursor.fetchone()[0]

    # Tokens etiquetados
    cursor.execute("""
        SELECT COUNT(*) FROM tokens WHERE label_completed = TRUE
    """)
    labeled = cursor.fetchone()[0]

    # Último entrenamiento
    cursor.execute("""
        SELECT model_name, precision_at_10, created_at
        FROM model_performance
        ORDER BY created_at DESC
        LIMIT 1
    """)
    last_train = cursor.fetchone()

    # Hipótesis activas
    cursor.execute("""
        SELECT COUNT(*) FROM token_hypotheses WHERE active = TRUE
    """)
    hyp_count = cursor.fetchone()[0]

    # Última tarea ejecutada
    cursor.execute("""
        SELECT task_name, status, ended_at
        FROM agent_execution_log
        ORDER BY started_at DESC
        LIMIT 1
    """)
    last_task = cursor.fetchone()

    conn.close()

    mode   = read_mode()
    paused = os.path.exists(PAUSE_FILE)

    lines = [
        "📊 *Estado del sistema*\\n",
        f"Modo: `{mode}` | Agente: {'⏸ pausado' if paused else '▶️ activo'}",
        f"Tokens totales: {total_tokens:,}",
        f"Tokens últimas 24h: {tokens_24h:,}",
        f"Tokens etiquetados: {labeled:,}",
        f"Hipótesis activas: {hyp_count}",
    ]

    if last_train:
        name, p10, ts = last_train
        lines.append(
            f"Último modelo: `{name}` P@10={p10:.2f} "
            f"({ts.strftime('%Y-%m-%d %H:%M')})"
        )

    if last_task:
        tname, tstatus, tend = last_task
        lines.append(
            f"Última tarea: `{tname}` [{tstatus}] "
            f"@ {tend.strftime('%H:%M') if tend else '?'} UTC"
        )

    await update.message.reply_text(
        "\\n".join(lines), parse_mode="Markdown"
    )


@restricted
async def cmd_top_pump(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn   = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT symbol, address, prob_pump_24h, prob_rug_48h,
               prob_survival_7d, created_at
        FROM tokens
        WHERE prob_pump_24h IS NOT NULL
          AND created_at >= NOW() - INTERVAL '48 hours'
        ORDER BY prob_pump_24h DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Sin datos de tokens recientes.")
        return

    lines = ["🚀 *Top 10 tokens por prob. pump (48h)*\\n"]

    for i, (symbol, addr, p_pump, p_rug, p_surv, created) in enumerate(rows, 1):
        short = addr[:8] + "..." if addr else "?"
        name  = symbol or short
        lines.append(
            f"{i}. `{name}` pump={p_pump:.2f} rug={p_rug:.2f} "
            f"surv={p_surv:.2f} @ {created.strftime('%H:%M')} UTC"
        )

    await update.message.reply_text(
        "\\n".join(lines), parse_mode="Markdown"
    )


@restricted
async def cmd_top_rug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn   = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT symbol, address, prob_pump_24h, prob_rug_48h,
               prob_survival_7d, created_at
        FROM tokens
        WHERE prob_rug_48h IS NOT NULL
          AND created_at >= NOW() - INTERVAL '48 hours'
        ORDER BY prob_rug_48h DESC
        LIMIT 10
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Sin datos de tokens recientes.")
        return

    lines = ["⚠️ *Top 10 tokens por riesgo de rug (48h)*\\n"]

    for i, (symbol, addr, p_pump, p_rug, p_surv, created) in enumerate(rows, 1):
        short = addr[:8] + "..." if addr else "?"
        name  = symbol or short
        lines.append(
            f"{i}. `{name}` rug={p_rug:.2f} pump={p_pump:.2f} "
            f"surv={p_surv:.2f} @ {created.strftime('%H:%M')} UTC"
        )

    await update.message.reply_text(
        "\\n".join(lines), parse_mode="Markdown"
    )


@restricted
async def cmd_hypotheses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn   = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT target_model, hypothesis_text,
               posterior_probability, total_tested,
               validated_count, refuted_count,
               last_updated
        FROM token_hypotheses
        WHERE active = TRUE
        ORDER BY posterior_probability DESC
        LIMIT 5
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Sin hipótesis activas todavía.")
        return

    lines = ["🧠 *Top 5 hipótesis activas*\\n"]

    for i, (model, text, posterior, tested, val, ref, updated) in enumerate(rows, 1):
        short = text[:100] + "..." if len(text) > 100 else text
        lines.append(
            f"{i}. [{model}] P={posterior:.2f} "
            f"({val}/{tested} validadas)\\n_{short}_\\n"
        )

    await update.message.reply_text(
        "\\n".join(lines), parse_mode="Markdown"
    )


@restricted
async def cmd_backtest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn   = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT ON (model_name)
            model_name, model_version,
            precision_at_10, precision_at_20,
            auc_roc, f1_score,
            n_tokens_train, n_tokens_test,
            created_at
        FROM model_performance
        ORDER BY model_name, created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Sin métricas de modelos todavía.")
        return

    lines = ["📈 *Métricas de modelos (última versión)*\\n"]

    for (name, version, p10, p20, auc, f1,
         n_train, n_test, ts) in rows:
        lines.append(
            f"*{name}*\\n"
            f"  P@10={p10:.3f} P@20={p20:.3f}\\n"
            f"  AUC={auc:.3f} F1={f1:.3f}\\n"
            f"  train={n_train:,} test={n_test:,}\\n"
            f"  versión: `{version}`\\n"
            f"  actualizado: {ts.strftime('%Y-%m-%d %H:%M')}\\n"
        )

    await update.message.reply_text(
        "\\n".join(lines), parse_mode="Markdown"
    )


@restricted
async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        mode = read_mode()
        await update.message.reply_text(
            f"Modo actual: `{mode}`\\n\\n"
            "Para cambiar:\\n"
            "/mode research — solo alertas y análisis\\n"
            "/mode execution confirm — trades reales (CUIDADO)",
            parse_mode="Markdown"
        )
        return

    requested = args[0].lower()

    if requested == "research":
        write_mode("research")
        await update.message.reply_text(
            "✅ Modo cambiado a `research`.\\n"
            "El sistema solo genera alertas. No ejecuta trades.",
            parse_mode="Markdown"
        )

    elif requested == "execution":
        if len(args) < 2 or args[1].lower() != "confirm":
            await update.message.reply_text(
                "⚠️ Para activar el modo execution escribe:\\n"
                "`/mode execution confirm`\\n\\n"
                "Esto permite trades reales con capital real.",
                parse_mode="Markdown"
            )
        else:
            write_mode("execution")
            await update.message.reply_text(
                "🔴 Modo `execution` activado.\\n"
                "El sistema puede ejecutar trades reales.\\n"
                "Límite por trade: configurado en MAX\\_POSITION\\_SOL.",
                parse_mode="Markdown"
            )

    else:
        await update.message.reply_text(
            "Modo no reconocido. Opciones: `research` | `execution`",
            parse_mode="Markdown"
        )


@restricted
async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with open(PAUSE_FILE, "w") as f:
        f.write(datetime.utcnow().isoformat())
    await update.message.reply_text(
        "⏸ Agente pausado.\\nLas tareas programadas se saltarán "
        "hasta que uses /resume."
    )


@restricted
async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
        await update.message.reply_text("▶️ Agente reanudado.")
    else:
        await update.message.reply_text("El agente no estaba pausado.")


# --- Helpers ---

def read_mode() -> str:
    if os.path.exists(MODE_FILE):
        with open(MODE_FILE) as f:
            return f.read().strip()
    return "research"


def write_mode(mode: str):
    with open(MODE_FILE, "w") as f:
        f.write(mode)


# --- Main ---

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN no configurado.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("ping",       cmd_ping))
    app.add_handler(CommandHandler("status",     cmd_status))
    app.add_handler(CommandHandler("top_pump",  cmd_top_pump))
    app.add_handler(CommandHandler("top_rug",     cmd_top_rug))
    app.add_handler(CommandHandler("hypotheses", cmd_hypotheses))
    app.add_handler(CommandHandler("backtest",    cmd_backtest))
    app.add_handler(CommandHandler("mode",        cmd_mode))
    app.add_handler(CommandHandler("pause",       cmd_pause))
    app.add_handler(CommandHandler("resume",      cmd_resume))

    logging.info("Telegram bot iniciado. Esperando comandos...")
    app.run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
```

---

### **8.2 Acceso desde iOS**

#### **Opción A — Telegram (principal)**

El bot de Telegram es la interfaz principal desde iOS. No requiere ninguna app adicional más allá de Telegram.

**Flujo típico desde iPhone:**

1. Abrir Telegram
2. Buscar tu bot por nombre
3. Enviar `/status` → ver estado general en segundos
4. Enviar `/top_pump` → ver candidatos de hoy
5. Enviar `/top_rug` → ver tokens peligrosos
6. Enviar `/hypotheses` → ver qué patrones están funcionando
7. Enviar `/pause` si quieres detener el agente temporalmente

#### **Opción B — SSH desde iOS (control avanzado)**

Para intervención directa en el servidor: ver logs, reiniciar servicios, ejecutar scripts manualmente.

**App recomendada:** Termius (gratuita, disponible en App Store)

```bash
# Configuración en Termius:

Host: IP de tu máquina o dominio Tailscale
Port: 22
User: tu_usuario
Auth: clave SSH (más seguro que contraseña)

# Comandos útiles desde iOS via SSH:

# Ver logs del agente en tiempo real
tail -f /var/log/memecoin-agent/agent.log

# Ver logs de una tarea específica
tail -f /var/log/memecoin-agent/collect_onchain.log

# Ejecutar backfill manualmente
cd /opt/memecoin-agent
python scripts/backfill_historical.py

# Reiniciar el bot de Telegram
sudo systemctl restart memecoin-telegram-bot

# Reiniciar Hermes
sudo systemctl restart hermes-memecoin

# Ver estado de todos los servicios
sudo systemctl status memecoin-*

# Ver cuántos tokens hay en la DB
psql -U memecoin_user -d memecoin_db \
  -c "SELECT COUNT(*), data_source FROM tokens GROUP BY data_source;"

# Ver últimas métricas de modelos
psql -U memecoin_user -d memecoin_db \
  -c "SELECT model_name, precision_at_10, created_at
      FROM model_performance
      ORDER BY created_at DESC LIMIT 6;"
```

#### **Opción C — Alertas automáticas proactivas**

El sistema puede enviarte alertas sin que tú preguntes. Añadir al final de `collect_onchain.py` y `validate_hypotheses.py`:

```python
def alert_if_interesting(conn, token_id: int):
    """
    Envía alerta Telegram si un token nuevo es muy interesante:
    - prob_pump_24h > 0.75
    - prob_rug_48h < 0.20
    - coincide con al menos 2 hipótesis activas con posterior > 0.65
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT t.symbol, t.address,
               t.prob_pump_24h, t.prob_rug_48h, t.prob_survival_7d,
               t.created_at
        FROM tokens t
        WHERE t.id = %s
          AND t.prob_pump_24h > 0.75
          AND t.prob_rug_48h  < 0.20
    """, (token_id,))

    row = cursor.fetchone()
    if not row:
        return

    symbol, addr, p_pump, p_rug, p_surv, created = row

    # Contar hipótesis que este token cumple
    cursor.execute("""
        SELECT id, conditions_json, hypothesis_text, posterior_probability
        FROM token_hypotheses
        WHERE active = TRUE
          AND posterior_probability > 0.65
          AND target_model = 'pump'
    """)
    hypotheses = cursor.fetchall()

    matched_hyp = []
    from validate_hypotheses import token_matches_conditions

    # Cargar features del token
    cursor.execute("""
        SELECT tx_velocity_0_5m, tx_velocity_5_60m, tx_velocity_60_240m,
               unique_wallets_0_10m, unique_wallets_0_60m,
               buy_tx_ratio_0_30m, liquidity_add_0_10m,
               liquidity_remove_0_2h, liquidity_drop_1_2h_pct,
               top_10_wallets_pct_0_1h, gini_concentration_0_1h,
               btc_change_pct_6h, btc_dominance_pct,
               launch_hour_utc, launch_day_of_week
        FROM token_features
        WHERE token_id = %s
    """, (token_id,))

    feat_row = cursor.fetchone()
    if not feat_row:
        return

    feat_cols = [
        "tx_velocity_0_5m", "tx_velocity_5_60m", "tx_velocity_60_240m",
        "unique_wallets_0_10m", "unique_wallets_0_60m",
        "buy_tx_ratio_0_30m", "liquidity_add_0_10m",
        "liquidity_remove_0_2h", "liquidity_drop_1_2h_pct",
        "top_10_wallets_pct_0_1h", "gini_concentration_0_1h",
        "btc_change_pct_6h", "btc_dominance_pct",
        "launch_hour_utc", "launch_day_of_week",
    ]

    token_features = dict(zip(feat_cols, feat_row))

    import json
    for hyp_id, cond_json, hyp_text, posterior in hypotheses:
        conditions = json.loads(cond_json) if cond_json else []
        if token_matches_conditions(token_features, conditions):
            matched_hyp.append((posterior, hyp_text))

    if len(matched_hyp) < 2:
        return

    # Construir y enviar alerta
    short_addr = addr[:12] + "..." if addr else "?"
    name       = symbol or short_addr

    hyp_lines = "\\n".join(
        f"  • P={p:.2f} — {t[:60]}..."
        for p, t in sorted(matched_hyp, reverse=True)[:3]
    )

    message = (
        f"🚨 *Alerta: token interesante detectado*\\n\\n"
        f"Token: `{name}`\\n"
        f"pump={p_pump:.2f} rug={p_rug:.2f} surv={p_surv:.2f}\\n"
        f"Lanzado: {created.strftime('%H:%M')} UTC\\n\\n"
        f"Hipótesis coincidentes ({len(matched_hyp)}):\\n{hyp_lines}\\n\\n"
        f"Dirección: `{addr}`"
    )

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_ALLOWED   = os.getenv("TELEGRAM_ALLOWED_USERS", "")

    import requests
    for user_id in TELEGRAM_ALLOWED.split(","):
        user_id = user_id.strip()
        if not user_id:
            continue

        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id":    user_id,
                    "text":       message,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
        except Exception as e:
            logging.error(f"Error enviando alerta a {user_id}: {e}")
```

---

## **CAPÍTULO 9 — Docker Compose y despliegue**

### **9.1 Estructura de directorios del proyecto**

```
memecoin-agent/
├── config/
│   ├── .env                        # variables de entorno (no commitear)
│   ├── .env.example                # plantilla pública
│   └── hermes-memecoin.toml        # configuración de Hermes
├── scripts/
│   ├── backfill_historical.py
│   ├── collect_onchain.py
│   ├── compute_features.py
│   ├── label_targets.py
│   ├── train_models_all.py
│   ├── generate_hypotheses_llm.py
│   ├── validate_hypotheses.py
│   ├── backtest_report.py
│   └── telegram_bot.py
├── sql/
│   └── schema_v2.2.sql             # esquema completo de DB
├── models/                         # modelos entrenados (.pkl)
├── logs/                           # logs de ejecución
├── data/                           # datos temporales y checkpoints
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

### **9.2 requirements.txt**

```text
# Base de datos
psycopg2-binary==2.9.9

# Solana on-chain
solana==0.34.0
solders==0.21.0
anchorpy==0.20.1

# HTTP y APIs
requests==2.31.0
httpx==0.27.0

# ML y análisis
pandas==2.2.1
numpy==1.26.4
scikit-learn==1.4.2
xgboost==2.0.3

# Datos
datasets==2.19.0          # HuggingFace datasets para backfill
pyarrow==15.0.2           # lectura de parquet

# Telegram
python-telegram-bot==21.3

# Utilidades
python-dotenv==1.0.1
pydantic==2.7.1
schedule==1.2.1
tenacity==8.2.3           # retry logic

# Logging
structlog==24.1.0
```

---

### **9.3 Dockerfile**

```dockerfile
FROM python:3.11-slim

# Dependencias del sistema
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    libpq-dev \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY scripts/ ./scripts/
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
```

---

### **9.4 docker-entrypoint.sh**

```bash
#!/bin/bash
set -e

echo "=== Memecoin Agent v2.2 ==="
echo "Iniciando en modo: ${EXECUTION_MODE:-research}"

# Esperar a que PostgreSQL esté listo
echo "Esperando PostgreSQL..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER"; do
    sleep 2
done
echo "PostgreSQL listo."

# Inicializar schema si no existe
echo "Inicializando schema..."
PGPASSWORD=$POSTGRES_PASSWORD psql \\
    -h "$POSTGRES_HOST" \\
    -p "$POSTGRES_PORT" \\
    -U "$POSTGRES_USER" \\
    -d "$POSTGRES_DB" \\
    -f /app/sql/schema_v2.2.sql \\
    --on-error-stop 2>/dev/null || echo "Schema ya existe, continuando."

# Ejecutar backfill si la DB está vacía
TOKEN_COUNT=$(PGPASSWORD=$POSTGRES_PASSWORD psql \\
    -h "$POSTGRES_HOST" \\
    -p "$POSTGRES_PORT" \\
    -U "$POSTGRES_USER" \\
    -d "$POSTGRES_DB" \\
    -tAc "SELECT COUNT(*) FROM tokens;" 2>/dev/null || echo "0")

if [ "$TOKEN_COUNT" -lt "100" ]; then
    echo "DB vacía (${TOKEN_COUNT} tokens). Iniciando backfill histórico..."
    python scripts/backfill_historical.py
else
    echo "DB ya tiene ${TOKEN_COUNT} tokens. Saltando backfill."
fi

# Iniciar bot de Telegram en background
echo "Iniciando Telegram bot..."
python scripts/telegram_bot.py &
TELEGRAM_PID=$!

# Iniciar Hermes como proceso principal
echo "Iniciando Hermes agent..."
exec hermes run --config config/hermes-memecoin.toml
```

---

### **9.5 docker-compose.yml**

```yaml
version: "3.9"

services:
  # ─── Base de datos ───────────────────────────────────────────────
  postgres:
    image: timescale/timescaledb:latest-pg16
    container_name: memecoin-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB:       ${POSTGRES_DB}
      POSTGRES_USER:     ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./sql/schema_v2.2.sql:/docker-entrypoint-initdb.d/01-schema.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─── Agente principal (Hermes + scripts + Telegram bot) ──────────
  agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: memecoin-agent
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    env_file:
      - config/.env
    environment:
      DATABASE_URL: >-
        postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}
        @postgres:5432/${POSTGRES_DB}
    volumes:
      - ./models:/data/models
      - ./logs:/app/logs
      - ./data:/data/checkpoints
      - /tmp:/tmp                   # para agent.pause y agent.mode
    ports:
      - "8000:8000"                 # API opcional FastAPI
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"

  # ─── Adminer — UI web para inspeccionar la DB (opcional) ─────────
  adminer:
    image: adminer:latest
    container_name: memecoin-adminer
    restart: unless-stopped
    depends_on:
      - postgres
    ports:
      - "8080:8080"
    profiles:
      - debug                       # solo arranca con: docker compose --profile debug up

volumes:
  postgres_data:
    driver: local
```

---

### **9.6 config/.env.example**

```bash
# ─── Base de datos ───────────────────────────────────────────────
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=memecoin_db
POSTGRES_USER=memecoin_user
POSTGRES_PASSWORD=CAMBIA_ESTO

# ─── Solana RPC ──────────────────────────────────────────────────
HELIUS_API_KEY=TU_HELIUS_API_KEY
BITQUERY_API_KEY=TU_BITQUERY_API_KEY
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=${HELIUS_API_KEY}

# ─── LLM (LiteLLM Gateway SAA) ───────────────────────────────────
LITELLM_ENDPOINT=http://100.68.1.180:8080/v1
LITELLM_MODEL=qwen3.5
LITELLM_API_KEY=TU_KEY_LOCAL

# ─── Telegram ────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=TU_TOKEN_DE_BOTFATHER
TELEGRAM_ALLOWED_USERS=TU_TELEGRAM_USER_ID

# ─── Modo operativo ──────────────────────────────────────────────
EXECUTION_MODE=research
# valores: research | execution
# NUNCA cambiar a execution sin validación previa de 8 semanas

MAX_POSITION_SOL=0.5
# Solo activo si EXECUTION_MODE=execution

# ─── Features y modelos ──────────────────────────────────────────
FEATURE_VERSION=v1-onchain-minimal
MODELS_DIR=/data/models

# ─── Backfill ────────────────────────────────────────────────────
BACKFILL_DAYS=90
BACKFILL_MODE=false
# Poner true solo durante el primer backfill para marcar hipótesis correctamente
```

---

### **9.7 Comandos de despliegue**

#### **Primera vez (instalación completa)**

```bash
# 1. Clonar el repo
git clone https://github.com/TU_USUARIO/memecoin-agent.git
cd memecoin-agent

# 2. Copiar y rellenar variables de entorno
cp config/.env.example config/.env
nano config/.env        # rellenar API keys, Telegram token, etc.

# 3. Construir imagen
docker compose build

# 4. Arrancar (el entrypoint lanza backfill automáticamente si DB vacía)
docker compose up -d

# 5. Ver logs en tiempo real
docker compose logs -f agent

# 6. Ver solo logs del backfill
docker compose logs -f agent | grep backfill
```

#### **Operación diaria**

```bash
# Ver estado de todos los contenedores
docker compose ps

# Ver logs del agente
docker compose logs -f agent --tail=100

# Reiniciar solo el agente (sin tocar la DB)
docker compose restart agent

# Parar todo
docker compose down

# Parar todo y borrar datos (CUIDADO: borra la DB)
docker compose down -v
```

#### **Inspeccionar la DB directamente**

```bash
# Entrar a PostgreSQL
docker compose exec postgres psql -U memecoin_user -d memecoin_db

# Queries útiles desde psql:

-- Cuántos tokens por fuente
SELECT data_source, COUNT(*) FROM tokens GROUP BY data_source;

-- Distribución de targets
SELECT
  pump_100pc_24h,
  rug_pull_48h,
  still_active_7d,
  COUNT(*)
FROM tokens
WHERE label_completed = TRUE
GROUP BY 1,2,3
ORDER BY 4 DESC;

-- Últimas métricas de modelos
SELECT model_name, precision_at_10, precision_at_20, auc_roc, created_at
FROM model_performance
ORDER BY created_at DESC
LIMIT 9;

-- Hipótesis más validadas
SELECT target_model, posterior_probability,
       validated_count, total_tested, hypothesis_text
FROM token_hypotheses
WHERE active = TRUE
ORDER BY posterior_probability DESC
LIMIT 10;
```

#### **Instalación sin Docker (macOS nativo para SAA)**

```bash
# Instalar dependencias del sistema
brew install postgresql@16
brew install pgvector        # opcional
pip install timescaledb      # o instalar via brew

# Iniciar PostgreSQL
brew services start postgresql@16

# Crear DB y usuario
createuser memecoin_user
createdb memecoin_db -O memecoin_user
psql -d memecoin_db -f sql/schema_v2.2.sql

# Instalar dependencias Python
pip install -r requirements.txt

# Instalar Hermes
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

# Arrancar Telegram bot como servicio (launchd en macOS)
cat > ~/Library/LaunchAgents/com.memecoin.telegram.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.memecoin.telegram</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/opt/memecoin-agent/scripts/telegram_bot.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/opt/memecoin-agent/logs/telegram.log</string>
  <key>StandardErrorPath</key>
  <string>/opt/memecoin-agent/logs/telegram.err</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.memecoin.telegram.plist

# Arrancar Hermes
hermes run --config config/hermes-memecoin.toml
```

---

## **CAPÍTULO 10 — Plan de implementación para Cline**

### **10.1 7 prompts exactos para Cline (fase a fase)**

#### **Fase 0: Configuración inicial y base de datos**

> **Prompt:** Crea la estructura de directorios para el proyecto memecoin-agent y configura el archivo `config/.env.example` con todas las variables de entorno necesarias. Incluye la plantilla completa con comentarios explicativos para cada sección (base de datos, Solana RPC, LLM, Telegram, modo operativo, features y modelos, backfill).

#### **Fase 1: Scripts de backfill histórico**

> **Prompt:** Implementa el script `scripts/backfill_historical.py` para descargar y almacenar 90 días de historia de tokens Pump.fun. El script debe: verificar si ya hay un backfill completado, intentar fuentes en orden de prioridad (HuggingFace, Bitquery, Helius), guardar checkpoints periódicamente, y registrar el progreso en la tabla `backfill_log`. Usa ON CONFLICT DO NOTHING en todos los inserts para idempotencia.

#### **Fase 2: Scripts de recolección y features**

> **Prompt:** Implementa tres scripts: `scripts/collect_onchain.py` (monitoriza nuevos tokens cada 15 min), `scripts/label_targets.py` (etiqueta tokens con suficiente historia cada hora), y `scripts/compute_features.py` (calcula features desde launches + btc_context cada hora). Todos deben registrar su ejecución en `agent_execution_log`.

#### **Fase 3: Scripts de entrenamiento de modelos**

> **Prompt:** Implementa `scripts/train_models_all.py` para entrenar los tres modelos (A, B, C) con split temporal estricto. El script debe: cargar el dataset desde PostgreSQL, dividir en train/test temporalmente, entrenar XGBoost con pos_weight para desbalance, calcular métricas (precision@top_k, AUC, F1, log_loss), guardar modelos en disco, y actualizar predicciones en la tabla `tokens`.

#### **Fase 4: Scripts de hipótesis y validación**

> **Prompt:** Implementa `scripts/generate_hypotheses_llm.py` (genera hipótesis comparando top-20 winners vs top-20 losers cada lunes) y `scripts/validate_hypotheses.py` (contrasta hipótesis con tokens nuevos cada 6h). Ambos deben actualizar la tabla `token_hypotheses` con actualización bayesiana simple (Beta).

#### **Fase 5: Telegram bot y control remoto**

> **Prompt:** Implementa `scripts/telegram_bot.py` con todos los comandos: /start, /status, /top_pump, /top_rug, /hypotheses, /backtest, /mode, /pause, /resume, /ping. El bot debe usar un decorador `@restricted` para verificar que solo usuarios autorizados pueden ejecutar comandos. Implementa el sistema de archivos para modo (research/execution) y pausa.

#### **Fase 6: Docker Compose y despliegue**

> **Prompt:** Crea los archivos `Dockerfile`, `docker-entrypoint.sh`, `docker-compose.yml`, y `requirements.txt` para despliegue con Docker Compose. El entrypoint debe esperar a PostgreSQL, inicializar el schema si no existe, y lanzar el backfill automáticamente si la DB está vacía.

#### **Fase 7: Checklist de validación pre-producción**

> **Prompt:** Crea un archivo `CHECKLIST_PRE_PROD.md` con todos los puntos de validación antes de pasar a producción: 1) Backfill completado con 90 días, 2) Modelos entrenados con precision@top_10 >= 0.40, 3) Hipótesis generadas y validadas, 4) Telegram bot funcionando, 5) Docker Compose desplegado y healthchecks pasando, 6) Variables de entorno configuradas, 7) EXECUTION_MODE = 'research' por defecto.

---

### **10.2 Checklist de validación pre-producción**

| # | Item | Estado |
| :--- | :--- | :--- |
| 1 | Backfill completado con 90 días de datos | [ ] |
| 2 | Modelos entrenados con precision@top_10 >= 0.40 | [ ] |
| 3 | Hipótesis generadas y validadas (mínimo 5 activas) | [ ] |
| 4 | Telegram bot funcionando y respondiendo comandos | [ ] |
| 5 | Docker Compose desplegado y healthchecks pasando | [ ] |
| 6 | Variables de entorno configuradas (no valores por defecto) | [ ] |
| 7 | EXECUTION_MODE = 'research' por defecto | [ ] |
| 8 | Stop-loss on-chain configurado para trades reales | [ ] |
| 9 | Límite de posición (MAX_POSITION_SOL) configurado | [ ] |
| 10 | Logs de ejecución configurados y rotando | [ ] |

---

### **10.3 Resumen de cambios v2.2**

| Versión | Cambios |
| :--- | :--- |
| v2.1 | Versión inicial con todos los componentes |
| v2.2 | Corrección de errores de numeración y formato en el documento blueprint |

---

**Fin del documento**

**Versión:** 2.2
**Fecha:** Marzo 2026