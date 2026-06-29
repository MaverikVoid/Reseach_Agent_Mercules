#!/bin/bash
# ============================================================
# Oracle Cloud Free Tier — Server Setup Script
# Provisions the Research Idea Evaluator orchestrator
# ============================================================
set -euo pipefail

echo "=== Research Idea Evaluator — Server Setup ==="

# ── 1. System update ───────────────────────────────────────────
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# ── 2. Install Docker ─────────────────────────────────────────
echo "[2/8] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    sudo systemctl enable --now docker
fi

# Install Docker Compose plugin
sudo apt install -y docker-compose-plugin

# ── 3. Install Python 3.11+ ───────────────────────────────────
echo "[3/8] Installing Python..."
sudo apt install -y python3 python3-pip python3-venv

# ── 4. Create orchestrator user and directory ──────────────────
echo "[4/8] Creating orchestrator user..."
sudo useradd -r -m -d /opt/orchestrator -s /bin/bash orchestrator || true
sudo usermod -aG docker orchestrator

# ── 5. Clone/copy project ─────────────────────────────────────
echo "[5/8] Setting up project..."
PROJ_DIR="/opt/orchestrator"

# If deploying from git:
# sudo -u orchestrator git clone <your-repo-url> $PROJ_DIR

# Create venv and install deps
sudo -u orchestrator python3 -m venv $PROJ_DIR/venv
sudo -u orchestrator $PROJ_DIR/venv/bin/pip install --upgrade pip
sudo -u orchestrator $PROJ_DIR/venv/bin/pip install -r $PROJ_DIR/requirements.txt

# ── 6. Start Postgres with pgvector ───────────────────────────
echo "[6/8] Starting Postgres..."
cd $PROJ_DIR/deployment
sudo docker compose up -d

# Wait for Postgres to be ready
echo "Waiting for Postgres..."
sleep 10

# ── 7. Copy .env ──────────────────────────────────────────────
echo "[7/8] Checking .env..."
if [ ! -f "$PROJ_DIR/.env" ]; then
    echo "WARNING: .env file not found at $PROJ_DIR/.env"
    echo "Please create it with your API keys before starting the service."
fi

# ── 8. Install and start systemd service ──────────────────────
echo "[8/8] Installing systemd service..."
sudo cp $PROJ_DIR/deployment/orchestrator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orchestrator
sudo systemctl start orchestrator

echo ""
echo "=== Setup complete! ==="
echo "Check status: sudo systemctl status orchestrator"
echo "View logs:    sudo journalctl -u orchestrator -f"
echo ""
echo "IMPORTANT: Make sure .env is configured at $PROJ_DIR/.env"
echo "  Required: OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN"
echo "  Optional: KAGGLE_USERNAME, KAGGLE_KEY, RUNPOD_API_KEY"
