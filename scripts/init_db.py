#!/usr/bin/env python3
"""
Inicializar base de datos PostgreSQL para Memecoin Agent v3.0-ultralite-fixed.

Este script crea la base de datos PostgreSQL con el schema v3.0.

Uso:
    python scripts/init_db.py
"""

import os
import sys
import logging

from db import get_conn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("init_db")


def init_db():
    """Inicializar base de datos PostgreSQL."""
    logger.info("Inicializando base de datos PostgreSQL")

    conn = get_conn()
    cursor = conn.cursor()

    try:
        # Crear tablas si no existen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                id SERIAL PRIMARY KEY,
                mint VARCHAR(44) UNIQUE NOT NULL,
                symbol VARCHAR(32),
                name VARCHAR(128),
                creator_address VARCHAR(44),
                created_at TIMESTAMPTZ NOT NULL,
                source VARCHAR(16) NOT NULL,
                initial_sol_liquidity NUMERIC(18,6),
                bonding_curve_address VARCHAR(44),
                metadata_uri TEXT,
                pump_100pc_24h BOOLEAN,
                rug_pull_48h BOOLEAN,
                still_active_7d BOOLEAN,
                creator_rug_history_count INTEGER DEFAULT 0,
                creator_total_tokens_launched INTEGER DEFAULT 0,
                creator_graduation_rate REAL,
                predicted_at TIMESTAMPTZ,
                model_A_version VARCHAR(64),
                model_B_version VARCHAR(64),
                model_C_version VARCHAR(64),
                label_completed INTEGER DEFAULT 0,
                prob_pump_24h REAL,
                prob_rug_48h REAL,
                prob_survival_7d REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_features (
                token_id INTEGER NOT NULL,
                feature_version VARCHAR(32) NOT NULL,
                max_feature_window_minutes INTEGER,
                tx_velocity_0_5m REAL,
                tx_velocity_5_60m REAL,
                tx_velocity_60_240m REAL,
                unique_wallets_0_10m INTEGER,
                unique_wallets_0_60m INTEGER,
                buy_tx_ratio_0_30m REAL,
                liquidity_add_0_10m INTEGER,
                liquidity_remove_0_2h INTEGER,
                liquidity_drop_1_2h_pct REAL,
                top_10_wallets_pct_0_1h REAL,
                gini_concentration_0_1h REAL,
                btc_change_pct_6h REAL,
                btc_dominance_pct REAL,
                launch_hour_utc INTEGER,
                launch_day_of_week INTEGER,
                bonding_curve_progress_pct REAL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (token_id, feature_version)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whales (
                wallet VARCHAR(64) PRIMARY KEY,
                label VARCHAR(64),
                win_rate NUMERIC(5,4),
                total_trades INTEGER DEFAULT 0,
                rug_count INTEGER DEFAULT 0,
                added_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_config (
                key VARCHAR(64) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_trades (
                id SERIAL PRIMARY KEY,
                token_id INTEGER,
                mint_address VARCHAR(44),
                signal_type VARCHAR(32),
                sniper_score REAL,
                whale_address VARCHAR(64),
                whale_delay_ms INTEGER,
                confidence REAL,
                executed INTEGER DEFAULT 0,
                executed_at TIMESTAMPTZ,
                execution_error TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                token_id INTEGER,
                mint_address VARCHAR(44),
                wallet_address VARCHAR(64),
                action VARCHAR(16),
                amount_sol NUMERIC(18,6),
                jito_bundle_id VARCHAR(88),
                timestamp TIMESTAMPTZ,
                status VARCHAR(16),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_performance (
                id SERIAL PRIMARY KEY,
                model_name VARCHAR(64),
                feature_version VARCHAR(32),
                model_version VARCHAR(128),
                train_start TIMESTAMPTZ,
                train_end TIMESTAMPTZ,
                test_start TIMESTAMPTZ,
                test_end TIMESTAMPTZ,
                n_tokens_train INTEGER,
                n_tokens_test INTEGER,
                pct_positive REAL,
                precision_at_10 REAL,
                precision_at_20 REAL,
                recall_at_10 REAL,
                auc_roc REAL,
                f1_score REAL,
                log_loss REAL,
                model_file_path TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS token_hypotheses (
                id SERIAL PRIMARY KEY,
                hypothesis_text TEXT,
                conditions_json TEXT,
                target_model VARCHAR(32),
                feature_version VARCHAR(32),
                estimated_probability REAL,
                confidence_interval REAL,
                prior_probability REAL,
                posterior_probability REAL,
                bayes_factor REAL,
                total_tested INTEGER DEFAULT 0,
                validated_count INTEGER DEFAULT 0,
                refuted_count INTEGER DEFAULT 0,
                generated_by VARCHAR(64),
                generated_on_data VARCHAR(64),
                active INTEGER DEFAULT 1,
                last_updated TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS btc_context (
                id SERIAL PRIMARY KEY,
                time TIMESTAMPTZ,
                change_pct_6h REAL,
                dominance_pct REAL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_events (
                id SERIAL PRIMARY KEY,
                token_id INTEGER,
                mint_address VARCHAR(44),
                risk_score REAL,
                risk_threshold REAL,
                decision VARCHAR(16),
                creator_address VARCHAR(64),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS circuit_breaker_log (
                id SERIAL PRIMARY KEY,
                triggered_at TIMESTAMPTZ DEFAULT NOW(),
                reason TEXT,
                resolved_at TIMESTAMPTZ,
                resumed_at TIMESTAMPTZ
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS launches (
                id SERIAL PRIMARY KEY,
                token_id INTEGER,
                time TIMESTAMPTZ,
                txs_0_30s INTEGER,
                txs_30_60s INTEGER,
                txs_0_5m INTEGER,
                txs_5_60m INTEGER,
                txs_60_240m INTEGER,
                unique_wallets_0_10m INTEGER,
                unique_wallets_0_60m INTEGER,
                buy_tx_0_30m INTEGER,
                sell_tx_0_30m INTEGER,
                liquidity_pool_before NUMERIC(18,6),
                liquidity_pool_after NUMERIC(18,6),
                top_10_wallets_pct_0_1h REAL,
                gini_concentration_0_1h REAL,
                liquidity_add_0_10m BOOLEAN,
                liquidity_remove_0_2h BOOLEAN,
                liquidity_drop_1_2h_pct REAL,
                bonding_curve_progress_pct REAL,
                volume_30s NUMERIC(18,6),
                volume_60s NUMERIC(18,6),
                volume_5m NUMERIC(18,6),
                price_usd REAL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        conn.commit()
        logger.info("Tablas creadas exitosamente")

        # Verificar tablas
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;")
        tables = cursor.fetchall()
        logger.info(f"Tablas en la base de datos: {len(tables)}")
        for table in tables:
            logger.info(f"  - {table[0]}")

        logger.info("Base de datos PostgreSQL inicializada exitosamente")
        return True

    except Exception as e:
        logger.error(f"Error inicializando base de datos: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


def main():
    """Función principal."""
    logger.info("=== Memecoin Agent v3.0-ultralite-fixed - Init DB ===")

    success = init_db()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()