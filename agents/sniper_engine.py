"""
sniper_engine.py

Capa A - Sniper Engine
Detecta tokens nuevos y calcula score heurístico en <2s

Arquitectura:
- Lee tokens nuevos de la tabla tokens
- Calcula micro-features en memoria
- Si score > umbral Y risk_filter lo aprueba → publica señal en pending_trades
- No toca modelos ML. No llama al LLM. Nunca.

Latencia objetivo: <2 segundos desde inserción en DB hasta decisión
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Optional

import psycopg2

# Configuración
DB_DSN = os.getenv("DATABASE_URL")
RISK_THRESHOLD = float(os.getenv("RISK_THRESHOLD", "0.65"))
SNIPER_TX_VELOCITY_THRESHOLD = float(os.getenv("SNIPER_TX_VELOCITY_THRESHOLD", "3.0"))
SNIPER_WALLET_THRESHOLD = int(os.getenv("SNIPER_WALLET_THRESHOLD", "10"))
SNIPER_BUY_RATIO_THRESHOLD = float(os.getenv("SNIPER_BUY_RATIO_THRESHOLD", "0.70"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sniper_engine")


def get_micro_features(cursor, token_id: int) -> dict:
    """Obtener micro-features de un token."""
    cursor.execute("""
        SELECT
            MAX(txs_0_10s) AS txs_0_10s,
            MAX(txs_10_30s) AS txs_10_30s,
            MAX(txs_30_60s) AS txs_30_60s,
            MAX(unique_wallets_0_10m) AS unique_wallets_0_10m,
            MAX(buy_tx_0_30m) AS buy_tx_0_30m,
            MAX(sell_tx_0_30m) AS sell_tx_0_30m,
            MAX(liquidity_add_0_10m) AS liquidity_add_0_10m,
            MAX(liquidity_remove_0_2h) AS liquidity_remove_0_2h,
            MAX(top_10_wallets_pct_0_1h) AS top_10_wallets_pct_0_1h,
            MAX(bonding_curve_progress_pct) AS bonding_curve_progress_pct
        FROM launches
        WHERE token_id = %s
    """, (token_id,))

    row = cursor.fetchone()
    cols = [
        "txs_0_10s", "txs_10_30s", "txs_30_60s",
        "unique_wallets_0_10m", "buy_tx_0_30m", "sell_tx_0_30m",
        "liquidity_add_0_10m", "liquidity_remove_0_2h",
        "top_10_wallets_pct_0_1h", "bonding_curve_progress_pct"
    ]

    return dict(zip(cols, row)) if row else {}


def calculate_sniper_score(features: dict) -> float:
    """Calcular score heurístico del sniper engine."""
    if not features:
        return 0.0

    score = 0.0
    max_score = 100.0

    # 1. Velocidad de transacciones (0-30 puntos)
    txs_0_10s = features.get("txs_0_10s", 0) or 0
    tx_velocity = txs_0_10s / 10.0  # txs por segundo en 10s
    if tx_velocity >= SNIPER_TX_VELOCITY_THRESHOLD:
        score += 30 * min(tx_velocity / SNIPER_TX_VELOCITY_THRESHOLD, 1.0)

    # 2. Wallets únicas (0-20 puntos)
    wallets = features.get("unique_wallets_0_10m", 0) or 0
    if wallets >= SNIPER_WALLET_THRESHOLD:
        score += 20 * min(wallets / SNIPER_WALLET_THRESHOLD, 1.0)

    # 3. Ratio compra/venta (0-20 puntos)
    buy = features.get("buy_tx_0_30m", 0) or 0
    sell = features.get("sell_tx_0_30m", 0) or 0
    total = buy + sell
    if total > 0:
        buy_ratio = buy / total
        if buy_ratio >= SNIPER_BUY_RATIO_THRESHOLD:
            score += 20 * min(buy_ratio / SNIPER_BUY_RATIO_THRESHOLD, 1.0)

    # 4. Liquidez añadida (0-15 puntos)
    if features.get("liquidity_add_0_10m"):
        score += 15

    # 5. Bonding curve progress (0-15 puntos)
    bc_progress = features.get("bonding_curve_progress_pct", 0) or 0
    score += 15 * (bc_progress / 100.0)

    return min(score, max_score)


async def check_risk_filter(token_id: int, mint: str) -> tuple[bool, str]:
    """
    Verificar risk filter.
    Devuelve (approved, reason)
    """
    try:
        import requests
        resp = requests.get(
            f"http://localhost:8001/risk/{mint}",
            timeout=1
        )
        if resp.status_code == 200:
            data = resp.json()
            risk_score = data.get("risk_score", 1.0)
            if risk_score > RISK_THRESHOLD:
                return False, f"Risk score {risk_score:.2f} > {RISK_THRESHOLD}"
            return True, "OK"
    except Exception as e:
        # Si el risk filter no responde, permitir con advertencia
        logger.warning(f"Risk filter no disponible: {e}")
        return True, "Risk filter unavailable"

    return True, "OK"


async def insert_pending_trade(cursor, token_id: int, mint: str, score: float):
    """Insertar señal pendiente de ejecución."""
    cursor.execute("""
        INSERT INTO pending_trades (token_id, mint_address, signal_type, sniper_score, confidence)
        VALUES (%s, %s, 'sniper_pump', %s, %s)
        ON CONFLICT DO NOTHING
    """, (token_id, mint, score, score / 100.0))


async def process_token(cursor, token_id: int, mint: str, created_at: datetime):
    """Procesar un token nuevo."""
    # Obtener micro-features
    features = get_micro_features(cursor, token_id)
    if not features:
        return

    # Calcular score
    score = calculate_sniper_score(features)
    logger.info(f"Token {mint}: score={score:.2f}")

    # Verificar risk filter
    approved, reason = await check_risk_filter(token_id, mint)
    if not approved:
        logger.info(f"Token {mint} bloqueado por risk filter: {reason}")
        return

    # Si score > umbral, insertar pending trade
    if score >= 50:  # Umbral del sniper engine
        await insert_pending_trade(cursor, token_id, mint, score)
        logger.info(f"Token {mint} generado como señal sniper (score={score:.2f})")


async def sniper_loop():
    """Loop principal del sniper engine."""
    logger.info("=== Sniper Engine iniciado ===")

    while True:
        try:
            conn = psycopg2.connect(DB_DSN)
            cursor = conn.cursor()

            # Buscar tokens nuevos sin procesar
            cursor.execute("""
                SELECT id, address, created_at
                FROM tokens
                WHERE created_at >= NOW() - INTERVAL '5 minutes'
                  AND NOT EXISTS (
                      SELECT 1 FROM pending_trades pt WHERE pt.token_id = tokens.id
                  )
                ORDER BY created_at DESC
                LIMIT 100
            """)

            tokens = cursor.fetchall()
            for token_id, mint, created_at in tokens:
                await process_token(cursor, token_id, mint, created_at)

            conn.commit()
            cursor.close()
            conn.close()

            # Esperar 1 segundo antes de la próxima iteración
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error en sniper loop: {e}")
            await asyncio.sleep(5)


async def main():
    """Función principal."""
    logger.info("=== Memecoin Agent v3.0 - Sniper Engine ===")
    logger.info(f"RISK_THRESHOLD: {RISK_THRESHOLD}")
    logger.info(f"SNIPER_TX_VELOCITY_THRESHOLD: {SNIPER_TX_VELOCITY_THRESHOLD}")
    logger.info(f"SNIPER_WALLET_THRESHOLD: {SNIPER_WALLET_THRESHOLD}")
    logger.info(f"SNIPER_BUY_RATIO_THRESHOLD: {SNIPER_BUY_RATIO_THRESHOLD}")

    await sniper_loop()


if __name__ == "__main__":
    asyncio.run(main())