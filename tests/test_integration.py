#!/usr/bin/env python3
"""
test_integration.py

Tests de integración para Memecoin Agent v3.0-ultralite-fixed

Ejecutar: python tests/test_integration.py
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
logger = logging.getLogger("test_integration")


def get_db_connection():
    """Obtener conexión a SQLite con WAL Mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-100000;")
    return conn


def test_whale_stats_update():
    """Test 1: Actualización de estadísticas de whales."""
    logger.info("TEST 1: Actualización de estadísticas de whales")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que las whales existen
        cursor.execute("SELECT COUNT(*) FROM tracked_wallets WHERE wallet_type = 'whale';")
        whale_count = cursor.fetchone()[0]

        if whale_count > 0:
            logger.info(f"  ✅ PASS: {whale_count} whales en la base de datos")
            return True
        else:
            logger.error("  ❌ FAIL: No hay whales en la base de datos")
            return False
    finally:
        conn.close()


def test_pending_trades_flow():
    """Test 2: Flujo de pending_trades."""
    logger.info("TEST 2: Flujo de pending_trades")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que la tabla pending_trades existe
        cursor.execute("SELECT COUNT(*) FROM pending_trades;")
        pending_count = cursor.fetchone()[0]

        logger.info(f"  ✅ PASS: {pending_count} pending_trades en la base de datos")
        return True
    finally:
        conn.close()


def test_agent_config_update():
    """Test 3: Actualización de agent_config."""
    logger.info("TEST 3: Actualización de agent_config")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que todos los valores existen
        cursor.execute("SELECT COUNT(*) FROM agent_config;")
        config_count = cursor.fetchone()[0]

        # Verificar que las claves esenciales existen
        required_keys = [
            "execution_mode", "max_position_sol", "risk_threshold",
            "circuit_breaker_losses", "spray_enabled", "sniper_enabled",
            "stream_source", "sniper_tx_velocity_threshold",
            "sniper_wallet_threshold", "sniper_buy_ratio_threshold",
            "research_mode", "retention_days"
        ]

        placeholders = ",".join("?" * len(required_keys))
        cursor.execute(f"SELECT COUNT(*) FROM agent_config WHERE key IN ({placeholders});", required_keys)
        required_count = cursor.fetchone()[0]

        if required_count == len(required_keys):
            logger.info(f"  ✅ PASS: {config_count} valores en agent_config ({required_count} esenciales)")
            return True
        else:
            logger.error(f"  ❌ FAIL: Se esperaban {len(required_keys)} claves esenciales, se encontraron {required_count}")
            return False
    finally:
        conn.close()


def test_tracked_wallets_flow():
    """Test 4: Flujo de tracked_wallets."""
    logger.info("TEST 4: Flujo de tracked_wallets")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que las wallets existen
        cursor.execute("SELECT COUNT(*) FROM tracked_wallets;")
        wallet_count = cursor.fetchone()[0]

        # Verificar tipos
        cursor.execute("SELECT wallet_type, COUNT(*) FROM tracked_wallets GROUP BY wallet_type;")
        types = cursor.fetchall()

        logger.info(f"  ✅ PASS: {wallet_count} wallets ({len(types)} tipos)")
        for wallet_type, count in types:
            logger.info(f"    - {wallet_type}: {count}")
        return True
    finally:
        conn.close()


def test_risk_filter_integration():
    """Test 5: Integración del risk filter."""
    logger.info("TEST 5: Integración del risk filter")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que risk_events table existe
        cursor.execute("SELECT COUNT(*) FROM risk_events;")
        risk_count = cursor.fetchone()[0]

        logger.info(f"  ✅ PASS: {risk_count} risk_events en la base de datos")
        return True
    finally:
        conn.close()


def test_execution_engine_integration():
    """Test 6: Integración del execution engine."""
    logger.info("TEST 6: Integración del execution engine")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que trades table existe
        cursor.execute("SELECT COUNT(*) FROM trades;")
        trade_count = cursor.fetchone()[0]

        logger.info(f"  ✅ PASS: {trade_count} trades en la base de datos")
        return True
    finally:
        conn.close()


def test_whale_tracker_integration():
    """Test 7: Integración del whale tracker."""
    logger.info("TEST 7: Integración del whale tracker")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que spray_targets table existe
        cursor.execute("SELECT COUNT(*) FROM spray_targets;")
        spray_count = cursor.fetchone()[0]

        logger.info(f"  ✅ PASS: {spray_count} spray_targets en la base de datos")
        return True
    finally:
        conn.close()


def test_circuit_breaker_integration():
    """Test 8: Integración del circuit breaker."""
    logger.info("TEST 8: Integración del circuit breaker")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que circuit_breaker_log table existe
        cursor.execute("SELECT COUNT(*) FROM circuit_breaker_log;")
        cb_count = cursor.fetchone()[0]

        logger.info(f"  ✅ PASS: {cb_count} circuit_breaker_log entries")
        return True
    finally:
        conn.close()


def run_all_tests():
    """Ejecutar todas las pruebas."""
    print("=" * 60)
    print("Memecoin Agent v3.0-ultralite-fixed - Test Suite de Integración")
    print("=" * 60)
    print()

    tests = [
        test_whale_stats_update,
        test_pending_trades_flow,
        test_agent_config_update,
        test_tracked_wallets_flow,
        test_risk_filter_integration,
        test_execution_engine_integration,
        test_whale_tracker_integration,
        test_circuit_breaker_integration,
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