#!/usr/bin/env python3
"""
stream_onchain_ws.py

Streaming on-chain usando PumpPortal WebSocket (primario).
PostgreSQL compatible para v3.0-ultralite-fixed.

Fase 2: Capa A (Sniper Engine) - ingesta de datos

Uso:
    python scripts/stream_onchain_ws.py [--dry-run] [--timeout N]
"""

import os
import sys
import asyncio
import logging
import json
from datetime import datetime
from typing import Optional

import requests
from websockets import connect
from websockets.exceptions import ConnectionClosed

from db import get_conn

# Configuración
PUMPPORTAL_WS_URL = os.getenv("PUMPPORTAL_WS_URL", "wss://pumpportal.fun/api/data")
RUGCHECK_API_BASE = os.getenv("RUGCHECK_API_BASE", "https://api.rugcheck.xyz/v1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("stream_ws")


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


async def connect_ws():
    """Conectar a PumpPortal WebSocket."""
    max_retries = 10
    base_delay = 1

    for attempt in range(max_retries):
        try:
            logger.info(f"Intentando conectar a PumpPortal WebSocket (intento {attempt + 1})...")
            ws = await connect(PUMPPORTAL_WS_URL)
            logger.info("Conectado a PumpPortal WebSocket")
            return ws
        except Exception as e:
            logger.error(f"Error conectando: {e}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.info(f"Reintentando en {delay}s...")
                await asyncio.sleep(delay)
            else:
                raise


async def subscribe_events(ws):
    """Suscribirse a eventos de PumpPortal."""
    # Suscribirse a tokens nuevos
    subscribe_new_token = {
        "method": "subscribeNewToken"
    }
    await ws.send(json.dumps(subscribe_new_token))

    # Suscribirse a migraciones a PumpSwap
    subscribe_migration = {
        "method": "subscribeMigration"
    }
    await ws.send(json.dumps(subscribe_migration))

    logger.info("Suscripciones enviadas")


async def fetch_rugcheck_score(mint: str) -> Optional[dict]:
    """Obtener rugcheck score para un token."""
    try:
        resp = requests.get(
            f"{RUGCHECK_API_BASE}/tokens/{mint}/report",
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Error fetching rugcheck for {mint}: {e}")
    return None


async def process_new_token(msg: dict):
    """Procesar evento de token nuevo."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        mint = msg.get("mint")
        if not mint:
            return

        # Verificar si ya existe
        cursor.execute("SELECT id FROM tokens WHERE mint = %s", (mint,))
        if cursor.fetchone():
            logger.info(f"Token {mint} ya existe, saltando")
            return

        # Insertar token
        created_at = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO tokens (mint, created_at, source)
            VALUES (%s, %s, 'live_ws')
            ON CONFLICT (mint) DO NOTHING
            RETURNING id
        """, (mint, created_at))

        result = cursor.fetchone()
        if result:
            token_id = result[0]
            logger.info(f"Token insertado: {mint} (id={token_id})")

            # Enriquecer con rugcheck score
            rugcheck = await fetch_rugcheck_score(mint)
            if rugcheck:
                cursor.execute("""
                    UPDATE tokens
                    SET rugcheck_score = %s,
                        rugcheck_risks = %s
                    WHERE mint = %s
                """, (
                    rugcheck.get("score"),
                    json.dumps(rugcheck.get("risks", [])),
                    mint
                ))

        conn.commit()

    except Exception as e:
        logger.error(f"Error procesando token: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


async def process_migration(msg: dict):
    """Procesar evento de migración a PumpSwap."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        mint = msg.get("mint")
        pool = msg.get("pool")

        if not mint:
            return

        cursor.execute("""
            UPDATE tokens
            SET migrated_to_pumpswap = 1,
                pumpswap_pool_address = %s
            WHERE mint = %s
        """, (pool, mint))

        conn.commit()
        logger.info(f"Token migrado a PumpSwap: {mint}")

    except Exception as e:
        logger.error(f"Error procesando migración: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


async def stream_loop():
    """Loop principal de streaming."""
    while True:
        try:
            ws = await connect_ws()
            await subscribe_events(ws)

            logger.info("Esperando eventos...")

            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    tx_type = msg.get("txType")

                    if tx_type == "create":
                        await process_new_token(msg)
                    elif tx_type == "migrate":
                        await process_migration(msg)

                except json.JSONDecodeError:
                    continue

        except ConnectionClosed:
            logger.warning("Conexión cerrada, reconectando...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error en stream loop: {e}")
            await asyncio.sleep(5)


async def main(dry_run: bool = False, timeout: Optional[int] = None):
    """Función principal."""
    logger.info("=== Memecoin Agent v3.0-ultralite-fixed - Stream WebSocket ===")
    logger.info(f"Modo: {'DRY-RUN' if dry_run else 'LIVE'}")

    if dry_run:
        logger.info("Dry-run: solo simulará la conexión")
        await asyncio.sleep(timeout or 30)
        logger.info("Dry-run completado")
        return

    if timeout:
        await asyncio.wait_for(stream_loop(), timeout=timeout)
    else:
        await stream_loop()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    timeout = None
    if "--timeout" in sys.argv:
        idx = sys.argv.index("--timeout")
        timeout = int(sys.argv[idx + 1])

    asyncio.run(main(dry_run=dry_run, timeout=timeout))