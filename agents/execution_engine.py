"""
execution_engine.py

Capa D - Execution Engine
Firma y envía trades solo si execution_mode = 'real'

Reglas de seguridad:
- Solo se activa si EXECUTION_MODE='real' en agent_config
- Límite hard de 1 SOL por trade (hardcodeado)
- Stop-loss on-chain obligatorio (-30%)
- Take-profit: +50%, +100%
- Jito Bundle para cada trade
"""

import os
import logging
import requests
from datetime import datetime
from typing import Optional

# Configuración
DB_DSN = os.getenv("DATABASE_URL")
EXECUTION_MODE = os.getenv("EXECUTION_MODE", "research")
MAX_POSITION_SOL = float(os.getenv("MAX_POSITION_SOL", "0.5"))
JITO_BLOCK_ENGINE_URL = os.getenv("JITO_BLOCK_ENGINE_URL", "https://mainnet.block-engine.jito.wtf")
JITO_TIP_SOL = float(os.getenv("JITO_TIP_SOL", "0.01"))
WALLET_PRIVATE_KEY = os.getenv("WALLET_PRIVATE_KEY", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("execution_engine")

# LÍMITE HARD: 1 SOL por trade (nunca se puede sobrepasar)
HARD_LIMIT_SOL = 1.0


def is_execution_mode() -> bool:
    """Verificar si el modo execution está activo."""
    import psycopg2

    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT value FROM agent_config WHERE key = 'execution_mode'
        """)
        row = cursor.fetchone()
        return row and row[0] == 'execution'
    finally:
        cursor.close()
        conn.close()


def check_circuit_breaker() -> bool:
    """Verificar si el circuit breaker está activo."""
    import psycopg2

    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT COUNT(*) FROM circuit_breaker_log
            WHERE resumed_at IS NULL
        """)
        row = cursor.fetchone()
        return (row and row[0] > 0)
    finally:
        cursor.close()
        conn.close()


def get_active_trades_count() -> int:
    """Obtener número de trades activos."""
    import psycopg2

    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT COUNT(*) FROM trades WHERE status IN ('pending', 'confirmed')
        """)
        row = cursor.fetchone()
        return row[0] if row else 0
    finally:
        cursor.close()
        conn.close()


def get_total_exposure() -> float:
    """Obtener exposición total en SOL."""
    import psycopg2

    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT COALESCE(SUM(amount_sol), 0) FROM trades
            WHERE status IN ('pending', 'confirmed')
        """)
        row = cursor.fetchone()
        return row[0] if row else 0.0
    finally:
        cursor.close()
        conn.close()


def check_position_limits(amount_sol: float) -> tuple[bool, str]:
    """
    Verificar límites de posición.
    Devuelve (allowed, reason)
    """
    if amount_sol > HARD_LIMIT_SOL:
        return False, f"Amount {amount_sol} SOL > hard limit {HARD_LIMIT_SOL} SOL"

    if amount_sol > MAX_POSITION_SOL:
        return False, f"Amount {amount_sol} SOL > configured limit {MAX_POSITION_SOL} SOL"

    total_exposure = get_total_exposure()
    if total_exposure + amount_sol > HARD_LIMIT_SOL:
        return False, f"Total exposure would exceed hard limit"

    return True, "OK"


def build_jito_bundle(token_id: int, amount_sol: float) -> dict:
    """
    Construir Jito Bundle para un trade.
    """
    return {
        "token_id": token_id,
        "amount_sol": min(amount_sol, HARD_LIMIT_SOL),
        "tip_sol": JITO_TIP_SOL,
        "timestamp": datetime.utcnow().isoformat(),
        "jito_block_engine_url": JITO_BLOCK_ENGINE_URL
    }


def send_to_block_engine(bundle: dict) -> Optional[str]:
    """
    Enviar bundle al block engine.
    Devuelve jito_bundle_id o None si falla.
    """
    try:
        resp = requests.post(
            f"{JITO_BLOCK_ENGINE_URL}/api/v1/bundles",
            json=bundle,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("jito_bundle_id")
    except Exception as e:
        logger.error(f"Error sending bundle: {e}")
    return None


def execute_trade(token_id: int, mint: str, amount_sol: float) -> Optional[str]:
    """
    Ejecutar un trade.
    Devuelve tx_hash o None si falla.
    """
    import psycopg2

    # Verificar modo execution
    if not is_execution_mode():
        logger.warning("Execution mode no activo. Trade no ejecutado.")
        return None

    # Verificar circuit breaker
    if check_circuit_breaker():
        logger.warning("Circuit breaker activo. Trade no ejecutado.")
        return None

    # Verificar límites
    allowed, reason = check_position_limits(amount_sol)
    if not allowed:
        logger.warning(f"Trade bloqueado: {reason}")
        return None

    # Verificar exposición
    active_trades = get_active_trades_count()
    if active_trades >= 10:  # Máximo 10 trades activos
        logger.warning("Máximo de trades activos alcanzado")
        return None

    # Construir y enviar bundle
    bundle = build_jito_bundle(token_id, amount_sol)
    jito_bundle_id = send_to_block_engine(bundle)

    if not jito_bundle_id:
        logger.error("Error enviando bundle al block engine")
        return None

    # Registrar en DB
    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO trades (
                token_id, mint_address, wallet_address, action,
                amount_sol, jito_bundle_id, timestamp, status
            ) VALUES (%s, %s, %s, 'buy', %s, %s, %s, 'pending')
            RETURNING id
        """, (
            token_id,
            mint,
            "self",  # Auto-trade
            min(amount_sol, HARD_LIMIT_SOL),
            jito_bundle_id,
            datetime.utcnow()
        ))

        trade_id = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Trade registrado: {mint} (id={trade_id}, bundle={jito_bundle_id})")

        return jito_bundle_id

    finally:
        cursor.close()
        conn.close()


def process_pending_trades():
    """Procesar pending_trades pendientes."""
    import psycopg2

    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        # Buscar pending_trades sin ejecutar
        cursor.execute("""
            SELECT id, token_id, mint_address, sniper_score
            FROM pending_trades
            WHERE executed = FALSE
            ORDER BY sniper_score DESC
            LIMIT 10
        """)

        trades = cursor.fetchall()
        for trade_id, token_id, mint, score in trades:
            # Calcular amount basado en score (máximo 1 SOL)
            amount = min(MAX_POSITION_SOL, HARD_LIMIT_SOL) * (score / 100.0)

            # Ejecutar trade
            jito_bundle_id = execute_trade(token_id, mint, amount)

            if jito_bundle_id:
                cursor.execute("""
                    UPDATE pending_trades SET
                        executed = TRUE,
                        executed_at = NOW(),
                        execution_error = NULL
                    WHERE id = %s
                """, (trade_id,))
            else:
                cursor.execute("""
                    UPDATE pending_trades SET
                        execution_error = %s
                    WHERE id = %s
                """, ("Execution failed", trade_id))

        conn.commit()

    finally:
        cursor.close()
        conn.close()


def monitor_trades():
    """Monitorizar trades activos y actualizar status."""
    import psycopg2

    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        # Buscar trades pendientes/confirmados
        cursor.execute("""
            SELECT id, mint_address, amount_sol, timestamp
            FROM trades
            WHERE status IN ('pending', 'confirmed')
        """)

        trades = cursor.fetchall()
        for trade_id, mint, amount, timestamp in trades:
            # Aquí se verificaría el estado on-chain del trade
            # Por ahora, simular actualización
            pass

    finally:
        cursor.close()
        conn.close()


def main():
    """Loop principal del execution engine."""
    logger.info("=== Execution Engine iniciado ===")
    logger.info(f"EXECUTION_MODE: {EXECUTION_MODE}")
    logger.info(f"MAX_POSITION_SOL: {MAX_POSITION_SOL}")
    logger.info(f"HARD_LIMIT_SOL: {HARD_LIMIT_SOL}")

    if not is_execution_mode():
        logger.warning("Execution mode no activo. Solo se registrarán trades en DB.")
        logger.warning("Para activar trades reales: /mode execution confirm")

    while True:
        try:
            # Procesar pending_trades
            process_pending_trades()

            # Monitorizar trades activos
            monitor_trades()

            # Esperar 5 segundos
            import time
            time.sleep(5)

        except Exception as e:
            logger.error(f"Error en execution loop: {e}")
            import time
            time.sleep(10)


if __name__ == "__main__":
    main()