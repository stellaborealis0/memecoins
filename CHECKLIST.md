# Memecoin Agent v3.0 - Checklist de Validación

## Fase 0: Análisis previo e inventario

- [ ] Leer schema actual de v2.3 y listar tablas
- [ ] Inventariar scripts de v2.3
- [ ] Verificar requirements.txt actual
- [ ] Verificar conectividad SAA (LiteLLM, PostgreSQL, Tailscale)
- [ ] Verificar Python 3.11
- [ ] Descargar repos de referencia
- [ ] Reportar inventario completo

## Fase 1: Infraestructura base

- [ ] Crear estructura de carpetas v3.0
- [ ] Crear sql/schema_v3.0.sql
- [ ] Actualizar requirements.txt
- [ ] Actualizar config/.env.example
- [ ] Crear .gitignore
- [ ] Crear README.md

## Fase 2: Streaming on-chain

- [ ] Implementar scripts/stream_onchain_grpc.py
- [ ] Implementar scripts/stream_onchain_ws.py
- [ ] Modificar scripts/collect_onchain.py
- [ ] Probar conexión gRPC (dry-run)
- [ ] Probar conexión WebSocket (dry-run)

## Fase 3: Micro-ventanas de features

- [ ] Actualizar schema con micro-ventanas (10s, 30s, 60s)
- [ ] Actualizar scripts/compute_features.py
- [ ] Actualizar scripts/label_targets.py

## Fase 4: Cuatro capas como módulos

- [ ] Implementar agents/sniper_engine.py
- [ ] Implementar agents/risk_filter.py
- [ ] Implementar agents/research_engine.py
- [ ] Implementar agents/execution_engine.py
- [ ] Implementar agents/whale_tracker.py
- [ ] Probar sniper engine (dry-run)
- [ ] Probar risk filter (dry-run)
- [ ] Probar research engine (dry-run)
- [ ] Probar execution engine (dry-run)
- [ ] Probar whale tracker (dry-run)

## Fase 5: Whale tracker y spray strategy

- [ ] Implementar tracked_wallets table
- [ ] Calcular graduation_rate para whales
- [ ] Implementar copy-trading logic
- [ ] Probar spray strategy (dry-run)

## Fase 6: Telegram Bot extendido

- [ ] Actualizar telegram_bot.py con nuevos comandos
- [ ] Probar comandos de estado
- [ ] Probar comandos de control

## Fase 7: Docker y despliegue

- [ ] Crear Dockerfile
- [ ] Crear docker-compose.yml
- [ ] Crear docker-entrypoint.sh
- [ ] Construir imagen docker compose build
- [ ] Arrancar docker compose up -d
- [ ] Verificar logs docker compose logs -f

## Fase 8: Tests y checklist

- [ ] Verificar estructura completa
- [ ] Crear checklist de validación
- [ ] Ejecutar tests unitarios
- [ ] Ejecutar tests de integración
- [ ] Verificar métricas de latencia
- [ ] Verificar métricas de precisión

## Validación Pre-Producción

### Requisitos mínimos

- [ ] Precision@top10 >= 0.60 (mínimo aceptable)
- [ ] Latencia Sniper < 2s
- [ ] Latencia Risk Filter < 500ms
- [ ] Uptime > 99.5%
- [ ] 8 semanas consecutivas de validación

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

## Comandos de Verificación

```bash
# Verificar estructura
ls -la memecoins/

# Verificar Docker
docker compose ps

# Verificar logs
docker compose logs -f

# Verificar base de datos
docker compose exec postgres psql -U memecoin_user -d memecoin_db -c "SELECT COUNT(*) FROM tokens;"

# Verificar métricas
docker compose exec postgres psql -U memecoin_user -d memecoin_db -c "SELECT model_name, precision_at_10 FROM model_performance ORDER BY created_at DESC LIMIT 5;"