#!/usr/bin/env python3
"""
stream_onchain_polling.py

Streaming on-chain usando Helius RPC polling (fallback).
PostgreSQL compatible para v3.0-ultralite-fixed.

Fase 2: Capa A (Sniper Engine) - ingesta de datos

Uso:
    python scripts/stream_onchain_polling.py [--dry-run] [--interval N]
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Set

import requests

from db import get_conn

# Configuración
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://mainnet.helius-rpc.com")
RUGCHECK_API_BASE = os.getenv("RUGCHECK_API_BASE", "https://api.rugcheck.xyz/v1")
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "300"))  # 5 min por defecto

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("stream_polling")


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def fetch_recent_transactions(since_slot: Optional[int] = None) -> dict:
    """Fetch recent transactions from Helius RPC."""
    payload = {
        "jsonrpc": "2.0",
        "id": "memecoin-polling",
        "method": "getSignaturesForAddress",
        "params": [
            "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",  # Pump.fun program
            {"limit": 100}
        ]
    }

    if since_slot:
        payload["params"].append({"before": since_slot})

    try:
        response = requests.post(SOLANA_RPC_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result
    except Exception as e:
        logger.error(f"Error fetching transactions: {e}")
        return {}


def fetch_transaction_details(signature: str) -> Optional[dict]:
    """Fetch transaction details by signature."""
    payload = {
        "jsonrpc": "2.0",
        "id": "memecoin-detail",
        "method": "getTransaction",
        "params": [
            signature,
            {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
        ]
    }

    try:
        response = requests.post(SOLANA_RPC_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        return result.get("result")
    except Exception as e:
        logger.warning(f"Error fetching transaction {signature}: {e}")
        return None


def extract_token_creation(tx_data: dict) -> Optional[str]:
    """Extract token mint from transaction data."""
    if not tx_data:
        return None

    transaction = tx_data.get("transaction", {})
    message = transaction.get("message", {})
    instructions = message.get("instructions", [])

    for instr in instructions:
        # Look for createAccount or createMint instructions
        if instr.get("program") == "token":
            data = instr.get("data", "")
            # Create mint instruction starts with specific data
            if len(data) > 10 and data[:10] == "77777777":
                return None  # Skip mint creation

        # Check for Pump.fun create instructions
        if instr.get("program") == "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P":
            # This is a Pump.fun instruction
            accounts = instr.get("accounts", [])
            if len(accounts) > 0:
                return accounts[0]  # First account is usually the mint

    return None


def fetch_rugcheck_score(mint: str) -> Optional[dict]:
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


def process_token(mint: str) -> bool:
    """Process a new token and insert into database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if not mint:
            return False

        # Verificar si ya existe
        cursor.execute("SELECT id FROM tokens WHERE mint = %s", (mint,))
        if cursor.fetchone():
            logger.info(f"Token {mint} ya existe, saltando")
            return False

        # Insertar token
        created_at = datetime.utcnow().isoformat()
        cursor.execute("""
            INSERT INTO tokens (mint, created_at, source)
            VALUES (%s, %s, 'live_polling')
            ON CONFLICT (mint) DO NOTHING
            RETURNING id
        """, (mint, created_at))

        result = cursor.fetchone()
        if result:
            token_id = result[0]
            logger.info(f"Token insertado: {mint} (id={token_id})")

            # Enriquecer con rugcheck score
            rugcheck = fetch_rugcheck_score(mint)
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
        return True

    except Exception as e:
        logger.error(f"Error processing token {mint}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


async def polling_loop():
    """Loop principal de polling."""
    last_slot = None
    processed_signatures: Set[str] = set()

    logger.info(f"Iniciando polling cada {POLLING_INTERVAL}s")

    while True:
        try:
            # Fetch recent transactions
            result = fetch_recent_transactions(since_slot=last_slot)

            if "result" not in result:
                logger.warning(f"Invalid response: {result}")
                time.sleep(POLLING_INTERVAL)
                continue

            signatures = result["result"]
            logger.info(f"Found {len(signatures)} new transactions")

            for sig_info in signatures:
                signature = sig_info.get("signature")
                if not signature or signature in processed_signatures:
                    continue

                processed_signatures.add(signature)

                # Fetch transaction details
                tx_data = fetch_transaction_details(signature)
                if not tx_data:
                    continue

                # Extract token mint
                mint = extract_token_creation(tx_data)
                if mint:
                    process_token(mint)

                # Update last slot
                last_slot = sig_info.get("slot")

            # Clean up old signatures (keep last 1000)
            if len(processed_signatures) > 1000:
                processed_signatures = set(list(processed_signatures)[-1000:])

            logger.info(f"Polling complete. Last slot: {last_slot}")

        except Exception as e:
            logger.error(f"Error in polling loop: {e}")

        time.sleep(POLLING_INTERVAL)


def main():
    """Función principal."""
    dry_run = "--dry-run" in sys.argv
    interval = None

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--interval" and i + 1 < len(sys.argv):
            interval = int(sys.argv[i + 1])
        elif arg == "--dry-run":
            dry_run = True

    if interval:
        global POLLING_INTERVAL
        POLLING_INTERVAL = interval

    logger.info("=== Memecoin Agent v3.0-ultralite-fixed - Stream Polling ===")
    logger.info(f"Modo: {'DRY-RUN' if dry_run else 'LIVE'}")
    logger.info(f"Interval: {POLLING_INTERVAL}s")

    if dry_run:
        logger.info("Dry-run: solo simulará una iteración")
        result = fetch_recent_transactions()
        logger.info(f"Response: {json.dumps(result, indent=2)[:500]}...")
        logger.info("Dry-run completado")
        return

    # Run polling loop
    polling_loop()


if __name__ == "__main__":
    main()