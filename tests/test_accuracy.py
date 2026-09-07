#!/usr/bin/env python3
"""
test_accuracy.py

Batería de pruebas de precisión para Memecoin Agent v3.0-ultralite-fixed

Ejecutar: python tests/test_accuracy.py
"""

import os
import sys
import sqlite3
import logging

# Configuración
DB_PATH = os.getenv("DATABASE_PATH", "data/memecoin.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_accuracy")


def get_db_connection():
    """Obtener conexión a SQLite con WAL Mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-100000;")
    return conn


def test_sniper_score_calculation():
    """Test 1: Precisión del cálculo de Sniper Score."""
    logger.info("TEST 1: Precisión del cálculo de Sniper Score")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Insertar datos de prueba
        cursor.execute("""
            INSERT OR IGNORE INTO tokens (id, address, created_at)
            VALUES (1, 'test_token_1', datetime('now', '-10 minutes'))
        """)

        cursor.execute("""
            INSERT OR IGNORE INTO token_features (
                token_id, feature_version, tx_velocity_0_5m,
                unique_wallets_0_10m, buy_tx_ratio_0_30m
            ) VALUES (1, 'v1-onchain-v73', 5.0, 15, 0.85)
        """)

        conn.commit()

        # Verificar que los datos se insertaron correctamente
        cursor.execute("""
            SELECT tx_velocity_0_5m, unique_wallets_0_10m, buy_tx_ratio_0_30m
            FROM token_features WHERE token_id = 1
        """)
        row = cursor.fetchone()

        if row and row[0] == 5.0 and row[1] == 15 and row[2] == 0.85:
            logger.info("  ✅ PASS: Sniper Score calculation data correct")
            return True
        else:
            logger.error(f"  ❌ FAIL: Data incorrect: {row}")
            return False
    finally:
        conn.close()


def test_risk_filter_threshold():
    """Test 2: Precisión del Risk Filter threshold."""
    logger.info("TEST 2: Precisión del Risk Filter threshold")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar risk_threshold
        cursor.execute("SELECT value FROM agent_config WHERE key='risk_threshold';")
        row = cursor.fetchone()

        if row and row[0] == "0.65":
            logger.info("  ✅ PASS: Risk threshold = 0.65")
            return True
        else:
            logger.error(f"  ❌ FAIL: Risk threshold incorrect: {row}")
            return False
    finally:
        conn.close()


def test_token_features_schema():
    """Test 3: Precisión del schema de token_features."""
    logger.info("TEST 3: Precisión del schema de token_features")

    required_columns = [
        "tx_velocity_0_5m", "tx_velocity_5_60m", "tx_velocity_60_240m",
        "tx_velocity_0_10s", "tx_velocity_10_30s", "tx_velocity_30_60s",
        "unique_wallets_0_10m", "unique_wallets_0_60m",
        "buy_tx_ratio_0_30m", "liquidity_add_0_10m", "liquidity_remove_0_2h",
        "liquidity_drop_1_2h_pct", "top_10_wallets_pct_0_1h",
        "gini_concentration_0_1h", "btc_change_pct_6h", "btc_dominance_pct",
        "launch_hour_utc", "launch_day_of_week",
        "creator_rug_history_count", "creator_graduation_rate",
        "bonding_curve_progress_pct", "rugcheck_score",
        "creator_bundled_buy", "avg_trade_size_0_30m", "slippage_0_30m"
    ]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(token_features);")
        columns = [row[1] for row in cursor.fetchall()]

        missing_columns = [c for c in required_columns if c not in columns]

        if not missing_columns:
            logger.info(f"  ✅ PASS: {len(required_columns)} columnas en token_features")
            return True
        else:
            logger.error(f"  ❌ FAIL: Columnas faltantes: {missing_columns}")
            return False
    finally:
        conn.close()


def test_launches_schema():
    """Test 4: Precisión del schema de launches."""
    logger.info("TEST 4: Precisión del schema de launches")

    required_columns = [
        "time", "token_id", "price_usd", "volume_5m", "volume_15m",
        "volume_60m", "volume_240m", "volume_30s", "volume_60s",
        "txs_0_5m", "txs_5_60m", "txs_60_240m", "txs_0_30s", "txs_30_60s",
        "unique_wallets_0_10m", "unique_wallets_0_60m",
        "buy_tx_0_30m", "sell_tx_0_30m",
        "liquidity_pool_before", "liquidity_pool_after",
        "is_liquidity_removed", "top_10_wallets_pct_0_1h",
        "gini_concentration_0_1h", "bonding_curve_progress_pct"
    ]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(launches);")
        columns = [row[1] for row in cursor.fetchall()]

        missing_columns = [c for c in required_columns if c not in columns]

        if not missing_columns:
            logger.info(f"  ✅ PASS: {len(required_columns)} columnas en launches")
            return True
        else:
            logger.error(f"  ❌ FAIL: Columnas faltantes: {missing_columns}")
            return False
    finally:
        conn.close()


def test_agent_config_values():
    """Test 5: Precisión de valores en agent_config."""
    logger.info("TEST 5: Precisión de valores en agent_config")

    expected_values = {
        "execution_mode": "research",
        "max_position_sol": "1.0",
        "risk_threshold": "0.65",
        "circuit_breaker_losses": "3",
        "spray_enabled": "false",
        "sniper_enabled": "false",
        "stream_source": "polling",
        "sniper_tx_velocity_threshold": "3.0",
        "sniper_wallet_threshold": "10",
        "sniper_buy_ratio_threshold": "0.70",
        "research_mode": "heuristic_only",
        "retention_days": "1"
    }

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM agent_config;")
        actual_values = {row[0]: row[1] for row in cursor.fetchall()}

        mismatches = []
        for key, expected in expected_values.items():
            if key not in actual_values:
                mismatches.append(f"{key}: missing")
            elif actual_values[key] != expected:
                mismatches.append(f"{key}: expected '{expected}', got '{actual_values[key]}'")

        if not mismatches:
            logger.info("  ✅ PASS: Todos los valores en agent_config correctos")
            return True
        else:
            logger.error(f"  ❌ FAIL: Mismatches: {mismatches}")
            return False
    finally:
        conn.close()


def test_pending_trades_schema():
    """Test 6: Precisión del schema de pending_trades."""
    logger.info("TEST 6: Precisión del schema de pending_trades")

    required_columns = [
        "token_id", "mint_address", "signal_type", "sniper_score",
        "risk_score", "whale_address", "whale_delay_ms", "confidence",
        "created_at", "executed_at", "executed", "execution_error"
    ]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(pending_trades);")
        columns = [row[1] for row in cursor.fetchall()]

        missing_columns = [c for c in required_columns if c not in columns]

        if not missing_columns:
            logger.info(f"  ✅ PASS: {len(required_columns)} columnas en pending_trades")
            return True
        else:
            logger.error(f"  ❌ FAIL: Columnas faltantes: {missing_columns}")
            return False
    finally:
        conn.close()


def test_trades_schema():
    """Test 7: Precisión del schema de trades."""
    logger.info("TEST 7: Precisión del schema de trades")

    required_columns = [
        "token_id", "mint_address", "wallet_address", "action",
        "amount_sol", "amount_usd", "price_per_token", "jito_bundle_id",
        "tx_hash", "block_slot", "timestamp", "pnl_sol", "pnl_pct",
        "status", "stop_loss_triggered", "take_profit_triggered"
    ]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(trades);")
        columns = [row[1] for row in cursor.fetchall()]

        missing_columns = [c for c in required_columns if c not in columns]

        if not missing_columns:
            logger.info(f"  ✅ PASS: {len(required_columns)} columnas en trades")
            return True
        else:
            logger.error(f"  ❌ FAIL: Columnas faltantes: {missing_columns}")
            return False
    finally:
        conn.close()


def run_all_tests():
    """Ejecutar todas las pruebas."""
    print("=" * 60)
    print("Memecoin Agent v3.0-ultralite-fixed - Test Suite de Precisión")
    print("=" * 60)
    print()

    tests = [
        test_sniper_score_calculation,
        test_risk_filter_threshold,
        test_token_features_schema,
        test_launches_schema,
        test_agent_config_values,
        test_pending_trades_schema,
        test_trades_schema,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            logger.error(f"  ❌ ERROR: {e}")
            results.append(False)
        print()

    passed = sum(results)
    total = len(results)

    print("=" * 60)
    print(f"Resultados: {passed}/{total} tests pasados")
    if passed == total:
        print("✅ TODOS LOS TESTS PASADOS")
        return 0
    else:
        print("❌ ALGUNOS TESTS FALLARON")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())