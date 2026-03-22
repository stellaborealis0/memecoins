"""
stream_onchain_grpc.py

Daemon de streaming on-chain usando Yellowstone gRPC.
Sustituye el polling de 15 min por streaming en tiempo real.

Fase 2: Capa A (Sniper Engine) - ingesta de datos

Uso:
    python scripts/stream_onchain_grpc.py [--dry-run] [--timeout N]
"""

import os
import sys
import asyncio
import logging
import json
from datetime import datetime
from typing import Optional

import psycopg2
from websockets import connect
from websockets.exceptions import ConnectionClosed

# Configuración
PUMP_PROGRAM_ADDRESS = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
YELLOWSTONE_ENDPOINT = os.getenv("YELLOWSTONE_ENDPOINT", "wss://grpc.geyser.finance")
YELLOWSTONE_TOKEN = os.getenv("YELLOWSTONE_TOKEN", "")
DB_DSN = os.getenv("DATABASE_URL")
LITELLM_ENDPOINT = os.getenv("LITELLM_ENDPOINT", "http://100.68.1.180:8080/v1")
RUGCHECK_API_BASE = os.getenv("RUGCHECK_API_BASE", "https://api.rugcheck.xyz/v1")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("stream_grpc")


async def connect_grpc():
    """Conectar a Yellowstone gRPC con reintentos."""
    max_retries = 10
    base_delay = 1

    for attempt in range(max_retries):
        try:
            logger.info(f"Intentando conectar a Yellowstone gRPC (intento {attempt + 1})...")
            ws = await connect(YELLOWSTONE_ENDPOINT)
            logger.info("Conectado a Yellowstone gRPC")
            return ws
        except Exception as e:
            logger.error(f"Error conectando: {e}")
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.info(f"Reintentando en {delay}s...")
                await asyncio.sleep(delay)
            else:
                raise


async def subscribe_to_pump_program(ws):
    """Suscribirse a eventos del programa Pump.fun."""
    subscribe_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [PUMP_PROGRAM_ADDRESS]},
            {"commitment": "processed"}
        ]
    }

    await ws.send(json.dumps(subscribe_msg))
    response = await ws.recv()
    result = json.loads(response)

    if "result" in result:
        logger.info(f"Suscrito a logs de Pump.fun. Subscription ID: {result['result']}")
        return True
    else:
        logger.error(f"Error en suscripción: {result}")
        return False


async def fetch_rugcheck_score(mint: str) -> Optional[dict]:
    """Obtener rugcheck score para un token."""
    try:
        import requests
        resp = requests.get(
            f"{RUGCHECK_API_BASE}/tokens/{mint}/report",
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Error fetching rugcheck for {mint}: {e}")
    return None


async def process_token_event(event_data: dict):
    """Procesar un evento de creación de token."""
    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        # Extraer información del evento
        mint = event_data.get("mint")
        if not mint:
            return

        # Verificar si ya existe
        cursor.execute("SELECT id FROM tokens WHERE address = %s", (mint,))
        if cursor.fetchone():
            logger.info(f"Token {mint} ya existe, saltando")
            return

        # Insertar token
        created_at = datetime.utcnow()
        cursor.execute("""
            INSERT INTO tokens (address, created_at, data_source)
            VALUES (%s, %s, 'live_grpc')
            ON CONFLICT (address) DO NOTHING
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
                    WHERE address = %s
                """, (
                    rugcheck.get("score"),
                    json.dumps(rugcheck.get("risks", [])),
                    mint
                ))

        conn.commit()
        logger.info(f"Evento procesado: {mint}")

    except Exception as e:
        logger.error(f"Error procesando evento: {e}")
        conn.rollback()
    finally:
        conn.close()


async def stream_loop():
    """Loop principal de streaming."""
    while True:
        try:
            ws = await connect_grpc()
            if not await subscribe_to_pump_program(ws):
                await ws.close()
                continue

            logger.info("Esperando eventos de Pump.fun...")

            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    # Verificar si es un evento de creación
                    if msg.get("method") == "logsNotification":
                        params = msg.get("params", {})
                        result = params.get("result", {})
                        value = result.get("value", {})

                        # Verificar si es una instrucción create de Pump.fun
                        if value.get("err") is None:
                            logs = value.get("logs", [])
                            if any("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P" in log for log in logs):
                                # Extraer mint del evento
                                for log in logs:
                                    if "Program data:" in log:
                                        # Decodificar datos si es necesario
                                        pass

                                # Procesar token nuevo
                                await process_token_event({"mint": "TODO"})

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
    logger.info("=== Memecoin Agent v3.0 - Stream gRPC ===")
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