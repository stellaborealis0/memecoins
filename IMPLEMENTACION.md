# Memecoin Agent v3.0 - Guía de Implementación por Fases

**Versión**: 3.0
**Fecha**: Marzo 2026
**Estado**: En desarrollo
**Arquitectura**: 4 capas independientes comunicadas via PostgreSQL

---

## 1. Compatibilidad con Arquitectura SAA v7.2

### 1.1 Requisitos de Hardware

| Componente | MB (Agente) | TO (Gateway) | WS (Backend) | IM (Fallback) |
|------------|-------------|--------------|--------------|---------------|
| **CPU** | 4+ cores | 4+ cores | 8+ cores | 4+ cores |
| **RAM** | 16GB+ | 8GB+ | 16GB+ | 8GB+ |
| **Storage** | 100GB SSD | 50GB SSD | 200GB SSD | 100GB SSD |
| **GPU** | No requerida | No requerida | Recomendada | No requerida |

### 1.2 Requisitos de Software

| Componente | Versión Mínima | Notas |
|------------|----------------|-------|
| Python | 3.11+ | Para todos los scripts |
| PostgreSQL | 16+ | Con TimescaleDB |
| Docker | 24+ | Para contenedores |
| Tailscale | 1.0+ | Para conectividad |

### 1.3 Compatibilidad con Nodos

| Nodo | Rol en Memecoin Agent | Estado |
|------|----------------------|--------|
| **MB** | Agente cliente (Hermes) | ✅ Activo |
| **TO** | LiteLLM Gateway (LLM) | ✅ Activo |
| **WS** | Backend IA principal | ⚠️ Ocupado COLMAP |
| **IM** | Fallback IA (phi) | ✅ Activo |
| **EW** | Backend extra | ❌ Offline |

### 1.4 Enrutamiento LLM para Memecoin Agent

```
Memecoin Agent (MB)
    ↓
LiteLLM Gateway (TO:8080)
    ↓
    ├─→ ws-qwen-heavy → WS:11435 (Qwen3.5) [⚠️ Ocupado]
    ├─→ im-qwen32b    → IM:11434 (Qwen32B) [✅ Disponible]
    └─→ ew-qwen       → EW:11434 (Qwen3.5) [❌ Offline]
```

**Recomendación**: Usar `im-qwen32b` para tareas de Memecoin Agent hasta que WS esté disponible.

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

   # Verificar disco
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

   # Verificar WS (llama-server)
   curl http://100.68.1.160:11435/health
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
Instalar y configurar PostgreSQL + TimescaleDB.

#### Tareas

1. **Instalar PostgreSQL 16**
   ```bash
   # macOS
   brew install postgresql@16
   brew services start postgresql@16

   # Ubuntu
   sudo apt install postgresql-16
   sudo systemctl start postgresql
   ```

2. **Instalar TimescaleDB**
   ```bash
   # macOS
   brew install timescaledb

   # Ubuntu
   sudo apt install timescaledb-2-postgresql-16
   ```

3. **Crear Base de Datos**
   ```bash
   createdb memecoin_db
   createuser memecoin_user
   psql -d memecoin_db -f sql/schema_v3.0.sql
   ```

4. **Verificar Instalación**
   ```sql
   -- Verificar TimescaleDB
   SELECT extname FROM pg_extension;

   -- Verificar hypertables
   SELECT * FROM timescaledb_information.hypertables;
   ```

#### Archivos Generados
- `sql/memecoin_db.sql` - Schema inicializado
- `logs/installation.log` - Log de instalación

---

### FASE 2: Streaming On-Chain (Días 6-8)

#### Objetivo
Implementar ingesta de datos en tiempo real.

#### Tareas

1. **Configurar Yellowstone gRPC**
   - Obtener endpoint de Chainstack
   - Configurar `YELLOWSTONE_ENDPOINT` en `.env`
   - Probar conexión con `scripts/stream_onchain_grpc.py --dry-run`

2. **Configurar PumpPortal WebSocket**
   - Obtener API key si es necesario
   - Configurar `PUMPPORTAL_WS_URL` en `.env`
   - Probar conexión con `scripts/stream_onchain_ws.py --dry-run`

3. **Implementar Fallback**
   - Configurar prioridad de fuentes en `docker-compose.yml`
   - Probar con `docker compose --profile fallback up`

#### Archivos Generados
- `scripts/stream_onchain_grpc.py` - Streaming gRPC
- `scripts/stream_onchain_ws.py` - Streaming WebSocket
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
   ```sql
   SELECT * FROM token_features WHERE feature_version LIKE '%micro%';
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

##### Capa C: Research Engine
- `agents/research_engine.py` - ML + Hipótesis
- APScheduler para:
  - Entrenamiento diario (3am)
  - Hipótesis semanal (lunes 4am)
  - Validación cada 6h
  - Backtest diario (8am)

##### Capa D: Execution Engine
- `agents/execution_engine.py` - Ejecución de trades
- Reglas:
  - Límite hard 1 SOL por trade
  - Stop-loss -30%
  - Take-profit +50%, +100%
  - Jito Bundles
  - Circuit breaker

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

### FASE 7: Docker y Despliegue (Días 24-25)

#### Objetivo
Desplegar sistema completo con Docker Compose.

#### Tareas

1. **Construir Imagen**
   ```bash
   docker compose build
   ```

2. **Arrancar Servicios**
   ```bash
   docker compose up -d
   ```

3. **Verificar Servicios**
   ```bash
   docker compose ps
   docker compose logs -f
   ```

4. **Configurar Backfill**
   ```bash
   docker compose exec agent python scripts/backfill_historical.py
   ```

#### Archivos Generados
- `docker-compose.yml` - Orquestación
- `Dockerfile` - Imagen
- `docker-entrypoint.sh` - Entrypoint
- `logs/docker.log` - Log de Docker

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

## 3. Especificación de Recursos

### 3.1 Recursos por Servicio

| Servicio | CPU | RAM | Storage | Notas |
|----------|-----|-----|---------|-------|
| postgres | 2 | 4GB | 50GB | PostgreSQL + TimescaleDB |
| stream-grpc | 1 | 2GB | 1GB | Streaming on-chain |
| stream-ws | 1 | 1GB | 1GB | Streaming WebSocket fallback |
| sniper | 2 | 4GB | 1GB | Sniper Engine |
| risk-filter | 1 | 2GB | 1GB | Risk Filter |
| research | 4 | 8GB | 10GB | Research Engine (ML) |
| execution | 2 | 4GB | 1GB | Execution Engine |
| whale-tracker | 1 | 2GB | 1GB | Whale Tracker |
| telegram-bot | 1 | 1GB | 1GB | Telegram Bot |

**Total Recomendado**: 15GB RAM, 15+ cores, 80GB+ Storage

### 3.2 Recursos por Fase

| Fase | CPU | RAM | Storage | Duración |
|------|-----|-----|---------|----------|
| 0 | 2 | 4GB | 10GB | 2 días |
| 1 | 2 | 8GB | 50GB | 3 días |
| 2 | 2 | 4GB | 10GB | 3 días |
| 3 | 4 | 8GB | 20GB | 3 días |
| 4 | 8 | 16GB | 30GB | 7 días |
| 5 | 2 | 4GB | 10GB | 3 días |
| 6 | 2 | 2GB | 5GB | 2 días |
| 7 | 8 | 16GB | 50GB | 2 días |
| 8 | 4 | 8GB | 20GB | 3 días |

**Total Recomendado**: 16GB RAM, 8+ cores, 200GB+ Storage

### 3.3 Costes Estimados

| Componente | Coste Mensual | Notas |
|------------|---------------|-------|
| Helius RPC | $50-100 | 100k req/mes |
| Bitquery | $50-100 | Free tier suficiente |
| Chainstack | $20-50 | gRPC endpoint |
| PostgreSQL (AWS RDS) | $50-100 | t3.medium |
| **Total Estimado** | **$170-350/mes** | Sin contar infraestructura |

---

## 4. Comandos de Verificación

### 4.1 Verificar Estado del Sistema

```bash
# Verificar todos los servicios
docker compose ps

# Verificar logs en tiempo real
docker compose logs -f

# Verificar base de datos
docker compose exec postgres psql -U memecoin_user -d memecoin_db -c "SELECT COUNT(*) FROM tokens;"

# Verificar métricas
docker compose exec postgres psql -U memecoin_user -d memecoin_db -c "SELECT model_name, precision_at_10 FROM model_performance ORDER BY created_at DESC LIMIT 5;"
```

### 4.2 Verificar Latencia

```bash
# Verificar latencia de streaming
docker compose logs stream-grpc | grep "Token insertado"

# Verificar latencia de sniper
docker compose logs sniper | grep "score="

# Verificar latencia de risk filter
docker compose logs risk-filter | grep "Score:"
```

### 4.3 Verificar Métricas

```sql
-- Tokens por fuente
SELECT data_source, COUNT(*) FROM tokens GROUP BY data_source;

-- Distribución de targets
SELECT pump_100pc_24h, rug_pull_48h, still_active_7d, COUNT(*)
FROM tokens WHERE label_completed = TRUE GROUP BY 1,2,3 ORDER BY 4 DESC;

-- Últimas métricas de modelos
SELECT model_name, precision_at_10, precision_at_20, auc_roc, created_at
FROM model_performance ORDER BY created_at DESC LIMIT 9;
```

---

## 5. Troubleshooting

### 5.1 PostgreSQL no inicia

```bash
# Verificar logs
docker compose logs postgres

# Reiniciar
docker compose restart postgres
```

### 5.2 Streaming no conecta

```bash
# Verificar endpoint
curl -v $YELLOWSTONE_ENDPOINT

# Verificar firewall
tailscale status
```

### 5.3 Agentes no se conectan

```bash
# Verificar red
docker compose exec agent ping postgres

# Verificar variables de entorno
docker compose exec agent env | grep DATABASE_URL
```

---

## 6. Checklist de Validación Pre-Producción

### 6.1 Requisitos Mínimos

- [ ] Precision@top10 >= 0.60
- [ ] Latencia Sniper < 2s
- [ ] Latencia Risk Filter < 500ms
- [ ] Uptime > 99.5%
- [ ] 8 semanas consecutivas de validación

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

## 7. Integración con SAA v7.2

### 7.1 Configuración de LiteLLM

```yaml
# litellm_config.yaml
model_list:
  - model_name: memecoin-agent
    litellm_params:
      model: openai/qwen3.5
      api_base: http://100.68.1.180:8080
      api_key: ${LITELLM_API_KEY}
```

### 7.2 Configuración de Hermes

```toml
# config/hermes-memecoin.toml
[agent]
name = "memecoin-analyst"
model = "http://100.68.1.180:8080/v1"
model_id = "im-qwen32b"  # Usar IM como fallback
temperature = 0.4
max_tokens = 2000
```

### 7.3 Configuración de Tailscale

```bash
# Verificar conectividad
tailscale status

# Verificar rutas
tailscale netcheck
```

---

## 8. Próximos Pasos

1. **Validar compatibilidad con SAA v7.2** (FASE 0)
2. **Instalar PostgreSQL + TimescaleDB** (FASE 1)
3. **Implementar streaming on-chain** (FASE 2)
4. **Implementar micro-ventanas** (FASE 3)
5. **Implementar 4 capas** (FASE 4)
6. **Implementar whale tracker** (FASE 5)
7. **Implementar Telegram Bot** (FASE 6)
8. **Desplegar con Docker** (FASE 7)
9. **Validar sistema** (FASE 8)

---

**Versión**: 3.0
**Fecha**: Marzo 2026
**Estado**: En desarrollo