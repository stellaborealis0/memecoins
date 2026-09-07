#!/usr/bin/env python3
"""
backtest_report.py

Genera informe diario de precision@top_k en datos recientes.
Envía resumen por Telegram.

Frecuencia: cada día a las 8am via Hermes/cron.

PostgreSQL - Conexión centralizada
"""

import os
import logging
from datetime import datetime

from db import get_conn

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USERS = os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backtest_report")


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def build_report() -> str:
    """Construir el informe."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Últimas métricas de cada modelo
        cursor.execute("""
            SELECT DISTINCT ON (model_name)
                model_name, model_version,
                precision_at_10, precision_at_20,
                auc_roc, f1_score,
                n_tokens_train, n_tokens_test,
                created_at
            FROM model_performance
            ORDER BY model_name, created_at DESC
        """)

        models = cursor.fetchall()

        # Hipótesis con mayor posterior_probability
        cursor.execute("""
            SELECT target_model, hypothesis_text,
                   posterior_probability, total_tested,
                   validated_count, refuted_count
            FROM token_hypotheses
            WHERE active = 1
            ORDER BY posterior_probability DESC
            LIMIT 5
        """)

        top_hyp = cursor.fetchall()

        # Tokens de hoy con mayor prob de pump y menor de rug
        cursor.execute("""
            SELECT symbol, address,
                   prob_pump_24h, prob_rug_48h, prob_survival_7d,
                   created_at
            FROM tokens
            WHERE created_at >= NOW() - INTERVAL '24 hours'
              AND prob_pump_24h IS NOT NULL
              AND prob_rug_48h IS NOT NULL
            ORDER BY (prob_pump_24h - prob_rug_48h) DESC
            LIMIT 5
        """)

        top_tokens = cursor.fetchall()

        # Construir mensaje
        lines = [
            f"📊 *Informe diario — {datetime.utcnow().strftime('%Y-%m-%d')}*",
            "",
            "*Modelos activos:*",
        ]

        for m in models:
            name, version, p10, p20, auc, f1, n_train, n_test, ts = m
            lines.append(
                f"• `{name}` | P@10={p10:.2f} P@20={p20:.2f} "
                f"AUC={auc:.2f} F1={f1:.2f} "
                f"(train={n_train} test={n_test})"
            )

        lines += ["", "*Top 5 hipótesis activas:*"]
        for h in top_hyp:
            model, text, posterior, tested, val, ref = h
            short_text = text[:80] + "..." if len(text) > 80 else text
            lines.append(
                f"• [{model}] P={posterior:.2f} "
                f"({val}/{tested} validadas) — {short_text}"
            )

        lines += ["", "*Top 5 tokens 24h (pump - rug score):*"]
        for t in top_tokens:
            symbol, addr, p_pump, p_rug, p_surv, created = t
            short_addr = addr[:8] + "..." if addr else "?"
            lines.append(
                f"• `{symbol or short_addr}` "
                f"pump={p_pump:.2f} rug={p_rug:.2f} surv={p_surv:.2f} "
                f"@ {created.strftime('%H:%M')} UTC"
            )

        return "\n".join(lines)

    finally:
        cursor.close()
        conn.close()


def send_telegram(message: str):
    """Enviar mensaje por Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Sin TELEGRAM_BOT_TOKEN. Informe no enviado.")
        return

    import requests

    for user_id in TELEGRAM_ALLOWED_USERS:
        user_id = user_id.strip()
        if not user_id:
            continue

        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info(f"Mensaje enviado a {user_id}")
            else:
                logger.error(f"Error enviando a {user_id}: {resp.text}")
        except Exception as e:
            logger.error(f"Error enviando Telegram a {user_id}: {e}")


def main():
    """Función principal."""
    logger.info("=== Backtest Report (v3.0-ultralite-fixed) ===")

    report = build_report()
    send_telegram(report)

    logger.info("backtest_report: informe enviado")


if __name__ == "__main__":
    main()