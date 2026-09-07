#!/usr/bin/env python3
"""
collect_onchain.py

Monitoriza nuevos tokens en Pump.fun en tiempo real.
Frecuencia: cada 15 minutos via Hermes/cron.

PostgreSQL - Conexión centralizada
"""

import os
import logging
import requests
from datetime import datetime, timedelta

from db import get_conn

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://mainnet.helius-rpc.com")
PUMP_PROGRAM_ADDRESS = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
LOOKBACK_MINUTES = 20  # margen extra sobre los 15 min del cron

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("collect_onchain")


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def fetch_new_tokens():
    """Obtener nuevos tokens desde Helius RPC."""
    cutoff = datetime.utcnow() - timedelta(minutes=LOOKBACK_MINUTES)

    try:
        resp = requests.post(
            f"{SOLANA_RPC_URL}",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [
                    PUMP_PROGRAM_ADDRESS,
                    {"limit": 200}
                ]
            },
            timeout=30
        )
        resp.raise_for_status()

        result = resp.json()
        if "result" not in result:
            return []

        signatures = result["result"]
        tokens = []

        for sig in signatures:
            block_time = datetime.utcfromtimestamp(sig.get("blockTime", 0))
            if block_time < cutoff:
                break
            tokens.append({
                "signature": sig.get("signature"),
                "created_at": block_time.isoformat()
            })

        return tokens

    except Exception as e:
        logger.error(f"Error fetching tokens: {e}")
        return []


def insert_token(cursor, token):
    """Insertar un token en la DB."""
    cursor.execute("""
        INSERT INTO tokens (mint, created_at, source)
        VALUES (%s, %s, 'live_rpc')
        ON CONFLICT (mint) DO NOTHING
        RETURNING id
    """, (token["signature"], token["created_at"]))

    return cursor.fetchone() is not None


def main():
    """Función principal."""
    logger.info("=== Collect Onchain (v3.0-ultralite-fixed) ===")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        new_tokens = fetch_new_tokens()
        stored = 0

        for token in new_tokens:
            if insert_token(cursor, token):
                stored += 1

        conn.commit()
        logger.info(f"collect_onchain: {stored} tokens nuevos almacenados")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()