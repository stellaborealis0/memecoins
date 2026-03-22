#!/usr/bin/env python3
"""
Script de limpieza automática para SQLite (cron cada 6h).

Elimina datos antiguos según retención y ejecuta VACUUM para compactar la base de datos.

Uso:
    python scripts/cleanup.py
    # O con cron: 0 */6 * * * python /path/memecoin/scripts/cleanup.py
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta

# Configuración
DB_PATH = os.getenv("DATABASE_PATH", "data/memecoin.db")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "1"))
LOG_PATH = os.getenv("CLEANUP_LOG_PATH", "logs/cleanup.log")


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
    """Elimina datos antiguos según retención y ejecuta VACUUM."""
    log(f"Iniciando limpieza: retención={RETENTION_DAYS} días")

    conn = sqlite3.connect(DB_PATH)

    try:
        # Activar WAL Mode
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")

        cutoff = (datetime.utcnow() - timedelta(days=RETENTION_DAYS)).isoformat()
        log(f"Cutoff: {cutoff}")

        # Contar registros antes de borrar
        cursor = conn.cursor()

        # Borrar launches antiguos
        cursor.execute("SELECT COUNT(*) FROM launches WHERE time < ?", (cutoff,))
        launches_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM launches WHERE time < ?", (cutoff,))
        log(f"Borrados {launches_count} launches antiguos")

        # Borrar token_features antiguos
        cursor.execute("SELECT COUNT(*) FROM token_features WHERE created_at < ?", (cutoff,))
        features_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM token_features WHERE created_at < ?", (cutoff,))
        log(f"Borrados {features_count} token_features antiguos")

        # Borrar trades antiguos
        cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp < ?", (cutoff,))
        trades_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM trades WHERE timestamp < ?", (cutoff,))
        log(f"Borrados {trades_count} trades antiguos")

        # Borrar risk_events antiguos
        cursor.execute("SELECT COUNT(*) FROM risk_events WHERE timestamp < ?", (cutoff,))
        risk_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM risk_events WHERE timestamp < ?", (cutoff,))
        log(f"Borrados {risk_count} risk_events antiguos")

        # Borrar pending_trades antiguos
        cursor.execute("SELECT COUNT(*) FROM pending_trades WHERE created_at < ?", (cutoff,))
        pending_count = cursor.fetchone()[0]
        cursor.execute("DELETE FROM pending_trades WHERE created_at < ?", (cutoff,))
        log(f"Borrados {pending_count} pending_trades antiguos")

        conn.commit()

        # Ejecutar VACUUM para compactar la base de datos
        log("Ejecutando VACUUM...")
        conn.execute("VACUUM;")
        conn.commit()

        # Verificar tamaño final
        cursor.execute("SELECT page_count * page_size / 1024 / 1024 AS size_mb FROM pragma_page_count(), pragma_page_size();")
        final_size = cursor.fetchone()[0]
        log(f"Limpieza completada. Tamaño final: {final_size:.2f} MB")

        return True

    except Exception as e:
        log(f"ERROR en limpieza: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


def main():
    """Función principal."""
    if not os.path.exists(DB_PATH):
        log(f"ERROR: Base de datos no encontrada: {DB_PATH}")
        sys.exit(1)

    success = cleanup_old_data()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()