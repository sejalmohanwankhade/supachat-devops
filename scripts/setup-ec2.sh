#!/bin/bash
# SupaChat EC2 Bootstrap Script
# Run once on a fresh Ubuntu 24.04 EC2 instance
# Usage: curl -sL https://raw.githubusercontent.com/you/supachat/main/scripts/setup-ec2.sh | bash

set -euo pipefail
BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${BLUE}[SETUP]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

log "Starting SupaChat EC2 setup..."

# ── 1. System Update ──────────────────────────────────────────────────────────
log "Updating system packages..."
sudo apt-get update -qq && sudo apt-get upgrade -y -qq
ok "System updated"

# ── 2. Docker ─────────────────────────────────────────────────────────────────
log "Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker ubuntu
    ok "Docker installed"
else
    ok "Docker already installed"
fi

# ── 3. Docker Compose ─────────────────────────────────────────────────────────
log "Installing Docker Compose..."
if ! docker compose version &>/dev/null; then
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | cut -d'"' -f4)
    sudo curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
        -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    ok "Docker Compose installed: $COMPOSE_VERSION"
else
    ok "Docker Compose already installed"
fi

# ── 4. Git & utilities ────────────────────────────────────────────────────────
log "Installing utilities..."
sudo apt-get install -y -qq git curl wget htop python3-pip jq
ok "Utilities installed"

# ── 5. Clone repo ─────────────────────────────────────────────────────────────
log "Setting up application..."
REPO_URL="${REPO_URL:-https://github.com/YOUR_USERNAME/supachat.git}"
APP_DIR="/opt/supachat"

if [ ! -d "$APP_DIR" ]; then
    sudo git clone "$REPO_URL" "$APP_DIR"
    sudo chown -R ubuntu:ubuntu "$APP_DIR"
    ok "Repo cloned to $APP_DIR"
else
    cd "$APP_DIR" && git pull origin main
    ok "Repo updated"
fi

# ── 6. Environment ────────────────────────────────────────────────────────────
log "Setting up environment..."
cd "$APP_DIR"
if [ ! -f .env ]; then
    cp .env.example .env
    warn "Created .env from .env.example — EDIT IT before starting!"
fi

# ── 7. Firewall ───────────────────────────────────────────────────────────────
log "Configuring firewall..."
sudo ufw --force enable
sudo ufw allow 22/tcp     # SSH
sudo ufw allow 80/tcp     # HTTP
sudo ufw allow 443/tcp    # HTTPS
sudo ufw allow 3001/tcp   # Grafana
sudo ufw allow 9090/tcp   # Prometheus (restrict in prod)
ok "Firewall configured"

# ── 8. Systemd service ────────────────────────────────────────────────────────
log "Installing systemd service..."
cat > /tmp/supachat.service << 'EOF'
[Unit]
Description=SupaChat Application Stack
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/supachat
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=300
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF
sudo mv /tmp/supachat.service /etc/systemd/system/supachat.service
sudo systemctl daemon-reload
sudo systemctl enable supachat
ok "Systemd service installed (auto-starts on reboot)"

# ── 9. DevOps agent ───────────────────────────────────────────────────────────
log "Setting up DevOps agent..."
pip3 install anthropic --quiet
sudo ln -sf "$APP_DIR/devops-agent/devops_agent.py" /usr/local/bin/supachat-agent
sudo chmod +x "$APP_DIR/devops-agent/devops_agent.py"
ok "DevOps agent available as 'supachat-agent'"

# ── 10. Log rotation ─────────────────────────────────────────────────────────
log "Configuring log rotation..."
cat | sudo tee /etc/logrotate.d/docker-supachat > /dev/null << 'EOF'
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    size 50M
    missingok
    delaycompress
    copytruncate
}
EOF
ok "Log rotation configured"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  ✅ SupaChat EC2 Setup Complete!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Edit /opt/supachat/.env with your secrets"
echo "  2. cd /opt/supachat && docker compose up -d"
echo "  3. Visit http://$(curl -s ifconfig.me)"
echo ""
echo "Useful commands:"
echo "  supachat-agent health    — check system health"
echo "  supachat-agent logs      — analyze logs"
echo "  supachat-agent chat      — interactive AI ops"
echo ""
