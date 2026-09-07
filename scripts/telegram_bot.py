#!/usr/bin/env python3
"""
telegram_bot.py

Telegram Bot extendido para Memecoin Agent v3.0-ultralite-fixed

Comandos disponibles:
- /status - Estado del sistema
- /stats - Estadísticas de tokens
- /whales - Whales cualificadas
- /config - Configuración actual
- /mode <research|execution> - Cambiar modo
- /help - Ayuda

PostgreSQL - Conexión centralizada
"""

import os
import sys
import logging
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

# Configuración
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USERS = os.getenv("TELEGRAM_ALLOWED_USERS", "").split(",")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

from db import get_conn


def get_db_connection():
    """Obtener conexión a PostgreSQL."""
    return get_conn()


def is_allowed_user(user_id: str) -> bool:
    """Verificar si el usuario está permitido."""
    return user_id in TELEGRAM_ALLOWED_USERS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start."""
    user_id = str(update.effective_user.id)

    if not is_allowed_user(user_id):
        await update.message.reply_text("❌ Acceso denegado. Usuario no autorizado.")
        return

    await update.message.reply_text(
        "🤖 *Memecoin Agent v3.0-ultralite-fixed*\n\n"
        "Comandos disponibles:\n"
        "/status - Estado del sistema\n"
        "/stats - Estadísticas de tokens\n"
        "/whales - Whales cualificadas\n"
        "/config - Configuración actual\n"
        "/mode <research|execution> - Cambiar modo\n"
        "/help - Ayuda",
        parse_mode=ParseMode.MARKDOWN
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /status."""
    user_id = str(update.effective_user.id)

    if not is_allowed_user(user_id):
        await update.message.reply_text("❌ Acceso denegado.")
        return

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Contar tokens
        cursor.execute("SELECT COUNT(*) FROM tokens;")
        total_tokens = cursor.fetchone()[0]

        # Contar tokens recientes (últimas 24h)
        cursor.execute("SELECT COUNT(*) FROM tokens WHERE created_at >= NOW() - INTERVAL '24 hours';")
        recent_tokens = cursor.fetchone()[0]

        # Contar pending_trades
        cursor.execute("SELECT COUNT(*) FROM pending_trades WHERE executed = 0;")
        pending_trades = cursor.fetchone()[0]

        # Contar trades activos
        cursor.execute("SELECT COUNT(*) FROM trades WHERE status IN ('pending', 'confirmed');")
        active_trades = cursor.fetchone()[0]

        # Verificar execution_mode
        cursor.execute("SELECT value FROM agent_config WHERE key='execution_mode';")
        execution_mode = cursor.fetchone()[0]

        await update.message.reply_text(
            f"*Estado del Sistema*\n\n"
            f"Tokens totales: {total_tokens}\n"
            f"Tokens recientes (24h): {recent_tokens}\n"
            f"Pending trades: {pending_trades}\n"
            f"Trades activos: {active_trades}\n"
            f"Execution mode: {execution_mode}\n"
            f"Timestamp: {datetime.utcnow().isoformat()}",
            parse_mode=ParseMode.MARKDOWN
        )
    finally:
        conn.close()


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /stats."""
    user_id = str(update.effective_user.id)

    if not is_allowed_user(user_id):
        await update.message.reply_text("❌ Acceso denegado.")
        return

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Tokens con alta probabilidad de pump
        cursor.execute("""
            SELECT COUNT(*) FROM tokens
            WHERE prob_pump_24h > 0.70
              AND created_at >= NOW() - INTERVAL '24 hours';
        """)
        high_pump = cursor.fetchone()[0]

        # Tokens con bajo riesgo de rug
        cursor.execute("""
            SELECT COUNT(*) FROM tokens
            WHERE prob_rug_48h < 0.30
              AND created_at >= NOW() - INTERVAL '24 hours';
        """)
        low_rug = cursor.fetchone()[0]

        # Whales cualificadas
        cursor.execute("SELECT COUNT(*) FROM whales WHERE label = 'whale' AND win_rate > 0.15;")
        whales = cursor.fetchone()[0]

        await update.message.reply_text(
            f"*Estadísticas de Tokens*\n\n"
            f"Tokens con alta probabilidad de pump (>70%): {high_pump}\n"
            f"Tokens con bajo riesgo de rug (<30%): {low_rug}\n"
            f"Whales cualificadas: {whales}\n"
            f"Timestamp: {datetime.utcnow().isoformat()}",
            parse_mode=ParseMode.MARKDOWN
        )
    finally:
        conn.close()


async def whales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /whales."""
    user_id = str(update.effective_user.id)

    if not is_allowed_user(user_id):
        await update.message.reply_text("❌ Acceso denegado.")
        return

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT label, win_rate, total_trades, rug_count
            FROM whales
            WHERE label = 'whale' AND win_rate > 0.15
            ORDER BY win_rate DESC
            LIMIT 10
        """)

        whales = cursor.fetchall()

        if not whales:
            await update.message.reply_text("No hay whales cualificadas.")
            return

        message = "*Whales cualificadas*\n\n"
        for name, grad_rate, total_tokens, rug_count in whales:
            message += f"• {name}\n"
            message += f"  Graduation rate: {grad_rate:.2%}\n"
            message += f"  Total tokens: {total_tokens}\n"
            message += f"  Rug count: {rug_count}\n\n"

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    finally:
        conn.close()


async def config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /config."""
    user_id = str(update.effective_user.id)

    if not is_allowed_user(user_id):
        await update.message.reply_text("❌ Acceso denegado.")
        return

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT key, value FROM agent_config ORDER BY key;")
        config_items = cursor.fetchall()

        message = "*Configuración actual*\n\n"
        for key, value in config_items:
            message += f"{key}: {value}\n"

        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    finally:
        conn.close()


async def mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /mode <research|execution>."""
    user_id = str(update.effective_user.id)

    if not is_allowed_user(user_id):
        await update.message.reply_text("❌ Acceso denegado.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Uso: /mode <research|execution>")
        return

    new_mode = context.args[0].lower()

    if new_mode not in ["research", "execution"]:
        await update.message.reply_text("Modo inválido. Usa: research o execution")
        return

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE agent_config SET value = %s, updated_at = NOW()
            WHERE key = 'execution_mode'
        """, (new_mode,))

        conn.commit()

        await update.message.reply_text(f"✅ Modo cambiado a: {new_mode}")
    finally:
        conn.close()


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help."""
    user_id = str(update.effective_user.id)

    if not is_allowed_user(user_id):
        await update.message.reply_text("❌ Acceso denegado.")
        return

    await update.message.reply_text(
        "*Ayuda - Memecoin Agent v3.0-ultralite-fixed*\n\n"
        "Comandos disponibles:\n"
        "/start - Iniciar bot\n"
        "/status - Estado del sistema\n"
        "/stats - Estadísticas de tokens\n"
        "/whales - Whales cualificadas\n"
        "/config - Configuración actual\n"
        "/mode <research|execution> - Cambiar modo\n"
        "/help - Ayuda\n\n"
        "Modos:\n"
        "- research: Solo alertas y análisis (por defecto)\n"
        "- execution: Ejecutar trades reales (¡CUIDADO!)",
        parse_mode=ParseMode.MARKDOWN
    )


def main():
    """Función principal."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no configurada")
        return 1

    logger.info("=== Telegram Bot iniciado ===")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("whales", whales))
    application.add_handler(CommandHandler("config", config))
    application.add_handler(CommandHandler("mode", mode))
    application.add_handler(CommandHandler("help", help_command))

    logger.info("Telegram Bot listo. Polling...")
    application.run_polling()

    return 0


if __name__ == "__main__":
    sys.exit(main())