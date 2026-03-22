# Memecoin Agent v3.0-ultralite - Checklist de Validación

**Estado**: SAA v7.2 compliant - 100% SQLite, sin Docker, sin gRPC

---

## Fase 0: Análisis previo e inventario

- [ ] Leer schema actual de v3.0-ultralite y listar tablas
- [ ] Inventariar scripts de v3.0-ultralite
- [ ] Verificar requirements.txt actual (ultralite)
- [ ] Verificar conectividad SAA (LiteLLM TO:8080, Tailscale)
- [ ] Verificar Python 3.11
- [ ] Reportar inventario completo

---

## Fase 1: Infraestructura base

- [ ] Crear estructura de carpetas v3.0-ultralite
- [ ] Crear sql/schema_v3.0.sql (SQLite compatible)
- [ ] Actualizar requirements.txt (ultralite)
- [ ] Actualizar config/.env.example
- [ ] Crear .gitignore
- [ ] Crear README.md (v3.0-ultralite)
- [ ] Crear scripts/init_db.py (WAL Mode)
- [ ] Crear scripts/db_manager.py (retención automática)

---

## Fase 2: Streaming on-chain

- [ ] Implementar scripts/stream_onchain_polling.py (15s Helius)
- [ ] Modificar scripts/collect_onchain.py
- [ ] Probar conexión RPC (dry-run)
- [ ] Reducir carga CPU con server-side filter

---

## Fase 3: Micro-ventanas de features

- [ ] Actualizar schema con micro-ventanas (10s, 30s, 60s)
- [ ] Actualizar scripts/compute_features.py
- [ ] Actualizar scripts/label_targets.py

---

## Fase 4: Cuatro capas como módulos

- [ ] Implementar agents/sniper_engine.py
- [ ] Implementar agents/risk_filter.py
- [ ] Implementar agents/research_engine.py (IM fallback)
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

## Fase 7: Despliegue nativo (sin Docker)

- [ ] Arrancar servicios nativos (sin Docker)
- [ ] Configurar Research Engine en IM
- [ ] Verificar WAL Mode en SQLite
- [ ] Configurar retención automática (cron job)

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
- [ ] SQLite con WAL Mode

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

## Comandos de Verificación (SQLite)

```bash
# Verificar estructura
ls -la memecoins/

# Verificar procesos
ps aux | grep python

# Verificar logs
tail -f logs/*.log

# Verificar base de datos SQLite
sqlite3 data/memecoin.db "SELECT COUNT(*) FROM tokens;"
sqlite3 data/memecoin.db "SELECT model_name, precision_at_10 FROM model_performance ORDER BY created_at DESC LIMIT 5;"

# Verificar WAL Mode
sqlite3 data/memecoin.db "PRAGMA journal_mode;"
# Debe devolver: wal