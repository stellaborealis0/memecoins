#!/usr/bin/env python3
"""
init_whales.py

Inicializar whales con wallets conocidas (v3.0-ultralite-fixed)

Ejecutar: python scripts/init_whales.py
"""

import os
import sys
import logging

from db import get_conn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_whales")


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def init_whales():
    """Inicializar whales conocidas."""
    logger.info("=== Inicializando whales conocidas ===")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Whales conocidas (ejemplo - reemplazar con datos reales)
        whales = [
            # Whale 1: Wallet con buen historial
            {
                "wallet": "whale1example1234567890123456789012345678901234",
                "name": "Whale Pro Alpha",
                "label": "whale",
                "graduation_rate": 0.45,
                "total_tokens": 150,
                "rug_count": 5,
                "first_seen": "2024-01-01T00:00:00",
                "last_seen": "2024-12-31T23:59:59"
            },
            # Whale 2: Wallet con historial excelente
            {
                "wallet": "whale2example1234567890123456789012345678901234",
                "name": "Whale Alpha Master",
                "label": "whale",
                "graduation_rate": 0.65,
                "total_tokens": 200,
                "rug_count": 3,
                "first_seen": "2024-01-01T00:00:00",
                "last_seen": "2024-12-31T23:59:59"
            },
            # Whale 3: Wallet con historial bueno
            {
                "wallet": "whale3example1234567890123456789012345678901234",
                "name": "Whale Beta Plus",
                "label": "whale",
                "graduation_rate": 0.35,
                "total_tokens": 100,
                "rug_count": 8,
                "first_seen": "2024-01-01T00:00:00",
                "last_seen": "2024-12-31T23:59:59"
            },
            # Bundler conocido
            {
                "wallet": "bundler1example1234567890123456789012345678901234",
                "name": "Bundler Pro",
                "label": "bundler",
                "graduation_rate": 0.25,
                "total_tokens": 500,
                "rug_count": 50,
                "first_seen": "2024-01-01T00:00:00",
                "last_seen": "2024-12-31T23:59:59"
            },
            # Creator conocido
            {
                "wallet": "creator1example1234567890123456789012345678901234",
                "name": "Creator Alpha",
                "label": "creator",
                "graduation_rate": 0.55,
                "total_tokens": 300,
                "rug_count": 15,
                "first_seen": "2024-01-01T00:00:00",
                "last_seen": "2024-12-31T23:59:59"
            }
        ]

        for whale in whales:
            wallet = whale["wallet"][:44] if len(whale["wallet"]) > 44 else whale["wallet"]
            cursor.execute("""
                INSERT INTO whales (
                    wallet, label, win_rate, total_trades, rug_count, added_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (wallet) DO NOTHING
            """, (
                wallet,
                whale["label"],
                whale["graduation_rate"],
                whale["total_tokens"],
                whale["rug_count"],
                whale["first_seen"]
            ))

        conn.commit()
        logger.info(f"Whales inicializadas: {len(whales)} wallets")

        # Verificar
        cursor.execute("SELECT COUNT(*) FROM whales WHERE label = 'whale';")
        whale_count = cursor.fetchone()[0]
        logger.info(f"Whales cualificadas: {whale_count}")

        return True

    finally:
        cursor.close()
        conn.close()


def main():
    """Función principal."""
    success = init_whales()
    if success:
        logger.info("=== Inicialización de whales completada ===")
        return 0
    else:
        logger.error("=== Error en inicialización de whales ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())