#!/usr/bin/env bash
# Aurum Commerce OS — Stop everything
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$DIR/.pids"

G="\e[32m" Y="\e[33m" R="\e[31m" B="\e[1m" X="\e[0m"

echo -e "\n${B}⬡  Aurum Commerce OS — Stopping${X}\n"

# Kill tracked PIDs
if [ -f "$PIDFILE" ]; then
  while read -r pid; do
    if kill "$pid" 2>/dev/null; then
      echo -e "  ${G}✓${X} Stopped PID $pid"
    fi
  done < "$PIDFILE"
  rm -f "$PIDFILE"
fi

# Belt-and-suspenders: kill by name too
pkill -f "uvicorn api.main" 2>/dev/null && echo -e "  ${G}✓${X} Stopped API" || true
pkill -f "next-server\|next dev" 2>/dev/null && echo -e "  ${G}✓${X} Stopped Dashboard" || true

# Stop Docker services
echo -e "\n  Stopping infrastructure..."
cd "$DIR"
docker compose stop postgres redis chromadb 2>&1 | grep -E "Stopping|Stopped" | sed 's/^/  /' || true

echo -e "\n${G}All services stopped.${X}\n"
echo -e "  Restart with: ${Y}./start.sh${X}\n"
