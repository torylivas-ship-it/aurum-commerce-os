#!/usr/bin/env bash
# Aurum Commerce OS — First-time setup script
set -e

BOLD="\e[1m"
GREEN="\e[32m"
YELLOW="\e[33m"
CYAN="\e[36m"
RESET="\e[0m"

cd "$(dirname "$0")/.."

echo -e "\n${BOLD}${CYAN}⬡  Aurum Commerce OS — Setup${RESET}\n"

# 1. Check .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo -e "${YELLOW}Created .env from .env.example — edit it now with your keys.${RESET}"
  echo -e "Required: POSTGRES_PASSWORD, ANTHROPIC_API_KEY (fallback), SHOPIFY_STORES"
fi

# 2. Install Python deps
echo -e "\n${BOLD}Installing Python dependencies...${RESET}"
pip install -r requirements.txt -q

# 3. Install dashboard deps
echo -e "\n${BOLD}Installing dashboard dependencies...${RESET}"
cd dashboard && npm install --silent && cd ..

# 4. Start infrastructure with Docker
echo -e "\n${BOLD}Starting infrastructure (PostgreSQL, Redis, ChromaDB)...${RESET}"
docker compose up -d postgres redis chromadb
sleep 5

# 5. Run migrations
echo -e "\n${BOLD}Running database migrations...${RESET}"
PYTHONPATH=. alembic upgrade head

# 6. Check Ollama
echo -e "\n${BOLD}Checking Ollama (local LLM)...${RESET}"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo -e "${GREEN}Ollama is running.${RESET}"
  echo -e "Recommended models for DGX Spark:"
  echo -e "  ollama pull llama3.1:70b   # Primary reasoning model"
  echo -e "  ollama pull llama3.2:3b    # Fast model for quick tasks"
  echo -e "  ollama pull nomic-embed-text  # Embeddings"
  echo -e "  ollama pull llava:13b      # Vision model"
else
  echo -e "${YELLOW}Ollama not running at localhost:11434.${RESET}"
  echo -e "Install: curl -fsSL https://ollama.com/install.sh | sh"
  echo -e "Then:    ollama serve"
fi

echo -e "\n${GREEN}${BOLD}Setup complete!${RESET}"
echo -e ""
echo -e "Start the full stack:     ${CYAN}make up${RESET}"
echo -e "Start API only:           ${CYAN}make dev-local${RESET}"
echo -e "Start dashboard:          ${CYAN}cd dashboard && npm run dev${RESET}"
echo -e "Run morning brief:        ${CYAN}make brief${RESET}"
echo -e "Trigger product discovery:${CYAN}make run-agent agent=product_discovery${RESET}"
echo -e "Open dashboard:           ${CYAN}http://localhost:3000${RESET}"
echo -e "Open API docs:            ${CYAN}http://localhost:8000/docs${RESET}"
echo -e "Open task monitor:        ${CYAN}http://localhost:5555${RESET}"
echo ""
