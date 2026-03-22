# Memecoin Agent v3.0-ultralite - Guía de Implementación

**Versión**: 3.0-ultralite
**Fecha**: Marzo 2026
**Estado**: SAA v7.2 compliant - 100% SQLite, sin Docker, sin gRPC
**Arquitectura**: 4 capas independientes comunicadas via SQLite (WAL Mode)

---

## 1. Compatibilidad con Arquitectura SAA v7.2

### 1.1 Requisitos de Hardware (v3.0-ultralite)

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
| Python | 3.11+ | Para todos los scripts |
| SQLite | 3.37+ | Con WAL Mode (obligatorio) |
| Tailscale | 1.0+ | Para conectividad |

**⚠️ Importante**:
- NO usar Docker en MB (imposible en 8GB RAM/SSD)
- NO usar PostgreSQL (no documentado en SAA v7.2)
- NO usar gRPC (hardware antiguo no lo soporta)

### 1.3 Compatibilidad con Nodos (v3.0-ultralite)

| Nodo | Rol en Memecoin Agent | Estado |
|------|----------------------|--------|
| **MB** | Control plane (Sniper, Risk, Telegram, SQLite) | ✅ Activo |
| **TO** | LiteLLM Gateway (LLM) | ✅ Activo |
| **IM** | Research Engine (ML + Hipótesis) | ✅ Fallback |
| **WS** | Ignorado (ocupado COLMAP) | ⚠️ No disponible |
| **EW** | Ignorado (offline) | ❌ No disponible |

### 1.4 Enrutamiento LLM para Memecoin Agent (v3.0-ultralite)

```
Memecoin Agent (MB)
    ↓
LiteLLM Gateway (TO:8080)
    ↓
    ├─→ im-qwen32b    → IM:11434 (Qwen32B) [✅ Disponible]
    └─→ ew-qwen       → EW:11434 (Qwen3.5) [❌ Offline - ignorar]
```

**Nota**: WS está ocupado con COLMAP y no se usa. Research Engine va a IM.

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
   ```

2. **Validación de Conectividad**
   ```bash
   # Verificar Tailscale
   tailscale status

   # Verificar LiteLLM Gateway
   curl http://100.68.1.180:8080/health
   ```

3. **Validación de Backend IA**
   ```bash
   # Verificar IM (Ollama)
   curl http://100.68.1.55:11434/api/tags

   # Verificar WS (ignorado)
   # curl http://100.68.1.160:11435/health  # No usar
   ```

4. **Configuración de Variables de Entorno**
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
Implementar ingesta de datos con polling simple.

#### Tareas

1. **Configurar Helius RPC**
   - Obtener API key de Helius (free tier)
   - Configurar `HELIUS_API_KEY` en `.env`
   - Probar conexión con `scripts/stream_onchain_polling.py --dry-run`

2. **Implementar Polling Simple**
   - `scripts/stream_onchain_polling.py` - Polling cada 15s
   - Filtrar solo transacciones de Pump.fun
   - Reducir carga CPU en un 90%

3. **Implementar Fallback**
   - Configurar prioridad de fuentes en `.env`
   - Probar con `python scripts/stream_onchain_polling.py`

#### Archivos Generados
- `scripts/stream_onchain_polling.py` - Polling simple
- `logs/streaming.log` - Log de streaming

---

### FASE 3: Micro-Ventanas de Features (Días 9-11)

#### Objetivo
Implementar features con resolución de 10s, 30s, 60s.

#### Tareas

1. **Actualizar Schema**
   - Verificar micro-ventanas en `launches` table
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

### FASE 4: Cuatro Capas como Módulos (Días 12-18)

#### Objetivo
Implementar las 4 capas independientes.

#### Tareas

##### Capa A: Sniper Engine
- `agents/sniper_engine.py` - Detección heurística <2s
- Calcular score basado en:
  - tx_velocity (10s, 30s, 60s)
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

##### Capa C: Research Engine (IM)
- `agents/research_engine.py` - ML + Hipótesis
- APScheduler para:
  - Entrenamiento diario (3am)
  - Hipótesis semanal (lunes 4am)
  - Validación cada 6h
  - Backtest diario (8am)
- Modo degradado: `heuristic_only` cuando IM no disponible

##### Capa D: Execution Engine
- `agents/execution_engine.py` - Ejecución de trades
- Reglas:
  - Límite hard 1 SOL por trade
  - Stop-loss -30%
  - Take-profit +50%, +100%
  - Circuit breaker
  - SQLite con WAL Mode

#### Archivos Generados
- `agents/sniper_engine.py` - Capa A
- `agents/risk_filter.py` - Capa B
- `agents/research_engine.py` - Capa C
- `agents/execution_engine.py` - Capa D
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
Desplegar sistema completo sin Docker.

#### Tareas

1. **Arrancar servicios nativos**
   ```bash
   # Arrancar todos los servicios en background
   python scripts/stream_onchain_polling.py &
   python agents/sniper_engine.py &
   python agents/risk_filter.py &
   python agents/execution_engine.py &
   python agents/whale_tracker.py &
   python scripts/telegram_bot.py &
   ```

2. **Verificar servicios**
   ```bash
   # Verificar procesos
   ps aux | grep python

   # Verificar logs
   tail -f logs/*.log
   ```

3. **Configurar Research Engine en IM**
   ```bash
   # En IM (fallback)
   python agents/research_engine.py &
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

## 3. Especificación de Recursos (v3.0-ultralite)

### 3.1 Recursos por Servicio

| Servicio | CPU | RAM | Storage | Notas |
|----------|-----|-----|---------|-------|
| SQLite DB | 1 | 512MB | 1GB | SQLite con WAL Mode |
| stream-polling | 1 | 1GB | 1GB | Polling cada 15s |
| sniper | 1 | 2GB | 1GB | Sniper Engine |
| risk-filter | 1 | 1GB | 1GB | Risk Filter |
| research | 4 | 8GB | 10GB | Research Engine (IM - CPU-only) |
| execution | 1 | 2GB | 1GB | Execution Engine |
| whale-tracker | 1 | 1GB | 1GB | Whale Tracker |
| telegram-bot | 1 | 1GB | 1GB | Telegram Bot |

**Total MB (8GB RAM)**: 8GB RAM suficiente (sin Docker, sin PostgreSQL)
**Total IM (8GB RAM)**: 8GB RAM para Research Engine

### 3.2 Recursos por Fase (v3.0-ultralite)

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

**Causa**: IM está ocupado o no disponible.

**Solución**: El sistema opera en modo `heuristic_only` automáticamente.

### 5.4 Error: Streaming no conecta

**Causa**: Helius RPC no accesible.

**Solución**:
```bash
# Verificar endpoint
curl -v https://mainnet.helius-rpc.com/

# Verificar firewall
tailscale status
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

### 7.2 db_manager.py - Gestión de base de datos

```python
#!/usr/bin/env python3
"""Gestión de base de datos SQLite con retención automática."""

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.getenv("DATABASE_PATH", "data/memecoin.db")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "1"))

def cleanup_old_data():
    """Eliminar datos antiguos según retención."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")

    cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()

    # Borrar launches antiguos
    conn.execute("DELETE FROM launches WHERE time < ?", (cutoff,))

    # Borrar token_features antiguos
    conn.execute("DELETE FROM token_features WHERE created_at < ?", (cutoff,))

    conn.commit()
    conn.close()
    print(f"Limpieza completada: datos anteriores a {cutoff}")

if __name__ == "__main__":
    cleanup_old_data()
```

---

## 8. Integración con SAA v7.2 (v3.0-ultralite)

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

### 8.2 Configuración de Research Engine (IM)

```bash
# Research Engine se ejecuta en IM (8GB RAM, CPU-only)
# Accede a MB via Tailscale para base de datos SQLite
# LLM access via TO:8080

# Modo degradado: heuristic_only cuando IM no disponible
export RESEARCH_MODE=heuristic_only
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
| QuickNode Free Tier | $0 | 100 req/día | Sin API key necesaria |
| RPC Pool | $0 | 100 req/día | Sin API key necesaria |

**Recomendación**: Usar Helius Free Tier (100k req/mes) o RPC público para MVP.

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
5. **Arrancar servicios** (scripts/telegram_bot.py, agents/*.py)
6. **Validar sistema** (comandos de Telegram)

---

**Versión**: 3.0-ultralite
**Fecha**: Marzo 2026
**Estado**: SAA v7.2 compliant