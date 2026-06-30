#!/usr/bin/env bash
# Aurum Commerce OS — Start everything
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$DIR/.pids"
LOG_DIR="$DIR/logs"

# Colors
G="\e[32m" Y="\e[33m" C="\e[36m" R="\e[31m" B="\e[1m" X="\e[0m"

ok()   { echo -e "  ${G}✓${X} $1"; }
warn() { echo -e "  ${Y}!${X} $1"; }
fail() { echo -e "  ${R}✗${X} $1"; }
step() { echo -e "\n${B}${C}▸ $1${X}"; }

cd "$DIR"
mkdir -p "$LOG_DIR"
> "$PIDFILE"

echo -e "\n${B}⬡  Aurum Commerce OS${X}"
echo -e "    Starting all services...\n"

# ── 1. Docker infrastructure ──────────────────────────────────────────────────
step "Infrastructure (PostgreSQL · Redis · ChromaDB)"

if ! docker info &>/dev/null; then
  fail "Docker is not running. Start Docker first."
  exit 1
fi

docker compose up -d postgres redis chromadb 2>&1 | grep -E "Started|Running|healthy|error" || true

# Wait for Postgres
printf "    Waiting for PostgreSQL"
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U aurum -q 2>/dev/null; then
    echo ""
    ok "PostgreSQL healthy"
    break
  fi
  printf "."
  sleep 1
  if [ $i -eq 30 ]; then
    echo ""
    fail "PostgreSQL did not become ready in 30s"
    exit 1
  fi
done

ok "Redis ready"
ok "ChromaDB ready"

# ── 2. Database migrations ────────────────────────────────────────────────────
step "Database migrations"
PYTHONPATH="$DIR" alembic upgrade head 2>&1 | grep -E "Running upgrade|up to date" | sed 's/^/    /' || true
ok "Schema up to date"

# ── 3. FastAPI ────────────────────────────────────────────────────────────────
step "FastAPI (port 8000)"

# Kill any existing instance
pkill -f "uvicorn api.main" 2>/dev/null && sleep 0.5 || true

PYTHONPATH="$DIR" nohup uvicorn api.main:app \
  --host 0.0.0.0 --port 8000 \
  --no-access-log \
  > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!
echo "$API_PID" >> "$PIDFILE"

# Wait for API to be ready
printf "    Waiting for API"
for i in $(seq 1 20); do
  if curl -sf http://localhost:8000/health &>/dev/null; then
    echo ""
    ok "API ready (PID $API_PID)"
    break
  fi
  printf "."
  sleep 0.5
  if [ $i -eq 20 ]; then
    echo ""
    fail "API did not start. Check logs/api.log"
    exit 1
  fi
done

# ── 4. Dashboard ──────────────────────────────────────────────────────────────
step "Dashboard (port 3000)"

# Kill any existing instance
pkill -f "next-server\|next dev" 2>/dev/null && sleep 0.5 || true

cd "$DIR/dashboard"
NEXT_PUBLIC_API_URL=http://localhost:8000 \
  nohup npm run dev \
  > "$LOG_DIR/dashboard.log" 2>&1 &
DASH_PID=$!
echo "$DASH_PID" >> "$PIDFILE"
cd "$DIR"

# Wait for dashboard
printf "    Waiting for Dashboard"
for i in $(seq 1 30); do
  STATUS=$(curl -so /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")
  if [[ "$STATUS" =~ ^(200|307)$ ]]; then
    echo ""
    ok "Dashboard ready (PID $DASH_PID)"
    break
  fi
  printf "."
  sleep 1
  if [ $i -eq 30 ]; then
    echo ""
    warn "Dashboard taking longer than expected. Check logs/dashboard.log"
  fi
done

# ── 5. Ollama check ───────────────────────────────────────────────────────────
step "Ollama (local LLM)"
if curl -sf http://localhost:11434/api/tags &>/dev/null; then
  MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; d=json.load(sys.stdin); print(', '.join(m['name'] for m in d.get('models',[])))" 2>/dev/null)
  ok "Ollama running — models: $MODELS"
else
  warn "Ollama not detected at localhost:11434"
  warn "Start it with:  ollama serve"
  warn "LLM calls will fail until Ollama is running"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo -e "\n${B}${G}✓  Aurum Commerce OS is running${X}\n"
echo -e "  ${B}Dashboard:${X}   ${C}http://localhost:3000${X}"
echo -e "  ${B}API:${X}         ${C}http://localhost:8000${X}"
echo -e "  ${B}API Docs:${X}    ${C}http://localhost:8000/docs${X}"
echo -e "  ${B}Logs:${X}        ${C}$LOG_DIR/${X}"
echo ""
echo -e "  ${B}Stop:${X}        ${Y}./stop.sh${X}"
echo -e "  ${B}Status:${X}      ${Y}./status.sh${X}"
echo -e "  ${B}Run agent:${X}   ${Y}python scripts/run_agent.py product_discovery${X}"
echo ""
