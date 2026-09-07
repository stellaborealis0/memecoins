# Prompt para Kilo Code en IM (iMac Intel 32GB RAM)

## Contexto
Sistema autónomo de trading de memecoins en Solana. Repo: https://github.com/stellaborealis0/memecoins

## Tareas Pendientes (Prioridad Alta → Baja)

### 1. Arreglar Sniper Engine SQL (CRÍTICO)
**Problema**: Agente en loop infinito con error `column "liquidity_add_0_10m" does not exist`
- Conectar a PostgreSQL en TO (100.68.1.180): `ssh eviwork@100.68.1.180`
- Verificar tabla `launches`: `\d launches`
- Si no existe, crear según `sql/schema_v3.0.sql`
- Si existe pero faltan columnas, ajustar query en `agents/sniper_engine.py` línea ~50
- Reiniciar agente en MB: `ssh noone@192.168.1.161 && sudo systemctl restart memecoin-agent.service`
- Verificar: `sudo journalctl -u memecoin-agent.service -f`

### 2. Configurar Research Engine en IM
- Clonar repo: `git clone https://github.com/stellaborealis0/memecoins.git`
- Instalar: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Configurar: `cp config/.env.example config/.env` (copiar credenciales de MB)
- Arrancar: `python agents/research_engine.py`
- Verificar conexión a TO (PostgreSQL 5432, LiteLLM 8080)

### 3. Verificar Google Sheets Sync
- Esperar 15-30 min después de arreglar sniper
- Abrir: https://docs.google.com/spreadsheets/d/1iArOEb9UKjxgpAvRY2WNsPkWvnwblb2beGAgG2AXqQM
- Verificar tabs: Tokens, Raw Analysis Log, Summary (deben mostrar datos reales, no solo "TEST")

## Credenciales
- **SSH MB**: `ssh noone@192.168.1.161` (clave: ~/.ssh/id_ed25519)
- **SSH TO**: `ssh eviwork@100.68.1.180`
- **PostgreSQL**: Host 100.68.1.180:5432, DB memecoin, user memecoin (password en MB: /home/noone/memecoins/config/.env)
- **Google OAuth**: Token en /Users/gerardo/openclaw-workspace/.kilo/secrets/token.json
- **GitHub**: Ya autenticado con gh CLI (stellaborealis0)

## Documentación Completa
Ver `HANDOFF_IM.md` en el repo para detalles completos de arquitectura, troubleshooting y métricas.

## Topología (Tailscale)
- **TO** (100.68.1.180): PostgreSQL, LiteLLM, Redis
- **MB** (192.168.1.161): Memecoin Agent (systemd service)
- **IM** (esta máquina): Research Engine (pendiente)

## Métricas de Éxito
- Sniper latency: <1s
- Precision@top10: >0.60
- Google Sheets: Sync cada 15 min con datos reales

## Nota
El subrepo está limpio, documentado y en GitHub. Solo falta arreglar el SQL bug y configurar IM.
