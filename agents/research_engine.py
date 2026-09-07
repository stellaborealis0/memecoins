#!/usr/bin/env python3
"""
research_engine.py

Capa C - Research Engine (v3.0-ultralite-fixed)
Wrapper del sistema v2.3 completo con APScheduler

Ejecuta:
- train_models_all.py (entrenamiento diario)
- generate_hypotheses_llm.py (generación semanal)
- validate_hypotheses.py (validación cada 6h)
- backtest_report.py (reporte diario)

Exporta umbrales actualizados a agent_config semanalmente

PostgreSQL - Conexión centralizada
"""

import os
import logging
import subprocess
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# Configuración
LITELLM_ENDPOINT = os.getenv("LITELLM_ENDPOINT", "http://100.68.1.180:8080/v1")
FEATURE_VERSION = os.getenv("FEATURE_VERSION", "v1-onchain-v73")
MODELS_DIR = os.getenv("MODELS_DIR", "models")
RESEARCH_MODE = os.getenv("RESEARCH_MODE", "heuristic_only")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("research_engine")

from db import get_conn


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def run_script(script_name: str, args: str = "") -> bool:
    """Ejecutar un script Python."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", script_name)
    cmd = f"python {script_path} {args}"
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            timeout=600,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if result.returncode != 0:
            logger.error(f"{script_name} FAILED: {result.stderr[:500]}")
            return False
        logger.info(f"{script_name} OK")
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"{script_name} TIMEOUT after 600s")
        return False
    except Exception as e:
        logger.error(f"{script_name} ERROR: {e}")
        return False


def update_sniper_thresholds():
    """
    Actualizar umbrales del sniper engine desde el research engine.
    Se ejecuta semanalmente para ajustar umbrales basados en datos reales.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Calcular umbrales basados en tokens recientes
        cursor.execute("""
            SELECT
                AVG(tx_velocity_0_5m) as avg_velocity,
                AVG(unique_wallets_0_10m) as avg_wallets,
                AVG(buy_tx_ratio_0_30m) as avg_buy_ratio
            FROM token_features
            WHERE feature_version = %s
              AND created_at >= NOW() - INTERVAL '7 days'
        """, (FEATURE_VERSION,))

        row = cursor.fetchone()
        if row and row[0]:
            avg_velocity, avg_wallets, avg_buy_ratio = row

            # Ajustar umbrales basados en el promedio
            new_tx_velocity = max(2.0, avg_velocity * 1.2)
            new_wallet_threshold = max(8, int(avg_wallets * 1.1))
            new_buy_ratio = max(0.60, avg_buy_ratio * 0.9)

            cursor.execute("""
                UPDATE agent_config SET
                    value = %s,
                    updated_at = NOW()
                WHERE key = 'sniper_tx_velocity_threshold'
            """, (str(new_tx_velocity),))

            cursor.execute("""
                UPDATE agent_config SET
                    value = %s,
                    updated_at = NOW()
                WHERE key = 'sniper_wallet_threshold'
            """, (str(new_wallet_threshold),))

            cursor.execute("""
                UPDATE agent_config SET
                    value = %s,
                    updated_at = NOW()
                WHERE key = 'sniper_buy_ratio_threshold'
            """, (str(new_buy_ratio),))

            conn.commit()
            logger.info(f"Umbrales actualizados: velocity={new_tx_velocity:.2f}, "
                       f"wallets={new_wallet_threshold}, buy_ratio={new_buy_ratio:.2f}")

    finally:
        cursor.close()
        conn.close()


def main():
    """Configurar y arrancar APScheduler."""
    logger.info("=== Research Engine (v3.0-ultralite-fixed) iniciado ===")
    logger.info(f"Research Mode: {RESEARCH_MODE}")

    scheduler = BlockingScheduler(timezone='UTC')

    # Entrenamiento diario a las 3am
    scheduler.add_job(
        lambda: run_script("train_models_all.py"),
        CronTrigger(hour=3, minute=0),
        id='train_models',
        name='Entrenamiento diario de modelos'
    )

    # Generación de hipótesis cada lunes a las 4am
    scheduler.add_job(
        lambda: run_script("generate_hypotheses_llm.py"),
        CronTrigger(day_of_week='mon', hour=4, minute=0),
        id='generate_hypotheses',
        name='Generación semanal de hipótesis'
    )

    # Validación de hipótesis cada 6 horas
    scheduler.add_job(
        lambda: run_script("validate_hypotheses.py"),
        CronTrigger(hour='*/6', minute=0),
        id='validate_hypotheses',
        name='Validación cada 6h de hipótesis'
    )

    # Reporte diario a las 8am
    scheduler.add_job(
        lambda: run_script("backtest_report.py"),
        CronTrigger(hour=8, minute=0),
        id='backtest_report',
        name='Reporte diario de backtest'
    )

    # Actualizar umbrales cada lunes a las 5am
    scheduler.add_job(
        update_sniper_thresholds,
        CronTrigger(day_of_week='mon', hour=5, minute=0),
        id='update_thresholds',
        name='Actualización semanal de umbrales'
    )

    logger.info("Scheduler configurado. Iniciando...")
    scheduler.start()


if __name__ == "__main__":
    main()