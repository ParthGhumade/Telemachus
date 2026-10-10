#!/bin/bash
set -e

echo "=================================================="
echo " Starting Telemachus Energy Intelligence Service  "
echo "=================================================="

# Ensure cloudflared is present (auto-download fallback if image not yet rebuilt)
if ! command -v cloudflared &> /dev/null; then
    echo "cloudflared binary not found in container, downloading..."
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then CF_ARCH="amd64"; elif [ "$ARCH" = "aarch64" ]; then CF_ARCH="arm64"; else CF_ARCH="amd64"; fi
    curl -sL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" -o /usr/local/bin/cloudflared 2>/dev/null || true
    chmod +x /usr/local/bin/cloudflared 2>/dev/null || true
fi

# Run dataset check, download from drive if missing, unzip, DuckDB init & Chroma indexing
python backend/setup_dataset.py

echo "=================================================="
echo " Launching Telemachus Uvicorn Server...          "
echo "=================================================="

# Launch uvicorn in background
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Wait for backend API to be healthy
echo "Waiting for backend API to initialize..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Launch Cloudflare Tunnel in background if cloudflared is available
CF_PID=""
CF_URL=""
if command -v cloudflared &> /dev/null; then
    echo "Starting Cloudflare Tunnel to host frontend & API..."
    rm -f /tmp/cloudflared.log /app/tunnel_url.txt
    cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate > /tmp/cloudflared.log 2>&1 &
    CF_PID=$!

    # Wait and extract temporary trycloudflare.com URL
    for i in {1..30}; do
        CF_URL=$(grep -o 'https://[-a-zA-Z0-9.]*trycloudflare.com' /tmp/cloudflared.log | head -n 1 || true)
        if [ -n "$CF_URL" ]; then
            break
        fi
        sleep 1
    done
fi

echo ""
echo "=================================================================="
if [ -n "$CF_URL" ]; then
    echo " 🚀 TELEMACHUS PUBLIC CLOUDFLARE TUNNEL URL:"
    echo "    $CF_URL"
    echo ""
    echo " 📱 Open the URL above in your browser to access the live app!"
    echo "$CF_URL" > /app/tunnel_url.txt 2>/dev/null || true
    echo "$CF_URL" > /tmp/tunnel_url.txt 2>/dev/null || true
else
    echo " ℹ️  Cloudflare Tunnel URL could not be extracted immediately."
    echo "    Check /tmp/cloudflared.log or container logs."
fi
echo " 🏠 Local URL:     http://localhost:8000"
echo " 📚 API Docs:      http://localhost:8000/docs"
echo "=================================================================="
echo ""

# Handle graceful shutdown
cleanup() {
    echo "Stopping Telemachus processes..."
    if [ -n "$CF_PID" ]; then
        kill -TERM "$CF_PID" 2>/dev/null || true
    fi
    if [ -n "$UVICORN_PID" ]; then
        kill -TERM "$UVICORN_PID" 2>/dev/null || true
        wait "$UVICORN_PID" 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGTERM SIGINT

# Keep container running by waiting for uvicorn
wait "$UVICORN_PID"
