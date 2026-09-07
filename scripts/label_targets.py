#!/usr/bin/env python3
"""
label_targets.py

Etiqueta tokens con suficiente historia.
Frecuencia: cada hora via Hermes/cron.

PostgreSQL - Conexión centralizada
"""

import os
import logging

from db import get_conn

LIQUIDITY_MIN_THRESHOLD = 500  # USD mínimo para considerar activo
PUMP_MULTIPLIER = 2.0  # 2x = pump 100%

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("label_targets")


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def compute_pump(cursor, token_id, initial_price):
    """Calcular si hubo pump en 24h."""
    if not initial_price or initial_price == 0:
        return False

    cursor.execute("""
        SELECT price_usd FROM launches
        WHERE token_id = %s
          AND time >= (SELECT created_at FROM tokens WHERE id = %s) + INTERVAL '23 hours'
          AND time <= (SELECT created_at FROM tokens WHERE id = %s) + INTERVAL '25 hours'
        ORDER BY time DESC
        LIMIT 1
    """, (token_id, token_id, token_id))

    row = cursor.fetchone()
    if not row or not row[0]:
        return False

    return (row[0] / initial_price) >= PUMP_MULTIPLIER


def compute_rug(cursor, token_id, created_at):
    """Calcular si hubo rug pull en 48h."""
    # Condición 1: liquidez retirada >80% en 48h
    cursor.execute("""
        SELECT liquidity_pool_before, liquidity_pool_after
        FROM launches
        WHERE token_id = %s
          AND time <= %s
          AND liquidity_remove_0_2h = 1
        LIMIT 1
    """, (token_id, created_at))

    row = cursor.fetchone()
    if row and row[0] and row[0] > 0:
        withdrawn_pct = 1.0 - (row[1] or 0) / row[0]
        if withdrawn_pct >= 0.80:
            return True

    # Condición 2: volumen colapsa a 0 tras pico inicial
    cursor.execute("""
        SELECT volume_5m FROM launches
        WHERE token_id = %s
        ORDER BY time ASC
        LIMIT 1
    """, (token_id,))

    row_first = cursor.fetchone()

    cursor.execute("""
        SELECT volume_5m FROM launches
        WHERE token_id = %s
          AND time BETWEEN %s + INTERVAL '24 hours'
                       AND %s + INTERVAL '48 hours'
        ORDER BY time DESC
        LIMIT 1
    """, (token_id, created_at, created_at))

    row_last = cursor.fetchone()

    if row_first and row_last:
        if (row_first[0] or 0) > 0 and (row_last[0] or 0) == 0:
            return True

    return False


def compute_survival(cursor, token_id, created_at):
    """Calcular si el token sigue activo a los 7 días."""
    cursor.execute("""
        SELECT NOW() > %s + INTERVAL '7 days'
    """, (created_at,))

    has_7d = cursor.fetchone()[0]
    if not has_7d:
        return None  # todavía no se puede etiquetar

    cursor.execute("""
        SELECT liquidity_pool_after, volume_5m
        FROM launches
        WHERE token_id = %s
          AND time BETWEEN %s + INTERVAL '6 days 20 hours'
                       AND %s + INTERVAL '7 days 4 hours'
        ORDER BY time DESC
        LIMIT 1
    """, (token_id, created_at, created_at))

    row = cursor.fetchone()
    if not row:
        return False

    liquidity_ok = (row[0] or 0) >= LIQUIDITY_MIN_THRESHOLD
    return liquidity_ok


def main():
    """Función principal."""
    logger.info("=== Label Targets (v3.0-ultralite-fixed) ===")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Tokens sin etiquetar con más de 24h de historia
        cursor.execute("""
            SELECT id, created_at, initial_price_usd
            FROM tokens
            WHERE label_completed = 0
              AND created_at < NOW() - INTERVAL '24 hours'
        """)

        tokens = cursor.fetchall()
        labeled = 0

        for token_id, created_at, initial_price in tokens:
            pump = compute_pump(cursor, token_id, initial_price)
            rug = compute_rug(cursor, token_id, created_at)
            surv = compute_survival(cursor, token_id, created_at)

            cursor.execute("""
                UPDATE tokens SET
                  pump_100pc_24h = %s,
                  rug_pull_48h = %s,
                  still_active_7d = %s,
                  label_completed = 1
                WHERE id = %s
            """, (pump, rug, surv, token_id))

            labeled += 1

        conn.commit()
        logger.info(f"label_targets: {labeled} tokens etiquetados")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()