#!/bin/bash
# Start the Bonsai BIM viewer: chat proxy + Vite dev server
# Usage: ./scripts/serve-bonsai-viewer.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Starting Bonsai BIM Viewer..."
echo "  Chat proxy: http://127.0.0.1:5174"
echo "  Viewer:     http://127.0.0.1:5173"
echo ""

# Start chat proxy in background
node "$PROJECT_DIR/viewer/src/chat-proxy.js" &
PROXY_PID=$!

# Cleanup on exit
cleanup() {
  echo ""
  echo "Shutting down..."
  kill $PROXY_PID 2>/dev/null
  exit 0
}
trap cleanup SIGINT SIGTERM

# Start Vite dev server
cd "$PROJECT_DIR/viewer" && npx vite --host 127.0.0.1 --port 5173
