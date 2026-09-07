#!/usr/bin/env python3
"""
generate_hypotheses_llm.py

Genera hipótesis falsables comparando top-20 winners vs top-20 losers.
Frecuencia: lunes a las 4am via Hermes/cron.

PostgreSQL - Conexión centralizada
"""

import os
import json
import logging
from datetime import datetime

from db import get_conn

LITELLM_ENDPOINT = os.getenv("LITELLM_ENDPOINT", "http://100.68.1.180:8080/v1")
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "im-qwen32b")
FEATURE_VERSION = os.getenv("FEATURE_VERSION", "v1-onchain-v73")
TOP_N = 20  # winners y losers a comparar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("generate_hypotheses_llm")


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def fetch_top_n(conn, target_col, is_winner, n):
    """Obtener los N tokens con mayor/menor probabilidad."""
    cursor = conn.cursor()

    prob_col_map = {
        "pump_100pc_24h": "prob_pump_24h",
        "rug_pull_48h": "prob_rug_48h",
        "still_active_7d": "prob_survival_7d",
    }

    prob_col = prob_col_map.get(target_col, "prob_pump_24h")
    order = "DESC" if is_winner else "ASC"

    cursor.execute(f"""
        SELECT
            t.address,
            t.created_at,
            t.{target_col},
            t.{prob_col},
            tf.tx_velocity_0_5m,
            tf.tx_velocity_5_60m,
            tf.tx_velocity_60_240m,
            tf.unique_wallets_0_10m,
            tf.unique_wallets_0_60m,
            tf.buy_tx_ratio_0_30m,
            tf.liquidity_add_0_10m,
            tf.liquidity_remove_0_2h,
            tf.liquidity_drop_1_2h_pct,
            tf.top_10_wallets_pct_0_1h,
            tf.gini_concentration_0_1h,
            tf.btc_change_pct_6h,
            tf.btc_dominance_pct,
            tf.launch_hour_utc,
            tf.launch_day_of_week
        FROM tokens t
        INNER JOIN token_features tf
            ON tf.token_id = t.id
            AND tf.feature_version = %s
        WHERE t.{target_col} = %s
          AND t.label_completed = 1
        ORDER BY t.{prob_col} {order}
        LIMIT %s
    """, (FEATURE_VERSION, 1 if is_winner else 0, n))

    cols = [
        "address", "created_at", "target", "probability",
        "tx_velocity_0_5m", "tx_velocity_5_60m", "tx_velocity_60_240m",
        "unique_wallets_0_10m", "unique_wallets_0_60m",
        "buy_tx_ratio_0_30m",
        "liquidity_add_0_10m", "liquidity_remove_0_2h",
        "liquidity_drop_1_2h_pct",
        "top_10_wallets_pct_0_1h", "gini_concentration_0_1h",
        "btc_change_pct_6h", "btc_dominance_pct",
        "launch_hour_utc", "launch_day_of_week",
    ]

    rows = cursor.fetchall()
    return [dict(zip(cols, row)) for row in rows]


def rows_to_csv(rows):
    """Convertir lista de dicts a CSV legible para LLM."""
    if not rows:
        return "(sin datos)"

    headers = [k for k in rows[0].keys() if k not in ("address", "created_at")]
    lines = [",".join(headers)]

    for row in rows:
        values = []
        for h in headers:
            val = row.get(h)
            if isinstance(val, float):
                values.append(str(round(val, 4)))
            elif isinstance(val, bool):
                values.append("1" if val else "0")
            else:
                values.append(str(val) if val else "")
        lines.append(",".join(values))

    return "\n".join(lines)


def generate_hypotheses(winners, losers, target_model):
    """Generar hipótesis usando LLM."""
    winners_csv = rows_to_csv(winners)
    losers_csv = rows_to_csv(losers)

    prompt = f"""Eres un analista cuantitativo especializado en memecoins de Solana.

Tienes dos grupos de tokens reales de Pump.fun:

=== WINNERS ({target_model}) ===
{winners_csv}

=== LOSERS ({target_model}) ===
{losers_csv}

INSTRUCCIONES ESTRICTAS:

1. Analiza los datos brutos. NO inventes correlaciones genéricas.
2. Busca patrones DIFERENCIALES concretos entre winners y losers.
3. Genera exactamente 5 hipótesis falsables.
4. Cada hipótesis DEBE tener este formato JSON exacto:

{{
  "hypothesis_text": "Si [condicion A] Y [condicion B], entonces [outcome] con probabilidad aproximada X%.",
  "conditions": [
    {{"feature": "nombre_feature", "op": ">", "threshold": valor_numerico}},
    {{"feature": "nombre_feature", "op": "<", "threshold": valor_numerico}}
  ],
  "estimated_probability": 0.XX,
  "confidence_interval": 0.XX,
  "reasoning": "Explicacion breve basada en los datos observados"
}}

5. Operadores válidos en conditions: ">", "<", ">=", "<=", "==", "!="
6. Features válidas: tx_velocity_0_5m, tx_velocity_5_60m, tx_velocity_60_240m,
   unique_wallets_0_10m, unique_wallets_0_60m, buy_tx_ratio_0_30m,
   liquidity_add_0_10m, liquidity_remove_0_2h, liquidity_drop_1_2h_pct,
   top_10_wallets_pct_0_1h, gini_concentration_0_1h,
   btc_change_pct_6h, btc_dominance_pct, launch_hour_utc, launch_day_of_week
7. NO menciones Twitter, sentiment ni noticias. Solo features on-chain.
8. Devuelve SOLO un array JSON con las 5 hipótesis. Sin texto adicional.
"""

    try:
        import requests
        response = requests.post(
            f"{LITELLM_ENDPOINT}/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('LITELLM_API_KEY', 'local')}",
                "Content-Type": "application/json",
            },
            json={
                "model": LITELLM_MODEL,
                "temperature": 0.3,
                "max_tokens": 2000,
                "messages": [
                    {"role": "system", "content": "Eres un analista cuantitativo. Respondes SOLO con JSON válido."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()

        # Limpiar posibles ```json ... ```
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        hypotheses = json.loads(content.strip())
        if not isinstance(hypotheses, list):
            hypotheses = [hypotheses]

        return [h for h in hypotheses if all(k in h for k in [
            "hypothesis_text", "conditions",
            "estimated_probability", "confidence_interval"
        ])]

    except Exception as e:
        logger.error(f"Error llamando a LLM: {e}")
        return []


def insert_hypothesis(conn, h, target_model):
    """Insertar hipótesis en la DB."""
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO token_hypotheses (
            hypothesis_text,
            conditions_json,
            target_model,
            feature_version,
            estimated_probability,
            confidence_interval,
            prior_probability,
            posterior_probability,
            generated_by,
            generated_on_data,
            active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
    """, (
        h["hypothesis_text"],
        json.dumps(h["conditions"]),
        target_model,
        FEATURE_VERSION,
        h["estimated_probability"],
        h["confidence_interval"],
        h["estimated_probability"],
        h["estimated_probability"],
        f"llm-{LITELLM_MODEL}",
        "backfill-90d" if os.getenv("BACKFILL_MODE", "false").lower() == "true" else "live-week-N",
    ))

    conn.commit()


def main():
    """Función principal."""
    logger.info("=== Generate Hypotheses LLM (v3.0-ultralite-fixed) ===")

    conn = get_db_connection()

    try:
        for target_model, target_col in [
            ("pump", "pump_100pc_24h"),
            ("rug", "rug_pull_48h"),
            ("survival", "still_active_7d"),
        ]:
            logger.info(f"Generando hipótesis para modelo: {target_model}")

            winners = fetch_top_n(conn, target_col, True, TOP_N)
            losers = fetch_top_n(conn, target_col, False, TOP_N)

            if len(winners) < 5 or len(losers) < 5:
                logger.warning(f"Datos insuficientes para {target_model}. Saltando.")
                continue

            hypotheses = generate_hypotheses(winners, losers, target_model)

            for h in hypotheses:
                insert_hypothesis(conn, h, target_model)

            logger.info(f"{target_model}: {len(hypotheses)} hipótesis generadas")

    finally:
        conn.close()


if __name__ == "__main__":
    main()