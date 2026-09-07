#!/bin/bash
# start_memecoin.sh - Iniciar Memecoin Agent en tmux

SESSION="memecoin"
DIR="/Users/gerardo/openclaw-workspace/memecoins"

# Crear sesión si no existe
if ! tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux new-session -d -s "$SESSION"
fi

# Crear ventanas si no existen
tmux new-window -t "$SESSION" -n "streaming" "cd $DIR && python scripts/stream_onchain_polling.py" 2>/dev/null || true
tmux new-window -t "$SESSION" -n "sniper" "cd $DIR && python agents/sniper_engine.py" 2>/dev/null || true
tmux new-window -t "$SESSION" -n "risk" "cd $DIR && python agents/risk_filter.py" 2>/dev/null || true
tmux new-window -t "$SESSION" -n "research" "cd $DIR && python agents/research_engine.py" 2>/dev/null || true
tmux new-window -t "$SESSION" -n "execution" "cd $DIR && python agents/execution_engine.py" 2>/dev/null || true
tmux new-window -t "$SESSION" -n "whale" "cd $DIR && python agents/whale_tracker.py" 2>/dev/null || true
tmux new-window -t "$SESSION" -n "telegram" "cd $DIR && python scripts/telegram_bot.py" 2>/dev/null || true
tmux new-window -t "$SESSION" -n "logs" "cd $DIR && tail -f logs/*.log" 2>/dev/null || true

# Listar ventanas
echo "Ventanas creadas:"
tmux list-windows -t "$SESSION"

# Conectarse a la sesión
echo ""
echo "Conectarte con: tmux attach-session -t $SESSION"
echo "Comandos tmux:"
echo "  Ctrl+B, n - Siguiente ventana"
echo "  Ctrl+B, p - Ventana anterior"
echo "  Ctrl+B, & - Cerrar ventana"
echo "  Ctrl+B, D - Desconectarse (dejar corriendo)"