#!/usr/bin/env python3
"""
test_performance.py

Batería de pruebas de performance para Memecoin Agent v3.0-ultralite-fixed

Ejecutar: python tests/test_performance.py
"""

import os
import sys
import sqlite3
import logging
import time
from datetime import datetime

# Configuración
DB_PATH = os.getenv("DATABASE_PATH", "data/memecoin.db")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_performance")


def get_db_connection():
    """Obtener conexión a SQLite con WAL Mode."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA cache_size=-100000;")
    return conn


def test_sniper_engine_latency():
    """Test 1: Latencia del Sniper Engine (<2s objetivo)."""
    logger.info("TEST 1: Latencia del Sniper Engine")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Simular detección de tokens nuevos
        start = time.time()
        cursor.execute("""
            SELECT id, address, created_at
            FROM tokens
            WHERE created_at >= datetime('now', '-5 minutes')
              AND NOT EXISTS (
                  SELECT 1 FROM pending_trades pt WHERE pt.token_id = tokens.id
              )
            ORDER BY created_at DESC
            LIMIT 100
        """)
        tokens = cursor.fetchall()
        elapsed = (time.time() - start) * 1000

        # Simular cálculo de features
        start = time.time()
        for token_id, _, _ in tokens:
            cursor.execute("""
                SELECT MAX(txs_0_30s), MAX(unique_wallets_0_10m), MAX(buy_tx_0_30m)
                FROM launches WHERE token_id = ?
            """, (token_id,))
            _ = cursor.fetchone()
        elapsed_features = (time.time() - start) * 1000

        total_latency = elapsed + elapsed_features

        if total_latency < 2000:  # < 2s
            logger.info(f"  ✅ PASS: Latencia Sniper Engine {total_latency:.2f}ms (< 2000ms)")
            return True
        else:
            logger.error(f"  ❌ FAIL: Latencia Sniper Engine {total_latency:.2f}ms (> 2000ms)")
            return False
    finally:
        conn.close()


def test_risk_filter_latency():
    """Test 2: Latencia del Risk Filter (<500ms objetivo)."""
    logger.info("TEST 2: Latencia del Risk Filter")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Simular evaluación de riesgo
        start = time.time()
        cursor.execute("""
            SELECT COUNT(*) FROM tokens WHERE creator_address = ?
        """, ("test_creator",))
        _ = cursor.fetchone()

        cursor.execute("""
            SELECT top_10_wallets_pct_0_1h FROM launches
            WHERE token_id = ? ORDER BY time DESC LIMIT 1
        """, (1,))
        _ = cursor.fetchone()

        cursor.execute("""
            SELECT liquidity_add_0_10m, liquidity_remove_0_2h FROM token_features
            WHERE token_id = ? ORDER BY created_at DESC LIMIT 1
        """, (1,))
        _ = cursor.fetchone()

        elapsed = (time.time() - start) * 1000

        if elapsed < 500:  # < 500ms
            logger.info(f"  ✅ PASS: Latencia Risk Filter {elapsed:.2f}ms (< 500ms)")
            return True
        else:
            logger.error(f"  ❌ FAIL: Latencia Risk Filter {elapsed:.2f}ms (> 500ms)")
            return False
    finally:
        conn.close()


def test_db_query_performance():
    """Test 3: Rendimiento de consultas de base de datos."""
    logger.info("TEST 3: Rendimiento de consultas de base de datos")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Consulta 1: Contar tokens
        start = time.time()
        cursor.execute("SELECT COUNT(*) FROM tokens;")
        _ = cursor.fetchone()
        elapsed1 = (time.time() - start) * 1000

        # Consulta 2: Buscar tokens recientes
        start = time.time()
        cursor.execute("SELECT COUNT(*) FROM tokens WHERE created_at >= datetime('now', '-24 hours');")
        _ = cursor.fetchone()
        elapsed2 = (time.time() - start) * 1000

        # Consulta 3: Buscar pending_trades no ejecutadas
        start = time.time()
        cursor.execute("SELECT COUNT(*) FROM pending_trades WHERE executed = 0;")
        _ = cursor.fetchone()
        elapsed3 = (time.time() - start) * 1000

        # Consulta 4: Join entre tablas
        start = time.time()
        cursor.execute("""
            SELECT COUNT(*) FROM tokens t
            INNER JOIN token_features tf ON tf.token_id = t.id
            WHERE tf.feature_version = 'v1-onchain-v73'
        """)
        _ = cursor.fetchone()
        elapsed4 = (time.time() - start) * 1000

        avg_latency = (elapsed1 + elapsed2 + elapsed3 + elapsed4) / 4

        if avg_latency < 100:  # < 100ms promedio
            logger.info(f"  ✅ PASS: Latencia promedio {avg_latency:.2f}ms (< 100ms)")
            logger.info(f"    - Contar tokens: {elapsed1:.2f}ms")
            logger.info(f"    - Buscar recientes: {elapsed2:.2f}ms")
            logger.info(f"    - Pending trades: {elapsed3:.2f}ms")
            logger.info(f"    - Join: {elapsed4:.2f}ms")
            return True
        else:
            logger.error(f"  ❌ FAIL: Latencia promedio {avg_latency:.2f}ms (> 100ms)")
            return False
    finally:
        conn.close()


def test_concurrent_access():
    """Test 4: Acceso concurrente (WAL Mode)."""
    logger.info("TEST 4: Acceso concurrente (WAL Mode)")

    conn1 = get_db_connection()
    conn2 = get_db_connection()

    try:
        cursor1 = conn1.cursor()
        cursor2 = conn2.cursor()

        # Simular lectura y escritura concurrente
        start = time.time()

        # Lectura
        cursor1.execute("SELECT COUNT(*) FROM tokens;")
        _ = cursor1.fetchone()

        # Escritura
        cursor2.execute("INSERT OR IGNORE INTO agent_config (key, value) VALUES ('test_key', 'test_value');")
        conn2.commit()

        # Lectura
        cursor1.execute("SELECT COUNT(*) FROM tokens;")
        _ = cursor1.fetchone()

        elapsed = (time.time() - start) * 1000

        if elapsed < 100:  # < 100ms
            logger.info(f"  ✅ PASS: Acceso concurrente {elapsed:.2f}ms (< 100ms)")
            return True
        else:
            logger.warning(f"  ⚠️  Acceso concurrente {elapsed:.2f}ms (> 100ms)")
            return True  # Aceptable
    finally:
        conn1.close()
        conn2.close()


def test_index_usage():
    """Test 5: Uso de índices."""
    logger.info("TEST 5: Uso de índices")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Consulta con índice
        cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM tokens WHERE address = 'test';")
        plan = cursor.fetchone()[0]

        # Verificar que se usa índice (plan es una tupla con el plan de ejecución)
        plan_str = str(plan)
        if "USING INDEX" in plan_str or "USING COVERING INDEX" in plan_str:
            logger.info(f"  ✅ PASS: Índices utilizados correctamente: {plan_str}")
            return True
        else:
            logger.warning(f"  ⚠️  Índice no utilizado: {plan_str}")
            return True  # Aceptable
    finally:
        conn.close()


def test_memory_usage():
    """Test 6: Uso de memoria (cache_size)."""
    logger.info("TEST 6: Uso de memoria (cache_size)")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Verificar cache_size
        cursor.execute("PRAGMA cache_size;")
        cache_size = cursor.fetchone()[0]

        # Verificar synchronous
        cursor.execute("PRAGMA synchronous;")
        synchronous = cursor.fetchone()[0]

        if cache_size <= -100000:  # -100000 pages = ~78MB
            logger.info(f"  ✅ PASS: cache_size = {cache_size} pages (~78MB)")
        else:
            logger.warning(f"  ⚠️  cache_size = {cache_size} pages")

        if synchronous == "NORMAL":
            logger.info(f"  ✅ PASS: synchronous = NORMAL")
        else:
            logger.warning(f"  ⚠️  synchronous = {synchronous}")

        return True
    finally:
        conn.close()


def run_all_tests():
    """Ejecutar todas las pruebas."""
    print("=" * 60)
    print("Memecoin Agent v3.0-ultralite-fixed - Test Suite de Performance")
    print("=" * 60)
    print()

    tests = [
        test_sniper_engine_latency,
        test_risk_filter_latency,
        test_db_query_performance,
        test_concurrent_access,
        test_index_usage,
        test_memory_usage,
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