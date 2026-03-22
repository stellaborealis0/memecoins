# **Sistema Autónomo de Análisis de Memecoins en Solana (v2.1)**

## **Blueprint de Arquitectura e Implementación — Retroanálisis First**

Fecha: Marzo 2026  
Versión: 2.1

* Cap  0 — Principio fundamental v2.1: retroanálisis de 90 días obligatorio antes de producción  
* Cap  1 — Objetivos, principios de diseño y stack técnico  
* Cap  2 — Fuentes de datos históricos (90 días) (Helius, Bitquery, DexScreener, HuggingFace, CoinGecko) \+ prevención de leakage y survivorship bias  
* Cap  3 — Arquitectura del sistema v2.1 completa con diagrama, flujo de datos y config de Hermes  
* Cap  4 — Esquema de base de datos completo. Schema SQL completo (8 tablas, TimescaleDB, índices, versionado)  
* Cap 5 — Scripts Python: especificación completa: backfill\_historical.py, collect\_onchain.py, label\_targets.py, compute\_features.py, train\_models\_all.py  
* Cap 6 — Modelos ML: entrenamiento y métricas   
* Cap 7 — Generación y validación de hipótesis. generate\_hypotheses\_llm.py, validate\_hypotheses.py, backtest\_report  
* Cap 8 — Telegram Bot y control desde iOS. telegram\_bot.py completo con todos los comandos \+ sistema de alertas automáticas  
* Cap 9 — Docker Compose y despliegue. Dockerfile, entrypoint, requirements.txt, instalación nativa macOS  
* Cap 10 — Plan de implementación para Cline. 7 prompts exactos para Cline (fase a fase) \+ checklist de validación pre-producción

---

## **CAPÍTULO 0 — Principio fundamental v2.1**

"No esperamos 3 meses. Tenemos 3 meses de historia disponible ahora mismo."

Pump.fun lleva operativo desde 2024\. Existen fuentes públicas y RPC histórico que permiten reconstruir el historial completo de lanzamientos, precios, wallets y liquidez de los últimos 90+ días SIN necesidad de esperar producción.

Secuencia de arranque:

1. Fase 0 — Ingesta histórica (días 1–7): descarga y procesa 90 días de datos reales.  
2. Fase 1 — Etiquetado y features (días 7–9): los outcomes ya ocurrieron, se etiquetan directamente.  
3. Fase 2 — Entrenamiento inicial (días 9–11): modelos A/B/C entrenados con datos reales.  
4. Fase 3 — Producción (día 11+): el sistema opera con modelos ya validados.

Dos modos operativos (obligatorio respetar el orden):

* Modo Research/Defense: análisis, alertas, paper trading. ACTIVO por defecto.  
* Modo Execution: trades reales. DESACTIVADO hasta validación demostrada (mínimo 8 semanas consecutivas con precision@top10 \>= 0.60 en datos vivos, no backtest).

Advertencia sobre el Modo Execution:

* Memecoins en Pump.fun son entorno adversarial. Bots MEV operan en milisegundos.  
* Nunca operar con más del 1% del capital total por trade en producción inicial.  
* Stop-loss on-chain obligatorio desde el primer trade real.  
* El sistema NO ejecuta trades reales hasta que el usuario lo active explícitamente con /mode execution confirm.

## **CAPÍTULO 1 — Objetivos y principios de diseño**

## **1.1 Objetivo del sistema**

* Recoger automáticamente datos on-chain de tokens nuevos en Pump.fun / Solana.  
* Predecir con tres modelos independientes:  
  * Modelo A: pump ≥100% en primeras 24 h.  
  * Modelo B: rug-pull en ≤48 h.  
  * Modelo C: token todavía activo a los 7 días.  
* Generar y refinar hipótesis falsables basadas en patrones on-chain reales (nunca inventadas por el LLM sin contraste empírico).  
* Ejecutar en macOS / Ubuntu 24/7 (SAA v7.2: nodo MB o IM).  
* Control remoto desde iOS vía SSH \+ Telegram.

## **1.2 Principios de diseño**

| Principio | Descripción |
| :---- | :---- |
| Retroanálisis first | Los modelos se entrenan con 90 días de historia antes de ver un solo token nuevo en producción. |
| On-chain \> Social | 70% features on-chain, 20% microestructura, 10% social ligero máximo. |
| Hermes \= orquestador | Hermes llama scripts Python. Nunca hace scraping masivo ni parsing HTML directo. |
| Versionado estricto | feature\_version \+ model\_version en cada fila. Sin esto no hay reproducibilidad ni comparación de experimentos. |
| Métricas de trading | precision@top\_k como métrica principal. Accuracy es engañosa en clases muy desbalanceadas. |
| Modelos separados | Nunca mezclar pump, rug y survival en un único label ni en un único modelo. |
| LLM fuera del loop rápido | LLM solo para análisis offline semanal y generación de hipótesis. Nunca en la ruta crítica de decisión en tiempo real. |
| Defense first | El sistema es más valioso evitando rugs que encontrando pumps. El edge principal es preservación de capital. |

## **1.3 Stack técnico**

| Componente | Tecnología | Justificación |
| :---- | :---- | :---- |

| Componente | Tecnología | Justificación |
| :---- | :---- | :---- |
| Agente orquestador | Hermes (Nous Research) | Open-source, MIT, loop de tareas nativo, Telegram integrado, compatible macOS/Linux. |
| LLM razonamiento | LiteLLM Gateway (TO:8080) → Qwen3.5 / phi local | Sin dependencia cloud obligatoria. Fallback local siempre disponible. |
| LLM auxiliar | Ollama \+ Llama-3-8B / Mistral-7B cuantizado | Para tareas baratas y pruebas de prompts sin consumir cuota. |
| On-chain / ETL | Python \+ requests \+ solana.py \+ RPC | Scraper robusto, sin dependencia de UI web. |
| Base de datos | PostgreSQL 16 \+ TimescaleDB | Series temporales financieras \+ versionado de features \+ índices ricos. |
| ML / estadística | XGBoost \+ sklearn \+ pandas | Ligero, CPU suficiente, métricas correctas. |
| Control remoto | SSH \+ Telegram bot (python-telegram-bot) | Comandos y alertas desde iOS, sin coste adicional. |

## **CAPÍTULO 2 — Fuentes de datos históricos (90 días)**

Este es el cambio estructural clave de v2.1: el sistema NO arranca en blanco.

## **2.1 Prioridad de fuentes**

| Prioridad | Fuente | Tipo | Coste | Uso principal |
| :---- | :---- | :---- | :---- | :---- |
| 1 | Dump CSV/Parquet comunitario (Hugging Face) | Bulk descarga | Gratis | Backfill masivo inicial, miles de tokens de una vez |
| 2 | Bitquery GraphQL API | REST/GraphQL | Free tier suficiente | Tokens nuevos \+ primeras horas de actividad por rango de fechas |
| 3 | Helius RPC histórico | JSON-RPC | Free tier \~100k req/mes | Transacciones, wallets y liquidez por token individual |
| 4 | DexScreener API | REST | Sin auth necesaria | Precios y volumen histórico por token |
| 5 | CoinGecko API | REST | Sin auth necesaria | Contexto BTC histórico (precio, dominancia, volumen) |

## **2.2 Endpoints y ejemplos de llamada**

DexScreener — precio y volumen histórico por token

bash

GET https://api.dexscreener.com/latest/dex/tokens/{token\_address}  
\# Sin API key. Devuelve precio actual, volumen 24h, liquidez, variación.

CoinGecko — BTC últimos 90 días

bash

GET https://api.coingecko.com/api/v3/coins/bitcoin/market\_chart  
    ?vs\_currency=usd\&days=90\&interval=hourly  
\# Sin API key. Devuelve array de \[timestamp, price\_usd\].

Helius — transacciones históricas del programa Pump.fun

json

POST https://mainnet.helius-rpc.com/?api-key=TU\_KEY  
{  
  "jsonrpc": "2.0",  
  "id": 1,  
  "method": "getSignaturesForAddress",  
  "params": \[  
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  
    {"limit": 1000, "before": "ULTIMA\_FIRMA\_PAGINACION"}  
  \]  
}  
\# La dirección es el programa oficial de Pump.fun en Solana mainnet.  
\# Paginar hacia atrás hasta cubrir 90 días.

Bitquery — tokens nuevos en Pump.fun por rango de fechas

graphql

POST https://graphql.bitquery.io/  
Header: X-API-KEY: TU\_KEY

query {  
  solana {  
    instructions(  
      programId: {is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}  
      date: {between: \["2025-12-22", "2026-03-22"\]}  
      instruction: {callPath: {is: "create"}}  
    ) {  
      block { timestamp { time } }  
      accounts { address }  
      transaction { signature }  
    }  
  }  
}

Hugging Face — dump comunitario de Pump.fun

bash

\# Buscar en: https://huggingface.co/datasets?search=pump.fun  
\# Datasets relevantes disponibles: pump-fun-tokens, solana-memecoin-launches  
\# Descarga directa en parquet, sin auth para datasets públicos.  
pip install datasets  
from datasets import load\_dataset  
ds \= load\_dataset("nombre/pump-fun-tokens")

## **2.3 Etiquetado automático con datos históricos**

Con 90 días de historia el outcome ya ocurrió. El etiquetado es determinista:

python

\# Modelo A — pump en 24h  
pump\_100pc\_24h \= (price\_at\_t24h / price\_initial) \>= 2.0

\# Modelo B — rug pull en 48h  
rug\_pull\_48h \= (  
    (liquidity\_withdrawn\_pct\_at\_t48h \> 0.80)  
    or (volume\_at\_t48h \== 0 and volume\_at\_t2h \> 0\)  
    or (top\_10\_wallets\_sold\_pct\_at\_t48h \> 0.90)  
)

\# Modelo C — supervivencia 7 días  
still\_active\_7d \= (  
    liquidity\_pool\_at\_t7d \> LIQUIDITY\_MIN\_THRESHOLD  
    and volume\_at\_t7d \> percentile\_25\_all\_tokens  
)

## **2.4 Prevención de sesgo de supervivencia**

Problema: los tokens que "ganaron" en el pasado son visibles precisamente  
porque sobrevivieron. Los miles que murieron en minutos tienen datos escasos.

Solución obligatoria:

* Incluir TODOS los tokens descubiertos en el backfill, no solo los que tienen  
  datos completos. Los tokens con datos incompletos tras t+2h se etiquetan como  
  rug\_pull\_48h \= True por defecto (heurística conservadora).  
* Registrar en backfill\_log cuántos tokens se descartaron y por qué.  
* Nunca filtrar tokens por "tienen suficientes datos" antes del etiquetado.  
* El modelo debe aprender también de los casos con señal mínima.

## **2.5 Prevención de leakage temporal**

Problema: features calculadas en ventanas largas (60 min, 4h) pueden  
contener información del outcome si el pump ocurrió dentro de esa ventana.

Regla estricta:

* Modelo A (pump 24h): usar SOLO features de ventana 0–30 min.  
* Modelo B (rug 48h): usar SOLO features de ventana 0–2h.  
* Modelo C (survival 7d): puede usar features hasta 4h, nunca más.  
* En token\_features: columna max\_feature\_window\_minutes documenta  
  la ventana máxima usada para cada fila.  
* El split train/test es SIEMPRE temporal (nunca aleatorio):  
  * Train: tokens lanzados antes de fecha de corte.  
  * Test: tokens lanzados después de fecha de corte.

## **CAPÍTULO 3 — Arquitectura del sistema v2.1**

## **3.1 Diagrama general**

text

┌─────────────────────────────────────────────────────────────────────────┐  
│                    macOS / Ubuntu 24/7 — SAA v7.2                      │  
│                                                                         │  
│  ┌─────────────────────────┐   ┌─────────────────────────────────────┐  │  
│  │    Hermes Agent         │   │   Python ETL \+ ML Scripts           │  │  
│  │    (orquestador)        │   │                                     │  │  
│  │                         │   │  scripts/                           │  │  
│  │  tasks:                 │   │  ├── backfill\_historical.py         │  │  
│  │  \- backfill    (1x)     │   │  ├── collect\_onchain.py             │  │  
│  │  \- collect     (\*/15m)  │   │  ├── compute\_features.py            │  │  
│  │  \- features    (\*/1h)   │   │  ├── label\_targets.py               │  │  
│  │  \- label       (\*/1h)   │   │  ├── train\_models\_all.py            │  │  
│  │  \- train       (3am)    │   │  ├── generate\_hypotheses\_llm.py     │  │  
│  │  \- hypotheses  (MON)    │   │  ├── validate\_hypotheses.py         │  │  
│  │  \- validate    (\*/6h)   │   │  ├── backtest\_report.py             │  │  
│  │  \- backtest    (\*/24h)  │   │  └── telegram\_bot.py                │  │  
│  └──────────┬──────────────┘   └──────────────┬────────────────────┘   │  
│             │                                  │                        │  
│             └──────────────┬───────────────────┘                        │  
│                            │                                            │  
│           ┌────────────────▼────────────────────────────────────────┐   │  
│           │           PostgreSQL 16 \+ TimescaleDB                   │   │  
│           │                                                         │   │  
│           │  tokens              token\_features (versionado)        │   │  
│           │  launches            token\_hypotheses                   │   │  
│           │  btc\_context         model\_performance                  │   │  
│           │  backfill\_log        agent\_execution\_log                │   │  
│           └─────────────────────────────────────────────────────────┘   │  
│                            │                                            │  
│           ┌────────────────▼────────────────────────────────────────┐   │  
│           │   Telegram Bot — control iOS                            │   │  
│           │   /status /top\_pump /top\_rug /hypotheses                │   │  
│           │   /backtest\_report /pause /resume /mode                 │   │  
│           └─────────────────────────────────────────────────────────┘   │  
└────────────────────────────┬────────────────────────────────────────────┘  
                             │  
          ┌──────────────────┼──────────────────┬──────────────────┐  
          │                  │                  │                  │  
     ┌────▼─────┐   ┌────────▼────────┐  ┌─────▼──────┐  ┌───────▼──────┐  
     │  iOS     │   │  LiteLLM        │  │ Helius RPC │  │ DexScreener  │  
     │  SSH \+   │   │  Gateway        │  │ Bitquery   │  │ CoinGecko    │  
     │ Telegram │   │  TO:8080        │  │ Solana FM  │  │ HuggingFace  │  
     └──────────┘   │  Qwen/phi local │  └────────────┘  └──────────────┘  
                    └─────────────────┘

┌────────────────────────────────────────────────────────────────────┐  
│  WORKSTATION (exploración e inferencia local)                      │  
│  \- Jupyter para EDA de datos históricos                            │  
│  \- Ollama \+ Llama-3-8B / Mistral-7B para pruebas de prompts        │  
│  \- XGBoost / sklearn en CPU (sin GPU necesaria para MVP)           │  
└────────────────────────────────────────────────────────────────────┘

## **3.2 Flujo de datos completo**

text

FASE 0 — BACKFILL (una sola vez)  
────────────────────────────────  
backfill\_historical.py  
  │  
  ├── Descarga dump CSV/Parquet de HuggingFace (si existe)  
  ├── Query Bitquery: todos los tokens Pump.fun en rango \-90d a hoy  
  ├── Para cada token: Helius RPC → txs, wallets, liquidez por ventana  
  ├── DexScreener → precio histórico por token  
  ├── CoinGecko → BTC context por hora  
  │  
  ├── INSERT INTO tokens (data\_source='backfill\_historical')  
  ├── INSERT INTO launches (ventanas 0-5m, 5-60m, 60-240m)  
  ├── INSERT INTO btc\_context  
  └── Registra progreso en backfill\_log cada 500 tokens

          │  
          ▼

label\_targets.py  
  └── Para cada token con datos suficientes:  
      \- pump\_100pc\_24h  → precio t+24h / precio\_inicial \>= 2.0  
      \- rug\_pull\_48h    → heurísticas de liquidez \+ wallets  
      \- still\_active\_7d → liquidez y volumen en t+7d  
      \- UPDATE tokens SET pump\_100pc\_24h=..., rug\_pull\_48h=..., still\_active\_7d=...

          │  
          ▼

compute\_features.py  
  └── Para cada token etiquetado:  
      \- Calcula features desde launches \+ btc\_context  
      \- INSERT INTO token\_features (feature\_version='v1-onchain-minimal')

          │  
          ▼

train\_models\_all.py  
  └── Split temporal (nunca aleatorio):  
      \- Train: tokens creados antes de fecha\_corte  
      \- Test:  tokens creados después de fecha\_corte  
      \- Entrena modelo A, B, C con XGBoost  
      \- Evalúa precision@top\_10, precision@top\_20, AUC, F1  
      \- INSERT INTO model\_performance

FASE 1 — PRODUCCIÓN (continua, cada 15 min)  
────────────────────────────────────────────  
collect\_onchain.py (\*/15m)  
  └── Nuevos tokens en Pump.fun → INSERT INTO tokens (data\_source='live\_rpc')  
      └── Muestras en t+5m, t+15m, t+60m, t+4h → INSERT INTO launches

compute\_features.py (\*/1h)  
  └── Calcula features para tokens nuevos sin features todavía

label\_targets.py (\*/1h)  
  └── Etiqueta tokens con suficiente historia (\>24h, \>48h, \>7d)

train\_models\_all.py (3am diario)  
  └── Reentrenamiento incremental con datos nuevos

generate\_hypotheses\_llm.py (lunes 4am)  
  └── Top 20 winners \+ top 20 losers → LLM → hipótesis → token\_hypotheses

validate\_hypotheses.py (\*/6h)  
  └── Contrasta hipótesis activas con tokens nuevos → actualiza posterior\_probability

backtest\_report.py (\*/24h)  
  └── Genera informe de precision@top\_k en últimas 24h → alerta Telegram

## **3.3 Hermes: configuración de tareas**

text

\# config/hermes-memecoin.toml

\[agent\]  
name \= "memecoin-analyst"  
model \= "http://100.68.1.180:8080/v1"   \# LiteLLM Gateway SAA  
model\_id \= "qwen3.5"  
temperature \= 0.4  
max\_tokens \= 2000

\[memory\]  
type \= "sqlite"  
path \= "/data/hermes/memory.db"

\[tasks.backfill\]  
run \= "python scripts/backfill\_historical.py"  
schedule \= "once"  
on\_startup\_if\_empty \= true

\[tasks.collect\]  
run \= "python scripts/collect\_onchain.py"  
schedule \= "\*/15 \* \* \* \*"

\[tasks.features\]  
run \= "python scripts/compute\_features.py \--version v1-onchain-minimal"  
schedule \= "0 \* \* \* \*"

\[tasks.label\]  
run \= "python scripts/label\_targets.py"  
schedule \= "30 \* \* \* \*"

\[tasks.train\]  
run \= "python scripts/train\_models\_all.py"  
schedule \= "0 3 \* \* \*"

\[tasks.hypotheses\]  
run \= "python scripts/generate\_hypotheses\_llm.py"  
schedule \= "0 4 \* \* MON"

\[tasks.validate\]  
run \= "python scripts/validate\_hypotheses.py"  
schedule \= "0 \*/6 \* \* \*"

\[tasks.backtest\]  
run \= "python scripts/backtest\_report.py"  
schedule \= "0 8 \* \* \*"

\[telegram\]  
enabled \= true  
token\_env \= "TELEGRAM\_BOT\_TOKEN"  
allowed\_users\_env \= "TELEGRAM\_ALLOWED\_USERS"

## **3.4 Variables de entorno requeridas**

bash

\# config/.env

\# Base de datos  
POSTGRES\_HOST=localhost  
POSTGRES\_PORT=5432  
POSTGRES\_DB=memecoin\_db  
POSTGRES\_USER=memecoin\_user  
POSTGRES\_PASSWORD=TU\_PASSWORD

\# RPC y APIs on-chain  
HELIUS\_API\_KEY=TU\_KEY  
BITQUERY\_API\_KEY=TU\_KEY  
SOLANA\_RPC\_URL=https://mainnet.helius-rpc.com/?api-key=${HELIUS\_API\_KEY}

\# LLM  
LITELLM\_ENDPOINT=http://100.68.1.180:8080/v1  
LITELLM\_MODEL=qwen3.5  
LITELLM\_API\_KEY=TU\_KEY\_LOCAL

\# Telegram  
TELEGRAM\_BOT\_TOKEN=TU\_TOKEN  
TELEGRAM\_ALLOWED\_USERS=TU\_USER\_ID

\# Modo operativo  
EXECUTION\_MODE=research   \# 'research' | 'execution'  
MAX\_POSITION\_SOL=0.5      \# solo activo si EXECUTION\_MODE=execution

---

## **CAPÍTULO 4 — Esquema de base de datos completo**

## **4.1 tokens**

sql

CREATE TABLE tokens (  
  id                  SERIAL PRIMARY KEY,  
  address             VARCHAR(255) UNIQUE NOT NULL,  
  name                VARCHAR(255),  
  symbol              VARCHAR(50),  
  chain               VARCHAR(50) DEFAULT 'solana',  
  creator\_address     VARCHAR(255),  
  created\_at          TIMESTAMP NOT NULL,

  \-- Datos iniciales del lanzamiento  
  initial\_liquidity   BIGINT,  
  initial\_market\_cap  BIGINT,  
  initial\_holders     INTEGER,  
  initial\_price\_usd   FLOAT,

  \-- Origen del dato  
  data\_source         VARCHAR(50),  
  \-- valores: 'backfill\_historical' | 'live\_rpc'

  \-- Targets (rellenados por label\_targets.py)  
  pump\_100pc\_24h      BOOLEAN,  
  rug\_pull\_48h        BOOLEAN,  
  still\_active\_7d     BOOLEAN,

  \-- Predicciones actuales de los modelos  
  prob\_pump\_24h       FLOAT,  
  prob\_rug\_48h        FLOAT,  
  prob\_survival\_7d    FLOAT,

  \-- Versiones de modelo usadas en la última predicción  
  model\_A\_version     VARCHAR(50),  
  model\_B\_version     VARCHAR(50),  
  model\_C\_version     VARCHAR(50),

  \-- Control  
  label\_completed     BOOLEAN DEFAULT FALSE,  
  features\_computed   BOOLEAN DEFAULT FALSE,  
  predicted\_at        TIMESTAMP  
);

CREATE INDEX idx\_tokens\_created\_at  ON tokens (created\_at DESC);  
CREATE INDEX idx\_tokens\_source      ON tokens (data\_source);  
CREATE INDEX idx\_tokens\_probs       ON tokens (prob\_pump\_24h DESC, prob\_rug\_48h ASC);  
CREATE INDEX idx\_tokens\_unlabeled   ON tokens (label\_completed) WHERE label\_completed \= FALSE;

## **4.2 launches (TimescaleDB hypertable)**

sql

CREATE TABLE launches (  
  time                        TIMESTAMP NOT NULL,  
  token\_id                    INTEGER   NOT NULL REFERENCES tokens(id),

  \-- Precio en el momento de la muestra  
  price\_usd                   FLOAT,

  \-- Volumen acumulado desde lanzamiento hasta t  
  volume\_5m                   BIGINT,  
  volume\_15m                  BIGINT,  
  volume\_60m                  BIGINT,  
  volume\_240m                 BIGINT,

  \-- Transacciones por ventana  
  txs\_0\_5m                    INTEGER,  
  txs\_5\_60m                   INTEGER,  
  txs\_60\_240m                 INTEGER,

  \-- Wallets únicas acumuladas  
  unique\_wallets\_0\_10m        INTEGER,  
  unique\_wallets\_0\_60m        INTEGER,

  \-- Dirección del flujo  
  buy\_tx\_0\_30m                INTEGER,  
  sell\_tx\_0\_30m               INTEGER,

  \-- Estado de liquidez  
  liquidity\_pool\_before       BIGINT,  
  liquidity\_pool\_after        BIGINT,  
  is\_liquidity\_removed        BOOLEAN DEFAULT FALSE,

  \-- Concentración de holders  
  top\_10\_wallets\_pct\_0\_1h     FLOAT,  
  gini\_concentration\_0\_1h     FLOAT,

  PRIMARY KEY (time, token\_id)  
);

SELECT create\_hypertable('launches', 'time', if\_not\_exists \=\> TRUE);

CREATE INDEX idx\_launches\_token ON launches (token\_id, time DESC);

## **4.3 btc\_context**

sql

CREATE TABLE btc\_context (  
  time                TIMESTAMP PRIMARY KEY,  
  price\_usd           FLOAT,  
  volume\_24h          BIGINT,  
  change\_pct\_1h       FLOAT,  
  change\_pct\_6h       FLOAT,  
  change\_pct\_24h      FLOAT,  
  dominance\_pct       FLOAT  
);

SELECT create\_hypertable('btc\_context', 'time', if\_not\_exists \=\> TRUE);

## **4.4 token\_features (versionado)**

sql

CREATE TABLE token\_features (  
  id                          SERIAL PRIMARY KEY,  
  token\_id                    INTEGER NOT NULL REFERENCES tokens(id),

  \-- Versionado obligatorio  
  feature\_version             VARCHAR(50) NOT NULL,  
  \-- valores: 'v1-onchain-minimal' | 'v2-onchain-plus' | 'v3-micro'  
  model\_version               VARCHAR(50),

  \-- Ventana máxima usada (para detectar leakage)  
  max\_feature\_window\_minutes  INTEGER,

  \-- 1\. Velocidad de transacciones  
  tx\_velocity\_0\_5m            FLOAT,   \-- txs / 5 min  
  tx\_velocity\_5\_60m           FLOAT,   \-- txs / 55 min  
  tx\_velocity\_60\_240m         FLOAT,   \-- txs / 180 min

  \-- 2\. Wallets únicas  
  unique\_wallets\_0\_10m        INTEGER,  
  unique\_wallets\_0\_60m        INTEGER,

  \-- 3\. Ratio compra/venta  
  buy\_tx\_ratio\_0\_30m          FLOAT,  
  \-- buy\_tx / (buy\_tx \+ sell\_tx), ventana 0-30 min

  \-- 4\. Liquidez  
  liquidity\_add\_0\_10m         BOOLEAN,  
  liquidity\_remove\_0\_2h       BOOLEAN,  
  liquidity\_drop\_1\_2h\_pct     FLOAT,  
  \-- (liq\_t1h \- liq\_t2h) / liq\_t1h

  \-- 5\. Concentración de holders  
  top\_10\_wallets\_pct\_0\_1h     FLOAT,  
  gini\_concentration\_0\_1h     FLOAT,

  \-- 6\. Contexto BTC en el momento del lanzamiento  
  btc\_change\_pct\_6h           FLOAT,  
  btc\_dominance\_pct           FLOAT,

  \-- 7\. Timing del lanzamiento  
  launch\_hour\_utc             INTEGER,   \-- 0-23  
  launch\_day\_of\_week          INTEGER,   \-- 0=lunes, 6=domingo

  \-- 8\. Microestructura (v2 en adelante)  
  avg\_trade\_size\_0\_30m        FLOAT,     \-- SOL por trade medio  
  slippage\_0\_30m              FLOAT,

  created\_at                  TIMESTAMP DEFAULT NOW(),  
  updated\_at                  TIMESTAMP DEFAULT NOW(),

  UNIQUE (token\_id, feature\_version)  
);

CREATE INDEX idx\_tf\_version ON token\_features (feature\_version);  
CREATE INDEX idx\_tf\_core    ON token\_features (  
  feature\_version,  
  tx\_velocity\_0\_5m DESC,  
  unique\_wallets\_0\_10m DESC  
);

## **4.5 token\_hypotheses**

sql

CREATE TABLE token\_hypotheses (  
  id                      SERIAL PRIMARY KEY,

  hypothesis\_text         TEXT NOT NULL,

  \-- Condiciones estructuradas para validación automática  
  conditions\_json         JSONB,  
  \-- Ejemplo:  
  \-- \[  
  \--   {"feature": "tx\_velocity\_0\_5m",    "op": "\>",  "threshold": 5.0},  
  \--   {"feature": "buy\_tx\_ratio\_0\_30m",  "op": "\>",  "threshold": 0.70},  
  \--   {"feature": "liquidity\_remove\_0\_2h","op": "=", "threshold": false}  
  \-- \]

  target\_model            VARCHAR(20),  
  \-- valores: 'pump' | 'rug' | 'survival'

  feature\_version         VARCHAR(50),  
  model\_version           VARCHAR(50),

  \-- Probabilidad estimada por el LLM al generar  
  estimated\_probability   FLOAT,  
  confidence\_interval     FLOAT,

  \-- Actualización bayesiana (Beta distribution)  
  prior\_probability       FLOAT DEFAULT 0.5,  
  posterior\_probability   FLOAT DEFAULT 0.5,  
  bayes\_factor            FLOAT,

  \-- Validación empírica acumulada  
  total\_tested            INTEGER DEFAULT 0,  
  validated\_count         INTEGER DEFAULT 0,  
  refuted\_count           INTEGER DEFAULT 0,

  \-- Origen de la hipótesis  
  generated\_by            VARCHAR(50),  
  \-- valores: 'llm-qwen' | 'llm-phi' | 'manual'  
  generated\_on\_data       VARCHAR(50),  
  \-- valores: 'backfill-90d' | 'live-week-N'

  \-- Estado  
  active                  BOOLEAN DEFAULT TRUE,

  created\_at              TIMESTAMP DEFAULT NOW(),  
  last\_updated            TIMESTAMP DEFAULT NOW()  
);

CREATE INDEX idx\_hyp\_prob     ON token\_hypotheses (posterior\_probability DESC);  
CREATE INDEX idx\_hyp\_model    ON token\_hypotheses (target\_model);  
CREATE INDEX idx\_hyp\_active   ON token\_hypotheses (active) WHERE active \= TRUE;  
CREATE INDEX idx\_hyp\_versions ON token\_hypotheses (feature\_version, model\_version);

## **4.6 model\_performance**

sql

CREATE TABLE model\_performance (  
  id                  SERIAL PRIMARY KEY,

  model\_name          VARCHAR(50) NOT NULL,  
  \-- valores: 'model-A-pump' | 'model-B-rug' | 'model-C-survival'

  feature\_version     VARCHAR(50),  
  model\_version       VARCHAR(50),

  \-- Rango de datos usado  
  train\_start         DATE,  
  train\_end           DATE,  
  test\_start          DATE,  
  test\_end            DATE,  
  n\_tokens\_train      INTEGER,  
  n\_tokens\_test       INTEGER,  
  pct\_positive        FLOAT,  
  \-- % de clase positiva (para detectar desbalance)

  \-- Métricas principales  
  precision\_at\_10     FLOAT,  
  precision\_at\_20     FLOAT,  
  recall\_at\_10        FLOAT,  
  auc\_roc             FLOAT,  
  f1\_score            FLOAT,  
  log\_loss            FLOAT,

  \-- Ruta del modelo serializado  
  model\_file\_path     VARCHAR(500),

  experiment\_notes    TEXT,  
  created\_at          TIMESTAMP DEFAULT NOW()  
);

CREATE INDEX idx\_mp\_model   ON model\_performance (model\_name, model\_version);  
CREATE INDEX idx\_mp\_created ON model\_performance (created\_at DESC);

## **4.7 backfill\_log**

sql

CREATE TABLE backfill\_log (  
  id                  SERIAL PRIMARY KEY,  
  source              VARCHAR(50),  
  \-- valores: 'huggingface' | 'bitquery' | 'helius' | 'dexscreener'

  date\_range\_from     DATE,  
  date\_range\_to       DATE,

  tokens\_discovered   INTEGER DEFAULT 0,  
  tokens\_stored       INTEGER DEFAULT 0,  
  tokens\_skipped      INTEGER DEFAULT 0,  
  launches\_stored     INTEGER DEFAULT 0,

  last\_checkpoint     VARCHAR(255),  
  \-- firma o cursor para reanudar si se interrumpe

  status              VARCHAR(20) DEFAULT 'running',  
  \-- valores: 'running' | 'completed' | 'failed' | 'partial'

  error\_message       TEXT,  
  started\_at          TIMESTAMP DEFAULT NOW(),  
  ended\_at            TIMESTAMP  
);

## **4.8 agent\_execution\_log**

sql

CREATE TABLE agent\_execution\_log (  
  id                    SERIAL PRIMARY KEY,  
  task\_name             VARCHAR(255),  
  status                VARCHAR(50),  
  \-- valores: 'success' | 'failed' | 'partial'

  error\_message         TEXT,  
  started\_at            TIMESTAMP,  
  ended\_at              TIMESTAMP,

  tokens\_processed      INTEGER DEFAULT 0,  
  data\_points\_collected INTEGER DEFAULT 0,

  extra\_json            JSONB  
  \-- para métricas adicionales específicas de cada tarea  
);

CREATE INDEX idx\_ael\_task    ON agent\_execution\_log (task\_name, started\_at DESC);  
CREATE INDEX idx\_ael\_status  ON agent\_execution\_log (status);

## **4.9 Script de inicialización completo**

bash

\# Ejecutar una sola vez para crear toda la estructura  
psql \-U memecoin\_user \-d memecoin\_db \-f schema\_v2.1.sql

\# Verificar que TimescaleDB está activo  
psql \-U memecoin\_user \-d memecoin\_db \-c "SELECT extname FROM pg\_extension;"  
\# Debe mostrar: timescaledb

\# Verificar hypertables  
psql \-U memecoin\_user \-d memecoin\_db \-c "SELECT \* FROM timescaledb\_information.hypertables;"  
\# Debe mostrar: launches, btc\_context

## **CAPÍTULO 5 — Scripts Python: especificación completa**

## **5.1 scripts/backfill\_historical.py**

python

"""

backfill\_historical.py

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

\# \--- Configuración \---

BACKFILL\_DAYS         \= 90

BACKFILL\_BATCH\_SIZE   \= 500

PUMP\_PROGRAM\_ADDRESS  \= "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

HELIUS\_API\_KEY        \= os.getenv("HELIUS\_API\_KEY")

BITQUERY\_API\_KEY      \= os.getenv("BITQUERY\_API\_KEY")

SOLANA\_RPC\_URL        \= os.getenv("SOLANA\_RPC\_URL")

DB\_DSN                \= os.getenv("DATABASE\_URL")

DATE\_FROM \= datetime.utcnow() \- timedelta(days=BACKFILL\_DAYS)

DATE\_TO   \= datetime.utcnow()

\# \--- Lógica principal \---

def main():

    conn \= psycopg2.connect(DB\_DSN)

    \# 1\. Verificar si ya hay un backfill completado

    if backfill\_already\_completed(conn):

        logging.info("Backfill ya completado. Saliendo.")

        return

    \# 2\. Obtener último checkpoint

    checkpoint \= get\_last\_checkpoint(conn)

    \# 3\. Intentar fuentes en orden de prioridad

    sources \= \["huggingface", "bitquery", "helius"\]

    for source in sources:

        try:

            logging.info(f"Intentando fuente: {source}")

            if source \== "huggingface":

                tokens \= fetch\_from\_huggingface()

            elif source \== "bitquery":

                tokens \= fetch\_from\_bitquery(DATE\_FROM, DATE\_TO, checkpoint)

            elif source \== "helius":

                tokens \= fetch\_from\_helius(checkpoint)

            if tokens:

                process\_tokens(conn, tokens, source)

                break

        except Exception as e:

            logging.error(f"Fuente {source} falló: {e}")

            continue

    \# 4\. Finalizar

    mark\_backfill\_completed(conn)

    conn.close()

    logging.info("Backfill completado.")

def fetch\_from\_huggingface() \-\> list:

    """

    Intenta cargar dataset público de Pump.fun desde HuggingFace.

    Buscar: huggingface.co/datasets?search=pump.fun

    Devuelve lista de dicts con campos: address, name, symbol,

    created\_at, initial\_liquidity, initial\_price\_usd.

    """

    from datasets import load\_dataset

    ds \= load\_dataset("datasets/pump-fun-tokens", split="train")

    return \[dict(row) for row in ds\]

def fetch\_from\_bitquery(date\_from: datetime, date\_to: datetime,

                        checkpoint: Optional\[str\]) \-\> list:

    """

    Query GraphQL a Bitquery para obtener tokens nuevos en Pump.fun

    en el rango de fechas dado.

    """

    query \= """

    query($from: ISO8601DateTime, $to: ISO8601DateTime) {

      solana {

        instructions(

          programId: {is: "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"}

          date: {between: \[$from, $to\]}

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

    variables \= {

        "from": date\_from.strftime("%Y-%m-%dT%H:%M:%SZ"),

        "to":   date\_to.strftime("%Y-%m-%dT%H:%M:%SZ")

    }

    resp \= requests.post(

        "https://graphql.bitquery.io/",

        json={"query": query, "variables": variables},

        headers={"X-API-KEY": BITQUERY\_API\_KEY},

        timeout=60

    )

    resp.raise\_for\_status()

    instructions \= resp.json()\["data"\]\["solana"\]\["instructions"\]

    return parse\_bitquery\_instructions(instructions)

def fetch\_from\_helius(checkpoint: Optional\[str\]) \-\> list:

    """

    Pagina hacia atrás en las firmas del programa Pump.fun

    usando Helius RPC hasta cubrir BACKFILL\_DAYS días.

    """

    client \= Client(SOLANA\_RPC\_URL)

    tokens  \= \[\]

    before  \= checkpoint

    cutoff  \= datetime.utcnow() \- timedelta(days=BACKFILL\_DAYS)

    while True:

        params \= {"limit": 1000}

        if before:

            params\["before"\] \= before

        resp \= client.get\_signatures\_for\_address(

            PUMP\_PROGRAM\_ADDRESS, \*\*params

        )

        sigs \= resp.value

        if not sigs:

            break

        for sig in sigs:

            block\_time \= datetime.utcfromtimestamp(sig.block\_time)

            if block\_time \< cutoff:

                return tokens

            tokens.append({"signature": str(sig.signature),

                           "block\_time": block\_time})

        before \= str(sigs\[-1\].signature)

        time.sleep(0.1)  \# respetar rate limit

    return tokens

def process\_tokens(conn, tokens: list, source: str):

    """

    Para cada token:

    1\. INSERT INTO tokens (ON CONFLICT DO NOTHING)

    2\. Enriquecer con DexScreener (precio histórico)

    3\. INSERT INTO launches

    4\. Guardar checkpoint cada BACKFILL\_BATCH\_SIZE tokens

    """

    cursor \= conn.cursor()

    for i, token in enumerate(tokens):

        try:

            \# Enriquecer con DexScreener

            price\_data \= fetch\_dexscreener(token.get("address", ""))

            cursor.execute("""

                INSERT INTO tokens

                  (address, name, symbol, created\_at, data\_source,

                   initial\_price\_usd, initial\_liquidity)

                VALUES (%s, %s, %s, %s, %s, %s, %s)

                ON CONFLICT (address) DO NOTHING

            """, (

                token.get("address"),

                token.get("name"),

                token.get("symbol"),

                token.get("created\_at"),

                source,

                price\_data.get("initial\_price\_usd"),

                price\_data.get("initial\_liquidity")

            ))

            \# Guardar checkpoint periódicamente

            if i % BACKFILL\_BATCH\_SIZE \== 0:

                conn.commit()

                save\_checkpoint(conn, token.get("signature", ""), source, i)

                logging.info(f"Checkpoint: {i} tokens procesados")

        except Exception as e:

            logging.error(f"Error procesando token {token}: {e}")

            continue

    conn.commit()

def fetch\_dexscreener(address: str) \-\> dict:

    """

    Obtiene precio y liquidez actuales/históricos de DexScreener.

    Sin API key requerida.

    """

    if not address:

        return {}

    try:

        resp \= requests.get(

            f"https://api.dexscreener.com/latest/dex/tokens/{address}",

            timeout=10

        )

        resp.raise\_for\_status()

        pairs \= resp.json().get("pairs", \[\])

        if not pairs:

            return {}

        p \= pairs\[0\]

        return {

            "initial\_price\_usd": float(p.get("priceUsd", 0\) or 0),

            "initial\_liquidity": int(p.get("liquidity", {}).get("usd", 0\) or 0\)

        }

    except Exception:

        return {}

def backfill\_already\_completed(conn) \-\> bool:

    cursor \= conn.cursor()

    cursor.execute("""

        SELECT id FROM backfill\_log

        WHERE status \= 'completed'

        LIMIT 1

    """)

    return cursor.fetchone() is not None

def get\_last\_checkpoint(conn) \-\> Optional\[str\]:

    cursor \= conn.cursor()

    cursor.execute("""

        SELECT last\_checkpoint FROM backfill\_log

        WHERE status IN ('running', 'partial')

        ORDER BY started\_at DESC

        LIMIT 1

    """)

    row \= cursor.fetchone()

    return row\[0\] if row else None

def save\_checkpoint(conn, checkpoint: str, source: str, count: int):

    cursor \= conn.cursor()

    cursor.execute("""

        INSERT INTO backfill\_log

          (source, date\_range\_from, date\_range\_to,

           tokens\_stored, last\_checkpoint, status)

        VALUES (%s, %s, %s, %s, %s, 'running')

        ON CONFLICT DO NOTHING

    """, (source, DATE\_FROM.date(), DATE\_TO.date(), count, checkpoint))

    conn.commit()

def mark\_backfill\_completed(conn):

    cursor \= conn.cursor()

    cursor.execute("""

        UPDATE backfill\_log SET status \= 'completed', ended\_at \= NOW()

        WHERE status \= 'running'

    """)

    conn.commit()

def parse\_bitquery\_instructions(instructions: list) \-\> list:

    tokens \= \[\]

    for instr in instructions:

        accounts \= instr.get("accounts", \[\])

        token\_addr \= next(

            (a\["address"\] for a in accounts if a.get("isWritable")), None

        )

        tokens.append({

            "address":    token\_addr,

            "created\_at": instr\["block"\]\["timestamp"\]\["time"\],

            "signature":  instr\["transaction"\]\["signature"\]

        })

    return tokens

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)

    main()

---

## **5.2 scripts/collect\_onchain.py**

python

"""

collect\_onchain.py

Monitoriza nuevos tokens en Pump.fun en tiempo real.

Frecuencia: cada 15 minutos via Hermes/cron.

"""

import os

import logging

from datetime import datetime, timedelta

import psycopg2

from solana.rpc.api import Client

PUMP\_PROGRAM\_ADDRESS \= "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

SOLANA\_RPC\_URL       \= os.getenv("SOLANA\_RPC\_URL")

DB\_DSN               \= os.getenv("DATABASE\_URL")

LOOKBACK\_MINUTES     \= 20  \# margen extra sobre los 15 min del cron

def main():

    conn   \= psycopg2.connect(DB\_DSN)

    client \= Client(SOLANA\_RPC\_URL)

    cutoff \= datetime.utcnow() \- timedelta(minutes=LOOKBACK\_MINUTES)

    new\_tokens \= fetch\_new\_tokens(client, cutoff)

    stored     \= 0

    for token in new\_tokens:

        if insert\_token(conn, token):

            stored \+= 1

    log\_execution(conn, "collect\_onchain", stored)

    conn.commit()

    conn.close()

    logging.info(f"collect\_onchain: {stored} tokens nuevos almacenados")

def fetch\_new\_tokens(client: Client, cutoff: datetime) \-\> list:

    tokens \= \[\]

    resp   \= client.get\_signatures\_for\_address(

        PUMP\_PROGRAM\_ADDRESS, limit=200

    )

    for sig in resp.value:

        block\_time \= datetime.utcfromtimestamp(sig.block\_time)

        if block\_time \< cutoff:

            break

        tokens.append({

            "signature":  str(sig.signature),

            "created\_at": block\_time

        })

    return tokens

def insert\_token(conn, token: dict) \-\> bool:

    cursor \= conn.cursor()

    cursor.execute("""

        INSERT INTO tokens (address, created\_at, data\_source)

        VALUES (%s, %s, 'live\_rpc')

        ON CONFLICT (address) DO NOTHING

        RETURNING id

    """, (token\["signature"\], token\["created\_at"\]))

    return cursor.fetchone() is not None

def log\_execution(conn, task: str, count: int):

    cursor \= conn.cursor()

    cursor.execute("""

        INSERT INTO agent\_execution\_log

          (task\_name, status, started\_at, ended\_at, tokens\_processed)

        VALUES (%s, 'success', NOW(), NOW(), %s)

    """, (task, count))

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)

    main()

---

## **5.3 scripts/label\_targets.py**

python

"""

label\_targets.py

Etiqueta tokens con suficiente historia.

Frecuencia: cada hora via Hermes/cron.

"""

import os

import logging

import psycopg2

DB\_DSN                   \= os.getenv("DATABASE\_URL")

LIQUIDITY\_MIN\_THRESHOLD  \= 500    \# USD mínimo para considerar activo

RLUG\_LIQUIDITY\_WITHDRAWN \= 0.80   \# % liquidez retirada \= rug

PUMP\_MULTIPLIER          \= 2.0    \# 2x \= pump 100%

def main():

    conn   \= psycopg2.connect(DB\_DSN)

    cursor \= conn.cursor()

    \# Tokens sin etiquetar con más de 24h de historia

    cursor.execute("""

        SELECT id, created\_at, initial\_price\_usd

        FROM tokens

        WHERE label\_completed \= FALSE

          AND created\_at \< NOW() \- INTERVAL '24 hours'

    """)

    tokens \= cursor.fetchall()

    labeled \= 0

    for token\_id, created\_at, initial\_price in tokens:

        pump  \= compute\_pump(cursor, token\_id, initial\_price)

        rug   \= compute\_rug(cursor, token\_id, created\_at)

        surv  \= compute\_survival(cursor, token\_id, created\_at)

        cursor.execute("""

            UPDATE tokens SET

              pump\_100pc\_24h  \= %s,

              rug\_pull\_48h    \= %s,

              still\_active\_7d \= %s,

              label\_completed \= TRUE

            WHERE id \= %s

        """, (pump, rug, surv, token\_id))

        labeled \+= 1

   conn.commit()

    conn.close()

    logging.info(f"label\_targets: {labeled} tokens etiquetados")

def compute\_pump(cursor, token\_id: int, initial\_price: float) \-\> bool:

    if not initial\_price or initial\_price \== 0:

        return False

    cursor.execute("""

        SELECT price\_usd FROM launches

        WHERE token\_id \= %s

          AND time \>= (SELECT created\_at FROM tokens WHERE id \= %s)

                    \+ INTERVAL '23 hours'

          AND time \<= (SELECT created\_at FROM tokens WHERE id \= %s)

                    \+ INTERVAL '25 hours'

        ORDER BY time DESC

        LIMIT 1

    """, (token\_id, token\_id, token\_id))

    row \= cursor.fetchone()

    if not row or not row\[0\]:

        return False

    return (row\[0\] / initial\_price) \>= PUMP\_MULTIPLIER

def compute\_rug(cursor, token\_id: int, created\_at) \-\> bool:

    \# Condición 1: liquidez retirada \>80% en 48h

    cursor.execute("""

        SELECT liquidity\_pool\_before, liquidity\_pool\_after

        FROM launches

        WHERE token\_id \= %s

          AND time \<= %s \+ INTERVAL '48 hours'

          AND is\_liquidity\_removed \= TRUE

        LIMIT 1

    """, (token\_id, created\_at))

    row \= cursor.fetchone()

    if row and row\[0\] and row\[0\] \> 0:

        withdrawn\_pct \= 1.0 \- (row\[1\] or 0\) / row\[0\]

        if withdrawn\_pct \>= RLUG\_LIQUIDITY\_WITHDRAWN:

            return True

    \# Condición 2: volumen colapsa a 0 tras pico inicial

    cursor.execute("""

        SELECT volume\_60m FROM launches

        WHERE token\_id \= %s

        ORDER BY time ASC

        LIMIT 1

    """, (token\_id,))

    row\_first \= cursor.fetchone()

    cursor.execute("""

        SELECT volume\_60m FROM launches

        WHERE token\_id \= %s

          AND time BETWEEN %s \+ INTERVAL '24 hours'

                       AND %s \+ INTERVAL '48 hours'

        ORDER BY time DESC

        LIMIT 1

    """, (token\_id, created\_at, created\_at))

    row\_last \= cursor.fetchone()

    if row\_first and row\_last:

        if (row\_first\[0\] or 0\) \> 0 and (row\_last\[0\] or 0\) \== 0:

            return True

    return False

def compute\_survival(cursor, token\_id: int, created\_at) \-\> bool:

    \# Solo para tokens con más de 7 días de historia

    cursor.execute("""

        SELECT NOW() \> %s \+ INTERVAL '7 days'

    """, (created\_at,))

    has\_7d \= cursor.fetchone()\[0\]

    if not has\_7d:

        return None  \# todavía no se puede etiquetar

    cursor.execute("""

        SELECT liquidity\_pool\_after, volume\_240m

        FROM launches

        WHERE token\_id \= %s

          AND time BETWEEN %s \+ INTERVAL '6 days 20 hours'

                       AND %s \+ INTERVAL '7 days 4 hours'

        ORDER BY time DESC

        LIMIT 1

    """, (token\_id, created\_at, created\_at))

    row \= cursor.fetchone()

    if not row:

        return False

    liquidity\_ok \= (row\[0\] or 0\) \>= LIQUIDITY\_MIN\_THRESHOLD

    return liquidity\_ok

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)

    main()

---

## **5.4 scripts/compute\_features.py**

python

"""

compute\_features.py

Calcula token\_features desde launches \+ btc\_context.

Frecuencia: cada hora via Hermes/cron.

Feature version actual: v1-onchain-minimal

"""

import os

import logging

import psycopg2

DB\_DSN          \= os.getenv("DATABASE\_URL")

FEATURE\_VERSION \= os.getenv("FEATURE\_VERSION", "v1-onchain-minimal")

def main():

    conn   \= psycopg2.connect(DB\_DSN)

    cursor \= conn.cursor()

    \# Tokens etiquetados sin features todavía

    cursor.execute("""

        SELECT t.id, t.created\_at

        FROM tokens t

        LEFT JOIN token\_features tf

          ON tf.token\_id \= t.id AND tf.feature\_version \= %s

        WHERE t.label\_completed \= TRUE

          AND tf.id IS NULL

    """, (FEATURE\_VERSION,))

    tokens \= cursor.fetchall()

    computed \= 0

    for token\_id, created\_at in tokens:

        features \= compute\_all\_features(cursor, token\_id, created\_at)

        if features:

            insert\_features(cursor, token\_id, features)

            computed \+= 1

    conn.commit()

    conn.close()

    logging.info(f"compute\_features: {computed} tokens con features calculadas")

def compute\_all\_features(cursor, token\_id: int, created\_at) \-\> dict:

    launches \= get\_launches(cursor, token\_id)

    if not launches:

        return None

    btc \= get\_btc\_context(cursor, created\_at)

    \# 1\. Velocidad de transacciones

    tx\_velocity\_0\_5m    \= safe\_div(launches.get("txs\_0\_5m", 0),    5.0)

    tx\_velocity\_5\_60m   \= safe\_div(launches.get("txs\_5\_60m", 0),   55.0)

    tx\_velocity\_60\_240m \= safe\_div(launches.get("txs\_60\_240m", 0), 180.0)

    \# 2\. Wallets únicas

    unique\_wallets\_0\_10m \= launches.get("unique\_wallets\_0\_10m", 0\)

    unique\_wallets\_0\_60m \= launches.get("unique\_wallets\_0\_60m", 0\)

    \# 3\. Ratio compra/venta (ventana 0-30 min)

    buy  \= launches.get("buy\_tx\_0\_30m", 0\) or 0

    sell \= launches.get("sell\_tx\_0\_30m", 0\) or 0

    buy\_tx\_ratio\_0\_30m \= safe\_div(buy, buy \+ sell)

    \# 4\. Liquidez

    liq\_before \= launches.get("liquidity\_pool\_before", 0\) or 0

    liq\_after  \= launches.get("liquidity\_pool\_after", 0\) or 0

    liq\_t1h    \= launches.get("liq\_t1h", 0\) or 0

    liq\_t2h    \= launches.get("liq\_t2h", 0\) or 0

    liquidity\_add\_0\_10m     \= liq\_after \> liq\_before

    liquidity\_remove\_0\_2h   \= launches.get("is\_liquidity\_removed", False)

    liquidity\_drop\_1\_2h\_pct \= safe\_div(liq\_t1h \- liq\_t2h, liq\_t1h)

    \# 5\. Concentración

    top\_10\_wallets\_pct\_0\_1h  \= launches.get("top\_10\_wallets\_pct\_0\_1h", None)

    gini\_concentration\_0\_1h  \= launches.get("gini\_concentration\_0\_1h", None)

    \# 6\. Contexto BTC

    btc\_change\_pct\_6h  \= btc.get("change\_pct\_6h", None)

    btc\_dominance\_pct  \= btc.get("dominance\_pct", None)

    \# 7\. Timing

    launch\_hour\_utc    \= created\_at.hour

    launch\_day\_of\_week \= created\_at.weekday()

    return {

        "feature\_version":           FEATURE\_VERSION,

        "max\_feature\_window\_minutes": 30,

        "tx\_velocity\_0\_5m":          tx\_velocity\_0\_5m,

        "tx\_velocity\_5\_60m":         tx\_velocity\_5\_60m,

        "tx\_velocity\_60\_240m":       tx\_velocity\_60\_240m,

        "unique\_wallets\_0\_10m":      unique\_wallets\_0\_10m,

        "unique\_wallets\_0\_60m":      unique\_wallets\_0\_60m,

        "buy\_tx\_ratio\_0\_30m":        buy\_tx\_ratio\_0\_30m,

        "liquidity\_add\_0\_10m":       liquidity\_add\_0\_10m,

        "liquidity\_remove\_0\_2h":     liquidity\_remove\_0\_2h,

        "liquidity\_drop\_1\_2h\_pct":   liquidity\_drop\_1\_2h\_pct,

        "top\_10\_wallets\_pct\_0\_1h":   top\_10\_wallets\_pct\_0\_1h,

        "gini\_concentration\_0\_1h":   gini\_concentration\_0\_1h,

        "btc\_change\_pct\_6h":         btc\_change\_pct\_6h,

        "btc\_dominance\_pct":         btc\_dominance\_pct,

        "launch\_hour\_utc":           launch\_hour\_utc,

        "launch\_day\_of\_week":        launch\_day\_of\_week,

    }

def get\_launches(cursor, token\_id: int) \-\> dict:

    cursor.execute("""

        SELECT

          MAX(txs\_0\_5m)               AS txs\_0\_5m,

          MAX(txs\_5\_60m)              AS txs\_5\_60m,

          MAX(txs\_60\_240m)            AS txs\_60\_240m,

          MAX(unique\_wallets\_0\_10m)   AS unique\_wallets\_0\_10m,

          MAX(unique\_wallets\_0\_60m)   AS unique\_wallets\_0\_60m,

          MAX(buy\_tx\_0\_30m)           AS buy\_tx\_0\_30m,

          MAX(sell\_tx\_0\_30m)          AS sell\_tx\_0\_30m,

          MAX(liquidity\_pool\_before)  AS liquidity\_pool\_before,

          MAX(liquidity\_pool\_after)   AS liquidity\_pool\_after,

          MAX(top\_10\_wallets\_pct\_0\_1h) AS top\_10\_wallets\_pct\_0\_1h,

          MAX(gini\_concentration\_0\_1h) AS gini\_concentration\_0\_1h,

          BOOL\_OR(is\_liquidity\_removed) AS is\_liquidity\_removed

        FROM launches

        WHERE token\_id \= %s

    """, (token\_id,))

    row \= cursor.fetchone()

    if not row:

        return {}

    cols \= \[

        "txs\_0\_5m","txs\_5\_60m","txs\_60\_240m",

        "unique\_wallets\_0\_10m","unique\_wallets\_0\_60m",

        "buy\_tx\_0\_30m","sell\_tx\_0\_30m",

        "liquidity\_pool\_before","liquidity\_pool\_after",

        "top\_10\_wallets\_pct\_0\_1h","gini\_concentration\_0\_1h",

        "is\_liquidity\_removed"

    \]

    return dict(zip(cols, row))

def get\_btc\_context(cursor, created\_at) \-\> dict:

    cursor.execute("""

        SELECT change\_pct\_6h, dominance\_pct

        FROM btc\_context

        WHERE time \<= %s

        ORDER BY time DESC

        LIMIT 1

    """, (created\_at,))

    row \= cursor.fetchone()

    if not row:

        return {}

    return {"change\_pct\_6h": row\[0\], "dominance\_pct": row\[1\]}

def insert\_features(cursor, token\_id: int, f: dict):

    cursor.execute("""

        INSERT INTO token\_features (

          token\_id, feature\_version, max\_feature\_window\_minutes,

          tx\_velocity\_0\_5m, tx\_velocity\_5\_60m, tx\_velocity\_60\_240m,

          unique\_wallets\_0\_10m, unique\_wallets\_0\_60m,

          buy\_tx\_ratio\_0\_30m,

          liquidity\_add\_0\_10m, liquidity\_remove\_0\_2h, liquidity\_drop\_1\_2h\_pct,

          top\_10\_wallets\_pct\_0\_1h, gini\_concentration\_0\_1h,

          btc\_change\_pct\_6h, btc\_dominance\_pct,

          launch\_hour\_utc, launch\_day\_of\_week

        ) VALUES (

          %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s

        )

        ON CONFLICT (token\_id, feature\_version) DO UPDATE SET

          updated\_at \= NOW()

    """, (

        token\_id,

        f\["feature\_version"\],

        f\["max\_feature\_window\_minutes"\],

        f\["tx\_velocity\_0\_5m"\],

        f\["tx\_velocity\_5\_60m"\],

        f\["tx\_velocity\_60\_240m"\],

        f\["unique\_wallets\_0\_10m"\],

        f\["unique\_wallets\_0\_60m"\],

        f\["buy\_tx\_ratio\_0\_30m"\],

        f\["liquidity\_add\_0\_10m"\],

        f\["liquidity\_remove\_0\_2h"\],

        f\["liquidity\_drop\_1\_2h\_pct"\],

        f\["top\_10\_wallets\_pct\_0\_1h"\],

        f\["gini\_concentration\_0\_1h"\],

        f\["btc\_change\_pct\_6h"\],

        f\["btc\_dominance\_pct"\],

        f\["launch\_hour\_utc"\],

        f\["launch\_day\_of\_week"\],

    ))

def safe\_div(a, b) \-\> float:

    if not b or b \== 0:

        return 0.0

    return float(a or 0\) / float(b)

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)

    main()

---

## **5.5 scripts/train\_models\_all.py (continuación)**

python

"""

train\_models\_all.py

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

from sklearn.metrics import roc\_auc\_score, f1\_score, log\_loss

from xgboost import XGBClassifier

DB\_DSN          \= os.getenv("DATABASE\_URL")

FEATURE\_VERSION \= os.getenv("FEATURE\_VERSION", "v1-onchain-minimal")

MODELS\_DIR      \= os.getenv("MODELS\_DIR", "/data/models")

TEST\_DAYS       \= 14  \# últimos 14 días como test, resto como train

FEATURE\_COLS \= \[

    "tx\_velocity\_0\_5m",

    "tx\_velocity\_5\_60m",

    "tx\_velocity\_60\_240m",

    "unique\_wallets\_0\_10m",

    "unique\_wallets\_0\_60m",

    "buy\_tx\_ratio\_0\_30m",

    "liquidity\_add\_0\_10m",

    "liquidity\_remove\_0\_2h",

    "liquidity\_drop\_1\_2h\_pct",

    "top\_10\_wallets\_pct\_0\_1h",

    "gini\_concentration\_0\_1h",

    "btc\_change\_pct\_6h",

    "btc\_dominance\_pct",

    "launch\_hour\_utc",

    "launch\_day\_of\_week",

\]

MODELS\_CONFIG \= \[

    {

        "name":        "model-A-pump",

        "target\_col":  "pump\_100pc\_24h",

        "description": "pump \>= 100% en 24h",

    },

    {

        "name":        "model-B-rug",

        "target\_col":  "rug\_pull\_48h",

        "description": "rug pull en \<= 48h",

    },

    {

        "name":        "model-C-survival",

        "target\_col":  "still\_active\_7d",

        "description": "token activo a los 7 dias",

    },

\]

def main():

    conn \= psycopg2.connect(DB\_DSN)

    df   \= load\_dataset(conn)

    if df.empty or len(df) \< 100:

        logging.warning("Datos insuficientes para entrenar. Minimo 100 tokens.")

        conn.close()

        return

    cutoff\_date \= datetime.utcnow() \- timedelta(days=TEST\_DAYS)

    df\_train    \= df\[df\["created\_at"\] \< cutoff\_date\].copy()

    df\_test     \= df\[df\["created\_at"\] \>= cutoff\_date\].copy()

    logging.info(f"Train: {len(df\_train)} tokens | Test: {len(df\_test)} tokens")

    os.makedirs(MODELS\_DIR, exist\_ok=True)

    for cfg in MODELS\_CONFIG:

        train\_model(conn, df\_train, df\_test, cfg)

    conn.close()

def load\_dataset(conn) \-\> pd.DataFrame:

    query \= """

        SELECT

            t.id,

            t.created\_at,

            t.pump\_100pc\_24h,

            t.rug\_pull\_48h,

            t.still\_active\_7d,

            tf.tx\_velocity\_0\_5m,

            tf.tx\_velocity\_5\_60m,

            tf.tx\_velocity\_60\_240m,

            tf.unique\_wallets\_0\_10m,

            tf.unique\_wallets\_0\_60m,

            tf.buy\_tx\_ratio\_0\_30m,

            tf.liquidity\_add\_0\_10m,

            tf.liquidity\_remove\_0\_2h,

            tf.liquidity\_drop\_1\_2h\_pct,

            tf.top\_10\_wallets\_pct\_0\_1h,

            tf.gini\_concentration\_0\_1h,

            tf.btc\_change\_pct\_6h,

            tf.btc\_dominance\_pct,

            tf.launch\_hour\_utc,

            tf.launch\_day\_of\_week

        FROM tokens t

        INNER JOIN token\_features tf

            ON tf.token\_id \= t.id

            AND tf.feature\_version \= %s

        WHERE t.label\_completed \= TRUE

          AND t.pump\_100pc\_24h IS NOT NULL

          AND t.rug\_pull\_48h IS NOT NULL

        ORDER BY t.created\_at ASC

    """

    df \= pd.read\_sql(query, conn, params=(FEATURE\_VERSION,))

    df\["liquidity\_add\_0\_10m"\]   \= df\["liquidity\_add\_0\_10m"\].astype(float)

    df\["liquidity\_remove\_0\_2h"\] \= df\["liquidity\_remove\_0\_2h"\].astype(float)

    return df

def train\_model(conn, df\_train: pd.DataFrame, df\_test: pd.DataFrame, cfg: dict):

    name       \= cfg\["name"\]

    target\_col \= cfg\["target\_col"\]

    \# Eliminar filas sin target

    train \= df\_train\[df\_train\[target\_col\].notna()\].copy()

    test  \= df\_test\[df\_test\[target\_col\].notna()\].copy()

    if len(train) \< 50:

        logging.warning(f"{name}: datos insuficientes ({len(train)} train). Saltando.")

        return

    X\_train \= train\[FEATURE\_COLS\].fillna(0)

    y\_train \= train\[target\_col\].astype(int)

    X\_test  \= test\[FEATURE\_COLS\].fillna(0)

    y\_test  \= test\[target\_col\].astype(int)

    \# Manejar desbalance de clases

    pos\_weight \= (y\_train \== 0).sum() / max((y\_train \== 1).sum(), 1\)

    model \= XGBClassifier(

        n\_estimators=300,

        max\_depth=4,

        learning\_rate=0.05,

        subsample=0.8,

        colsample\_bytree=0.8,

        scale\_pos\_weight=pos\_weight,

        use\_label\_encoder=False,

        eval\_metric="logloss",

        random\_state=42,

        n\_jobs=-1,

    )

    model.fit(

        X\_train, y\_train,

        eval\_set=\[(X\_test, y\_test)\],

        verbose=False,

    )

    \# \--- Métricas \---

    probs \= model.predict\_proba(X\_test)\[:, 1\]

    precision\_at\_10 \= compute\_precision\_at\_k(y\_test.values, probs, k=10)

    precision\_at\_20 \= compute\_precision\_at\_k(y\_test.values, probs, k=20)

    recall\_at\_10    \= compute\_recall\_at\_k(y\_test.values, probs, k=10)

    auc             \= roc\_auc\_score(y\_test, probs) if y\_test.nunique() \> 1 else 0.0

    f1              \= f1\_score(y\_test, (probs \>= 0.5).astype(int), zero\_division=0)

    ll              \= log\_loss(y\_test, probs) if y\_test.nunique() \> 1 else 0.0

    logging.info(

        f"{name} | P@10={precision\_at\_10:.3f} P@20={precision\_at\_20:.3f} "

        f"AUC={auc:.3f} F1={f1:.3f} LogLoss={ll:.3f}"

    )

    \# \--- Guardar modelo \---

    timestamp     \= datetime.utcnow().strftime("%Y%m%d\_%H%M")

    model\_version \= f"{name}-{FEATURE\_VERSION}-{timestamp}"

    model\_path    \= os.path.join(MODELS\_DIR, f"{model\_version}.pkl")

    with open(model\_path, "wb") as f:

        pickle.dump(model, f)

    \# \--- Guardar métricas en DB \---

    cursor \= conn.cursor()

    cursor.execute("""

        INSERT INTO model\_performance (

            model\_name, feature\_version, model\_version,

            train\_start, train\_end, test\_start, test\_end,

            n\_tokens\_train, n\_tokens\_test, pct\_positive,

            precision\_at\_10, precision\_at\_20, recall\_at\_10,

            auc\_roc, f1\_score, log\_loss,

            model\_file\_path

        ) VALUES (

            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s

        )

    """, (

        name,

        FEATURE\_VERSION,

        model\_version,

        df\_train\["created\_at"\].min().date(),

        df\_train\["created\_at"\].max().date(),

        df\_test\["created\_at"\].min().date() if len(df\_test) \> 0 else None,

        df\_test\["created\_at"\].max().date() if len(df\_test) \> 0 else None,

        len(train),

        len(test),

        float(y\_train.mean()),

        precision\_at\_10,

        precision\_at\_20,

        recall\_at\_10,

        auc,

        f1,

        ll,

        model\_path,

    ))

    conn.commit()

    \# \--- Actualizar predicciones en tabla tokens \---

    update\_predictions(conn, model, model\_version, name, target\_col)

def update\_predictions(conn, model, model\_version: str,

                        model\_name: str, target\_col: str):

    """

    Recalcula probabilidades para todos los tokens con features disponibles

    y actualiza la columna correspondiente en tokens.

    """

    cursor \= conn.cursor()

    cursor.execute("""

        SELECT t.id, tf.tx\_velocity\_0\_5m, tf.tx\_velocity\_5\_60m,

               tf.tx\_velocity\_60\_240m, tf.unique\_wallets\_0\_10m,

               tf.unique\_wallets\_0\_60m, tf.buy\_tx\_ratio\_0\_30m,

               tf.liquidity\_add\_0\_10m, tf.liquidity\_remove\_0\_2h,

               tf.liquidity\_drop\_1\_2h\_pct, tf.top\_10\_wallets\_pct\_0\_1h,

               tf.gini\_concentration\_0\_1h, tf.btc\_change\_pct\_6h,

               tf.btc\_dominance\_pct, tf.launch\_hour\_utc,

               tf.launch\_day\_of\_week

        FROM tokens t

        INNER JOIN token\_features tf ON tf.token\_id \= t.id

          AND tf.feature\_version \= %s

    """, (FEATURE\_VERSION,))

    rows \= cursor.fetchall()

    if not rows:

        return

    ids \= \[r\[0\] for r in rows\]

    X   \= pd.DataFrame(

        \[r\[1:\] for r in rows\],

        columns=FEATURE\_COLS

    ).fillna(0)

    probs \= model.predict\_proba(X)\[:, 1\]

    prob\_col\_map \= {

        "model-A-pump":     "prob\_pump\_24h",

        "model-B-rug":      "prob\_rug\_48h",

        "model-C-survival": "prob\_survival\_7d",

    }

    prob\_col      \= prob\_col\_map.get(model\_name, "prob\_pump\_24h")

    version\_col   \= {"model-A-pump":     "model\_A\_version",

                     "model-B-rug":      "model\_B\_version",

                     "model-C-survival": "model\_C\_version"}.get(model\_name)

    for token\_id, prob in zip(ids, probs):

        cursor.execute(f"""

            UPDATE tokens

            SET {prob\_col} \= %s,

                {version\_col} \= %s,

                predicted\_at \= NOW()

            WHERE id \= %s

        """, (float(prob), model\_version, token\_id))

    conn.commit()

    logging.info(f"update\_predictions: {len(ids)} tokens actualizados con {model\_name}")

def compute\_precision\_at\_k(y\_true: np.ndarray,

                            probs: np.ndarray, k: int) \-\> float:

    if len(probs) \< k:

        k \= len(probs)

    top\_k\_idx    \= np.argsort(probs)\[::-1\]\[:k\]

    y\_top\_k      \= y\_true\[top\_k\_idx\]

    return float(y\_top\_k.sum()) / k

def compute\_recall\_at\_k(y\_true: np.ndarray,

                         probs: np.ndarray, k: int) \-\> float:

    total\_positive \= y\_true.sum()

    if total\_positive \== 0:

        return 0.0

    if len(probs) \< k:

        k \= len(probs)

    top\_k\_idx \= np.argsort(probs)\[::-1\]\[:k\]

    y\_top\_k   \= y\_true\[top\_k\_idx\]

    return float(y\_top\_k.sum()) / float(total\_positive)

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)  
    main()

## **CAPÍTULO 6 — Modelos ML: entrenamiento y métricas**

## **6.1 Diseño de los tres modelos**

| Modelo | Nombre | Target | Horizonte de features | Horizonte de outcome |
| :---- | :---- | :---- | :---- | :---- |
| **A** | **model-A-pump** | **pump\_100pc\_24h** | **0–30 min** | **24 h** |
| **B** | **model-B-rug** | **rug\_pull\_48h** | **0–2 h** | **48 h** |
| **C** | **model-C-survival** | **still\_active\_7d** | **0–4 h** | **7 días** |

## **Regla estricta de ventanas:**

* ## **Modelo A usa SOLO features con max\_feature\_window\_minutes \<= 30.**

* ## **Modelo B usa SOLO features con max\_feature\_window\_minutes \<= 120.**

* ## **Modelo C puede usar features hasta 240 min.**

* ## **Esta regla previene leakage temporal y se verifica en train\_models\_all.py**   **filtrando por max\_feature\_window\_minutes antes de entrenar.**

## ---

## **6.2 Features por modelo**

## **Modelo A — Pump (ventana máx 30 min)**

## **python**

## **FEATURES\_MODEL\_A \= \[**

##     **"tx\_velocity\_0\_5m",**

##     **"unique\_wallets\_0\_10m",**

##     **"buy\_tx\_ratio\_0\_30m",**

##     **"liquidity\_add\_0\_10m",**

##     **"top\_10\_wallets\_pct\_0\_1h",   \# calculada en t+10m, no t+1h real**

##     **"btc\_change\_pct\_6h",**

##     **"btc\_dominance\_pct",**

##     **"launch\_hour\_utc",**

##     **"launch\_day\_of\_week",**

## **\]**

## 

## **Modelo B — Rug (ventana máx 120 min)**

## **python**

## **FEATURES\_MODEL\_B \= \[**

##     **"tx\_velocity\_0\_5m",**

##     **"tx\_velocity\_5\_60m",**

##     **"unique\_wallets\_0\_10m",**

##     **"unique\_wallets\_0\_60m",**

##     **"buy\_tx\_ratio\_0\_30m",**

##     **"liquidity\_add\_0\_10m",**

##     **"liquidity\_remove\_0\_2h",**

##     **"liquidity\_drop\_1\_2h\_pct",**

##     **"top\_10\_wallets\_pct\_0\_1h",**

##     **"gini\_concentration\_0\_1h",**

##     **"btc\_change\_pct\_6h",**

##     **"launch\_hour\_utc",**

## **\]**

## 

## **Modelo C — Survival (ventana máx 240 min)**

## **python**

## **FEATURES\_MODEL\_C \= \[**

##     **"tx\_velocity\_0\_5m",**

##     **"tx\_velocity\_5\_60m",**

##     **"tx\_velocity\_60\_240m",**

##     **"unique\_wallets\_0\_10m",**

##     **"unique\_wallets\_0\_60m",**

##     **"buy\_tx\_ratio\_0\_30m",**

##     **"liquidity\_add\_0\_10m",**

##     **"liquidity\_remove\_0\_2h",**

##     **"liquidity\_drop\_1\_2h\_pct",**

##     **"top\_10\_wallets\_pct\_0\_1h",**

##     **"gini\_concentration\_0\_1h",**

##     **"btc\_change\_pct\_6h",**

##     **"btc\_dominance\_pct",**

##     **"launch\_hour\_utc",**

##     **"launch\_day\_of\_week",**

## **\]**

## 

## ---

## **6.3 Split temporal estricto**

## **text**

## **Timeline de datos disponibles tras backfill de 90 días:**

## 

## **|←────────────── 90 días ──────────────────→|**

## **|←── 76 días TRAIN ──→|←── 14 días TEST ──→|**

##                        **↑**

##                   **cutoff\_date \=**

##                   **hoy \- TEST\_DAYS (14)**

## 

## **Reglas:**

## **\- NUNCA split aleatorio (train\_test\_split con shuffle=False obligatorio).**

## **\- NUNCA usar datos del futuro para entrenar.**

## **\- El test set representa siempre los últimos N días.**

## **\- En producción, el test set avanza con el tiempo (walk-forward).**

## 

## **python**

## **\# En train\_models\_all.py**

## **TEST\_DAYS   \= 14**

## **cutoff\_date \= datetime.utcnow() \- timedelta(days=TEST\_DAYS)**

## 

## **df\_train \= df\[df\["created\_at"\] \<  cutoff\_date\]**

## **df\_test  \= df\[df\["created\_at"\] \>= cutoff\_date\]**

## 

## **\# Verificación anti-leakage**

## **assert df\_train\["created\_at"\].max() \< df\_test\["created\_at"\].min(), \\**

##     **"ERROR: leakage temporal detectado en el split"**

## 

## ---

## **6.4 Configuración XGBoost por modelo**

## **python**

## **\# Parámetros base (iguales para los tres modelos en v1)**

## **BASE\_PARAMS \= {**

##     **"n\_estimators":      300,**

##     **"max\_depth":         4,**

##     **"learning\_rate":     0.05,**

##     **"subsample":         0.8,**

##     **"colsample\_bytree":  0.8,**

##     **"use\_label\_encoder": False,**

##     **"eval\_metric":       "logloss",**

##     **"random\_state":      42,**

##     **"n\_jobs":            \-1,**

## **}**

## 

## **\# Ajuste de desbalance de clases**

## **\# Pump.fun: \~5-10% de tokens hacen pump real**

## **\# \~80-90% de tokens son rug o mueren rápido**

## **\# scale\_pos\_weight \= n\_negativos / n\_positivos**

## **pos\_weight \= (y\_train \== 0).sum() / max((y\_train \== 1).sum(), 1\)**

## 

## **model \= XGBClassifier(\*\*BASE\_PARAMS, scale\_pos\_weight=pos\_weight)**

## 

## **model.fit(**

##     **X\_train, y\_train,**

##     **eval\_set=\[(X\_test, y\_test)\],**

##     **verbose=False,**

## **)**

## 

## ---

## **6.5 Métricas: definición y cálculo**

## **Métrica principal: precision@top\_k**

## **text**

## **¿Qué mide?**

##   **De los K tokens con mayor probabilidad predicha,**

##   **cuántos realmente cumplieron el outcome.**

## 

## **¿Por qué es la métrica correcta?**

##   **En trading no te importa clasificar bien todos los tokens.**

##   **Te importa que cuando el modelo dice "este es interesante",**

##   **tenga razón la mayor parte de las veces.**

## 

## **Ejemplo real:**

##   **\- Hay 1000 tokens en el test set.**

##   **\- Solo 50 hacen pump real (5%).**

##   **\- El modelo ordena los 1000 por probabilidad descendente.**

##   **\- Tomamos los top 10\.**

##   **\- Si 6 de esos 10 hicieron pump real → precision@10 \= 0.60.**

##   **\- Random baseline: precision@10 ≈ 0.05 (5% de la clase).**

##   **\- Un modelo con precision@10 \= 0.60 es 12x mejor que random.**

## 

## **python**

## **def compute\_precision\_at\_k(y\_true: np.ndarray,**

##                             **probs: np.ndarray,**

##                             **k: int) \-\> float:**

##     **"""**

##     **Fracción de aciertos entre los k tokens**

##     **con mayor probabilidad predicha.**

##     **"""**

##     **k       \= min(k, len(probs))**

##     **top\_idx \= np.argsort(probs)\[::-1\]\[:k\]**

##     **return float(y\_true\[top\_idx\].sum()) / k**

## 

## 

## **def compute\_recall\_at\_k(y\_true: np.ndarray,**

##                          **probs: np.ndarray,**

##                          **k: int) \-\> float:**

##     **"""**

##     **Fracción de positivos reales capturados**

##     **en los top k tokens predichos.**

##     **"""**

##     **total\_pos \= y\_true.sum()**

##     **if total\_pos \== 0:**

##         **return 0.0**

##     **k       \= min(k, len(probs))**

##     **top\_idx \= np.argsort(probs)\[::-1\]\[:k\]**

##     **return float(y\_true\[top\_idx\].sum()) / float(total\_pos)**

## 

## **Métricas secundarias**

## **python**

## **from sklearn.metrics import roc\_auc\_score, f1\_score, log\_loss**

## 

## **\# AUC-ROC: mide la capacidad de ranking general del modelo**

## **\# Útil para comparar versiones de modelo entre sí**

## **auc \= roc\_auc\_score(y\_test, probs) if y\_test.nunique() \> 1 else 0.0**

## 

## **\# F1: balance entre precision y recall en threshold 0.5**

## **\# Útil para detectar si el modelo está sesgado a una clase**

## **f1 \= f1\_score(y\_test, (probs \>= 0.5).astype(int), zero\_division=0)**

## 

## **\# LogLoss: mide calibración de probabilidades**

## **\# Un modelo bien calibrado tiene logloss bajo**

## **ll \= log\_loss(y\_test, probs) if y\_test.nunique() \> 1 else 0.0**

## 

## **Umbrales de aceptación mínimos (v1)**

## **python**

## **\# Si un modelo no supera estos umbrales en test temporal,**

## **\# NO se despliega y se registra en model\_performance con nota.**

## 

## **MINIMUM\_THRESHOLDS \= {**

##     **"model-A-pump":     {"precision\_at\_10": 0.40, "auc\_roc": 0.60},**

##     **"model-B-rug":      {"precision\_at\_10": 0.50, "auc\_roc": 0.65},**

##     **"model-C-survival": {"precision\_at\_10": 0.45, "auc\_roc": 0.60},**

## **}**

## 

## **def model\_passes\_threshold(model\_name: str,**

##                             **precision\_at\_10: float,**

##                             **auc\_roc: float) \-\> bool:**

##     **thresholds \= MINIMUM\_THRESHOLDS.get(model\_name, {})**

##     **return (**

##         **precision\_at\_10 \>= thresholds.get("precision\_at\_10", 0.0)**

##         **and auc\_roc     \>= thresholds.get("auc\_roc", 0.0)**

##     **)**

## 

## ---

## **6.6 Feature importance y diagnóstico**

## **python**

## **def log\_feature\_importance(model: XGBClassifier,**

##                             **feature\_cols: list,**

##                             **model\_name: str):**

##     **"""**

##     **Registra las features más importantes después de entrenar.**

##     **Útil para detectar si el modelo depende de features inesperadas**

##     **(posible señal de leakage o sobreajuste).**

##     **"""**

##     **importances \= model.feature\_importances\_**

##     **ranked \= sorted(**

##         **zip(feature\_cols, importances),**

##         **key=lambda x: x\[1\],**

##         **reverse=True**

##     **)**

## 

##     **logging.info(f"\\n=== Feature importance: {model\_name} \===")**

##     **for feat, imp in ranked:**

##         **bar \= "█" \* int(imp \* 50\)**

##         **logging.info(f"  {feat:\<35} {imp:.4f} {bar}")**

## 

##     **\# Alerta si una sola feature domina demasiado**

##     **top\_importance \= ranked\[0\]\[1\] if ranked else 0**

##     **if top\_importance \> 0.40:**

##         **logging.warning(**

##             **f"ALERTA: '{ranked\[0\]\[0\]}' tiene importancia {top\_importance:.2f}. "**

##             **"Posible leakage o feature dominante. Revisar."**

##         **)**

## 

## ---

## **6.7 Versionado de modelos**

## **text**

## **Esquema de nombres de versión:**

##   **{model\_name}-{feature\_version}-{timestamp}**

## 

## **Ejemplo:**

##   **model-A-pump-v1-onchain-minimal-20260322\_0300**

## 

## **Fichero en disco:**

##   **/data/models/model-A-pump-v1-onchain-minimal-20260322\_0300.pkl**

## 

## **Registro en model\_performance:**

##   **model\_name    \= "model-A-pump"**

##   **feature\_version \= "v1-onchain-minimal"**

##   **model\_version \= "model-A-pump-v1-onchain-minimal-20260322\_0300"**

##   **model\_file\_path \= "/data/models/model-A-pump-v1-onchain-minimal-20260322\_0300.pkl"**

## 

## **Política de retención:**

##   **\- Mantener los últimos 5 modelos por cada model\_name.**

##   **\- Borrar automáticamente los más antiguos.**

##   **\- NUNCA borrar un modelo si es el único con precision\_at\_10 \>= 0.40.**

## 

## **python**

## **def cleanup\_old\_models(models\_dir: str,**

##                         **model\_name: str,**

##                         **keep\_last: int \= 5):**

##     **"""**

##     **Borra modelos antiguos manteniendo los últimos keep\_last.**

##     **"""**

##     **import glob**

##     **pattern \= os.path.join(models\_dir, f"{model\_name}-\*.pkl")**

##     **files   \= sorted(glob.glob(pattern))**

## 

##     **if len(files) \<= keep\_last:**

##         **return**

## 

##     **to\_delete \= files\[:-keep\_last\]**

##     **for f in to\_delete:**

##         **os.remove(f)**

##         **logging.info(f"Modelo antiguo borrado: {f}")**

## 

## ---

## **6.8 Walk-forward validation (para producción)**

## **Una vez el sistema está en producción, el reentrenamiento diario** **implementa automáticamente una walk-forward validation:**

## **text**

## **Semana 1:  Train=\[días 1-76\]  Test=\[días 77-90\]**

## **Semana 2:  Train=\[días 1-77\]  Test=\[días 78-91\]**

## **Semana 3:  Train=\[días 1-78\]  Test=\[días 79-92\]**

## **...**

## 

## **Cada día que pasa:**

## **\- El train set crece en 1 día.**

## **\- El test set avanza en 1 día.**

## **\- precision@top\_k se recalcula sobre datos siempre frescos.**

## **\- model\_performance acumula el histórico de métricas.**

## 

## **python**

## **\# Visualizar evolución de precision@10 en el tiempo**

## **\# (query para ejecutar en psql o Jupyter)**

## **SELECT**

##     **DATE(created\_at)    AS fecha,**

##     **model\_name,**

##     **precision\_at\_10,**

##     **auc\_roc**

## **FROM model\_performance**

## **WHERE model\_name \= 'model-A-pump'**

## **ORDER BY created\_at ASC;**

## **CAPÍTULO 7 — Generación y validación de hipótesis**

## **7.1 scripts/generate\_hypotheses\_llm.py**

python

"""

generate\_hypotheses\_llm.py

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

DB\_DSN           \= os.getenv("DATABASE\_URL")

LITELLM\_ENDPOINT \= os.getenv("LITELLM\_ENDPOINT", "http://100.68.1.180:8080/v1")

LITELLM\_MODEL    \= os.getenv("LITELLM\_MODEL", "qwen3.5")

LITELLM\_API\_KEY  \= os.getenv("LITELLM\_API\_KEY", "local")

FEATURE\_VERSION  \= os.getenv("FEATURE\_VERSION", "v1-onchain-minimal")

TOP\_N            \= 20  \# winners y losers a comparar

def main():

    conn \= psycopg2.connect(DB\_DSN)

    for target\_model, target\_col in \[

        ("pump",     "pump\_100pc\_24h"),

        ("rug",      "rug\_pull\_48h"),

        ("survival", "still\_active\_7d"),

    \]:

        logging.info(f"Generando hipótesis para modelo: {target\_model}")

        winners \= fetch\_top\_n(conn, target\_col, True,  TOP\_N)

        losers  \= fetch\_top\_n(conn, target\_col, False, TOP\_N)

        if len(winners) \< 5 or len(losers) \< 5:

            logging.warning(f"Datos insuficientes para {target\_model}. Saltando.")

            continue

        hypotheses \= call\_llm(winners, losers, target\_model)

        for h in hypotheses:

            insert\_hypothesis(conn, h, target\_model)

        logging.info(f"{target\_model}: {len(hypotheses)} hipótesis generadas")

    conn.close()

def fetch\_top\_n(conn, target\_col: str,

                is\_winner: bool, n: int) \-\> list:

    """

    Devuelve los N tokens con mayor/menor probabilidad

    junto a sus features completas (filas brutas, no promedios).

    """

    prob\_col \= {

        "pump\_100pc\_24h":  "prob\_pump\_24h",

        "rug\_pull\_48h":    "prob\_rug\_48h",

        "still\_active\_7d": "prob\_survival\_7d",

    }\[target\_col\]

    order \= "DESC" if is\_winner else "ASC"

    cursor \= conn.cursor()

    cursor.execute(f"""

        SELECT

            t.address,

            t.created\_at,

            t.{target\_col},

            t.{prob\_col},

            tf.tx\_velocity\_0\_5m,

            tf.tx\_velocity\_5\_60m,

            tf.tx\_velocity\_60\_240m,

            tf.unique\_wallets\_0\_10m,

            tf.unique\_wallets\_0\_60m,

            tf.buy\_tx\_ratio\_0\_30m,

            tf.liquidity\_add\_0\_10m,

            tf.liquidity\_remove\_0\_2h,

            tf.liquidity\_drop\_1\_2h\_pct,

            tf.top\_10\_wallets\_pct\_0\_1h,

            tf.gini\_concentration\_0\_1h,

            tf.btc\_change\_pct\_6h,

            tf.btc\_dominance\_pct,

            tf.launch\_hour\_utc,

            tf.launch\_day\_of\_week

        FROM tokens t

        INNER JOIN token\_features tf

            ON tf.token\_id \= t.id

            AND tf.feature\_version \= %s

        WHERE t.{target\_col} \= %s

          AND t.label\_completed \= TRUE

        ORDER BY t.{prob\_col} {order}

        LIMIT %s

    """, (FEATURE\_VERSION, is\_winner, n))

    cols \= \[

        "address", "created\_at", "target", "probability",

        "tx\_velocity\_0\_5m", "tx\_velocity\_5\_60m", "tx\_velocity\_60\_240m",

        "unique\_wallets\_0\_10m", "unique\_wallets\_0\_60m",

        "buy\_tx\_ratio\_0\_30m",

        "liquidity\_add\_0\_10m", "liquidity\_remove\_0\_2h",

        "liquidity\_drop\_1\_2h\_pct",

        "top\_10\_wallets\_pct\_0\_1h", "gini\_concentration\_0\_1h",

        "btc\_change\_pct\_6h", "btc\_dominance\_pct",

        "launch\_hour\_utc", "launch\_day\_of\_week",

    \]

    rows \= cursor.fetchall()

    return \[dict(zip(cols, row)) for row in rows\]

def call\_llm(winners: list, losers: list, target\_model: str) \-\> list:

    """

    Llama al LLM con datos brutos de winners y losers.

    Devuelve lista de hipótesis estructuradas.

    """

    winners\_csv \= rows\_to\_csv(winners)

    losers\_csv  \= rows\_to\_csv(losers)

    prompt \= f"""Eres un analista cuantitativo especializado en memecoins de Solana.

Tienes dos grupos de tokens reales de Pump.fun:

\=== WINNERS ({target\_model}) \===

{winners\_csv}

\=== LOSERS ({target\_model}) \===

{losers\_csv}

INSTRUCCIONES ESTRICTAS:

1\. Analiza los datos brutos. NO inventes correlaciones genéricas.

2\. Busca patrones DIFERENCIALES concretos entre winners y losers.

3\. Genera exactamente 5 hipótesis falsables.

4\. Cada hipótesis DEBE tener este formato JSON exacto:

{{

  "hypothesis\_text": "Si \[condicion A\] Y \[condicion B\], entonces \[outcome\] con probabilidad aproximada X%.",

  "conditions": \[

    {{"feature": "nombre\_feature", "op": "\>", "threshold": valor\_numerico}},

    {{"feature": "nombre\_feature", "op": "\<", "threshold": valor\_numerico}}

  \],

  "estimated\_probability": 0.XX,

  "confidence\_interval": 0.XX,

  "reasoning": "Explicacion breve basada en los datos observados"

}}

5\. Operadores válidos en conditions: "\>", "\<", "\>=", "\<=", "==", "\!="

6\. Features válidas: tx\_velocity\_0\_5m, tx\_velocity\_5\_60m, tx\_velocity\_60\_240m,

   unique\_wallets\_0\_10m, unique\_wallets\_0\_60m, buy\_tx\_ratio\_0\_30m,

   liquidity\_add\_0\_10m, liquidity\_remove\_0\_2h, liquidity\_drop\_1\_2h\_pct,

   top\_10\_wallets\_pct\_0\_1h, gini\_concentration\_0\_1h,

   btc\_change\_pct\_6h, btc\_dominance\_pct, launch\_hour\_utc, launch\_day\_of\_week

7\. NO menciones Twitter, sentiment ni noticias. Solo features on-chain.

8\. Devuelve SOLO un array JSON con las 5 hipótesis. Sin texto adicional.

"""

    response \= requests.post(

        f"{LITELLM\_ENDPOINT}/chat/completions",

        headers={

            "Authorization": f"Bearer {LITELLM\_API\_KEY}",

            "Content-Type":  "application/json",

        },

        json={

            "model":       LITELLM\_MODEL,

            "temperature": 0.3,

            "max\_tokens":  2000,

            "messages": \[

                {"role": "system", "content":

                    "Eres un analista cuantitativo. Respondes SOLO con JSON válido."},

                {"role": "user", "content": prompt},

            \],

        },

        timeout=120,

    )

    response.raise\_for\_status()

    content \= response.json()\["choices"\]\[0\]\["message"\]\["content"\].strip()

    return parse\_llm\_response(content)

def parse\_llm\_response(content: str) \-\> list:

    """

    Parsea la respuesta del LLM y valida estructura mínima.

    Tolerante a markdown code blocks.

    """

    \# Limpiar posibles \`\`\`json ... \`\`\`

    if "\`\`\`" in content:

        content \= content.split("\`\`\`")\[1\]

        if content.startswith("json"):

            content \= content\[4:\]

    try:

        hypotheses \= json.loads(content.strip())

        if not isinstance(hypotheses, list):

            hypotheses \= \[hypotheses\]

    except json.JSONDecodeError as e:

        logging.error(f"Error parseando JSON del LLM: {e}\\nContenido: {content}")

        return \[\]

    valid \= \[\]

    for h in hypotheses:

        if all(k in h for k in \[

            "hypothesis\_text", "conditions",

            "estimated\_probability", "confidence\_interval"

        \]):

            valid.append(h)

        else:

            logging.warning(f"Hipótesis incompleta ignorada: {h}")

    return valid

def insert\_hypothesis(conn, h: dict, target\_model: str):

    cursor \= conn.cursor()

    cursor.execute("""

        INSERT INTO token\_hypotheses (

            hypothesis\_text,

            conditions\_json,

            target\_model,

            feature\_version,

            estimated\_probability,

            confidence\_interval,

            prior\_probability,

            posterior\_probability,

            generated\_by,

            generated\_on\_data,

            active

        ) VALUES (

            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE

        )

    """, (

        h\["hypothesis\_text"\],

        json.dumps(h\["conditions"\]),

        target\_model,

        FEATURE\_VERSION,

        h\["estimated\_probability"\],

        h\["confidence\_interval"\],

        h\["estimated\_probability"\],   \# prior \= estimación inicial del LLM

        h\["estimated\_probability"\],   \# posterior arranca igual que prior

        f"llm-{LITELLM\_MODEL}",

        f"backfill-90d" if is\_backfill\_mode() else f"live-{get\_week\_label()}",

    ))

    conn.commit()

def rows\_to\_csv(rows: list) \-\> str:

    """

    Convierte lista de dicts a formato CSV legible para el LLM.

    """

    if not rows:

        return "(sin datos)"

    headers \= \[k for k in rows\[0\].keys() if k not in ("address", "created\_at")\]

    lines   \= \[",".join(headers)\]

    for row in rows:

        values \= \[str(round(row\[h\], 4\) if isinstance(row\[h\], float)

                      else row\[h\]) for h in headers\]

        lines.append(",".join(values))

    return "\\n".join(lines)

def is\_backfill\_mode() \-\> bool:

    return os.getenv("BACKFILL\_MODE", "false").lower() \== "true"

def get\_week\_label() \-\> str:

    now \= datetime.utcnow()

    return f"{now.year}-W{now.isocalendar()\[1\]:02d}"

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)

    main()

---

## **7.2 scripts/validate\_hypotheses.py**

python

"""

validate\_hypotheses.py

Contrasta hipótesis activas con tokens nuevos etiquetados.

Actualiza posterior\_probability con actualización bayesiana simple (Beta).

Frecuencia: cada 6h via Hermes/cron.

"""

import os

import json

import logging

import psycopg2

from datetime import datetime, timedelta

DB\_DSN \= os.getenv("DATABASE\_URL")

\# Parámetros Beta prior iniciales

BETA\_ALPHA\_INIT \= 1.0

BETA\_BETA\_INIT  \= 1.0

def main():

    conn   \= psycopg2.connect(DB\_DSN)

    cursor \= conn.cursor()

    \# Hipótesis activas

    cursor.execute("""

        SELECT id, conditions\_json, target\_model,

               prior\_probability, total\_tested,

               validated\_count, refuted\_count

        FROM token\_hypotheses

        WHERE active \= TRUE

    """)

    hypotheses \= cursor.fetchall()

    \# Tokens etiquetados en las últimas 6h (ventana de validación)

    cursor.execute("""

        SELECT

            t.id, t.pump\_100pc\_24h, t.rug\_pull\_48h, t.still\_active\_7d,

            tf.tx\_velocity\_0\_5m, tf.tx\_velocity\_5\_60m,

            tf.tx\_velocity\_60\_240m, tf.unique\_wallets\_0\_10m,

            tf.unique\_wallets\_0\_60m, tf.buy\_tx\_ratio\_0\_30m,

            tf.liquidity\_add\_0\_10m, tf.liquidity\_remove\_0\_2h,

            tf.liquidity\_drop\_1\_2h\_pct, tf.top\_10\_wallets\_pct\_0\_1h,

            tf.gini\_concentration\_0\_1h, tf.btc\_change\_pct\_6h,

            tf.btc\_dominance\_pct, tf.launch\_hour\_utc,

            tf.launch\_day\_of\_week

        FROM tokens t

        INNER JOIN token\_features tf ON tf.token\_id \= t.id

        WHERE t.label\_completed \= TRUE

          AND t.predicted\_at \>= NOW() \- INTERVAL '6 hours'

    """)

    cols \= \[

        "id", "pump\_100pc\_24h", "rug\_pull\_48h", "still\_active\_7d",

        "tx\_velocity\_0\_5m", "tx\_velocity\_5\_60m", "tx\_velocity\_60\_240m",

        "unique\_wallets\_0\_10m", "unique\_wallets\_0\_60m",

        "buy\_tx\_ratio\_0\_30m", "liquidity\_add\_0\_10m",

        "liquidity\_remove\_0\_2h", "liquidity\_drop\_1\_2h\_pct",

        "top\_10\_wallets\_pct\_0\_1h", "gini\_concentration\_0\_1h",

        "btc\_change\_pct\_6h", "btc\_dominance\_pct",

        "launch\_hour\_utc", "launch\_day\_of\_week",

    \]

    tokens \= \[dict(zip(cols, row)) for row in cursor.fetchall()\]

    if not tokens:

        logging.info("validate\_hypotheses: sin tokens nuevos en ventana.")

        conn.close()

        return

    target\_col\_map \= {

        "pump":     "pump\_100pc\_24h",

        "rug":      "rug\_pull\_48h",

        "survival": "still\_active\_7d",

    }

    updated \= 0

    for hyp in hypotheses:

        hyp\_id, conditions\_json, target\_model, prior, total, validated, refuted \= hyp

        conditions \= json.loads(conditions\_json) if conditions\_json else \[\]

        target\_col \= target\_col\_map.get(target\_model)

        if not target\_col:

            continue

        new\_tested    \= 0

        new\_validated \= 0

        new\_refuted   \= 0

        for token in tokens:

            if not token\_matches\_conditions(token, conditions):

                continue

            new\_tested \+= 1

            outcome \= token.get(target\_col)

            if outcome is True:

                new\_validated \+= 1

            elif outcome is False:

                new\_refuted \+= 1

        if new\_tested \== 0:

            continue

        \# Actualización bayesiana Beta-Binomial

        alpha \= BETA\_ALPHA\_INIT \+ (validated \+ new\_validated)

        beta  \= BETA\_BETA\_INIT  \+ (refuted  \+ new\_refuted)

        posterior \= alpha / (alpha \+ beta)

        \# Bayes factor simple

        bayes\_factor \= (

            posterior / max(prior, 0.01)

            if posterior \> prior

            else prior / max(posterior, 0.01) \* \-1

        )

        cursor.execute("""

            UPDATE token\_hypotheses SET

                total\_tested       \= total\_tested     \+ %s,

                validated\_count    \= validated\_count  \+ %s,

                refuted\_count      \= refuted\_count    \+ %s,

                posterior\_probability \= %s,

                bayes\_factor          \= %s,

                last\_updated          \= NOW()

            WHERE id \= %s

        """, (

            new\_tested, new\_validated, new\_refuted,

            posterior, bayes\_factor, hyp\_id

        ))

        updated \+= 1

    conn.commit()

    conn.close()

    logging.info(f"validate\_hypotheses: {updated} hipótesis actualizadas "

                 f"con {len(tokens)} tokens nuevos")

def token\_matches\_conditions(token: dict, conditions: list) \-\> bool:

    """

    Evalúa si un token cumple TODAS las condiciones de una hipótesis.

    """

    for cond in conditions:

        feature   \= cond.get("feature")

        op        \= cond.get("op")

        threshold \= cond.get("threshold")

        value \= token.get(feature)

        if value is None:

            return False

        \# Normalizar booleanos

        if isinstance(value, bool):

            value \= float(value)

        if isinstance(threshold, bool):

            threshold \= float(threshold)

        try:

            value     \= float(value)

            threshold \= float(threshold)

        except (TypeError, ValueError):

            return False

        if op \== "\>"  and not (value \>  threshold): return False

        if op \== "\<"  and not (value \<  threshold): return False

        if op \== "\>=" and not (value \>= threshold): return False

        if op \== "\<=" and not (value \<= threshold): return False

        if op \== "==" and not (value \== threshold): return False

        if op \== "\!=" and not (value \!= threshold): return False

    return True

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)

    main()

---

## **7.3 scripts/backtest\_report.py**

python

"""

backtest\_report.py

Genera informe diario de precision@top\_k en datos recientes.

Envía resumen por Telegram.

Frecuencia: cada dia a las 8am via Hermes/cron.

"""

import os

import logging

import psycopg2

import requests

from datetime import datetime, timedelta

DB\_DSN               \= os.getenv("DATABASE\_URL")

TELEGRAM\_BOT\_TOKEN   \= os.getenv("TELEGRAM\_BOT\_TOKEN")

TELEGRAM\_ALLOWED     \= os.getenv("TELEGRAM\_ALLOWED\_USERS", "")

def main():

    conn   \= psycopg2.connect(DB\_DSN)

    report \= build\_report(conn)

    conn.close()

    send\_telegram(report)

    logging.info("backtest\_report: informe enviado")

def build\_report(conn) \-\> str:

    cursor \= conn.cursor()

    \# Últimas métricas de cada modelo

    cursor.execute("""

        SELECT DISTINCT ON (model\_name)

            model\_name, model\_version,

            precision\_at\_10, precision\_at\_20,

            auc\_roc, f1\_score,

            n\_tokens\_train, n\_tokens\_test,

            created\_at

        FROM model\_performance

        ORDER BY model\_name, created\_at DESC

    """)

    models \= cursor.fetchall()

    \# Hipótesis con mayor posterior\_probability

    cursor.execute("""

        SELECT target\_model, hypothesis\_text,

               posterior\_probability, total\_tested,

               validated\_count, refuted\_count

        FROM token\_hypotheses

        WHERE active \= TRUE

        ORDER BY posterior\_probability DESC

        LIMIT 5

    """)

    top\_hyp \= cursor.fetchall()

    \# Tokens de hoy con mayor prob de pump y menor de rug

    cursor.execute("""

        SELECT symbol, address,

               prob\_pump\_24h, prob\_rug\_48h, prob\_survival\_7d,

               created\_at

        FROM tokens

        WHERE created\_at \>= NOW() \- INTERVAL '24 hours'

          AND prob\_pump\_24h IS NOT NULL

          AND prob\_rug\_48h IS NOT NULL

        ORDER BY (prob\_pump\_24h \- prob\_rug\_48h) DESC

        LIMIT 5

    """)

    top\_tokens \= cursor.fetchall()

    \# Construir mensaje

    lines \= \[

        f"📊 \*Informe diario — {datetime.utcnow().strftime('%Y-%m-%d')}\*",

        "",

        "\*Modelos activos:\*",

    \]

    for m in models:

        name, version, p10, p20, auc, f1, n\_train, n\_test, ts \= m

        lines.append(

            f"• \`{name}\` | P@10={p10:.2f} P@20={p20:.2f} "

            f"AUC={auc:.2f} F1={f1:.2f} "

            f"(train={n\_train} test={n\_test})"

        )

    lines \+= \["", "\*Top 5 hipótesis activas:\*"\]

    for h in top\_hyp:

        model, text, posterior, tested, val, ref \= h

        short\_text \= text\[:80\] \+ "..." if len(text) \> 80 else text

        lines.append(

            f"• \[{model}\] P={posterior:.2f} "

            f"({val}/{tested} validadas) — {short\_text}"

        )

    lines \+= \["", "\*Top 5 tokens 24h (pump \- rug score):\*"\]

    for t in top\_tokens:

        symbol, addr, p\_pump, p\_rug, p\_surv, created \= t

        short\_addr \= addr\[:8\] \+ "..." if addr else "?"

        lines.append(

            f"• \`{symbol or short\_addr}\` "

            f"pump={p\_pump:.2f} rug={p\_rug:.2f} surv={p\_surv:.2f} "

            f"@ {created.strftime('%H:%M')} UTC"

        )

    return "\\n".join(lines)

def send\_telegram(message: str):

    if not TELEGRAM\_BOT\_TOKEN:

        logging.warning("Sin TELEGRAM\_BOT\_TOKEN. Informe no enviado.")

        return

    for user\_id in TELEGRAM\_ALLOWED.split(","):

        user\_id \= user\_id.strip()

        if not user\_id:

            continue

        try:

            requests.post(

                f"https://api.telegram.org/bot{TELEGRAM\_BOT\_TOKEN}/sendMessage",

                json={

                    "chat\_id":    user\_id,

                    "text":       message,

                    "parse\_mode": "Markdown",

                },

                timeout=10,

            )

        except Exception as e:

            logging.error(f"Error enviando Telegram a {user\_id}: {e}")

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)

    main()

---

## **CAPÍTULO 8 — Telegram Bot y control desde iOS**

## **8.1 scripts/telegram\_bot.py**

python

"""

telegram\_bot.py

Bot de Telegram para control remoto del sistema desde iOS.

Comandos disponibles:

  /start          — ayuda

  /status         — estado general del sistema

  /top\_pump       — top 10 tokens con mayor prob de pump

  /top\_rug        — top 10 tokens con mayor prob de rug

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

DB\_DSN               \= os.getenv("DATABASE\_URL")

TELEGRAM\_BOT\_TOKEN   \= os.getenv("TELEGRAM\_BOT\_TOKEN")

TELEGRAM\_ALLOWED     \= os.getenv("TELEGRAM\_ALLOWED\_USERS", "")

PAUSE\_FILE           \= "/tmp/agent.pause"

MODE\_FILE            \= "/tmp/agent.mode"

ALLOWED\_USER\_IDS \= set(

    int(x.strip()) for x in TELEGRAM\_ALLOWED.split(",") if x.strip()

)

\# \--- Decorador de seguridad \---

def restricted(func):

    async def wrapper(update: Update, context: ContextTypes.DEFAULT\_TYPE):

        user\_id \= update.effective\_user.id

        if user\_id not in ALLOWED\_USER\_IDS:

            await update.message.reply\_text("⛔ No autorizado.")

            logging.warning(f"Acceso denegado: user\_id={user\_id}")

            return

        return await func(update, context)

    wrapper.\_\_name\_\_ \= func.\_\_name\_\_

    return wrapper

\# \--- Comandos \---

@restricted

async def cmd\_start(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    text \= (

        "🤖 \*Memecoin Agent v2.1\*\\n\\n"

        "Comandos disponibles:\\n"

        "/status — estado general\\n"

        "/top\\\\\_pump — top 10 tokens pump\\n"

        "/top\\\\\_rug — top 10 tokens rug risk\\n"

        "/hypotheses — top 5 hipótesis activas\\n"

        "/backtest — métricas de modelos\\n"

        "/mode — ver/cambiar modo operativo\\n"

        "/pause — pausar agente\\n"

        "/resume — reanudar agente\\n"

        "/ping — verificar estado\\n"

    )

    await update.message.reply\_text(text, parse\_mode="Markdown")

@restricted

async def cmd\_ping(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    paused \= os.path.exists(PAUSE\_FILE)

    mode   \= read\_mode()

    await update.message.reply\_text(

        f"✅ Bot activo — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC\\n"

        f"Modo: \`{mode}\` | Agente: {'⏸ pausado' if paused else '▶️ activo'}",

        parse\_mode="Markdown"

    )

@restricted

async def cmd\_status(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    conn   \= psycopg2.connect(DB\_DSN)

    cursor \= conn.cursor()

    \# Total tokens

    cursor.execute("SELECT COUNT(\*) FROM tokens")

    total\_tokens \= cursor.fetchone()\[0\]

    \# Tokens últimas 24h

    cursor.execute("""

        SELECT COUNT(\*) FROM tokens

        WHERE created\_at \>= NOW() \- INTERVAL '24 hours'

    """)

    tokens\_24h \= cursor.fetchone()\[0\]

    \# Tokens etiquetados

    cursor.execute("""

        SELECT COUNT(\*) FROM tokens WHERE label\_completed \= TRUE

    """)

    labeled \= cursor.fetchone()\[0\]

    \# Último entrenamiento

    cursor.execute("""

        SELECT model\_name, precision\_at\_10, created\_at

        FROM model\_performance

        ORDER BY created\_at DESC

        LIMIT 1

    """)

    last\_train \= cursor.fetchone()

    \# Hipótesis activas

    cursor.execute("""

        SELECT COUNT(\*) FROM token\_hypotheses WHERE active \= TRUE

    """)

    hyp\_count \= cursor.fetchone()\[0\]

    \# Última tarea ejecutada

    cursor.execute("""

        SELECT task\_name, status, ended\_at

        FROM agent\_execution\_log

        ORDER BY started\_at DESC

        LIMIT 1

    """)

    last\_task \= cursor.fetchone()

    conn.close()

    mode   \= read\_mode()

    paused \= os.path.exists(PAUSE\_FILE)

    lines \= \[

        "📊 \*Estado del sistema\*\\n",

        f"Modo: \`{mode}\` | Agente: {'⏸ pausado' if paused else '▶️ activo'}",

        f"Tokens totales: {total\_tokens:,}",

        f"Tokens últimas 24h: {tokens\_24h:,}",

        f"Tokens etiquetados: {labeled:,}",

        f"Hipótesis activas: {hyp\_count}",

    \]

    if last\_train:

        name, p10, ts \= last\_train

        lines.append(

            f"Último modelo: \`{name}\` P@10={p10:.2f} "

            f"({ts.strftime('%Y-%m-%d %H:%M')})"

        )

    if last\_task:

        tname, tstatus, tend \= last\_task

        lines.append(

            f"Última tarea: \`{tname}\` \[{tstatus}\] "

            f"@ {tend.strftime('%H:%M') if tend else '?'} UTC"

        )

    await update.message.reply\_text(

        "\\n".join(lines), parse\_mode="Markdown"

    )

@restricted

async def cmd\_top\_pump(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    conn   \= psycopg2.connect(DB\_DSN)

    cursor \= conn.cursor()

    cursor.execute("""

        SELECT symbol, address, prob\_pump\_24h, prob\_rug\_48h,

               prob\_survival\_7d, created\_at

        FROM tokens

        WHERE prob\_pump\_24h IS NOT NULL

          AND created\_at \>= NOW() \- INTERVAL '48 hours'

        ORDER BY prob\_pump\_24h DESC

        LIMIT 10

    """)

    rows \= cursor.fetchall()

    conn.close()

    if not rows:

        await update.message.reply\_text("Sin datos de tokens recientes.")

        return

    lines \= \["🚀 \*Top 10 tokens por prob. pump (48h)\*\\n"\]

    for i, (symbol, addr, p\_pump, p\_rug, p\_surv, created) in enumerate(rows, 1):

        short \= addr\[:8\] \+ "..." if addr else "?"

        name  \= symbol or short

        lines.append(

            f"{i}. \`{name}\` pump={p\_pump:.2f} rug={p\_rug:.2f} "

            f"surv={p\_surv:.2f} @ {created.strftime('%H:%M')} UTC"

        )

    await update.message.reply\_text(

        "\\n".join(lines), parse\_mode="Markdown"

    )

@restricted

async def cmd\_top\_rug(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    conn   \= psycopg2.connect(DB\_DSN)

    cursor \= conn.cursor()

    cursor.execute("""

        SELECT symbol, address, prob\_pump\_24h, prob\_rug\_48h,

               prob\_survival\_7d, created\_at

        FROM tokens

        WHERE prob\_rug\_48h IS NOT NULL

          AND created\_at \>= NOW() \- INTERVAL '48 hours'

        ORDER BY prob\_rug\_48h DESC

        LIMIT 10

    """)

    rows \= cursor.fetchall()

    conn.close()

    if not rows:

        await update.message.reply\_text("Sin datos de tokens recientes.")

        return

    lines \= \["⚠️ \*Top 10 tokens por riesgo de rug (48h)\*\\n"\]

    for i, (symbol, addr, p\_pump, p\_rug, p\_surv, created) in enumerate(rows, 1):

        short \= addr\[:8\] \+ "..." if addr else "?"

        name  \= symbol or short

        lines.append(

            f"{i}. \`{name}\` rug={p\_rug:.2f} pump={p\_pump:.2f} "

            f"surv={p\_surv:.2f} @ {created.strftime('%H:%M')} UTC"

        )

    await update.message.reply\_text(

        "\\n".join(lines), parse\_mode="Markdown"

    )

@restricted

async def cmd\_hypotheses(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    conn   \= psycopg2.connect(DB\_DSN)

    cursor \= conn.cursor()

    cursor.execute("""

        SELECT target\_model, hypothesis\_text,

               posterior\_probability, total\_tested,

               validated\_count, refuted\_count,

               last\_updated

        FROM token\_hypotheses

        WHERE active \= TRUE

        ORDER BY posterior\_probability DESC

        LIMIT 5

    """)

    rows \= cursor.fetchall()

    conn.close()

    if not rows:

        await update.message.reply\_text("Sin hipótesis activas todavía.")

        return

    lines \= \["🧠 \*Top 5 hipótesis activas\*\\n"\]

    for i, (model, text, posterior, tested, val, ref, updated) in enumerate(rows, 1):

        short \= text\[:100\] \+ "..." if len(text) \> 100 else text

        lines.append(

            f"{i}. \[{model}\] P={posterior:.2f} "

            f"({val}/{tested} validadas)\\n\_{short}\_\\n"

        )

    await update.message.reply\_text(

        "\\n".join(lines), parse\_mode="Markdown"

    )

@restricted

async def cmd\_backtest(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    conn   \= psycopg2.connect(DB\_DSN)

    cursor \= conn.cursor()

    cursor.execute("""

        SELECT DISTINCT ON (model\_name)

            model\_name, model\_version,

            precision\_at\_10, precision\_at\_20,

            auc\_roc, f1\_score,

            n\_tokens\_train, n\_tokens\_test,

            created\_at

        FROM model\_performance

        ORDER BY model\_name, created\_at DESC

    """)

    rows \= cursor.fetchall()

    conn.close()

    if not rows:

        await update.message.reply\_text("Sin métricas de modelos todavía.")

        return

    lines \= \["📈 \*Métricas de modelos (última versión)\*\\n"\]

    for (name, version, p10, p20, auc, f1,

         n\_train, n\_test, ts) in rows:

        lines.append(

            f"\*{name}\*\\n"

            f"  P@10={p10:.3f} P@20={p20:.3f}\\n"

            f"  AUC={auc:.3f} F1={f1:.3f}\\n"

            f"  train={n\_train:,} test={n\_test:,}\\n"

            f"  versión: \`{version}\`\\n"

            f"  actualizado: {ts.strftime('%Y-%m-%d %H:%M')}\\n"

        )

    await update.message.reply\_text(

        "\\n".join(lines), parse\_mode="Markdown"

    )

@restricted

async def cmd\_mode(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    args \= context.args

    if not args:

        mode \= read\_mode()

        await update.message.reply\_text(

            f"Modo actual: \`{mode}\`\\n\\n"

            "Para cambiar:\\n"

            "/mode research — solo alertas y análisis\\n"

            "/mode execution confirm — trades reales (CUIDADO)",

            parse\_mode="Markdown"

        )

        return

    requested \= args\[0\].lower()

    if requested \== "research":

        write\_mode("research")

        await update.message.reply\_text(

            "✅ Modo cambiado a \`research\`.\\n"

            "El sistema solo genera alertas. No ejecuta trades.",

            parse\_mode="Markdown"

        )

    elif requested \== "execution":

        if len(args) \< 2 or args\[1\].lower() \!= "confirm":

            await update.message.reply\_text(

                "⚠️ Para activar el modo execution escribe:\\n"

                "\`/mode execution confirm\`\\n\\n"

                "Esto permite trades reales con capital real.",

                parse\_mode="Markdown"

            )

        else:

            write\_mode("execution")

            await update.message.reply\_text(

                "🔴 Modo \`execution\` activado.\\n"

                "El sistema puede ejecutar trades reales.\\n"

                "Límite por trade: configurado en MAX\\\\\_POSITION\\\\\_SOL.",

                parse\_mode="Markdown"

            )

    else:

        await update.message.reply\_text(

            "Modo no reconocido. Opciones: \`research\` | \`execution\`",

            parse\_mode="Markdown"

        )

@restricted

async def cmd\_pause(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    with open(PAUSE\_FILE, "w") as f:

        f.write(datetime.utcnow().isoformat())

    await update.message.reply\_text(

        "⏸ Agente pausado.\\nLas tareas programadas se saltarán "

        "hasta que uses /resume."

    )

@restricted

async def cmd\_resume(update: Update, context: ContextTypes.DEFAULT\_TYPE):

    if os.path.exists(PAUSE\_FILE):

        os.remove(PAUSE\_FILE)

        await update.message.reply\_text("▶️ Agente reanudado.")

    else:

        await update.message.reply\_text("El agente no estaba pausado.")

\# \--- Helpers \---

def read\_mode() \-\> str:

    if os.path.exists(MODE\_FILE):

        with open(MODE\_FILE) as f:

            return f.read().strip()

    return "research"

def write\_mode(mode: str):

    with open(MODE\_FILE, "w") as f:

        f.write(mode)

\# \--- Main \---

def main():

    if not TELEGRAM\_BOT\_TOKEN:

        raise ValueError("TELEGRAM\_BOT\_TOKEN no configurado.")

    app \= ApplicationBuilder().token(TELEGRAM\_BOT\_TOKEN).build()

    app.add\_handler(CommandHandler("start",      cmd\_start))

    app.add\_handler(CommandHandler("ping",       cmd\_ping))

    app.add\_handler(CommandHandler("status",     cmd\_status))

    app.add\_handler(CommandHandler("top\_pump",  cmd\_top\_pump))

    app.add\_handler(CommandHandler("top\_rug",     cmd\_top\_rug))

    app.add\_handler(CommandHandler("hypotheses", cmd\_hypotheses))

    app.add\_handler(CommandHandler("backtest",    cmd\_backtest))

    app.add\_handler(CommandHandler("mode",        cmd\_mode))

    app.add\_handler(CommandHandler("pause",       cmd\_pause))

    app.add\_handler(CommandHandler("resume",      cmd\_resume))

    logging.info("Telegram bot iniciado. Esperando comandos...")

    app.run\_polling()

if \_\_name\_\_ \== "\_\_main\_\_":

    logging.basicConfig(level=logging.INFO)

    main()

## **8.2 Acceso desde iOS**

## **Opción A — Telegram (principal)**

El bot de Telegram es la interfaz principal desde iOS.  
No requiere ninguna app adicional más allá de Telegram.

text

Flujo típico desde iPhone:

1\. Abrir Telegram

2\. Buscar tu bot por nombre

3\. Enviar /status → ver estado general en segundos

4\. Enviar /top\_pump → ver candidatos de hoy

5\. Enviar /top\_rug → ver tokens peligrosos

6\. Enviar /hypotheses → ver qué patrones están funcionando

7\. Enviar /pause si quieres detener el agente temporalmente

## **Opción B — SSH desde iOS (control avanzado)**

Para intervención directa en el servidor: ver logs, reiniciar  
servicios, ejecutar scripts manualmente.

App recomendada: Termius (gratuita, disponible en App Store)

bash

\# Configuración en Termius:

Host: IP de tu máquina o dominio Tailscale

Port: 22

User: tu\_usuario

Auth: clave SSH (más seguro que contraseña)

\# Comandos útiles desde iOS via SSH:

\# Ver logs del agente en tiempo real

tail \-f /var/log/memecoin-agent/agent.log

\# Ver logs de una tarea específica

tail \-f /var/log/memecoin-agent/collect\_onchain.log

\# Ejecutar backfill manualmente

cd /opt/memecoin-agent

python scripts/backfill\_historical.py

\# Reiniciar el bot de Telegram

sudo systemctl restart memecoin-telegram-bot

\# Reiniciar Hermes

sudo systemctl restart hermes-memecoin

\# Ver estado de todos los servicios

sudo systemctl status memecoin-\*

\# Ver cuántos tokens hay en la DB

psql \-U memecoin\_user \-d memecoin\_db \\

  \-c "SELECT COUNT(\*), data\_source FROM tokens GROUP BY data\_source;"

\# Ver últimas métricas de modelos

psql \-U memecoin\_user \-d memecoin\_db \\

  \-c "SELECT model\_name, precision\_at\_10, created\_at

      FROM model\_performance

      ORDER BY created\_at DESC LIMIT 6;"

## **Opción C — Alertas automáticas proactivas**

El sistema puede enviarte alertas sin que tú preguntes.  
Añadir al final de collect\_onchain.py y validate\_hypotheses.py:

python

def alert\_if\_interesting(conn, token\_id: int):

    """

    Envía alerta Telegram si un token nuevo es muy interesante:

    \- prob\_pump\_24h \> 0.75

    \- prob\_rug\_48h \< 0.20

    \- coincide con al menos 2 hipótesis activas con posterior \> 0.65

    """

    cursor \= conn.cursor()

    cursor.execute("""

        SELECT t.symbol, t.address,

               t.prob\_pump\_24h, t.prob\_rug\_48h, t.prob\_survival\_7d,

               t.created\_at

        FROM tokens t

        WHERE t.id \= %s

          AND t.prob\_pump\_24h \> 0.75

          AND t.prob\_rug\_48h  \< 0.20

    """, (token\_id,))

    row \= cursor.fetchone()

    if not row:

        return

    symbol, addr, p\_pump, p\_rug, p\_surv, created \= row

    \# Contar hipótesis que este token cumple

    cursor.execute("""

        SELECT id, conditions\_json, hypothesis\_text, posterior\_probability

        FROM token\_hypotheses

        WHERE active \= TRUE

          AND posterior\_probability \> 0.65

          AND target\_model \= 'pump'

    """)

    hypotheses \= cursor.fetchall()

    matched\_hyp \= \[\]

    from validate\_hypotheses import token\_matches\_conditions

    \# Cargar features del token

    cursor.execute("""

        SELECT tx\_velocity\_0\_5m, tx\_velocity\_5\_60m, tx\_velocity\_60\_240m,

               unique\_wallets\_0\_10m, unique\_wallets\_0\_60m,

               buy\_tx\_ratio\_0\_30m, liquidity\_add\_0\_10m,

               liquidity\_remove\_0\_2h, liquidity\_drop\_1\_2h\_pct,

               top\_10\_wallets\_pct\_0\_1h, gini\_concentration\_0\_1h,

               btc\_change\_pct\_6h, btc\_dominance\_pct,

               launch\_hour\_utc, launch\_day\_of\_week

        FROM token\_features

        WHERE token\_id \= %s

    """, (token\_id,))

    feat\_row \= cursor.fetchone()

    if not feat\_row:

        return

    feat\_cols \= \[

        "tx\_velocity\_0\_5m", "tx\_velocity\_5\_60m", "tx\_velocity\_60\_240m",

        "unique\_wallets\_0\_10m", "unique\_wallets\_0\_60m",

        "buy\_tx\_ratio\_0\_30m", "liquidity\_add\_0\_10m",

        "liquidity\_remove\_0\_2h", "liquidity\_drop\_1\_2h\_pct",

        "top\_10\_wallets\_pct\_0\_1h", "gini\_concentration\_0\_1h",

        "btc\_change\_pct\_6h", "btc\_dominance\_pct",

        "launch\_hour\_utc", "launch\_day\_of\_week",

    \]

    token\_features \= dict(zip(feat\_cols, feat\_row))

    import json

    for hyp\_id, cond\_json, hyp\_text, posterior in hypotheses:

        conditions \= json.loads(cond\_json) if cond\_json else \[\]

        if token\_matches\_conditions(token\_features, conditions):

            matched\_hyp.append((posterior, hyp\_text))

    if len(matched\_hyp) \< 2:

        return

    \# Construir y enviar alerta

    short\_addr \= addr\[:12\] \+ "..." if addr else "?"

    name       \= symbol or short\_addr

    hyp\_lines  \= "\\n".join(

        f"  • P={p:.2f} — {t\[:60\]}..."

        for p, t in sorted(matched\_hyp, reverse=True)\[:3\]

    )

    message \= (

        f"🚨 \*Alerta: token interesante detectado\*\\n\\n"

        f"Token: \`{name}\`\\n"

        f"pump={p\_pump:.2f} rug={p\_rug:.2f} surv={p\_surv:.2f}\\n"

        f"Lanzado: {created.strftime('%H:%M')} UTC\\n\\n"

        f"Hipótesis coincidentes ({len(matched\_hyp)}):\\n{hyp\_lines}\\n\\n"

        f"Dirección: \`{addr}\`"

    )

    TELEGRAM\_BOT\_TOKEN \= os.getenv("TELEGRAM\_BOT\_TOKEN")

    TELEGRAM\_ALLOWED   \= os.getenv("TELEGRAM\_ALLOWED\_USERS", "")

    import requests

    for user\_id in TELEGRAM\_ALLOWED.split(","):

        user\_id \= user\_id.strip()

        if not user\_id:

            continue

        try:

            requests.post(

                f"https://api.telegram.org/bot{TELEGRAM\_BOT\_TOKEN}/sendMessage",

                json={

                    "chat\_id":    user\_id,

                    "text":       message,

                    "parse\_mode": "Markdown",

                },

                timeout=10,

            )

        except Exception as e:

            logging.error(f"Error enviando alerta a {user\_id}: {e}")

## **CAPÍTULO 9 — Docker Compose y despliegue**

## **9.1 Estructura de directorios del proyecto**

text

memecoin-agent/

├── config/

│   ├── .env                        \# variables de entorno (no commitear)

│   ├── .env.example                \# plantilla pública

│   └── hermes-memecoin.toml        \# configuración de Hermes

├── scripts/

│   ├── backfill\_historical.py

│   ├── collect\_onchain.py

│   ├── compute\_features.py

│   ├── label\_targets.py

│   ├── train\_models\_all.py

│   ├── generate\_hypotheses\_llm.py

│   ├── validate\_hypotheses.py

│   ├── backtest\_report.py

│   └── telegram\_bot.py

├── sql/

│   └── schema\_v2.1.sql             \# esquema completo de DB

├── models/                         \# modelos entrenados (.pkl)

├── logs/                           \# logs de ejecución

├── data/                           \# datos temporales y checkpoints

├── docker-compose.yml

├── Dockerfile

├── requirements.txt

└── README.md

---

## **9.2 requirements.txt**

text

\# Base de datos

psycopg2-binary==2.9.9

\# Solana on-chain

solana==0.34.0

solders==0.21.0

anchorpy==0.20.1

\# HTTP y APIs

requests==2.31.0

httpx==0.27.0

\# ML y análisis

pandas==2.2.1

numpy==1.26.4

scikit-learn==1.4.2

xgboost==2.0.3

\# Datos

datasets==2.19.0          \# HuggingFace datasets para backfill

pyarrow==15.0.2           \# lectura de parquet

\# Telegram

python-telegram-bot==21.3

\# Utilidades

python-dotenv==1.0.1

pydantic==2.7.1

schedule==1.2.1

tenacity==8.2.3           \# retry logic

\# Logging

structlog==24.1.0

---

## **9.3 Dockerfile**

text

FROM python:3.11-slim

\# Dependencias del sistema

RUN apt-get update && apt-get install \-y \\

    gcc \\

    g++ \\

    libpq-dev \\

    curl \\

    && rm \-rf /var/lib/apt/lists/\*

\# Directorio de trabajo

WORKDIR /app

\# Instalar dependencias Python

COPY requirements.txt .

RUN pip install \--no-cache-dir \-r requirements.txt

\# Copiar código

COPY scripts/ ./scripts/

COPY config/  ./config/

COPY sql/     ./sql/

\# Directorios de datos y logs

RUN mkdir \-p /data/models /data/checkpoints /app/logs

\# Variables de entorno por defecto

ENV PYTHONUNBUFFERED=1

ENV PYTHONPATH=/app

ENV MODELS\_DIR=/data/models

\# Script de entrada

COPY docker-entrypoint.sh .

RUN chmod \+x docker-entrypoint.sh

ENTRYPOINT \["./docker-entrypoint.sh"\]

---

## **9.4 docker-entrypoint.sh**

bash

\#\!/bin/bash

set \-e

echo "=== Memecoin Agent v2.1 \==="

echo "Iniciando en modo: ${EXECUTION\_MODE:-research}"

\# Esperar a que PostgreSQL esté listo

echo "Esperando PostgreSQL..."

until pg\_isready \-h "$POSTGRES\_HOST" \-p "$POSTGRES\_PORT" \-U "$POSTGRES\_USER"; do

    sleep 2

done

echo "PostgreSQL listo."

\# Inicializar schema si no existe

echo "Inicializando schema..."

PGPASSWORD=$POSTGRES\_PASSWORD psql \\

    \-h "$POSTGRES\_HOST" \\

    \-p "$POSTGRES\_PORT" \\

    \-U "$POSTGRES\_USER" \\

    \-d "$POSTGRES\_DB" \\

    \-f /app/sql/schema\_v2.1.sql \\

    \--on-error-stop 2\>/dev/null || echo "Schema ya existe, continuando."

\# Ejecutar backfill si la DB está vacía

TOKEN\_COUNT=$(PGPASSWORD=$POSTGRES\_PASSWORD psql \\

    \-h "$POSTGRES\_HOST" \\

    \-p "$POSTGRES\_PORT" \\

    \-U "$POSTGRES\_USER" \\

    \-d "$POSTGRES\_DB" \\

    \-tAc "SELECT COUNT(\*) FROM tokens;" 2\>/dev/null || echo "0")

if \[ "$TOKEN\_COUNT" \-lt "100" \]; then

    echo "DB vacía (${TOKEN\_COUNT} tokens). Iniciando backfill histórico..."

    python scripts/backfill\_historical.py

else

    echo "DB ya tiene ${TOKEN\_COUNT} tokens. Saltando backfill."

fi

\# Iniciar bot de Telegram en background

echo "Iniciando Telegram bot..."

python scripts/telegram\_bot.py &

TELEGRAM\_PID=$\!

\# Iniciar Hermes como proceso principal

echo "Iniciando Hermes agent..."

exec hermes run \--config config/hermes-memecoin.toml

---

## **9.5 docker-compose.yml**

text

version: "3.9"

services:

  \# ─── Base de datos ───────────────────────────────────────────────

  postgres:

    image: timescale/timescaledb:latest-pg16

    container\_name: memecoin-postgres

    restart: unless-stopped

    environment:

      POSTGRES\_DB:       ${POSTGRES\_DB}

      POSTGRES\_USER:     ${POSTGRES\_USER}

      POSTGRES\_PASSWORD: ${POSTGRES\_PASSWORD}

    volumes:

      \- postgres\_data:/var/lib/postgresql/data

      \- ./sql/schema\_v2.1.sql:/docker-entrypoint-initdb.d/01-schema.sql

    ports:

      \- "5432:5432"

    healthcheck:

      test: \["CMD-SHELL", "pg\_isready \-U ${POSTGRES\_USER} \-d ${POSTGRES\_DB}"\]

      interval: 10s

      timeout: 5s

      retries: 5

  \# ─── Agente principal (Hermes \+ scripts \+ Telegram bot) ──────────

  agent:

    build:

      context: .

      dockerfile: Dockerfile

    container\_name: memecoin-agent

    restart: unless-stopped

    depends\_on:

      postgres:

        condition: service\_healthy

    env\_file:

      \- config/.env

    environment:

      DATABASE\_URL: \>-

        postgresql://${POSTGRES\_USER}:${POSTGRES\_PASSWORD}

        @postgres:5432/${POSTGRES\_DB}

    volumes:

      \- ./models:/data/models

      \- ./logs:/app/logs

      \- ./data:/data/checkpoints

      \- /tmp:/tmp                   \# para agent.pause y agent.mode

    ports:

      \- "8000:8000"                 \# API opcional FastAPI

    logging:

      driver: "json-file"

      options:

        max-size: "50m"

        max-file: "5"

  \# ─── Adminer — UI web para inspeccionar la DB (opcional) ─────────

  adminer:

    image: adminer:latest

    container\_name: memecoin-adminer

    restart: unless-stopped

    depends\_on:

      \- postgres

    ports:

      \- "8080:8080"

    profiles:

      \- debug                       \# solo arranca con: docker compose \--profile debug up

volumes:

  postgres\_data:

    driver: local

---

## **9.6 config/.env.example**

bash

\# ─── Base de datos ───────────────────────────────────────────────

POSTGRES\_HOST=postgres

POSTGRES\_PORT=5432

POSTGRES\_DB=memecoin\_db

POSTGRES\_USER=memecoin\_user

POSTGRES\_PASSWORD=CAMBIA\_ESTO

\# ─── Solana RPC ──────────────────────────────────────────────────

HELIUS\_API\_KEY=TU\_HELIUS\_API\_KEY

BITQUERY\_API\_KEY=TU\_BITQUERY\_API\_KEY

SOLANA\_RPC\_URL=https://mainnet.helius-rpc.com/?api-key=${HELIUS\_API\_KEY}

\# ─── LLM (LiteLLM Gateway SAA) ───────────────────────────────────

LITELLM\_ENDPOINT=http://100.68.1.180:8080/v1

LITELLM\_MODEL=qwen3.5

LITELLM\_API\_KEY=TU\_KEY\_LOCAL

\# ─── Telegram ────────────────────────────────────────────────────

TELEGRAM\_BOT\_TOKEN=TU\_TOKEN\_DE\_BOTFATHER

TELEGRAM\_ALLOWED\_USERS=TU\_TELEGRAM\_USER\_ID

\# ─── Modo operativo ──────────────────────────────────────────────

EXECUTION\_MODE=research

\# valores: research | execution

\# NUNCA cambiar a execution sin validación previa de 8 semanas

MAX\_POSITION\_SOL=0.5

\# Solo activo si EXECUTION\_MODE=execution

\# ─── Features y modelos ──────────────────────────────────────────

FEATURE\_VERSION=v1-onchain-minimal

MODELS\_DIR=/data/models

\# ─── Backfill ────────────────────────────────────────────────────

BACKFILL\_DAYS=90

BACKFILL\_MODE=false

\# Poner true solo durante el primer backfill para marcar hipótesis correctamente

---

## **9.7 Comandos de despliegue**

## **Primera vez (instalación completa)**

bash

\# 1\. Clonar el repo

git clone https://github.com/TU\_USUARIO/memecoin-agent.git

cd memecoin-agent

\# 2\. Copiar y rellenar variables de entorno

cp config/.env.example config/.env

nano config/.env        \# rellenar API keys, Telegram token, etc.

\# 3\. Construir imagen

docker compose build

\# 4\. Arrancar (el entrypoint lanza backfill automáticamente si DB vacía)

docker compose up \-d

\# 5\. Ver logs en tiempo real

docker compose logs \-f agent

\# 6\. Ver solo logs del backfill

docker compose logs \-f agent | grep backfill

## **Operación diaria**

bash

\# Ver estado de todos los contenedores

docker compose ps

\# Ver logs del agente

docker compose logs \-f agent \--tail=100

\# Reiniciar solo el agente (sin tocar la DB)

docker compose restart agent

\# Parar todo

docker compose down

\# Parar todo y borrar datos (CUIDADO: borra la DB)

docker compose down \-v

## **Inspeccionar la DB directamente**

bash

\# Entrar a PostgreSQL

docker compose exec postgres psql \-U memecoin\_user \-d memecoin\_db

\# Queries útiles desde psql:

\-- Cuántos tokens por fuente

SELECT data\_source, COUNT(\*) FROM tokens GROUP BY data\_source;

\-- Distribución de targets

SELECT

  pump\_100pc\_24h,

  rug\_pull\_48h,

  still\_active\_7d,

  COUNT(\*)

FROM tokens

WHERE label\_completed \= TRUE

GROUP BY 1,2,3

ORDER BY 4 DESC;

\-- Últimas métricas de modelos

SELECT model\_name, precision\_at\_10, precision\_at\_20, auc\_roc, created\_at

FROM model\_performance

ORDER BY created\_at DESC

LIMIT 9;

\-- Hipótesis más validadas

SELECT target\_model, posterior\_probability,

       validated\_count, total\_tested, hypothesis\_text

FROM token\_hypotheses

WHERE active \= TRUE

ORDER BY posterior\_probability DESC

LIMIT 10;

## **Instalación sin Docker (macOS nativo para SAA)**

bash

\# Instalar dependencias del sistema

brew install postgresql@16

brew install pgvector        \# opcional

pip install timescaledb      \# o instalar via brew

\# Iniciar PostgreSQL

brew services start postgresql@16

\# Crear DB y usuario

createuser memecoin\_user

createdb memecoin\_db \-O memecoin\_user

psql \-d memecoin\_db \-f sql/schema\_v2.1.sql

\# Instalar dependencias Python

pip install \-r requirements.txt

\# Instalar Hermes

curl \-fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash

\# Arrancar Telegram bot como servicio (launchd en macOS)

cat \> \~/Library/LaunchAgents/com.memecoin.telegram.plist \<\< EOF

\<?xml version="1.0" encoding="UTF-8"?\>

\<\!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"

  "http://www.apple.com/DTDs/PropertyList-1.0.dtd"\>

\<plist version="1.0"\>

\<dict\>

  \<key\>Label\</key\>

  \<string\>com.memecoin.telegram\</string\>

  \<key\>ProgramArguments\</key\>

  \<array\>

    \<string\>/usr/bin/python3\</string\>

    \<string\>/opt/memecoin-agent/scripts/telegram\_bot.py\</string\>

  \</array\>

  \<key\>RunAtLoad\</key\>

  \<true/\>

  \<key\>KeepAlive\</key\>

  \<true/\>

  \<key\>StandardOutPath\</key\>

  \<string\>/opt/memecoin-agent/logs/telegram.log\</string\>

  \<key\>StandardErrorPath\</key\>

  \<string\>/opt/memecoin-agent/logs/telegram.err\</string\>

\</dict\>

\</plist\>

EOF

launchctl load \~/Library/LaunchAgents/com.memecoin.telegram.plist

\# Arrancar Hermes

hermes run \--config config/hermes-memecoin.toml

