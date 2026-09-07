# Memecoin Agent v3.0-ultralite-fixed - Checklist de Validación

**Estado**: SAA v7.2 compliant - 100% PostgreSQL, sin Docker, sin gRPC
**Versión**: v3.0-ultralite-fixed (corrección de errores críticos - PostgreSQL)

---

## Fase 0: Análisis previo e inventario

- [ ] Leer schema actual de v3.0-ultralite-fixed y listar tablas
- [ ] Inventariar scripts de v3.0-ultralite-fixed
- [ ] Verificar requirements.txt actual (ultralite-fixed)
- [ ] Verificar conectividad SAA (LiteLLM TO:8080, Tailscale)
- [ ] Verificar Python 3.11 (NO 3.12 - solana-py incompatible)
- [ ] Verificar RAM libre en IM con Ollama corriendo: ≥5 GB disponibles
- [ ] Montar almacenamiento externo o NFS: verificar que /data y pip install tienen al menos 10 GB libres
- [ ] Reportar inventario completo

---

## Fase 1: Infraestructura base

- [ ] Crear estructura de carpetas v3.0-ultralite-fixed
- [ ] Crear sql/schema_v3.0.sql (PostgreSQL compatible, micro-ventanas 30s)
- [ ] Actualizar requirements.txt (ultralite-fixed con openai>=1.30, psycopg2-binary)
- [ ] Actualizar config/.env.example
- [ ] Crear .gitignore
- [ ] Crear README.md (v3.0-ultralite-fixed)
- [ ] Crear scripts/init_db.py (PostgreSQL)
- [ ] Crear scripts/cleanup.py (cron cada 6h con VACUUM)
- [ ] Crear scripts/llm_client.py (helper centralizado)

---

## Fase 2: Streaming on-chain (PumpPortal WebSocket)

- [ ] Implementar scripts/stream_onchain_ws.py (PumpPortal WebSocket - primario)
- [ ] Implementar scripts/stream_onchain_polling.py (Helius 5min - fallback)
- [ ] Modificar scripts/collect_onchain.py
- [ ] Probar conexión RPC (dry-run)
- [ ] Reducir carga CPU con server-side filter

---

## Fase 3: Micro-ventanas de features

- [ ] Actualizar schema con micro-ventanas (30s, 60s, 5m)
- [ ] Actualizar scripts/compute_features.py
- [ ] Actualizar scripts/label_targets.py

---

## Fase 4: Cuatro capas como módulos

- [ ] Implementar agents/sniper_engine.py
- [ ] Implementar agents/risk_filter.py
- [ ] Implementar agents/research_engine.py (MB con fallback heuristic_only)
- [ ] Implementar agents/execution_engine.py
- [ ] Implementar agents/whale_tracker.py
- [ ] Probar sniper engine (dry-run)
- [ ] Probar risk filter (dry-run)
- [ ] Probar research engine (dry-run)
- [ ] Probar execution engine (dry-run)
- [ ] Probar whale tracker (dry-run)

---

## Fase 5: Whale tracker y spray strategy

- [ ] Implementar tracked_wallets table
- [ ] Calcular graduation_rate para whales
- [ ] Implementar copy-trading logic
- [ ] Probar spray strategy (dry-run)

---

## Fase 6: Telegram Bot extendido

- [ ] Actualizar telegram_bot.py con nuevos comandos
- [ ] Probar comandos de estado
- [ ] Probar comandos de control

---

## Fase 7: Despliegue nativo (Hermes + systemd)

- [ ] Configurar hermes-memecoin.toml (tasks cron)
- [ ] Arrancar servicios con systemd (no & manual)
- [ ] Configurar transferencia de datos MB→IM antes de training (scp o http)
- [ ] Verificar retención automática (cron job cada 6h)
- [ ] Configurar cron: `0 */6 * * * python /path/memecoin/scripts/cleanup.py`

---

## Fase 8: Tests y checklist

- [ ] Verificar estructura completa
- [ ] Crear checklist de validación
- [ ] Ejecutar tests unitarios
- [ ] Ejecutar tests de integración
- [ ] Verificar métricas de latencia
- [ ] Verificar métricas de precisión

---

## Validación Pre-Producción

### Requisitos mínimos

- [ ] Precision@top10 >= 0.60 (mínimo aceptable)
- [ ] Latencia Sniper < 2s
- [ ] Latencia Risk Filter < 500ms
- [ ] Uptime > 99.5%
- [ ] PostgreSQL (única base de datos soportada)

### Seguridad

- [ ] Límite hard de 1 SOL por trade
- [ ] Stop-loss on-chain obligatorio (-30%)
- [ ] Circuit breaker tras 3 pérdidas
- [ ] Execution PIN de 6 dígitos
- [ ] WALLET_PRIVATE_KEY protegida

### Documentación

- [ ] README.md completo
- [ ] Arquitectura documentada
- [ ] Comandos de Telegram documentados
- [ ] Troubleshooting guide

---

## Comandos de Verificación (PostgreSQL)

```bash
# Verificar estructura
ls -la memecoins/

# Verificar procesos
ps aux | grep python

# Verificar logs
tail -f logs/*.log

# Verificar base de datos PostgreSQL
psql postgresql://saa:saa@localhost:5432/saa -c "SELECT COUNT(*) FROM tokens;"
psql postgresql://saa:saa@localhost:5432/saa -c "SELECT model_name, precision_at_10 FROM model_performance ORDER BY created_at DESC LIMIT 5;"

# Verificar tamaño de base de datos
psql postgresql://saa:saa@localhost:5432/saa -c "SELECT pg_size_pretty(pg_database_size('saa'));"
```

---

## Cron Jobs (sistema de limpieza)

```bash
# Limpieza automática cada 6 horas
0 */6 * * * python /path/memecoin/scripts/cleanup.py >> /path/memecoin/logs/cleanup.log 2>&1

# Verificar tamaño de base de datos cada hora
0 * * * * psql postgresql://saa:saa@localhost:5432/saa -c "SELECT pg_size_pretty(pg_database_size('saa'));"