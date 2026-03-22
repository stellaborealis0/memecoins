"""
risk_filter.py

Capa B - Risk Filter
Evalúa risk_score de tokens en <500ms

Reglas de evaluación (en orden):
1. rugcheck_score (si disponible, <500ms de API gratuita)
2. creator_rug_history_count (desde DB, instantáneo)
3. top_10_wallets_pct (concentración)
4. liquidity_add_0_10m (¿hubo add inicial?)
5. creator_bundled_buy (señal de alerta)

Bloquea trade si risk_score > RISK_THRESHOLD (default 0.65)
"""

import os
import logging
import requests
from typing import Tuple, Dict, Any

# Configuración
DB_DSN = os.getenv("DATABASE_URL")
RUGCHECK_API_BASE = os.getenv("RUGCHECK_API_BASE", "https://api.rugcheck.xyz/v1")
RISK_THRESHOLD = float(os.getenv("RISK_THRESHOLD", "0.65"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("risk_filter")


def get_creator_stats(cursor, creator_address: str) -> Dict[str, Any]:
    """Obtener estadísticas del creador."""
    cursor.execute("""
        SELECT
            COUNT(*) as total_tokens,
            SUM(CASE WHEN rug_pull_48h THEN 1 ELSE 0 END) as rug_count
        FROM tokens
        WHERE creator_address = %s
    """, (creator_address,))

    row = cursor.fetchone()
    total = row[0] or 0
    rugs = row[1] or 0

    return {
        "total_tokens": total,
        "rug_count": rugs,
        "rug_history_rate": rugs / total if total > 0 else 0
    }


def get_top_10_concentration(cursor, token_id: int) -> float:
    """Obtener concentración top 10 wallets."""
    cursor.execute("""
        SELECT top_10_wallets_pct_0_1h
        FROM launches
        WHERE token_id = %s
        ORDER BY time DESC
        LIMIT 1
    """, (token_id,))

    row = cursor.fetchone()
    return row[0] if row and row[0] else 0.0


def get_liquidity_status(cursor, token_id: int) -> str:
    """Obtener estado de liquidez."""
    cursor.execute("""
        SELECT liquidity_add_0_10m, liquidity_remove_0_2h
        FROM launches
        WHERE token_id = %s
        ORDER BY time DESC
        LIMIT 1
    """, (token_id,))

    row = cursor.fetchone()
    if not row:
        return "unknown"

    added = row[0] or False
    removed = row[1] or False

    if removed:
        return "removed"
    elif added:
        return "added"
    return "none"


def fetch_rugcheck_score(mint: str) -> Tuple[bool, int, str]:
    """
    Obtener rugcheck score desde API.
    Devuelve (success, score, risks_json)
    """
    try:
        resp = requests.get(
            f"{RUGCHECK_API_BASE}/tokens/{mint}/report",
            timeout=0.5
        )
        if resp.status_code == 200:
            data = resp.json()
            score = data.get("score", 500)
            risks = data.get("risks", [])
            return True, score, str(risks)
    except Exception as e:
        logger.warning(f"Error fetching rugcheck for {mint}: {e}")

    return False, -1, "[]"


def calculate_risk_score(
    rugcheck_score: int,
    creator_rug_count: int,
    top_10_concentration: float,
    liquidity_status: str,
    creator_bundled_buy: bool
) -> float:
    """
    Calcular risk score (0.0 a 1.0).
    Mayor score = mayor riesgo.
    """
    score = 0.0

    # 1. RugCheck score (0-0.35)
    if rugcheck_score > 0:
        # Score 0-1000, normalizar a 0-1
        normalized = rugcheck_score / 1000.0
        score += normalized * 0.35

    # 2. Historial de rugs del creador (0-0.25)
    if creator_rug_count > 0:
        # Cada rug añade riesgo
        rug_penalty = min(creator_rug_count * 0.05, 0.25)
        score += rug_penalty

    # 3. Concentración top 10 (0-0.20)
    if top_10_concentration > 0.5:
        score += min((top_10_concentration - 0.5) * 0.5, 0.20)

    # 4. Liquidez (0-0.10)
    if liquidity_status == "removed":
        score += 0.10
    elif liquidity_status == "none":
        score += 0.05

    # 5. Creator bundled buy (0-0.10)
    if creator_bundled_buy:
        score += 0.10

    return min(score, 1.0)


def evaluate_token(mint: str, creator_address: str, token_id: int) -> Dict[str, Any]:
    """
    Evaluar riesgo de un token.
    Devuelve dict con risk_score y detalles.
    """
    import psycopg2

    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        # 1. RugCheck score
        success, rugcheck_score, risks = fetch_rugcheck_score(mint)

        # 2. Creator stats
        creator_stats = get_creator_stats(cursor, creator_address)

        # 3. Top 10 concentration
        top_10 = get_top_10_concentration(cursor, token_id)

        # 4. Liquidity status
        liquidity = get_liquidity_status(cursor, token_id)

        # 5. Creator bundled buy (default False)
        bundled = False

        # Calcular risk score
        risk_score = calculate_risk_score(
            rugcheck_score if success else -1,
            creator_stats["rug_count"],
            top_10,
            liquidity,
            bundled
        )

        # Determinar decisión
        if risk_score > RISK_THRESHOLD:
            decision = "block"
            reason = f"Risk score {risk_score:.2f} > {RISK_THRESHOLD}"
        elif risk_score > RISK_THRESHOLD - 0.15:
            decision = "warn"
            reason = f"Risk score {risk_score:.2f}接近 threshold"
        else:
            decision = "allow"
            reason = f"Risk score {risk_score:.2f} OK"

        return {
            "risk_score": risk_score,
            "decision": decision,
            "reason": reason,
            "details": {
                "rugcheck_score": rugcheck_score if success else "unavailable",
                "creator_rug_count": creator_stats["rug_count"],
                "top_10_concentration": top_10,
                "liquidity_status": liquidity,
                "creator_bundled_buy": bundled
            }
        }

    finally:
        cursor.close()
        conn.close()


def register_risk_event(
    token_id: int,
    mint: str,
    risk_score: float,
    decision: str,
    creator_address: str
):
    """Registrar evento de risk en la DB."""
    import psycopg2

    conn = psycopg2.connect(DB_DSN)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO risk_events (
                token_id, mint_address, risk_score, risk_threshold,
                decision, creator_address
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            token_id,
            mint,
            risk_score,
            RISK_THRESHOLD,
            decision,
            creator_address
        ))

        conn.commit()
    finally:
        cursor.close()
        conn.close()


def is_token_allowed(mint: str, creator_address: str, token_id: int) -> Tuple[bool, str]:
    """
    Verificar si un token está permitido para trade.
    Devuelve (allowed, reason)
    """
    result = evaluate_token(mint, creator_address, token_id)

    if result["decision"] == "block":
        return False, result["reason"]

    return True, result["reason"]


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        mint = sys.argv[1]
        result = evaluate_token(mint, "test_creator", 1)
        print(f"Risk evaluation for {mint}:")
        print(f"  Score: {result['risk_score']:.2f}")
        print(f"  Decision: {result['decision']}")
        print(f"  Reason: {result['reason']}")
        print(f"  Details: {result['details']}")