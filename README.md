# SupaChat — Conversational Analytics Platform

> **Ask your blog data anything. Get charts, tables, and insights back.**

SupaChat is a production-grade full-stack application that lets users query a blog analytics PostgreSQL database in natural language. Built with FastAPI, React, Supabase, and Claude AI — fully Dockerized and deployed with a complete DevOps lifecycle.

---

## 📸 Demo

```
User: "Show top trending topics in last 30 days"
  → Bar chart: AI (45K views), ML (38K), DevOps (29K)...

User: "Plot daily views trend"
  → Area chart: 30-day time series with trend analysis

User: "Compare engagement by topic"
  → Table + bar chart: likes, comments, shares per topic
```

---

## 🏗️ Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Nginx (Port 80/443)          │
                    │   /       → Frontend                 │
                    │   /api    → Backend                  │
                    │   /ws     → WebSocket (future)       │
                    └───────────┬─────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
     ┌────────▼────────┐               ┌──────────▼────────┐
     │   React Frontend │               │  FastAPI Backend   │
     │   (Recharts UI)  │               │  (NL → SQL → Data) │
     └─────────────────┘               └──────────┬─────────┘
                                                   │
                              ┌────────────────────┼──────────────────┐
                              │                    │                  │
                    ┌─────────▼──────┐  ┌──────────▼──────┐  ┌───────▼────────┐
                    │  Supabase DB   │  │   Claude API     │  │  Prometheus     │
                    │  (PostgreSQL)  │  │  (NL→SQL+Chart)  │  │  + Grafana      │
                    └────────────────┘  └─────────────────┘  │  + Loki         │
                                                              └────────────────┘

Monitoring Stack:
  Prometheus ← scrapes ← Backend /metrics, cAdvisor, Node Exporter
  Loki       ← ships  ← Promtail (Docker logs)
  Grafana    → dashboards → CPU, Memory, Request Rate, Latency, Error Rate, Logs
```

---

## 📦 Project Structure

```
supachat/
├── frontend/                  # React app (CRA)
│   ├── src/
│   │   └── App.js             # Main component (chat + charts + tables)
│   ├── Dockerfile             # Multi-stage build
│   └── nginx-spa.conf         # SPA nginx config
│
├── backend/                   # FastAPI app
│   ├── main.py                # API + NL→SQL engine + Prometheus metrics
│   ├── requirements.txt
│   └── Dockerfile
│
├── nginx/                     # Reverse proxy
│   ├── nginx.conf             # Main config (gzip, rate limiting, headers)
│   └── conf.d/
│       └── supachat.conf      # Site config (routing, WebSocket, caching)
│
├── monitoring/
│   ├── prometheus/
│   │   ├── prometheus.yml     # Scrape configs
│   │   └── alerts.yml         # Alerting rules
│   ├── grafana/
│   │   ├── datasources.yml    # Prometheus + Loki sources
│   │   └── dashboards/
│   │       └── supachat.json  # Pre-built dashboard
│   └── loki/
│       ├── loki.yml           # Log storage config
│       └── promtail.yml       # Log shipping from Docker
│
├── devops-agent/
│   └── devops_agent.py        # AI-powered ops automation
│
├── scripts/
│   ├── setup-ec2.sh           # One-command EC2 bootstrap
│   └── supabase-schema.sql    # Database schema + seed data
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml          # Full CI/CD pipeline
│
├── docker-compose.yml         # Full stack orchestration
├── .env.example               # Environment template
└── README.md
```

---

## 🚀 Quick Start

### Option A: Demo mode (no credentials needed)

```bash
git clone https://github.com/YOUR_USERNAME/supachat.git
cd supachat
cp .env.example .env
docker compose up -d frontend backend nginx
open http://localhost
```

The app runs fully with demo data — no Supabase or API key required.

### Option B: Full mode (with Supabase + Claude)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/supachat.git
cd supachat

# 2. Create Supabase project at https://supabase.com
#    Run scripts/supabase-schema.sql in the SQL editor

# 3. Configure
cp .env.example .env
nano .env  # Fill in SUPABASE_URL, SUPABASE_ANON_KEY, ANTHROPIC_API_KEY

# 4. Start everything
docker compose up -d

# 5. Open
open http://localhost          # App
open http://localhost:3001     # Grafana (admin / changeme_in_production)
open http://localhost:9090     # Prometheus
```

---

## 🐳 Docker Details

### Services

| Service | Image | Ports | Memory Limit |
|---------|-------|-------|-------------|
| `frontend` | Built locally | (internal) | 256M |
| `backend` | Built locally | (internal) | 512M |
| `nginx` | nginx:1.27-alpine | 80, 443 | 64M |
| `prometheus` | prom/prometheus | 9090 | 512M |
| `grafana` | grafana/grafana | 3001 | 256M |
| `loki` | grafana/loki | 3100 | 256M |
| `promtail` | grafana/promtail | — | 128M |
| `node-exporter` | prom/node-exporter | — | 64M |
| `cadvisor` | gcr.io/cadvisor | — | 128M |

### Useful commands

```bash
# View all logs
docker compose logs -f

# Restart just the backend
docker compose restart backend

# Check health
curl http://localhost/health | jq

# Scale backend
docker compose up -d --scale backend=3 backend

# Stop everything
docker compose down

# Full rebuild
docker compose build --no-cache && docker compose up -d
```

---

## 🌐 Nginx Reverse Proxy

| Path | Target | Notes |
|------|--------|-------|
| `/` | frontend:80 | React SPA with fallback |
| `/api/*` | backend:8000 | 30 req/min rate limit |
| `/api/chat` | backend:8000 | 10 req/min (LLM endpoint) |
| `/health` | backend:8000 | No rate limit |
| `/metrics` | backend:8000 | LAN only |
| `/ws/*` | backend:8000 | WebSocket upgrade |

Features enabled:
- ✅ Gzip compression (level 6)
- ✅ Static asset caching (1 year, immutable)
- ✅ Security headers (X-Frame-Options, XSS Protection, etc.)
- ✅ Rate limiting (per-IP, zone-based)
- ✅ WebSocket support
- ✅ Keep-alive connections
- ✅ Request timeout tuning for LLM calls (120s)

---

## ☁️ AWS EC2 Deployment

### Instance recommendations

- **Instance type**: t3.medium (2 vCPU, 4GB RAM) minimum; t3.large for production
- **Storage**: 30GB gp3
- **OS**: Ubuntu 24.04 LTS
- **Security Group**: Allow 22 (SSH), 80 (HTTP), 443 (HTTPS), 3001 (Grafana), 9090 (Prometheus)

### One-command setup

```bash
# On your local machine
ssh ubuntu@YOUR_EC2_IP

# On the EC2 instance
curl -sL https://raw.githubusercontent.com/YOU/supachat/main/scripts/setup-ec2.sh | bash
```

### Manual deployment

```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# Clone and configure
git clone https://github.com/YOU/supachat.git /opt/supachat
cd /opt/supachat
cp .env.example .env
nano .env  # Fill in your secrets

# Start
docker compose up -d

# Verify
curl http://localhost/health
```

---

## 🔁 CI/CD Pipeline (GitHub Actions)

### Workflow: `.github/workflows/ci-cd.yml`

```
Push to main
    │
    ▼
┌───────────┐    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────┐
│  Test     │ → │  Build & Push    │ → │  Deploy to EC2   │ → │  Smoke Test  │
│  (lint,   │    │  (GHCR images,  │    │  (SSH, pull,     │    │  (health,    │
│  build)   │    │  multi-arch)    │    │  rolling update) │    │  API, UI)    │
└───────────┘    └──────────────────┘    └──────────────────┘    └──────────────┘
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `EC2_HOST` | EC2 public IP or hostname |
| `EC2_USER` | SSH user (typically `ubuntu`) |
| `EC2_SSH_KEY` | Private SSH key (PEM format) |

### Zero-downtime deployment strategy

1. Pull new images from GHCR
2. Scale backend to 2 replicas (old + new)
3. Wait 15s for new instance to be healthy
4. Scale back to 1 (old removed)
5. Update frontend
6. Nginx reload (no restart, zero downtime)
7. Health check verification
8. Auto-rollback trigger on failure

---

## 📊 Monitoring & Observability

### Grafana Dashboard

Open `http://YOUR_IP:3001` (admin / your-password)

Pre-built panels:
- 📈 Request rate (req/s)
- ❌ Error rate (%)
- ⏱️ P50 / P95 / P99 latency
- 🔌 Active connections
- 🤖 LLM processing time
- 💻 CPU usage
- 🧠 Memory usage
- 📦 Container memory per service

### Prometheus Metrics (backend)

| Metric | Type | Description |
|--------|------|-------------|
| `supachat_requests_total` | Counter | HTTP requests by method/endpoint/status |
| `supachat_request_duration_seconds` | Histogram | Request latency |
| `supachat_active_connections` | Gauge | Live connections |
| `supachat_queries_total` | Counter | NL queries by success/error |
| `supachat_llm_duration_seconds` | Histogram | Claude API latency |

### Alerting Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| BackendDown | `up == 0` for 1m | Critical |
| HighErrorRate | Error rate > 5% | Warning |
| HighP95Latency | Chat p95 > 30s | Warning |
| HighCPU | CPU > 85% for 5m | Warning |
| HighMemory | Memory > 85% for 5m | Warning |

### Log Exploration (Loki)

In Grafana → Explore → Loki:
```
# Backend errors
{container="supachat-backend"} |= "error"

# Slow queries
{container="supachat-backend"} | json | duration_ms > 5000

# All nginx 500s
{job="nginx"} | logfmt | status = "500"
```

---

## 🤖 DevOps Agent (Bonus)

An AI-powered operations CLI built on Claude:

```bash
# Install
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Run diagnostics
python devops-agent/devops_agent.py health

# Analyze logs with AI
python devops-agent/devops_agent.py logs --container supachat-backend

# RCA for a failing container
python devops-agent/devops_agent.py rca --container supachat-backend

# Explain a CI/CD failure
cat failed-job.log | python devops-agent/devops_agent.py cicd-explain

# Interactive AI ops chat
python devops-agent/devops_agent.py chat
```

### Agent capabilities

| Command | What it does |
|---------|-------------|
| `health` | Full diagnostics: containers, API, resources, recent errors, AI summary |
| `logs` | Fetches container logs + AI analysis of patterns/errors |
| `restart` | Safe restart with post-restart verification |
| `rca` | Collects inspect/logs/events/resources → AI root cause analysis |
| `cicd-explain` | Paste a GitHub Actions log → AI explains failure + fix |
| `chat` | Interactive AI chat with system context aware |

---

## 🧪 Example Queries

Try these in the chatbot:

```
"Show top trending topics in last 30 days"
"Compare article engagement by topic"
"Plot daily views trend for AI articles"
"Who are the top 5 authors by total views?"
"Show me articles with highest comment activity"
"What's the average read time per topic?"
"Show weekly publishing frequency"
"Compare views vs unique visitors over last month"
"Which topics have best comment-to-view ratio?"
```

---

## 🛠️ Tech Stack

### Frontend
- **React 18** — UI framework
- **Recharts** — bar, line, area, pie charts
- **Axios** — HTTP client
- **Custom CSS** — Space Mono + Sora fonts, dark theme

### Backend
- **FastAPI** — async Python API
- **Anthropic SDK** — Claude claude-opus-4-5 for NL→SQL
- **httpx** — async Supabase HTTP client
- **prometheus-client** — metrics export
- **structlog** — structured JSON logging
- **Uvicorn** — ASGI server

### Infrastructure
- **Docker + Docker Compose** — containerization
- **Nginx** — reverse proxy, gzip, rate limiting
- **AWS EC2** — deployment target
- **GitHub Actions** — CI/CD pipeline

### Monitoring
- **Prometheus** — metrics collection
- **Grafana** — dashboards + alerting
- **Loki** — log aggregation
- **Promtail** — Docker log shipping
- **cAdvisor** — container metrics
- **Node Exporter** — host metrics

---

## 🤝 AI Tools Used

This project was built with AI assistance throughout:

| Tool | Usage |
|------|-------|
| **Claude (claude.ai)** | Architecture design, full code generation, debugging |
| **Claude API** | Runtime NL→SQL translation, chart type selection, narrative generation |
| **DevOps Agent** | AI-powered log analysis, RCA, CI/CD failure explanation |

---

## 📋 GitHub Secrets Setup

```
Settings → Secrets → Actions:

EC2_HOST         = 54.xxx.xxx.xxx
EC2_USER         = ubuntu
EC2_SSH_KEY      = -----BEGIN RSA PRIVATE KEY-----
                   ...your key...
                   -----END RSA PRIVATE KEY-----
```

---

## 📜 License

MIT — see LICENSE

---

*Built with ❤️ for the SupaChat DevOps challenge*
## 📜 🎉 AMAZING! Everything is working!

Now Test Everything
Test 1 — Backend Health
https://supachat-devops-production.up.railway.app/health

Test 2 — Full App
https://lovely-dream-production-36ea.up.railway.app

## Test 3 — Type These Queries
# Show top trending topics in last 30 days
# Plot daily views trend
# Compare article engagement by topic
# Who are top 5 authors by total views

## 📜 Output:

<img width="955" height="381" alt="image" src="https://github.com/user-attachments/assets/201833d2-0c4b-48b3-9da4-00854aecfdc1" />


