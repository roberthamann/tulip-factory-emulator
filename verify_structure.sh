#!/bin/bash
echo "=== ACME Factory Structure Verification ==="
echo ""

PASS=0
FAIL=0

check() {
  if [ -e "$1" ]; then
    echo "  ✅  $1"
    ((PASS++))
  else
    echo "  ❌  $1  — MISSING"
    ((FAIL++))
  fi
}

echo "--- Config ---"
check "config/plant_config.yaml"

echo "--- Sim / Machines ---"
check "sim/__init__.py"
check "sim/plant.py"
check "sim/opcua_server.py"
check "sim/mqtt_publisher.py"
check "sim/raw_publisher.py"
check "sim/ai_brain.py"
check "sim/machines/__init__.py"
check "sim/machines/base.py"
check "sim/machines/types.py"

echo "--- Dashboard ---"
check "dashboard/__init__.py"
check "dashboard/server.py"
check "dashboard/static/index.html"

echo "--- Node-RED ---"
check "nodered/flows.json"
check "nodered/settings.js"
check "nodered/package.json"

echo "--- Root ---"
check "main.py"
check "requirements.txt"
check "mosquitto.conf"
check "docker-compose.yml"
check "CLAUDE.md"

echo ""
echo "=== Results: $PASS passed, $FAIL missing ==="
if [ $FAIL -eq 0 ]; then
  echo "🎉 All 20 files accounted for!"
else
  echo "⚠️  Fix the $FAIL missing file(s) above before proceeding."
fi
