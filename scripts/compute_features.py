#!/usr/bin/env python3
"""
compute_features.py

Calcula token_features desde launches + btc_context.
Frecuencia: cada hora via Hermes/cron.

Feature version actual: v1-onchain-v73

PostgreSQL - Conexión centralizada
"""

import os
import logging

from db import get_conn

FEATURE_VERSION = os.getenv("FEATURE_VERSION", "v1-onchain-v73")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("compute_features")


def safe_div(a, b):
    """División segura."""
    if not b or b == 0:
        return 0.0
    return float(a or 0) / float(b)


def get_launches(cursor, token_id):
    """Obtener datos de launches para un token."""
    cursor.execute("""
        SELECT
            MAX(txs_0_30s) AS txs_0_30s,
            MAX(txs_30_60s) AS txs_30_60s,
            MAX(txs_0_5m) AS txs_0_5m,
            MAX(txs_5_60m) AS txs_5_60m,
            MAX(txs_60_240m) AS txs_60_240m,
            MAX(unique_wallets_0_10m) AS unique_wallets_0_10m,
            MAX(unique_wallets_0_60m) AS unique_wallets_0_60m,
            MAX(buy_tx_0_30m) AS buy_tx_0_30m,
            MAX(sell_tx_0_30m) AS sell_tx_0_30m,
            MAX(liquidity_pool_before) AS liquidity_pool_before,
            MAX(liquidity_pool_after) AS liquidity_pool_after,
            MAX(top_10_wallets_pct_0_1h) AS top_10_wallets_pct_0_1h,
            MAX(gini_concentration_0_1h) AS gini_concentration_0_1h,
            MAX(liquidity_add_0_10m) AS liquidity_add_0_10m,
            MAX(liquidity_remove_0_2h) AS liquidity_remove_0_2h,
            MAX(liquidity_drop_1_2h_pct) AS liquidity_drop_1_2h_pct,
            MAX(bonding_curve_progress_pct) AS bonding_curve_progress_pct,
            MAX(volume_30s) AS volume_30s,
            MAX(volume_60s) AS volume_60s,
            MAX(volume_5m) AS volume_5m
        FROM launches
        WHERE token_id = %s
    """, (token_id,))

    row = cursor.fetchone()
    cols = [
        "txs_0_30s", "txs_30_60s", "txs_0_5m", "txs_5_60m", "txs_60_240m",
        "unique_wallets_0_10m", "unique_wallets_0_60m",
        "buy_tx_0_30m", "sell_tx_0_30m",
        "liquidity_pool_before", "liquidity_pool_after",
        "top_10_wallets_pct_0_1h", "gini_concentration_0_1h",
        "liquidity_add_0_10m", "liquidity_remove_0_2h", "liquidity_drop_1_2h_pct",
        "bonding_curve_progress_pct", "volume_30s", "volume_60s", "volume_5m"
    ]

    return dict(zip(cols, row)) if row else {}


def get_btc_context(cursor, created_at):
    """Obtener contexto de BTC."""
    cursor.execute("""
        SELECT change_pct_6h, dominance_pct
        FROM btc_context
        WHERE time <= %s
        ORDER BY time DESC
        LIMIT 1
    """, (created_at,))

    row = cursor.fetchone()
    if not row:
        return {}
    return {"change_pct_6h": row[0], "dominance_pct": row[1]}


def compute_all_features(cursor, token_id, created_at):
    """Calcular todas las features para un token."""
    launches = get_launches(cursor, token_id)
    if not launches:
        return None

    btc = get_btc_context(cursor, created_at)

    # 1. Velocidad de transacciones
    tx_velocity_0_5m = safe_div(launches.get("txs_0_5m", 0), 5.0)
    tx_velocity_5_60m = safe_div(launches.get("txs_5_60m", 0), 55.0)
    tx_velocity_60_240m = safe_div(launches.get("txs_60_240m", 0), 180.0)

    # 2. Wallets únicas
    unique_wallets_0_10m = launches.get("unique_wallets_0_10m", 0) or 0
    unique_wallets_0_60m = launches.get("unique_wallets_0_60m", 0) or 0

    # 3. Ratio compra/venta (ventana 0-30 min)
    buy = launches.get("buy_tx_0_30m", 0) or 0
    sell = launches.get("sell_tx_0_30m", 0) or 0
    buy_tx_ratio_0_30m = safe_div(buy, buy + sell)

    # 4. Liquidez
    liq_before = launches.get("liquidity_pool_before", 0) or 0
    liq_after = launches.get("liquidity_pool_after", 0) or 0
    liq_drop = launches.get("liquidity_drop_1_2h_pct", 0) or 0

    liquidity_add_0_10m = bool(launches.get("liquidity_add_0_10m"))
    liquidity_remove_0_2h = bool(launches.get("liquidity_remove_0_2h"))
    liquidity_drop_1_2h_pct = liq_drop

    # 5. Concentración
    top_10_wallets_pct_0_1h = launches.get("top_10_wallets_pct_0_1h", 0) or 0
    gini_concentration_0_1h = launches.get("gini_concentration_0_1h", 0) or 0

    # 6. Contexto BTC
    btc_change_pct_6h = btc.get("change_pct_6h")
    btc_dominance_pct = btc.get("dominance_pct")

    # 7. Timing
    import datetime
    if isinstance(created_at, str):
        created_at = datetime.datetime.fromisoformat(created_at)
    launch_hour_utc = created_at.hour
    launch_day_of_week = created_at.weekday()

    # 8. Bonding curve
    bonding_curve_progress_pct = launches.get("bonding_curve_progress_pct", 0) or 0

    return {
        "feature_version": FEATURE_VERSION,
        "max_feature_window_minutes": 30,
        "tx_velocity_0_5m": tx_velocity_0_5m,
        "tx_velocity_5_60m": tx_velocity_5_60m,
        "tx_velocity_60_240m": tx_velocity_60_240m,
        "unique_wallets_0_10m": unique_wallets_0_10m,
        "unique_wallets_0_60m": unique_wallets_0_60m,
        "buy_tx_ratio_0_30m": buy_tx_ratio_0_30m,
        "liquidity_add_0_10m": 1 if liquidity_add_0_10m else 0,
        "liquidity_remove_0_2h": 1 if liquidity_remove_0_2h else 0,
        "liquidity_drop_1_2h_pct": liquidity_drop_1_2h_pct,
        "top_10_wallets_pct_0_1h": top_10_wallets_pct_0_1h,
        "gini_concentration_0_1h": gini_concentration_0_1h,
        "btc_change_pct_6h": btc_change_pct_6h,
        "btc_dominance_pct": btc_dominance_pct,
        "launch_hour_utc": launch_hour_utc,
        "launch_day_of_week": launch_day_of_week,
        "bonding_curve_progress_pct": bonding_curve_progress_pct,
    }


def insert_features(cursor, token_id, features):
    """Insertar features en la DB."""
    cursor.execute("""
        INSERT INTO token_features (
            token_id, feature_version, max_feature_window_minutes,
            tx_velocity_0_5m, tx_velocity_5_60m, tx_velocity_60_240m,
            unique_wallets_0_10m, unique_wallets_0_60m,
            buy_tx_ratio_0_30m,
            liquidity_add_0_10m, liquidity_remove_0_2h, liquidity_drop_1_2h_pct,
            top_10_wallets_pct_0_1h, gini_concentration_0_1h,
            btc_change_pct_6h, btc_dominance_pct,
            launch_hour_utc, launch_day_of_week,
            bonding_curve_progress_pct
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (token_id, feature_version) DO UPDATE SET
            updated_at = NOW()
    """, (
        token_id,
        features["feature_version"],
        features["max_feature_window_minutes"],
        features["tx_velocity_0_5m"],
        features["tx_velocity_5_60m"],
        features["tx_velocity_60_240m"],
        features["unique_wallets_0_10m"],
        features["unique_wallets_0_60m"],
        features["buy_tx_ratio_0_30m"],
        features["liquidity_add_0_10m"],
        features["liquidity_remove_0_2h"],
        features["liquidity_drop_1_2h_pct"],
        features["top_10_wallets_pct_0_1h"],
        features["gini_concentration_0_1h"],
        features["btc_change_pct_6h"],
        features["btc_dominance_pct"],
        features["launch_hour_utc"],
        features["launch_day_of_week"],
        features["bonding_curve_progress_pct"],
    ))


def main():
    """Función principal."""
    logger.info("=== Compute Features (v3.0-ultralite-fixed) ===")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Buscar tokens etiquetados sin features todavía
        cursor.execute("""
            SELECT t.id, t.created_at
            FROM tokens t
            LEFT JOIN token_features tf
                ON tf.token_id = t.id AND tf.feature_version = %s
            WHERE t.label_completed = 1
              AND tf.id IS NULL
        """, (FEATURE_VERSION,))

        tokens = cursor.fetchall()
        computed = 0

        for token_id, created_at in tokens:
            features = compute_all_features(cursor, token_id, created_at)
            if features:
                insert_features(cursor, token_id, features)
                computed += 1

        conn.commit()
        logger.info(f"compute_features: {computed} tokens con features calculadas")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()