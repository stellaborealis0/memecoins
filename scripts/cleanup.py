#!/usr/bin/env python3
"""
Script de limpieza automática para PostgreSQL (cron cada 6h).

Elimina datos antiguos según retención.

Uso:
    python scripts/cleanup.py
    # O con cron: 0 */6 * * * python /path/memecoin/scripts/cleanup.py
"""

import os
import sys
import logging
from datetime import datetime, timedelta

from db import get_conn

# Configuración
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "1"))
LOG_PATH = os.getenv("CLEANUP_LOG_PATH", "logs/cleanup.log")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cleanup")


def log(message: str):
    """Escribe un mensaje en el log."""
    timestamp = datetime.utcnow().isoformat()
    log_line = f"[{timestamp}] {message}\n"
    print(log_line, end="")

    # Escribir en archivo de log
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(log_line)


def cleanup_old_data():
    """Elimina datos antiguos según retención."""
    log(f"Iniciando limpieza: retención={RETENTION_DAYS} días")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
        log(f"Cutoff: {cutoff}")

        # Contar registros antes de borrar

        # Borrar launches antiguos
        cursor.execute("SELECT COUNT(*) FROM launches WHERE time < %s", (cutoff,))
        launches_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM launches WHERE time < %s", (cutoff,))
        log(f"Borrados {launches_count} launches antiguos")

        # Borrar token_features antiguos
        cursor.execute("SELECT COUNT(*) FROM token_features WHERE created_at < %s", (cutoff,))
        features_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM token_features WHERE created_at < %s", (cutoff,))
        log(f"Borrados {features_count} token_features antiguos")

        # Borrar trades antiguos
        cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp < %s", (cutoff,))
        trades_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM trades WHERE timestamp < %s", (cutoff,))
        log(f"Borrados {trades_count} trades antiguos")

        # Borrar risk_events antiguos
        cursor.execute("SELECT COUNT(*) FROM risk_events WHERE created_at < %s", (cutoff,))
        risk_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM risk_events WHERE created_at < %s", (cutoff,))
        log(f"Borrados {risk_count} risk_events antiguos")

        # Borrar pending_trades antiguos
        cursor.execute("SELECT COUNT(*) FROM pending_trades WHERE created_at < %s", (cutoff,))
        pending_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM pending_trades WHERE created_at < %s", (cutoff,))
        log(f"Borrados {pending_count} pending_trades antiguos")

        conn.commit()

        log("Limpieza completada")
        return True

    except Exception as e:
        log(f"ERROR en limpieza: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def main():
    """Función principal."""
    success = cleanup_old_data()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()