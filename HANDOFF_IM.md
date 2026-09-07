# Memecoin Agent - Handoff Prompt for IM (iMac Intel 32GB RAM)

## Contexto del Proyecto

Sistema autónomo de análisis y trading de memecoins en Solana (v3.1). Arquitectura distribuida en múltiples nodos:

- **MB** (MacBook Pro 7,1, 8GB RAM): Ejecuta agentes principales (sniper, risk filter, execution, whale tracker)
- **TO** (Tailscale 100.68.1.180): PostgreSQL, LiteLLM Gateway, Redis
- **IM** (iMac Intel 32GB RAM): Research Engine (ML training, hipótesis LLM)

## Estado Actual (2026-09-07)

### ✅ Completado
1. **Subrepo limpiado y reorganizado**: Eliminados archivos temporales, .DS_Store, _OLD/
2. **Documentación actualizada**: README_v3.1.md con arquitectura completa
3. **Commit y push a GitHub**: https://github.com/stellaborealis0/memecoins (commit fbea50e)
4. **Google Sheets integrado**: Sync automático cada 15 min con OAuth (stellaborealis0@gmail.com)
   - Sheet ID: `1iArOEb9UKjxgpAvRY2WNsPkWvnwblb2beGAgG2AXqQM`
   - Tabs: Tokens, Whales, Trades, Model Performance, Raw Analysis Log, Summary, System Metrics

### ❌ Pendiente
1. **Sniper Engine SQL bug**: La tabla `launches` no existe o tiene columnas incorrectas
   - Error: `column "liquidity_add_0_10m" does not exist`
   - El agente está en loop infinito desde hace 6+ horas
   - Necesita: verificar schema de `launches` y corregir query en `agents/sniper_engine.py`

2. **Research Engine en IM**: No está configurado ni ejecutándose
   - IM tiene 32GB RAM (vs 8GB en MB), ideal para ML training
   - Necesita: instalar dependencias, configurar .env, arrancar `agents/research_engine.py`

3. **Google Sheets con datos reales**: Sync funciona pero no hay datos reales aún
   - El sniper engine está roto, por lo que no se generan tokens
   - Una vez arreglado el SQL, los datos fluirán automáticamente

## Instrucciones para IM

### 1. Clonar el repositorio
```bash
cd ~/openclaw-workspace
git clone https://github.com/stellaborealis0/memecoins.git
cd memecoins
```

### 2. Instalar dependencias
```bash
# Crear venv
python3 -m venv .venv
source .venv/bin/activate

# Instalar
pip install -r requirements.txt
```

### 3. Configurar variables de entorno
```bash
cp config/.env.example config/.env
nano config/.env
```

Variables críticas:
- `POSTGRES_HOST`: IP de TO (100.68.1.180)
- `POSTGRES_PORT`: 5432
- `POSTGRES_DB`: memecoin
- `POSTGRES_USER`: memecoin
- `POSTGRES_PASSWORD`: (ver en MB: /home/noone/memecoins/config/.env)
- `LITELLM_ENDPOINT`: http://100.68.1.180:8080/v1
- `LITELLM_MODEL`: im-qwen32b

### 4. Verificar conectividad
```bash
# Test PostgreSQL (debe conectarse a TO)
psql -h 100.68.1.180 -U memecoin -d memecoin -c "SELECT COUNT(*) FROM tokens;"

# Test LiteLLM
curl http://100.68.1.180:8080/v1/models
```

### 5. Arrancar Research Engine
```bash
python agents/research_engine.py
```

El Research Engine:
- Entrena modelos XGBoost diariamente
- Genera hipótesis con LLM (vía LiteLLM en TO)
- Valida hipótesis con datos históricos
- Modo degradado: `heuristic_only` si IM no disponible

## Tareas Prioritarias

### TAREA 1: Arreglar Sniper Engine SQL

**Problema**: `agents/sniper_engine.py` línea ~50 hace query a tabla `launches` con columnas que no existen.

**Pasos**:
1. Conectar a PostgreSQL en TO:
   ```bash
   ssh eviwork@100.68.1.180
   psql -U memecoin -d memecoin
   ```

2. Verificar schema de `launches`:
   ```sql
   \d launches
   ```

3. Si la tabla no existe, crearla según `sql/schema_v3.0.sql`

4. Si existe pero faltan columnas, ajustar query en `agents/sniper_engine.py`:
   - Cambiar columnas que no existen
   - O agregar columnas faltantes a la tabla

5. Reiniciar agente en MB:
   ```bash
   ssh noone@192.168.1.161
   sudo systemctl restart memecoin-agent.service
   ```

6. Verificar que no hay errores:
   ```bash
   sudo journalctl -u memecoin-agent.service -f
   ```

### TAREA 2: Configurar Research Engine en IM

**Objetivo**: Aprovechar los 32GB RAM de IM para ML training.

**Pasos**:
1. Seguir instrucciones de instalación arriba
2. Verificar que TO está accesible (PostgreSQL, LiteLLM)
3. Arrancar `agents/research_engine.py`
4. Monitorear logs para verificar que:
   - Se conecta a PostgreSQL
   - Entrena modelos cada 24h
   - Genera hipótesis semanales
   - Actualiza `model_performance` en DB

### TAREA 3: Verificar Google Sheets Sync

**Objetivo**: Confirmar que datos reales fluyen a Google Sheets.

**Pasos**:
1. Esperar 15-30 min después de arreglar sniper engine
2. Abrir Google Sheet: https://docs.google.com/spreadsheets/d/1iArOEb9UKjxgpAvRY2WNsPkWvnwblb2beGAgG2AXqQM
3. Verificar tabs:
   - **Tokens**: Debe mostrar tokens analizados (no solo "TEST")
   - **Raw Analysis Log**: Todos los tokens analizados (incluyendo baja probabilidad)
   - **Summary**: Contadores actualizados
   - **System Metrics**: Timestamp de último sync

4. Si no hay datos, verificar:
   ```bash
   # En MB
   tail -f /tmp/memecoin_sheets_sync.log
   
   # En IM (si está corriendo)
   python3 scripts/simple_sync.py --sheet-id "1iArOEb9UKjxgpAvRY2WNsPkWvnwblb2beGAgG2AXqQM"
   ```

## Topología de Red (Tailscale)

- **TO**: 100.68.1.180 (control plane 24/7)
  - PostgreSQL: 5432
  - LiteLLM: 8080
  - Redis: 6379
  - Dashboard: http://100.68.1.180:8780

- **MB**: 192.168.1.161 (LAN) / 100.68.1.160 (Tailscale)
  - Memecoin Agent: systemd service `memecoin-agent.service`
  - Logs: /tmp/memecoin_sheets_sync.log

- **IM**: (esta máquina, iMac Intel 32GB RAM)
  - Research Engine: pendiente de configurar
  - Kilo CLI: ya instalado

- **MI**: 100.68.1.52 (Mac Mini M4)
  - Desarrollo/UI

## Credenciales y Accesos

### SSH
- MB: `ssh noone@192.168.1.161` (clave: ~/.ssh/id_ed25519)
- TO: `ssh eviwork@100.68.1.180`

### PostgreSQL (en TO)
- Host: 100.68.1.180:5432
- DB: memecoin
- User: memecoin
- Password: (ver en MB: /home/noone/memecoins/config/.env)

### Google OAuth
- Account: stellaborealis0@gmail.com
- Token: /Users/gerardo/openclaw-workspace/.kilo/secrets/token.json
- Sheet ID: 1iArOEb9UKjxgpAvRY2WNsPkWvnwblb2beGAgG2AXqQM

### GitHub
- Repo: https://github.com/stellaborealis0/memecoins
- Auth: gh CLI (ya autenticado como stellaborealis0)

## Estructura del Código

```
memecoins/
├── agents/
│   ├── sniper_engine.py      # Capa A: detección <1s (⚠️ SQL bug)
│   ├── risk_filter.py        # Capa B: evaluación riesgo <500ms
│   ├── research_engine.py    # Capa C: ML + hipótesis (para IM)
│   ├── execution_engine.py   # Capa D: trades + circuit breaker
│   └── whale_tracker.py      # Copy-trading de whales
├── scripts/
│   ├── init_db.py            # Inicializar PostgreSQL
│   ├── stream_onchain_polling.py  # Polling RPC cada 15s
│   ├── telegram_bot.py       # Bot de control
│   └── simple_sync.py        # Sync a Google Sheets (en workspace root)
├── config/
│   ├── .env.example          # Template de variables
│   └── memecoin-agent.service # Systemd service
├── sql/
│   └── schema_v3.0.sql       # Schema PostgreSQL
└── README_v3.1.md            # Documentación completa
```

## Métricas de Éxito

- **Precision@top10**: > 0.60
- **Latencia Sniper**: < 1s
- **Latencia Risk Filter**: < 500ms
- **Uptime**: > 99.5%
- **Google Sheets**: Sync cada 15 min con datos reales

## Próximos Pasos Inmediatos

1. **Arreglar sniper engine SQL** (prioridad alta)
   - Verificar tabla `launches` en TO
   - Corregir query en `agents/sniper_engine.py`
   - Reiniciar agente en MB
   - Verificar que tokens empiecen a fluir

2. **Configurar Research Engine en IM** (prioridad media)
   - Instalar dependencias
   - Configurar .env
   - Arrancar y monitorear

3. **Verificar Google Sheets** (prioridad media)
   - Esperar 15-30 min
   - Confirmar datos reales en sheet
   - Ajustar queries si es necesario

## Notas Importantes

- **NO usar Docker**: El sistema es 100% PostgreSQL, sin contenedores
- **NO tocar modelos en producción**: Solo en modo research
- **Circuit breaker**: Se activa tras 3 pérdidas consecutivas
- **Stop-loss**: -30% hard limit
- **Max position**: 1 SOL por trade
- **Execution PIN**: Requerido para trades reales (6 dígitos)

## Troubleshooting

### Sniper engine en loop
```bash
# Ver errores
sudo journalctl -u memecoin-agent.service -f | grep ERROR

# Reiniciar
sudo systemctl restart memecoin-agent.service
```

### Google Sheets no actualiza
```bash
# Ver log de sync
tail -f /tmp/memecoin_sheets_sync.log

# Forzar sync manual
python3 /Users/gerardo/openclaw-workspace/scripts/simple_sync.py \
  --sheet-id "1iArOEb9UKjxgpAvRY2WNsPkWvnwblb2beGAgG2AXqQM"
```

### PostgreSQL no conecta
```bash
# Verificar tunnel SSH
ssh -L 5432:localhost:5432 eviwork@100.68.1.180

# O conectar directo
psql -h 100.68.1.180 -U memecoin -d memecoin
```

---

**Fecha de handoff**: 2026-09-07
**Versión**: v3.1
**Estado**: Subrepo limpio, documentado, en GitHub. Pendiente: arreglar SQL y configurar IM.
