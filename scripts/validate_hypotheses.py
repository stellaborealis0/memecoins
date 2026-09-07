#!/usr/bin/env python3
"""
validate_hypotheses.py

Validar hipótesis activas con tokens nuevos etiquetados.
Actualiza posterior_probability con actualización bayesiana simple (Beta).

Frecuencia: cada 6h via Hermes/cron.

PostgreSQL - Conexión centralizada
"""

import os
import json
import logging
from datetime import datetime, timedelta

from db import get_conn

# Parámetros Beta prior iniciales
BETA_ALPHA_INIT = 1.0
BETA_BETA_INIT = 1.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validate_hypotheses")


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def token_matches_conditions(token: dict, conditions: list) -> bool:
    """
    Evalúa si un token cumple TODAS las condiciones de una hipótesis.
    """
    for cond in conditions:
        feature = cond.get("feature")
        op = cond.get("op")
        threshold = cond.get("threshold")
        value = token.get(feature)

        if value is None:
            return False

        # Normalizar booleanos
        if isinstance(value, bool):
            value = float(value)
        if isinstance(threshold, bool):
            threshold = float(threshold)

        try:
            value = float(value)
            threshold = float(threshold)
        except (TypeError, ValueError):
            return False

        if op == ">" and not (value > threshold):
            return False
        if op == "<" and not (value < threshold):
            return False
        if op == ">=" and not (value >= threshold):
            return False
        if op == "<=" and not (value <= threshold):
            return False
        if op == "==" and not (value == threshold):
            return False
        if op == "!=" and not (value != threshold):
            return False

    return True


def main():
    """Función principal."""
    logger.info("=== Validate Hypotheses (v3.0-ultralite-fixed) ===")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Hipótesis activas
        cursor.execute("""
            SELECT id, conditions_json, target_model,
                   prior_probability, total_tested,
                   validated_count, refuted_count
            FROM token_hypotheses
            WHERE active = 1
        """)

        hypotheses = cursor.fetchall()

        # Tokens etiquetados en las últimas 6h (ventana de validación)
        cutoff = (datetime.utcnow() - timedelta(hours=6)).isoformat()
        cursor.execute("""
            SELECT
                t.id, t.pump_100pc_24h, t.rug_pull_48h, t.still_active_7d,
                tf.tx_velocity_0_5m, tf.tx_velocity_5_60m,
                tf.tx_velocity_60_240m, tf.unique_wallets_0_10m,
                tf.unique_wallets_0_60m, tf.buy_tx_ratio_0_30m,
                tf.liquidity_add_0_10m, tf.liquidity_remove_0_2h,
                tf.liquidity_drop_1_2h_pct, tf.top_10_wallets_pct_0_1h,
                tf.gini_concentration_0_1h, tf.btc_change_pct_6h,
                tf.btc_dominance_pct, tf.launch_hour_utc,
                tf.launch_day_of_week
            FROM tokens t
            INNER JOIN token_features tf ON tf.token_id = t.id
            WHERE t.label_completed = 1
              AND t.predicted_at >= %s
        """, (cutoff,))

        cols = [
            "id", "pump_100pc_24h", "rug_pull_48h", "still_active_7d",
            "tx_velocity_0_5m", "tx_velocity_5_60m", "tx_velocity_60_240m",
            "unique_wallets_0_10m", "unique_wallets_0_60m",
            "buy_tx_ratio_0_30m", "liquidity_add_0_10m",
            "liquidity_remove_0_2h", "liquidity_drop_1_2h_pct",
            "top_10_wallets_pct_0_1h", "gini_concentration_0_1h",
            "btc_change_pct_6h", "btc_dominance_pct",
            "launch_hour_utc", "launch_day_of_week",
        ]

        tokens = [dict(zip(cols, row)) for row in cursor.fetchall()]

        if not tokens:
            logger.info("validate_hypotheses: sin tokens nuevos en ventana.")
            return

        target_col_map = {
            "pump": "pump_100pc_24h",
            "rug": "rug_pull_48h",
            "survival": "still_active_7d",
        }

        updated = 0
        for hyp in hypotheses:
            hyp_id, conditions_json, target_model, prior, total, validated, refuted = hyp
            conditions = json.loads(conditions_json) if conditions_json else []
            target_col = target_col_map.get(target_model)

            if not target_col:
                continue

            new_tested = 0
            new_validated = 0
            new_refuted = 0

            for token in tokens:
                if not token_matches_conditions(token, conditions):
                    continue

                new_tested += 1
                outcome = token.get(target_col)

                if outcome is True:
                    new_validated += 1
                elif outcome is False:
                    new_refuted += 1

            if new_tested == 0:
                continue

            # Actualización bayesiana Beta-Binomial
            alpha = BETA_ALPHA_INIT + (validated + new_validated)
            beta = BETA_BETA_INIT + (refuted + new_refuted)
            posterior = alpha / (alpha + beta)

            # Bayes factor simple
            bayes_factor = (
                posterior / max(prior, 0.01)
                if posterior > prior
                else prior / max(posterior, 0.01) * -1
            )

            cursor.execute("""
                UPDATE token_hypotheses SET
                    total_tested = total_tested + %s,
                    validated_count = validated_count + %s,
                    refuted_count = refuted_count + %s,
                    posterior_probability = %s,
                    bayes_factor = %s,
                    last_updated = NOW()
                WHERE id = %s
            """, (new_tested, new_validated, new_refuted, posterior, bayes_factor, hyp_id))

            updated += 1

        conn.commit()
        logger.info(f"validate_hypotheses: {updated} hipótesis actualizadas con {len(tokens)} tokens nuevos")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()