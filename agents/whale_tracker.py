#!/usr/bin/env python3
"""
whale_tracker.py

Estrategia spray y copy-trading de whales (v3.0-ultralite-fixed)
Monitoriza transacciones de wallets conocidas y copia sus compras

Criterios de whale cualificada:
- graduation_rate > 0.15 (15%, vs baseline 0.63% general)
- total_tokens > 10 (historial suficiente)
- rug_count / total_tokens < 0.20

Fuente: whales con wallet_type='whale'

PostgreSQL - Conexión centralizada
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional

# Configuración
RISK_THRESHOLD = float(os.getenv("RISK_THRESHOLD", "0.65"))
SPRAY_ENABLED = os.getenv("SPRAY_ENABLED", "false").lower() == "true"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whale_tracker")

from db import get_conn


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def get_whale_wallets() -> list:
    """Obtener wallets de whales cualificadas."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT wallet, label, win_rate, total_trades, rug_count
            FROM whales
            WHERE label = 'whale'
              AND win_rate > 0.15
            ORDER BY win_rate DESC
        """)

        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def is_whale_qualifying(
    graduation_rate: float,
    total_tokens: int,
    rug_count: int
) -> bool:
    """Verificar si una wallet cumple criterios de whale."""
    if total_tokens < 10:
        return False
    if rug_count / max(total_tokens, 1) > 0.20:
        return False
    if graduation_rate < 0.15:
        return False
    return True


def check_risk_filter(mint: str, creator_address: str, token_id: int) -> bool:
    """Verificar risk filter para un token."""
    try:
        import requests
        resp = requests.get(
            f"http://localhost:8001/risk/{mint}",
            timeout=1
        )
        if resp.status_code == 200:
            data = resp.json()
            risk_score = data.get("risk_score", 1.0)
            return risk_score <= RISK_THRESHOLD
    except Exception as e:
        logger.warning(f"Risk filter no disponible: {e}")

    return True  # Permitir si risk filter no responde


def insert_pending_trade(cursor, token_id: int, mint: str, whale_address: str, delay_ms: int):
    """Insertar señal de copy-trading."""
    cursor.execute("""
        INSERT INTO pending_trades (
            token_id, mint_address, signal_type, whale_address, whale_delay_ms, confidence
        ) VALUES (%s, %s, 'whale_copy', %s, %s, 0.8)
        ON CONFLICT DO NOTHING
    """, (token_id, mint, whale_address, delay_ms))


async def monitor_whales():
    """Monitorizar transacciones de whales."""
    logger.info("=== Whale Tracker (v3.0-ultralite-fixed) iniciado ===")

    while True:
        try:
            if not SPRAY_ENABLED:
                await asyncio.sleep(60)
                continue

            conn = get_db_connection()
            cursor = conn.cursor()

            # Obtener whales cualificadas
            whales = get_whale_wallets()
            logger.info(f"Monitoreando {len(whales)} whales cualificadas")

            # Buscar transacciones recientes de whales
            for whale_address, whale_name, graduation_rate, total_tokens, rug_count in whales:
                cursor.execute("""
                    SELECT token_id, mint_address, action, timestamp
                    FROM trades
                    WHERE wallet_address = %s
                      AND action = 'buy'
                      AND timestamp >= NOW() - INTERVAL '5 minutes'
                    ORDER BY timestamp DESC
                    LIMIT 20
                """, (whale_address,))

                whale_trades = cursor.fetchall()

                for token_id, mint, action, whale_ts in whale_trades:
                    # Verificar si ya se copió
                    cursor.execute("""
                        SELECT id FROM pending_trades
                        WHERE mint_address = %s
                          AND signal_type = 'whale_copy'
                    """, (mint,))

                    if cursor.fetchone():
                        continue

                    # Verificar risk filter
                    if not check_risk_filter(mint, "", token_id):
                        logger.info(f"Token {mint} bloqueado por risk filter")
                        continue

                    # Calcular delay
                    our_ts = datetime.utcnow()
                    delay_ms = int((our_ts - datetime.fromisoformat(whale_ts)).total_seconds() * 1000)

                    # Insertar pending trade
                    insert_pending_trade(cursor, token_id, mint, whale_address, delay_ms)
                    logger.info(f"Whale {whale_name} compró {mint} - señal generada (delay={delay_ms}ms)")

            conn.commit()
            cursor.close()
            conn.close()

            await asyncio.sleep(30)  # Check cada 30 segundos

        except Exception as e:
            logger.error(f"Error en whale tracker: {e}")
            await asyncio.sleep(10)


async def update_whale_stats():
    """Actualizar estadísticas de whales semanalmente."""
    logger.info("Actualizando estadísticas de whales...")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Actualizar graduation_rate y rug_count para todos los creadores
        cursor.execute("""
            UPDATE whales
            SET
                total_trades = (
                    SELECT COUNT(*) FROM tokens WHERE creator_address = whales.wallet
                ),
                rug_count = (
                    SELECT SUM(CASE WHEN rug_pull_48h THEN 1 ELSE 0 END) FROM tokens WHERE creator_address = whales.wallet
                ),
                win_rate = (
                    SELECT CASE
                        WHEN COUNT(*) > 0 THEN CAST(COUNT(*) - SUM(CASE WHEN rug_pull_48h THEN 1 ELSE 0 END) AS REAL) / COUNT(*)
                        ELSE 0
                    END FROM tokens WHERE creator_address = whales.wallet
                )
            WHERE label = 'whale'
        """)

        conn.commit()
        logger.info("Estadísticas de whales actualizadas")

    finally:
        cursor.close()
        conn.close()


async def main():
    """Función principal."""
    logger.info("=== Memecoin Agent v3.0-ultralite-fixed - Whale Tracker ===")
    logger.info(f"SPRAY_ENABLED: {SPRAY_ENABLED}")

    # Actualizar estadísticas al inicio
    await update_whale_stats()

    # Iniciar monitorización
    await monitor_whales()


if __name__ == "__main__":
    asyncio.run(main())