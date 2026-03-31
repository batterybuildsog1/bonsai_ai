#!/bin/bash
# ============================================================================
# start-tunnel.sh
# Start the Cloudflare tunnel for the Bonsai BIM Viewer
#
# Prerequisites:
#   - Run setup-cloudflare-tunnel.sh first (one-time)
#   - Run serve-bonsai-viewer.sh in another terminal (viewer + chat proxy)
#
# Usage:
#   ./scripts/start-tunnel.sh          # start tunnel
#   ./scripts/start-tunnel.sh --check  # verify config without starting
#   ./scripts/start-tunnel.sh --stop   # stop tunnel (if running in background)
# ============================================================================

set -euo pipefail

TUNNEL_NAME="bonsai-viewer"
CONFIG_FILE="$HOME/.cloudflared/config.yml"
PID_FILE="/tmp/bonsai-tunnel.pid"

# ---------------------------------------------------------------------------
# --check: verify everything is ready
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--check" ]; then
  echo "Checking Bonsai tunnel readiness..."
  echo ""

  # cloudflared installed?
  if ! command -v cloudflared &>/dev/null; then
    echo "  [FAIL] cloudflared not installed"
    echo "         Run: brew install cloudflare/cloudflare/cloudflared"
    exit 1
  else
    echo "  [OK]   cloudflared $(cloudflared --version 2>&1 | head -1)"
  fi

  # Authenticated?
  if [ -f "$HOME/.cloudflared/cert.pem" ]; then
    echo "  [OK]   Authenticated (cert.pem exists)"
  else
    echo "  [FAIL] Not authenticated. Run: ./scripts/setup-cloudflare-tunnel.sh"
    exit 1
  fi

  # Config exists?
  if [ -f "$CONFIG_FILE" ]; then
    echo "  [OK]   Config exists: $CONFIG_FILE"
  else
    echo "  [FAIL] No config. Run: ./scripts/setup-cloudflare-tunnel.sh <domain>"
    exit 1
  fi

  # Tunnel exists?
  if cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    echo "  [OK]   Tunnel '$TUNNEL_NAME' exists"
  else
    echo "  [FAIL] Tunnel '$TUNNEL_NAME' not found. Run setup script."
    exit 1
  fi

  # Local services running?
  if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 2>/dev/null | grep -q "200"; then
    echo "  [OK]   Viewer running on :5173"
  else
    echo "  [WARN] Viewer not detected on :5173"
    echo "         Run: ./scripts/serve-bonsai-viewer.sh"
  fi

  if curl -s -o /dev/null http://localhost:5174/models 2>/dev/null; then
    echo "  [OK]   Chat proxy running on :5174"
  else
    echo "  [WARN] Chat proxy not detected on :5174"
    echo "         Run: ./scripts/serve-bonsai-viewer.sh"
  fi

  echo ""
  echo "Ready to start. Run: ./scripts/start-tunnel.sh"
  exit 0
fi

# ---------------------------------------------------------------------------
# --stop: kill background tunnel
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--stop" ]; then
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "Stopping tunnel (PID $PID)..."
      kill "$PID"
      rm -f "$PID_FILE"
      echo "Tunnel stopped."
    else
      echo "Tunnel process $PID not running. Cleaning up PID file."
      rm -f "$PID_FILE"
    fi
  else
    echo "No PID file found. Tunnel may not be running."
    echo "To kill manually: pkill -f 'cloudflared tunnel run'"
  fi
  exit 0
fi

# ---------------------------------------------------------------------------
# --background: run in background
# ---------------------------------------------------------------------------
if [ "${1:-}" = "--background" ]; then
  echo "Starting Bonsai tunnel in background..."
  cloudflared tunnel --config "$CONFIG_FILE" run "$TUNNEL_NAME" &
  echo $! > "$PID_FILE"
  echo "Tunnel running (PID $(cat "$PID_FILE"))."
  echo "Stop with: ./scripts/start-tunnel.sh --stop"
  exit 0
fi

# ---------------------------------------------------------------------------
# Default: run in foreground
# ---------------------------------------------------------------------------
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Error: No tunnel config found at $CONFIG_FILE"
  echo "Run setup first: ./scripts/setup-cloudflare-tunnel.sh <your-domain>"
  exit 1
fi

echo "============================================"
echo "  Bonsai BIM Viewer - Cloudflare Tunnel"
echo "============================================"
echo ""
echo "Starting tunnel '$TUNNEL_NAME'..."
echo "Press Ctrl+C to stop."
echo ""

# Run the tunnel (foreground, logs to stdout)
exec cloudflared tunnel --config "$CONFIG_FILE" run "$TUNNEL_NAME"
