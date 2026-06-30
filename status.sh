#!/usr/bin/env bash
# Aurum Commerce OS — Show live status
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

G="\e[32m" Y="\e[33m" R="\e[31m" C="\e[36m" B="\e[1m" X="\e[0m"

check() {
  local name="$1" url="$2"
  local code
  code=$(curl -so /dev/null -w "%{http_code}" --connect-timeout 2 "$url" 2>/dev/null || echo "000")
  if [[ "$code" =~ ^(200|307)$ ]]; then
    echo -e "  ${G}●${X} ${B}$name${X}  ${C}$url${X}"
  else
    echo -e "  ${R}●${X} ${B}$name${X}  (not responding)"
  fi
}

echo -e "\n${B}⬡  Aurum Commerce OS — Status${X}\n"

# Services
check "Dashboard  " "http://localhost:3000"
check "API        " "http://localhost:8000/health"
check "Ollama     " "http://localhost:11434/api/tags"
check "ChromaDB   " "http://localhost:8001/api/v2/heartbeat"

# Docker
echo ""
docker compose ps 2>/dev/null | tail -n +2 | while read -r line; do
  name=$(echo "$line" | awk '{print $1}')
  status=$(echo "$line" | grep -o 'Up [^)]*' | head -1)
  if echo "$line" | grep -q "(healthy)\|Up"; then
    echo -e "  ${G}●${X} $name  $status"
  else
    echo -e "  ${R}●${X} $name  (down)"
  fi
done

# Business metrics (if API is up)
echo ""
SUMMARY=$(curl -sf http://localhost:8000/api/v1/dashboard/summary 2>/dev/null)
if [ -n "$SUMMARY" ]; then
  echo -e "${B}  Business Metrics${X}"
  echo "$SUMMARY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
pipe = d['pipeline']
alerts = d['alerts']
ops = d.get('top_opportunities', [])
print(f\"  Discovered: {pipe['discovered']}  |  Pending Approval: {pipe['pending_approval']}  |  Launched: {pipe['launched']}\")
if alerts['critical']:   print(f\"\033[31m  ! {alerts['critical']} CRITICAL alert(s)\033[0m\")
if alerts['warning']:    print(f\"\033[33m  ! {alerts['warning']} warning alert(s)\033[0m\")
if ops:
    best = ops[0]
    print(f\"  Top opportunity: {best['name']} (score {best['opportunity_score']:.0f}, {best['gross_margin']*100:.0f}% margin)\")
" 2>/dev/null
fi

echo ""
