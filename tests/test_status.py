#!/usr/bin/env python3
"""
test_status.py

Batería de comprobaciones de estado para Memecoin Agent v3.0-ultralite-fixed

Ejecutar: python tests/test_status.py
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime

# Configuración
DB_PATH = os.getenv("DATABASE_PATH", "data/memecoin.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_status")


def get_db_connection():
    """Obtener conexión a SQLite con WAL Mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-100000;")
    return conn


def test_database_exists():
    """Test 1: Verificar que la base de datos existe."""
    logger.info("TEST 1: Verificar que la base de datos existe")
    if os.path.exists(DB_PATH):
        logger.info(f"  ✅ PASS: Base de datos encontrada: {DB_PATH}")
        return True
    else:
        logger.error(f"  ❌ FAIL: Base de datos no encontrada: {DB_PATH}")
        return False


def test_wal_mode():
    """Test 2: Verificar que WAL Mode está activado."""
    logger.info("TEST 2: Verificar que WAL Mode está activado")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        if mode == "wal":
            logger.info(f"  ✅ PASS: WAL Mode activado ({mode})")
            return True
        else:
            logger.error(f"  ❌ FAIL: WAL Mode no activado ({mode})")
            return False
    finally:
        conn.close()


def test_tables_exist():
    """Test 3: Verificar que todas las tablas existen."""
    logger.info("TEST 3: Verificar que todas las tablas existen")
    required_tables = [
        "tokens", "launches", "btc_context", "token_features",
        "token_hypotheses", "model_performance", "backfill_log",
        "agent_execution_log", "trades", "risk_events",
        "circuit_breaker_log", "tracked_wallets", "spray_targets",
        "agent_config", "pending_trades"
    ]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        existing_tables = [row[0] for row in cursor.fetchall()]

        missing_tables = [t for t in required_tables if t not in existing_tables]

        if not missing_tables:
            logger.info(f"  ✅ PASS: Todas las {len(required_tables)} tablas existen")
            return True
        else:
            logger.error(f"  ❌ FAIL: Tablas faltantes: {missing_tables}")
            return False
    finally:
        conn.close()


def test_agent_config():
    """Test 4: Verificar configuración de agent_config."""
    logger.info("TEST 4: Verificar configuración de agent_config")
    required_keys = [
        "execution_mode", "max_position_sol", "risk_threshold",
        "circuit_breaker_losses", "spray_enabled", "sniper_enabled",
        "stream_source", "sniper_tx_velocity_threshold",
        "sniper_wallet_threshold", "sniper_buy_ratio_threshold",
        "research_mode", "retention_days"
    ]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT key FROM agent_config;")
        existing_keys = [row[0] for row in cursor.fetchall()]

        missing_keys = [k for k in required_keys if k not in existing_keys]

        if not missing_keys:
            logger.info(f"  ✅ PASS: Todas las {len(required_keys)} claves existen")
            return True
        else:
            logger.error(f"  ❌ FAIL: Claves faltantes: {missing_keys}")
            return False
    finally:
        conn.close()


def test_default_values():
    """Test 5: Verificar valores por defecto."""
    logger.info("TEST 5: Verificar valores por defecto")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar execution_mode
        cursor.execute("SELECT value FROM agent_config WHERE key='execution_mode';")
        row = cursor.fetchone()
        if row and row[0] == "research":
            logger.info("  ✅ execution_mode = research")
        else:
            logger.error(f"  ❌ execution_mode incorrecto: {row}")
            return False

        # Verificar risk_threshold
        cursor.execute("SELECT value FROM agent_config WHERE key='risk_threshold';")
        row = cursor.fetchone()
        if row and row[0] == "0.65":
            logger.info("  ✅ risk_threshold = 0.65")
        else:
            logger.error(f"  ❌ risk_threshold incorrecto: {row}")
            return False

        # Verificar retention_days
        cursor.execute("SELECT value FROM agent_config WHERE key='retention_days';")
        row = cursor.fetchone()
        if row and row[0] == "1":
            logger.info("  ✅ retention_days = 1")
        else:
            logger.error(f"  ❌ retention_days incorrecto: {row}")
            return False

        logger.info("  ✅ PASS: Todos los valores por defecto correctos")
        return True
    finally:
        conn.close()


def test_indexes_exist():
    """Test 6: Verificar que los índices existen."""
    logger.info("TEST 6: Verificar que los índices existen")
    required_indexes = [
        "idx_tokens_created_at", "idx_tokens_source", "idx_tokens_probs",
        "idx_tokens_unlabeled", "idx_tokens_creator",
        "idx_launches_token",
        "idx_tf_version", "idx_tf_core", "idx_tf_token_version",
        "idx_hyp_prob", "idx_hyp_model", "idx_hyp_active",
        "idx_mp_model", "idx_mp_created",
        "idx_ael_task", "idx_ael_status",
        "idx_trades_token", "idx_trades_wallet", "idx_trades_status",
        "idx_trades_timestamp",
        "idx_risk_token", "idx_risk_timestamp", "idx_risk_decision",
        "idx_cb_trigger", "idx_cb_paused",
        "idx_tw_type", "idx_tw_qualifying",
        "idx_st_whale", "idx_st_token", "idx_st_outcome",
        "idx_pt_token", "idx_pt_executed"
    ]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name;")
        existing_indexes = [row[0] for row in cursor.fetchall()]

        missing_indexes = [i for i in required_indexes if i not in existing_indexes]

        if not missing_indexes:
            logger.info(f"  ✅ PASS: Todos los {len(required_indexes)} índices existen")
            return True
        else:
            logger.error(f"  ❌ FAIL: Índices faltantes: {missing_indexes}")
            return False
    finally:
        conn.close()


def test_views_exist():
    """Test 7: Verificar que las vistas existen."""
    logger.info("TEST 7: Verificar que las vistas existen")
    required_views = [
        "tokens_pending_label", "tokens_ready_for_training",
        "model_performance_daily", "trades_daily_summary",
        "tokens_recent_24h", "tokens_high_pump_prob",
        "tokens_low_rug_prob"
    ]

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name;")
        existing_views = [row[0] for row in cursor.fetchall()]

        missing_views = [v for v in required_views if v not in existing_views]

        if not missing_views:
            logger.info(f"  ✅ PASS: Todas las {len(required_views)} vistas existen")
            return True
        else:
            logger.error(f"  ❌ FAIL: Vistas faltantes: {missing_views}")
            return False
    finally:
        conn.close()


def test_schema_version():
    """Test 8: Verificar versión del schema."""
    logger.info("TEST 8: Verificar versión del schema")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tokens';")
        schema = cursor.fetchone()[0]

        # Verificar que el schema contiene las columnas de v3.0
        required_columns = [
            "creator_rug_history_count", "creator_total_tokens_launched",
            "creator_graduation_rate", "bonding_curve_progress_pct",
            "pumpswap_pool_address", "migrated_to_pumpswap",
            "rugcheck_score", "rugcheck_risks"
        ]

        missing_columns = [c for c in required_columns if c not in schema]

        if not missing_columns:
            logger.info("  ✅ PASS: Schema v3.0 completo")
            return True
        else:
            logger.error(f"  ❌ FAIL: Columnas faltantes en schema v3.0: {missing_columns}")
            return False
    finally:
        conn.close()


def test_data_integrity():
    """Test 9: Verificar integridad de datos."""
    logger.info("TEST 9: Verificar integridad de datos")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar que no hay tokens duplicados
        cursor.execute("SELECT COUNT(*) FROM tokens;")
        total_tokens = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT address) FROM tokens;")
        unique_tokens = cursor.fetchone()[0]

        if total_tokens == unique_tokens:
            logger.info(f"  ✅ No hay tokens duplicados ({total_tokens} únicos)")
        else:
            logger.error(f"  ❌ Tokens duplicados encontrados: {total_tokens - unique_tokens}")
            return False

        # Verificar integridad referencial (tokens con features)
        cursor.execute("SELECT COUNT(*) FROM token_features;")
        total_features = cursor.fetchone()[0]

        if total_features > 0:
            cursor.execute("""
                SELECT COUNT(*) FROM token_features tf
                WHERE NOT EXISTS (
                    SELECT 1 FROM tokens t WHERE t.id = tf.token_id
                )
            """)
            orphan_features = cursor.fetchone()[0]

            if orphan_features == 0:
                logger.info(f"  ✅ No hay features huérfanas ({total_features} features)")
            else:
                logger.error(f"  ❌ Features huérfanas: {orphan_features}")
                return False

        logger.info("  ✅ PASS: Integridad de datos verificada")
        return True
    finally:
        conn.close()


def test_performance():
    """Test 10: Verificar rendimiento básico."""
    logger.info("TEST 10: Verificar rendimiento básico")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Medir tiempo de consulta simple
        start = datetime.now()
        cursor.execute("SELECT COUNT(*) FROM tokens;")
        _ = cursor.fetchone()
        elapsed = (datetime.now() - start).total_seconds() * 1000

        if elapsed < 100:  # < 100ms
            logger.info(f"  ✅ Consulta simple rápida: {elapsed:.2f}ms")
        else:
            logger.warning(f"  ⚠️  Consulta simple lenta: {elapsed:.2f}ms")

        # Medir tiempo de consulta con índice
        start = datetime.now()
        cursor.execute("SELECT COUNT(*) FROM tokens WHERE created_at >= datetime('now', '-24 hours');")
        _ = cursor.fetchone()
        elapsed = (datetime.now() - start).total_seconds() * 1000

        if elapsed < 50:  # < 50ms
            logger.info(f"  ✅ Consulta con índice rápida: {elapsed:.2f}ms")
        else:
            logger.warning(f"  ⚠️  Consulta con índice lenta: {elapsed:.2f}ms")

        logger.info("  ✅ PASS: Rendimiento básico verificado")
        return True
    finally:
        conn.close()


def run_all_tests():
    """Ejecutar todas las pruebas."""
    print("=" * 60)
    print("Memecoin Agent v3.0-ultralite-fixed - Test Suite de Estado")
    print("=" * 60)
    print()

    tests = [
        test_database_exists,
        test_wal_mode,
        test_tables_exist,
        test_agent_config,
        test_default_values,
        test_indexes_exist,
        test_views_exist,
        test_schema_version,
        test_data_integrity,
        test_performance,
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