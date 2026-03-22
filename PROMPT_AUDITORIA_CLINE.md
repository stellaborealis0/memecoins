# Prompt para Cline - Auditoría de Compatibilidad Memecoin Agent v3.0 con SAA v7.2

## Contexto

Se ha propuesto un sistema Memecoin Agent v3.0 que requiere auditoría de compatibilidad con la arquitectura SAA v7.2.

## Especificaciones del Sistema Objetivo

### MacBook Pro 7,1 (MB)
- **OS**: Ubuntu 24.04
- **RAM**: 8 GB
- **Storage**: 8 GB SSD (probablemente eMMC)
- **CPU**: Intel Core i7 (MBP 7,1 es de 2010, probablemente 2.8 GHz Intel Core i7)
- **Estado**: Cliente Cline (nodo MB en SAA v7.2)

### Arquitectura SAA v7.2
- **TO (Gateway)**: 100.68.1.180:8080 - LiteLLM Gateway
- **WS (Backend IA)**: 100.68.1.160 - Ocupado con COLMAP
- **IM (Fallback IA)**: 100.68.1.55 - Ollama + phi (CPU-only)
- **EW**: Offline

## Requisitos del Memecoin Agent v3.0 (tal como diseñado)

### Recursos Requeridos (según IMPLEMENTACION.md)
- **Total**: 15GB RAM, 15+ cores, 80GB+ Storage
- **PostgreSQL + TimescaleDB**: 4GB RAM, 50GB Storage
- **Research Engine (XGBoost)**: 8GB RAM
- **Sniper Engine**: 4GB RAM
- **Streaming gRPC**: 2GB RAM
- **Docker Compose**: 2GB RAM adicional

### Servicios Propuestos
1. PostgreSQL + TimescaleDB (base de datos)
2. stream_onchain_grpc.py (streaming on-chain)
3. stream_onchain_ws.py (fallback WebSocket)
4. sniper_engine.py (detección heurística)
5. risk_filter.py (evaluación de riesgo)
6. research_engine.py (ML + Hipótesis)
7. execution_engine.py (ejecución de trades)
8. whale_tracker.py (copy-trading)
9. telegram_bot.py (control remoto)

## Tareas para Cline

### TAREA 1: Auditoría de Compatibilidad Real

Analiza si el Memecoin Agent v3.0 es viable en el MacBook Pro 7,1 (Ubuntu 24, 8GB RAM) considerando:

1. **Recursos de Hardware**
   - ¿8GB RAM es suficiente para los 9 servicios propuestos?
   - ¿El SSD de 8GB es suficiente para PostgreSQL + datos?
   - ¿El CPU de 2010 puede manejar XGBoost + streaming en tiempo real?

2. **Restricciones SAA v7.2**
   - ¿Docker es compatible con SAA v7.2?
   - ¿PostgreSQL + TimescaleDB requiere documentación previa?
   - ¿Streaming gRPC/WebSocket está permitido?

3. **Problemas Críticos Identificados**
   - MB tiene 8GB RAM, pero el sistema requiere 15GB+ (según IMPLEMENTACION.md)
   - El sistema propone Docker Compose con 9 servicios
   - PostgreSQL + TimescaleDB no está documentado como parte de SAA v7.2

### TAREA 2: Generar Reporte de Compatibilidad

Genera un reporte con:

1. **Veredicto Final**: Viabile / No viable / Requiere redistribución
2. **Problemas Críticos**: Lista de bloqueantes
3. **Problemas Menores**: Ajustes necesarios
4. **Recomendaciones**: Qué cambiar para que sea viable

### TAREA 3: Si No es Viabile - Generar Alternativa Lightweight

Si el sistema no es viable en MB con 8GB RAM, genera una versión "v3.0-lite" que:

1. **Elimine dependencias pesadas**
   - No Docker Compose
   - No PostgreSQL + TimescaleDB
   - No streaming gRPC complejo

2. **Use recursos disponibles**
   - SQLite en lugar de PostgreSQL
   - Polling rápido (no streaming)
   - Scripts Python simples

3. **Mantenga funcionalidad crítica**
   - Sniper Engine (detección heurística)
   - Risk Filter (evaluación de riesgo)
   - Telegram Bot (control remoto)
   - Research Engine (ML) - opcional

### TAREA 4: Si es Viabile - Generar Plan de Implementación

Si el sistema es viable, genera:

1. **Plan de implementación paso a paso**
2. **Comandos exactos para cada fase**
3. **Verificación de cada paso**
4. **Rollback plan en caso de fallo**

## Instrucciones Específicas para Cline

1. **No asumas recursos**: Pregunta por specs reales si no están claras
2. **Prioriza SAA v7.2**: No propuestas que rompan la arquitectura actual
3. **Sé realista**: El MacBook Pro 7,1 es de 2010 con hardware limitado
4. **Propón alternativas**: Si no es viable, sugiere una versión simplificada

## Archivos a Revisar

- `memecoins/IMPLEMENTACION.md` - Guía de implementación
- `memecoins/README.md` - Documentación del sistema
- `memecoins/sql/schema_v3.0.sql` - Schema de base de datos
- `memecoins/requirements.txt` - Dependencias Python
- `memecoins/docker-compose.yml` - Orquestación Docker
- `memecoins/Dockerfile` - Imagen Docker

## Salida Esperada

Cline debe responder con:

```
## AUDITORÍA DE COMPATIBILIDAD - Memecoin Agent v3.0

### Veredicto: [Viabile / No viable / Requiere redistribución]

### Recursos Requeridos vs Disponibles:
| Recurso | Requerido | Disponible | Estado |
|---------|-----------|------------|--------|
| RAM | XX GB | 8 GB | [OK / CRÍTICO] |
| Storage | XX GB | 8 GB SSD | [OK / CRÍTICO] |
| CPU | XX cores | 4 cores (estimado) | [OK / CRÍTICO] |

### Problemas Críticos:
1. [Problema 1]
2. [Problema 2]
3. [Problema 3]

### Recomendaciones:
1. [Recomendación 1]
2. [Recomendación 2]

### Próximo Paso:
[Si es viable: "Generar plan de implementación"]
[Si no es viable: "Generar versión lightweight v3.0-lite"]