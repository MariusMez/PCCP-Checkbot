#!/bin/bash
# Wrapper PCCP Comet Watch R85
# Compatible macOS et Linux.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/watch.log"
ALERT_FILE="$SCRIPT_DIR/alert_pending.json"
HEARTBEAT_FLAG="$SCRIPT_DIR/heartbeat_alert.flag"

# Rotation du log (garder 500 lignes max)
if [ -f "$LOG_FILE" ] && [ "$(wc -l < "$LOG_FILE")" -gt 500 ]; then
    tail -400 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi

echo "--- $(date -u '+%Y-%m-%d %H:%M UTC') ---" >> "$LOG_FILE"

# Trouver python3 (chercher dans les emplacements courants sur macOS/Linux)
PYTHON=$(command -v python3 \
    || echo /usr/bin/python3 \
    || echo /usr/local/bin/python3 \
    || echo /opt/homebrew/bin/python3)

if [ ! -x "$PYTHON" ]; then
    echo "[ERROR] python3 introuvable" >> "$LOG_FILE"
    exit 1
fi

# Lancer le script Python
OUTPUT=$("$PYTHON" "$SCRIPT_DIR/check_pccp.py" 2>>"$LOG_FILE")
EXIT_CODE=$?

echo "$OUTPUT" >> "$LOG_FILE"

if [ $EXIT_CODE -ne 0 ]; then
    echo "[ERROR] Script échoué (code $EXIT_CODE)" >> "$LOG_FILE"
    exit 1
fi

# Si alerte générée → poser le flag pour heartbeat OpenClaw
if [ -f "$ALERT_FILE" ]; then
    touch "$HEARTBEAT_FLAG"
    echo "[ALERT] Flag heartbeat posé" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
