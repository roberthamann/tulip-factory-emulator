#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  FACTORY HYBRID — START ALL SERVICES
#  Factory Sim → OPC UA :4840 → Node.js Bridge :4841 → Docker →
#  Connector Host → Tulip Cloud
#  + MQTT (Mosquitto) + Node-RED
# ═══════════════════════════════════════════════════════════════════

set -e
GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  FACTORY HYBRID — STARTUP SEQUENCE${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

# ─────────────────────────────────────────────────────────────────
#  PREFLIGHT CHECKS
# ─────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}▸ Preflight checks...${NC}"
FAIL=0

# Python
if ! command -v python3 &>/dev/null; then
  echo -e "${RED}  ✗ python3 not found${NC}"; FAIL=1
else
  echo -e "${GREEN}  ✓ python3 $(python3 --version 2>&1 | awk '{print $2}')${NC}"
fi

# Virtual environment
if [ ! -f "venv/bin/python3" ]; then
  echo -e "${RED}  ✗ venv not found — run: python3 -m venv venv && pip install -r requirements.txt${NC}"; FAIL=1
  VENV_PY="python3"
else
  echo -e "${GREEN}  ✓ venv exists${NC}"
  source venv/bin/activate
  VENV_PY="venv/bin/python3"
fi

# Python dependencies
for pkg in asyncua aiohttp fastapi uvicorn websockets paho.mqtt; do
  if ! $VENV_PY -c "import $pkg" 2>/dev/null; then
    echo -e "${RED}  ✗ Python package '$pkg' missing — run: pip install -r requirements.txt${NC}"; FAIL=1
  else
    echo -e "${GREEN}  ✓ $pkg${NC}"
  fi
done

# Node.js
if ! command -v node &>/dev/null; then
  echo -e "${RED}  ✗ node not found${NC}"; FAIL=1
else
  echo -e "${GREEN}  ✓ node $(node --version)${NC}"
fi

# Node dependencies (for OPC UA bridge)
if [ -d "opcua-bridge" ] && [ ! -d "opcua-bridge/node_modules" ]; then
  echo -e "${YELLOW}  ⚠ opcua-bridge/node_modules missing — running npm install${NC}"
  (cd opcua-bridge && npm install)
fi
if [ -d "opcua-bridge/node_modules/node-opcua" ]; then
  echo -e "${GREEN}  ✓ node-opcua${NC}"
elif [ -d "opcua-bridge" ]; then
  echo -e "${RED}  ✗ node-opcua missing in opcua-bridge/${NC}"; FAIL=1
fi

# Colima / Docker
if command -v colima &>/dev/null; then
  if colima status 2>&1 | grep -q "colima is running"; then
    echo -e "${GREEN}  ✓ Colima running${NC}"
  else
    echo -e "${YELLOW}  ⚠ Colima not running — starting...${NC}"
    colima start
    sleep 3
  fi
elif command -v docker &>/dev/null; then
  echo -e "${GREEN}  ✓ Docker available${NC}"
else
  echo -e "${RED}  ✗ Neither Colima nor Docker found${NC}"; FAIL=1
fi

if ! command -v docker &>/dev/null; then
  echo -e "${RED}  ✗ docker CLI not found${NC}"; FAIL=1
else
  echo -e "${GREEN}  ✓ docker $(docker --version | awk '{print $3}' | tr -d ',')${NC}"
fi

if [ $FAIL -ne 0 ]; then
  echo -e "\n${RED}Preflight failed — fix the above and retry.${NC}"
  exit 1
fi

echo -e "${GREEN}▸ All preflight checks passed!${NC}\n"

# ─────────────────────────────────────────────────────────────────
#  CLEANUP — kill previous instances
# ─────────────────────────────────────────────────────────────────
echo -e "${YELLOW}▸ Cleaning up previous instances...${NC}"
pkill -f "python3.*main.py" 2>/dev/null || true
pkill -f "Python.*main.py" 2>/dev/null || true
pkill -f "node.*bridge" 2>/dev/null || true
sleep 1

# ─────────────────────────────────────────────────────────────────
#  1. MOSQUITTO (MQTT Broker)
# ─────────────────────────────────────────────────────────────────
echo -e "${CYAN}▸ [1/5] Mosquitto MQTT Broker${NC}"
if docker ps --format '{{.Names}}' | grep -q '^mosquitto$'; then
  echo -e "${GREEN}  ✓ Already running${NC}"
elif docker ps -a --format '{{.Names}}' | grep -q '^mosquitto$'; then
  echo -e "${YELLOW}  ⚠ Container stopped — restarting${NC}"
  docker start mosquitto
  echo -e "${GREEN}  ✓ Restarted on :1883${NC}"
else
  docker run -d \
    --name mosquitto \
    -p 1883:1883 \
    -p 9001:9001 \
    eclipse-mosquitto:2 \
    mosquitto -c /mosquitto-no-auth.conf
  echo -e "${GREEN}  ✓ Started on :1883${NC}"
fi

# ─────────────────────────────────────────────────────────────────
#  2. NODE-RED
# ─────────────────────────────────────────────────────────────────
echo -e "${CYAN}▸ [2/5] Node-RED${NC}"
if docker ps --format '{{.Names}}' | grep -q '^nodered$'; then
  echo -e "${GREEN}  ✓ Already running${NC}"
elif docker ps -a --format '{{.Names}}' | grep -q '^nodered$'; then
  echo -e "${YELLOW}  ⚠ Container stopped — restarting${NC}"
  docker start nodered
  echo -e "${GREEN}  ✓ Restarted on :1880${NC}"
else
  docker run -d \
    --name nodered \
    -p 1880:1880 \
    -v nodered_data:/data \
    --add-host=host.docker.internal:host-gateway \
    nodered/node-red:latest
  echo -e "${GREEN}  ✓ Started on :1880${NC}"
fi

# ─────────────────────────────────────────────────────────────────
#  3. TULIP CONNECTOR HOST
# ─────────────────────────────────────────────────────────────────
echo -e "${CYAN}▸ [3/4] Tulip Connector Host (ROBERTHAMANN-CH)${NC}"
if docker ps --format '{{.Names}}' | grep -qi 'connector\|tulip'; then
  echo -e "${GREEN}  ✓ Already running${NC}"
else
  echo -e "${YELLOW}  ⚠ Connector host not detected — start manually if needed${NC}"
  echo -e "${YELLOW}    (It may use a custom container name)${NC}"
fi

# ─────────────────────────────────────────────────────────────────
#  4. FACTORY SIMULATION (Python + OPC UA + Web Dashboard)
# ─────────────────────────────────────────────────────────────────
echo -e "${CYAN}▸ [4/4] Factory Simulation${NC}"

# Create logs dir
mkdir -p logs

# Start OPC UA bridge (Node.js)
BRIDGE_PID=""
if [ -d "opcua-bridge" ]; then
  echo -e "  Starting OPC UA bridge on :4841..."
  cd opcua-bridge
  nohup node bridge.js > ../logs/opcua-bridge.log 2>&1 &
  BRIDGE_PID=$!
  cd "$DIR"
  echo -e "${GREEN}  ✓ OPC UA bridge PID $BRIDGE_PID${NC}"
  # Watchdog: restart bridge if it exits
  (
    while true; do
      sleep 15
      if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] OPC UA bridge exited — restarting..." | tee -a logs/opcua-bridge.log
        cd "$DIR/opcua-bridge"
        nohup node bridge.js >> "$DIR/logs/opcua-bridge.log" 2>&1 &
        BRIDGE_PID=$!
        cd "$DIR"
        echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] Restarted as PID $BRIDGE_PID" | tee -a logs/opcua-bridge.log
      fi
    done
  ) &
else
  echo -e "${YELLOW}  ⚠ opcua-bridge/ not found — skipping Node.js bridge${NC}"
fi

# Start Python factory sim (OPC UA :4840 + Web :3000)
echo -e "  Starting factory sim on :3000 (OPC UA :4840)..."
nohup venv/bin/python3 main.py > logs/factory-sim.log 2>&1 &
SIM_PID=$!
echo -e "${GREEN}  ✓ Factory sim PID $SIM_PID${NC}"
# Watchdog: restart sim if it exits
(
  while true; do
    sleep 15
    if ! kill -0 "$SIM_PID" 2>/dev/null; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] Factory sim exited — restarting..." | tee -a logs/factory-sim.log
      cd "$DIR"
      nohup venv/bin/python3 main.py >> logs/factory-sim.log 2>&1 &
      SIM_PID=$!
      echo "$(date '+%Y-%m-%d %H:%M:%S') [watchdog] Restarted as PID $SIM_PID" | tee -a logs/factory-sim.log
    fi
  done
) &

# ─────────────────────────────────────────────────────────────────
#  WAIT FOR SERVICES
# ─────────────────────────────────────────────────────────────────
echo -e "\n${YELLOW}▸ Waiting for services...${NC}"
sleep 3

# Health checks
echo -e "${CYAN}▸ Health checks:${NC}"

# Factory sim
if curl -s http://localhost:3000/api/plant > /dev/null 2>&1; then
  echo -e "${GREEN}  ✓ Factory Sim        http://localhost:3000${NC}"
else
  echo -e "${RED}  ✗ Factory Sim not responding on :3000${NC}"
fi

# MQTT
if docker ps --format '{{.Names}}' | grep -q '^mosquitto$'; then
  echo -e "${GREEN}  ✓ Mosquitto MQTT     localhost:1883${NC}"
else
  echo -e "${RED}  ✗ Mosquitto not running${NC}"
fi

# Node-RED
if curl -s http://localhost:1880 > /dev/null 2>&1; then
  echo -e "${GREEN}  ✓ Node-RED           http://localhost:1880${NC}"
else
  echo -e "${YELLOW}  ⚠ Node-RED starting  http://localhost:1880 (may need a moment)${NC}"
fi

# Tulip Connector Host (user-managed)
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qi 'connector\|tulip'; then
  CONNECTOR_NAME=$(docker ps --format '{{.Names}}' | grep -i 'connector\|tulip' | head -1)
  echo -e "${GREEN}  ✓ Tulip Connector    (${CONNECTOR_NAME})${NC}"
else
  echo -e "${YELLOW}  ⚠ Tulip Connector    not detected — start your connector host manually${NC}"
fi

# Dashboard
echo -e "\n${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  🎮 GAME:       http://localhost:3000${NC}"
echo -e "${GREEN}  🔧 NODE-RED:   http://localhost:1880${NC}"
echo -e "${GREEN}  📊 NR DASH:    http://localhost:1880/dashboard${NC}"
echo -e "${GREEN}  📡 MQTT:       localhost:1883${NC}"
echo -e "${GREEN}  🏭 OPC UA SIM: opc.tcp://localhost:4840${NC}"
echo -e "${GREEN}  🌉 OPC BRIDGE: opc.tcp://localhost:4841${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "\n${YELLOW}  Logs: tail -f logs/factory-sim.log${NC}"
echo -e "${YELLOW}        tail -f logs/opcua-bridge.log${NC}"
echo -e "${YELLOW}  Stop: pkill -f main.py && docker stop mosquitto nodered${NC}\n"