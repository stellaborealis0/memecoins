# Memecoin Agent v3.0-ultralite-fixed - Guía de Implementación

**Versión**: 3.0-ultralite-fixed
**Fecha**: Marzo 2026
**Estado**: SAA v7.2 compliant - 100% SQLite, sin Docker, sin gRPC
**Arquitectura**: 4 capas + Hermes orquestador comunicadas via SQLite (WAL Mode)

---

## 1. Compatibilidad con Arquitectura SAA v7.2

### 1.1 Requisitos de Hardware (v3.0-ultralite-fixed)

| Componente | MB (Agente) | TO (Gateway) | IM (Fallback) |
|------------|-------------|--------------|---------------|
| **CPU** | 4 cores (MBP 7,1) | 4+ cores | 4+ cores |
| **RAM** | 8 GB | 8GB+ | 8 GB |
| **Storage** | 8 GB SSD (eMMC) | 50GB SSD | 50 GB SSD |
| **GPU** | No requerida | No requerida | No requerida |

**⚠️ CRÍTICO - Storage MB**: El SSD de 8GB se llenará rápidamente. Implementar:
- Retención de datos: 24h máximo (configurable en agent_config)
- Rotación de logs: 10MB máximo por archivo
- Limpieza automática cada 6h

### 1.2 Requisitos de Software

| Componente | Versión Mínima | Notas |
|------------|----------------|-------|
| Python | 3.11+ | Para todos los scripts (NO 3.12 - solana-py incompatible) |
| SQLite | 3.37+ | Con WAL Mode (obligatorio) |
| Tailscale | 1.0+ | Para conectividad |
| openai | >=1.30 | Para LiteLLM Gateway (TO:8080) |

**⚠️ Importante**:
- NO usar Docker en MB (imposible en 8GB RAM/SSD)
- NO usar PostgreSQL (no documentado en SAA v7.2)
- NO usar gRPC (hardware antiguo no lo soporta)

### 1.3 Compatibilidad con Nodos (v3.0-ultralite-fixed)

| Nodo | Rol en Memecoin Agent | Estado |
|------|----------------------|--------|
| **MB** | Control plane (Sniper, Risk, Telegram, SQLite, Hermes, Research) | ✅ Activo |
| **TO** | LiteLLM Gateway (LLM) | ✅ Activo |
| **IM** | Research Engine fallback (ML + Hipótesis) | ✅ Fallback |
| **WS** | Ignorado (ocupado COLMAP) | ⚠️ No disponible |
| **EW** | Ignorado (offline) | ❌ No disponible |

### 1.4 Enrutamiento LLM para Memecoin Agent (v3.0-ultralite-fixed)

```
Memecoin Agent (MB)
    ↓
LiteLLM Gateway (TO:8080)
    ↓
    ├─→ im-qwen32b    → IM:11434 (Qwen32B) [✅ Disponible]
    └─→ ew-qwen       → EW:11434 (Qwen3.5) [❌ Offline - ignorar]
```

**Nota**: Research Engine corre en MB con Hermes. IM solo como fallback si MB no responde.

---

## 2. Fases de Implementación

### FASE 0: Preparación y Validación (Días 1-2)

#### Objetivo
Validar compatibilidad con SAA v7.2 y preparar entorno.

#### Tareas

1. **Validación de Hardware**
   ```bash
   # Verificar RAM en MB
   free -h

   # Verificar CPU
   lscpu

   # Verificar disco (CRÍTICO: 8GB)
   df -h

   # Verificar RAM libre en IM con Ollama corriendo: ≥5 GB disponibles
   ssh user@100.68.1.55 "free -h"
   ```

2. **Validación de Conectividad**
   ```bash
   # Verificar Tailscale
   tailscale status

   # Verificar LiteLLM Gateway
   curl http://100.68.1.180:8080/health
   ```

3. **Configuración de Variables de Entorno**
   ```bash
   # Copiar .env.example
   cp config/.env.example config/.env

   # Editar con valores reales
   nano config/.env
   ```

#### Archivos Generados
- `config/.env` - Variables de entorno
- `logs/prevalidation.log` - Log de validación

---

### FASE 1: Infraestructura Base (Días 3-5)

#### Objetivo
Configurar SQLite con WAL Mode y crear base de datos.

#### Tareas

1. **Crear estructura de directorios**
   ```bash
   mkdir -p data logs models
   ```

2. **Inicializar base de datos SQLite con WAL Mode**
   ```bash
   # Crear script init_db.py (ver sección 7)
   python scripts/init_db.py
   ```

3. **Verificar WAL Mode**
   ```bash
   sqlite3 data/memecoin.db "PRAGMA journal_mode;"
   # Debe devolver: wal
   ```

4. **Verificar tablas**
   ```bash
   sqlite3 data/memecoin.db ".tables"
   ```

#### Archivos Generados
- `data/memecoin.db` - Base de datos SQLite
- `logs/installation.log` - Log de instalación

---

### FASE 2: Streaming On-Chain (Días 6-8)

#### Objetivo
Implementar ingesta de datos con PumpPortal WebSocket (primario) + Helius polling (fallback).

#### Tareas

1. **Configurar PumpPortal WebSocket**
   - `scripts/stream_onchain_ws.py` - PumpPortal WebSocket (primario)
   - Filtrar solo transacciones de Pump.fun
   - Latencia <1s

2. **Configurar Helius RPC (fallback)**
   - `scripts/stream_onchain_polling.py` - Helius polling cada 5min
   - Solo para enriquecer tokens individuales
   - Máximo ~50-100 tokens/día × 3 llamadas = ~4,500 req/mes

3. **Probar conexión**
   ```bash
   python scripts/stream_onchain_ws.py --dry-run
   python scripts/stream_onchain_polling.py --dry-run
   ```

#### Archivos Generados
- `scripts/stream_onchain_ws.py` - PumpPortal WebSocket
- `scripts/stream_onchain_polling.py` - Helius polling
- `logs/streaming.log` - Log de streaming

---

### FASE 3: Micro-Ventanas de Features (Días 9-11)

#### Objetivo
Implementar features con resolución de 30s, 60s, 5m.

#### Tareas

1. **Actualizar Schema**
   - Verificar micro-ventanas en `launches` table (30s, 60s, 5m)
   - Verificar micro-features en `token_features` table

2. **Implementar Scripts**
   - `scripts/collect_onchain.py` - Recolección con micro-ventanas
   - `scripts/compute_features.py` - Cálculo de features
   - `scripts/label_targets.py` - Etiquetado con micro-ventanas

3. **Validar Features**
   ```bash
   sqlite3 data/memecoin.db "SELECT * FROM token_features LIMIT 5;"
   ```

#### Archivos Generados
- `scripts/collect_onchain.py` - Recolección actualizada
- `scripts/compute_features.py` - Features actualizado
- `logs/features.log` - Log de features

---

### FASE 4: Cuatro Capas + Hermes (Días 12-18)

#### Objetivo
Implementar las 4 capas independientes + Hermes como orquestador.

#### Tareas

##### Capa A: Sniper Engine
- `agents/sniper_engine.py` - Detección heurística <2s
- Calcular score basado en:
  - tx_velocity (30s, 60s, 5m)
  - unique_wallets (10m)
  - buy_ratio (30m)
  - liquidity_add
  - bonding_curve_progress

##### Capa B: Risk Filter
- `agents/risk_filter.py` - Evaluación <500ms
- Fuentes:
  - RugCheck API
  - Historial creador
  - Concentración top 10
  - Liquidez
  - Creator bundled buy

##### Capa C: Research Engine (MB + IM fallback)
- `agents/research_engine.py` - ML + Hipótesis
- APScheduler para:
  - Entrenamiento diario (3am)
  - Hipótesis semanal (lunes 4am)
  - Validación cada 6h
  - Backtest diario (8am)
- Modo degradado: `heuristic_only` cuando IM no disponible
- Transferencia de datos MB→IM: scp data/memecoin.db user@100.68.1.55:/tmp/memecoin_train.db

##### Capa D: Execution Engine
- `agents/execution_engine.py` - Ejecución de trades
- Reglas:
  - Límite hard 1 SOL por trade
  - Stop-loss -30%
  - Take-profit +50%, +100%
  - Circuit breaker
  - SQLite con WAL Mode

##### Hermes Agent
- `hermes-memecoin.toml` - Orquestador con tasks cron
- Tasks:
  - sniper: */15 * * * *
  - research: 0 3 * * *
  - validate: 0 */6 * * *
  - backtest: 0 8 * * *

#### Archivos Generados
- `agents/sniper_engine.py` - Capa A
- `agents/risk_filter.py` - Capa B
- `agents/research_engine.py` - Capa C
- `agents/execution_engine.py` - Capa D
- `hermes-memecoin.toml` - Orquestador
- `logs/agents.log` - Log de agentes

---

### FASE 5: Whale Tracker y Spray Strategy (Días 19-21)

#### Objetivo
Implementar copy-trading de whales cualificadas.

#### Tareas

1. **Tabla tracked_wallets**
   - Crear vista de whales cualificadas
   - Calcular graduation_rate
   - Calcular rug_rate

2. **Whale Tracker**
   - Monitorizar transacciones de whales
   - Calcular delay para copy-trading
   - Insertar señales en pending_trades

3. **Spray Targets**
   - Tracking de copy-trading
   - Métricas de profit/loss
   - Optimización de delay

#### Archivos Generados
- `agents/whale_tracker.py` - Whale tracker
- `logs/whale.log` - Log de whales

---

### FASE 6: Telegram Bot Extendido (Días 22-23)

#### Objetivo
Implementar control remoto desde iOS.

#### Tareas

1. **Comandos de Estado**
   - `/status` - Estado general
   - `/top_pump` - Top 10 tokens pump
   - `/top_rug` - Top 10 tokens rug
   - `/hypotheses` - Top 5 hipótesis
   - `/backtest` - Métricas de modelos

2. **Comandos de Control**
   - `/mode` - Ver/cambiar modo
   - `/pause` - Pausar agente
   - `/resume` - Reanudar agente
   - `/ping` - Verificar estado

3. **Alertas Proactivas**
   - Token interesante detectado
   - Whale comprando
   - Risk filter bloqueando

#### Archivos Generados
- `scripts/telegram_bot.py` - Bot actualizado
- `logs/telegram.log` - Log de Telegram

---

### FASE 7: Despliegue Nativo (Días 24-25)

#### Objetivo
Desplegar sistema completo con systemd (no & manual).

#### Tareas

1. **Configurar systemd services**
   ```bash
   # Crear servicios systemd
   sudo cp config/memecoin-*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable memecoin-*
   sudo systemctl start memecoin-*
   ```

2. **Configurar Research Engine en MB**
   ```bash
   # Research Engine corre en MB con Hermes
   # IM solo como fallback para LLM pesado
   ```

3. **Configurar transferencia de datos MB→IM**
   ```bash
   # SCP nightly before training
   0 2 * * * scp data/memecoin.db user@100.68.1.55:/tmp/memecoin_train.db
   ```

4. **Configurar retención automática (cron job cada 6h)**
   ```bash
   # Cron job
   0 */6 * * * python /path/memecoin/scripts/cleanup.py >> /path/memecoin/logs/cleanup.log 2>&1
   ```

#### Archivos Generados
- `logs/deployment.log` - Log de despliegue

---

### FASE 8: Tests y Validación (Días 26-28)

#### Objetivo
Validar sistema completo antes de producción.

#### Tareas

1. **Tests Unitarios**
   - Sniper Engine
   - Risk Filter
   - Research Engine
   - Execution Engine
   - Whale Tracker

2. **Tests de Integración**
   - Streaming on-chain
   - Features calculation
   - Model training
   - Trade execution

3. **Validación Pre-Producción**
   - Precision@top10 >= 0.60
   - Latencia Sniper < 2s
   - Latencia Risk Filter < 500ms
   - Uptime > 99.5%

#### Archivos Generados
- `tests/unit/` - Tests unitarios
- `tests/integration/` - Tests de integración
- `logs/tests.log` - Log de tests

---

## 3. Especificación de Recursos (v3.0-ultralite-fixed)

### 3.1 Recursos por Servicio

| Servicio | CPU | RAM | Storage | Notas |
|----------|-----|-----|---------|-------|
| SQLite DB | 1 | 512MB | 1GB | SQLite con WAL Mode |
| stream-polling | 1 | 1GB | 1GB | PumpPortal WS (primario) |
| sniper | 1 | 2GB | 1GB | Sniper Engine |
| risk-filter | 1 | 1GB | 1GB | Risk Filter |
| research | 4 | 4GB | 5GB | Research Engine (MB - CPU-only) |
| execution | 1 | 2GB | 1GB | Execution Engine |
| whale-tracker | 1 | 1GB | 1GB | Whale Tracker |
| telegram-bot | 1 | 1GB | 1GB | Telegram Bot |
| hermes | 1 | 512MB | 1GB | Orquestador |

**Total MB (8GB RAM)**: 8GB RAM suficiente (sin Docker, sin PostgreSQL)

### 3.2 Recursos por Fase (v3.0-ultralite-fixed)

| Fase | CPU | RAM MB | RAM IM | Storage | Duración |
|------|-----|--------|--------|---------|----------|
| 0 | 2 | 4GB | - | 1GB | 2 días |
| 1 | 2 | 2GB | - | 1GB | 3 días |
| 2 | 2 | 2GB | - | 1GB | 3 días |
| 3 | 4 | 4GB | - | 1GB | 3 días |
| 4 | 8 | 8GB | - | 1GB | 7 días |
| 5 | 2 | 2GB | - | 1GB | 3 días |
| 6 | 2 | 2GB | - | 1GB | 2 días |
| 7 | 8 | 8GB | - | 1GB | 2 días |
| 8 | 4 | 4GB | - | 1GB | 3 días |

**Total MB**: 8GB RAM suficiente (sin Docker, sin PostgreSQL)

---

## 4. Comandos de Verificación

### 4.1 Verificar Estado del Sistema

```bash
# Verificar procesos
ps aux | grep python

# Verificar logs en tiempo real
tail -f logs/*.log

# Verificar base de datos SQLite
sqlite3 data/memecoin.db "SELECT COUNT(*) FROM tokens;"

# Verificar métricas
sqlite3 data/memecoin.db "SELECT model_name, precision_at_10 FROM model_performance ORDER BY created_at DESC LIMIT 5;"

# Verificar tamaño de base de datos
sqlite3 data/memecoin.db "SELECT page_count * page_size / 1024 / 1024 AS size_mb FROM pragma_page_count(), pragma_page_size();"
```

### 4.2 Verificar Latencia

```bash
# Verificar latencia de streaming
tail -f logs/streaming.log | grep "Token insertado"

# Verificar latencia de sniper
tail -f logs/sniper.log | grep "score="

# Verificar latencia de risk filter
tail -f logs/risk-filter.log | grep "Score:"
```

### 4.3 Verificar Métricas

```bash
# Tokens por fuente
sqlite3 data/memecoin.db "SELECT data_source, COUNT(*) FROM tokens GROUP BY data_source;"

# Distribución de targets
sqlite3 data/memecoin.db "SELECT pump_100pc_24h, rug_pull_48h, still_active_7d, COUNT(*) FROM tokens WHERE label_completed = 1 GROUP BY 1,2,3 ORDER BY 4 DESC;"

# Últimas métricas de modelos
sqlite3 data/memecoin.db "SELECT model_name, precision_at_10, precision_at_20, auc_roc, created_at FROM model_performance ORDER BY created_at DESC LIMIT 9;"
```

---

## 5. Troubleshooting

### 5.1 Error: database is locked

**Causa**: SQLite sin WAL mode o múltiples escritores simultáneos.

**Solución**: Asegurar que todos los scripts ejecuten al conectar:
```python
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA busy_timeout=5000;")
```

### 5.2 Error: No space left on device

**Causa**: SSD de 8GB lleno por logs y datos.

**Solución**:
1. Limpieza automática cada 6h (configurable)
2. Rotación de logs: 10MB máximo
3. Retención de datos: 24h máximo

### 5.3 Error: Research Engine no responde

**Causa**: MB está ocupado o no disponible.

**Solución**: El sistema opera en modo `heuristic_only` automáticamente.

### 5.4 Error: Streaming no conecta

**Causa**: PumpPortal WebSocket o Helius RPC no accesible.

**Solución**:
```bash
# Verificar endpoint
curl -v https://mainnet.helius-rpc.com/

# Verificar firewall
tailscale status
```

### 5.5 Error: Transferencia MB→IM falla

**Causa**: SSH sin clave o red inestable.

**Solución**:
```bash
# Configurar SSH keyless
ssh-keygen -t ed25519 -C "memecoin"
ssh-copy-id user@100.68.1.55

# Probar transferencia manual
scp data/memecoin.db user@100.68.1.55:/tmp/memecoin_train.db
```

---

## 6. Checklist de Validación Pre-Producción

### 6.1 Requisitos Mínimos

- [ ] Precision@top10 >= 0.60
- [ ] Latencia Sniper < 2s
- [ ] Latencia Risk Filter < 500ms
- [ ] Uptime > 99.5%
- [ ] SQLite con WAL Mode

### 6.2 Seguridad

- [ ] Límite hard 1 SOL por trade
- [ ] Stop-loss on-chain obligatorio (-30%)
- [ ] Circuit breaker tras 3 pérdidas
- [ ] Execution PIN de 6 dígitos
- [ ] WALLET_PRIVATE_KEY protegida

### 6.3 Documentación

- [ ] README.md completo
- [ ] Arquitectura documentada
- [ ] Comandos de Telegram documentados
- [ ] Troubleshooting guide

---

## 7. Scripts Esenciales

### 7.1 init_db.py - Inicializar SQLite con WAL Mode

```python
#!/usr/bin/env python3
"""Inicializar base de datos SQLite con WAL Mode."""

import sqlite3
import os

DB_PATH = os.getenv("DATABASE_PATH", "data/memecoin.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)

    # WAL Mode obligatorio para concurrencia
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-100000;")

    # Cargar schema
    with open("sql/schema_v3.0.sql", "r") as f:
        conn.executescript(f.read())

    conn.commit()
    conn.close()
    print(f"Base de datos inicializada: {DB_PATH}")

if __name__ == "__main__":
    init_db()
```

### 7.2 cleanup.py - Limpieza automática cada 6h

```python
#!/usr/bin/env python3
"""Script de limpieza automática para SQLite (cron cada 6h)."""

import sqlite3
import os
import sys
from datetime import datetime, timedelta

DB_PATH = os.getenv("DATABASE_PATH", "data/memecoin.db")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "1"))
LOG_PATH = os.getenv("CLEANUP_LOG_PATH", "logs/cleanup.log")


def log(message: str):
    """Escribe un mensaje en el log."""
    timestamp = datetime.utcnow().isoformat()
    log_line = f"[{timestamp}] {message}\n"
    print(log_line, end="")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(log_line)


def cleanup_old_data():
    """Elimina datos antiguos según retención y ejecuta VACUUM."""
    log(f"Iniciando limpieza: retención={RETENTION_DAYS} días")
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")

        cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
        log(f"Cutoff: {cutoff}")

        cursor = conn.cursor()

        # Borrar launches antiguos
        cursor.execute("SELECT COUNT(*) FROM launches WHERE time < ?", (cutoff,))
        launches_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM launches WHERE time < ?", (cutoff,))
        log(f"Borrados {launches_count} launches antiguos")

        # Borrar token_features antiguos
        cursor.execute("SELECT COUNT(*) FROM token_features WHERE created_at < ?", (cutoff,))
        features_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM token_features WHERE created_at < ?", (cutoff,))
        log(f"Borrados {features_count} token_features antiguos")

        conn.commit()

        # Ejecutar VACUUM para compactar la base de datos
        log("Ejecutando VACUUM...")
        conn.execute("VACUUM;")
        conn.commit()

        # Verificar tamaño final
        cursor.execute("SELECT page_count * page_size / 1024 / 1024 AS size_mb FROM pragma_page_count(), pragma_page_size();")
        final_size = cursor.fetchone()[0]
        log(f"Limpieza completada. Tamaño final: {final_size:.2f} MB")

        return True

    except Exception as e:
        log(f"ERROR en limpieza: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def main():
    """Función principal."""
    if not os.path.exists(DB_PATH):
        log(f"ERROR: Base de datos no encontrada: {DB_PATH}")
        sys.exit(1)

    success = cleanup_old_data()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

### 7.3 llm_client.py - Helper centralizado para LLM calls

```python
#!/usr/bin/env python3
"""
Helper centralizado para llamadas a LLM vía LiteLLM Gateway (TO:8080).

Este módulo proporciona una única función para todas las llamadas a LLM,
garantizando consistencia y manejo de errores centralizado.

Uso:
    from scripts.llm_client import llm_call

    response = llm_call("Tu prompt aquí", model="im-qwen32b")
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = os.getenv("LITELLM_ENDPOINT", "http://100.68.1.180:8080")
DEFAULT_MODEL = os.getenv("LITELLM_MODEL", "im-qwen32b")
DEFAULT_TIMEOUT = int(os.getenv("LITELLM_TIMEOUT", "60"))


def llm_call(prompt: str, model: str = None, temperature: float = 0.3) -> str:
    """Llama al LLM vía LiteLLM Gateway y devuelve el contenido de la respuesta."""
    endpoint = os.getenv("LITELLM_ENDPOINT", DEFAULT_ENDPOINT)
    model = model or os.getenv("LITELLM_MODEL", DEFAULT_MODEL)

    if not endpoint.endswith("/v1"):
        endpoint = f"{endpoint}/v1"
    endpoint_url = f"{endpoint}/chat/completions"

    logger.debug(f"LLM call: model={model}, endpoint={endpoint_url}")

    try:
        response = requests.post(
            endpoint_url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]
        logger.debug(f"LLM response length: {len(content)} chars")
        return content

    except requests.exceptions.Timeout:
        logger.error(f"LLM call timeout after {DEFAULT_TIMEOUT}s")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"LLM call failed: {e}")
        raise
    except (KeyError, IndexError) as e:
        logger.error(f"LLM response parsing failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_prompt = "Di hola en una palabra."
    try:
        result = llm_call(test_prompt)
        print(f"Prompt: {test_prompt}")
        print(f"Response: {result}")
    except Exception as e:
        print(f"Error: {e}")
```

---

## 8. Integración con SAA v7.2 (v3.0-ultralite-fixed)

### 8.1 Configuración de LiteLLM

```yaml
# litellm_config.yaml
model_list:
  - model_name: memecoin-agent
    litellm_params:
      model: openai/qwen3.5
      api_base: http://100.68.1.180:8080
      api_key: ${LITELLM_API_KEY}
```

### 8.2 Configuración de Hermes

```toml
# config/hermes-memecoin.toml

[agent]
name = "memecoin-analyst"
model = "http://100.68.1.180:8080/v1"
model_id = "im-qwen32b"
temperature = 0.4
max_tokens = 2000

[tasks.sniper]
run = "python agents/sniper_engine.py"
schedule = "*/15 * * * *"

[tasks.research]
run = "python agents/research_engine.py"
schedule = "0 3 * * *"

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

### 8.3 Configuración de Tailscale

```bash
# Verificar conectividad
tailscale status

# Verificar rutas
tailscale netcheck
```

### 8.4 RPC Solana Free Tier (Sin coste)

| RPC | Coste | Límite | Notas |
|-----|-------|--------|-------|
| Helius Free Tier | $0 | 100k req/mes | Sin API key necesaria |
| PumpPortal WebSocket | $0 | Sin límites | Sin auth necesaria |

**Recomendación**: Usar PumpPortal WebSocket (primario) + Helius polling (fallback).

### 8.5 APIs Públicas (Sin coste)

| API | Coste | Notas |
|-----|-------|-------|
| DexScreener API | $0 | Sin auth necesaria |
| CoinGecko API | $0 | Sin auth necesaria |
| SolanaFM API | $0 | Sin auth necesaria |
| RugCheck API | $0 | API pública de Solana |

---

## 9. Próximos Pasos

1. **Validar hardware** (MB 8GB + IM 8GB)
2. **Instalar dependencias** (pip install -r requirements.txt)
3. **Inicializar SQLite** (python scripts/init_db.py)
4. **Configurar variables** (config/.env)
5. **Arrancar servicios** (systemctl start memecoin-*)
6. **Validar sistema** (comandos de Telegram)

---

**Versión**: 3.0-ultralite-fixed
**Fecha**: Marzo 2026
**Estado**: SAA v7.2 compliant