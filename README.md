# Tulip Factory Emulator

A hybrid AI-dynamic manufacturing plant simulator that exposes real industrial protocols (OPC UA, MQTT), serves a live factory floor dashboard, and uses a local LLM (Ollama) for both an in-dashboard chat panel and an autonomous AI brain loop that drives realistic factory behavior.

---

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Functionality](#functionality)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Tulip Factory Emulator simulates a three-line manufacturing plant with 13 machines across precision machining, heavy fabrication, and CNC assembly lines. It is designed to be a realistic integration target for industrial dashboards, SCADA systems, and IoT platforms.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     main.py (entry point)               │
├────────────┬──────────────┬──────────────┬──────────────┤
│  FastAPI   │  OPC UA      │  MQTT        │  AI Brain    │
│  Dashboard │  Server      │  Publisher   │  (Ollama)    │
│  :3000     │  :4840       │  :1883       │  :11434      │
└────────────┴──────────────┴──────────────┴──────────────┘
                        │
              ┌─────────▼──────────┐
              │   Plant Simulation  │
              │  sim/plant.py       │
              │  13 machines, 3     │
              │  production lines   │
              └────────────────────┘
```

### Production Lines

| Line | Name               | Machines                                              |
|------|--------------------|-------------------------------------------------------|
| L1   | Precision Machining | MILL-L1-01, LATHE-L1-02, LATHE-L1-03, GRND-L1-04   |
| L2   | Heavy Fabrication  | GRND-L2-01, MILL-L2-02, PRESS-L2-03, DRILL-L2-04    |
| L3   | CNC Assembly       | CNC-L3-01, CNC-L3-02, MILL-L3-03, LATHE-L3-04, CONV-L3-05 |

### Key Ports

| Service    | Port  | Protocol         |
|------------|-------|------------------|
| Dashboard  | 3000  | HTTP + WebSocket |
| OPC UA     | 4840  | opc.tcp          |
| MQTT Broker| 1883  | mqtt             |
| Ollama LLM | 11434 | HTTP             |

---

## Installation

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- [Ollama](https://ollama.com/) with a model pulled (e.g. `llama3`)

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/roberthamann/tulip-factory-emulator.git
cd tulip-factory-emulator
```

**2. Create and activate a Python virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
```

**3. Install Python dependencies**

```bash
pip install -r requirements.txt
```

**4. Pull an Ollama model**

```bash
ollama pull llama3
```

**5. Start the MQTT broker**

```bash
docker-compose up -d mosquitto
```

**6. Start Ollama** (separate terminal)

```bash
ollama serve
```

**7. Start the simulation**

```bash
python main.py
```

The dashboard will be available at **http://localhost:3000**.

### Restart Policy

| Change made                          | Action required                     |
|--------------------------------------|-------------------------------------|
| Any `.py` file                       | `Ctrl+C` → `python main.py`        |
| `dashboard/static/index.html`        | Hard-refresh browser (`Ctrl+Shift+R`) |
| `config/plant_config.yaml`           | `Ctrl+C` → `python main.py`        |

---

## Functionality

### Live Dashboard

A single-page dashboard (no frontend framework) served at `http://localhost:3000` displays:

- Real-time machine state cards for all 13 machines across 3 lines
- Per-machine telemetry: temperature, vibration, power, oil pressure, cycle time, throughput, OEE
- Plant-level summary: running count, faulted count, average OEE
- Active fault alerts with severity levels (info / warning / critical)
- In-dashboard chat panel powered by Ollama

### REST API

```
GET  /api/plant              Full plant snapshot (JSON)
GET  /api/machine/{id}       Single machine telemetry
POST /api/command            Execute commands on the plant
WS   /ws                     Live plant state pushed every tick
```

#### Command API

Send commands via `POST /api/command` with body `{"commands": [...]}`.

**Set machine state**
```json
{"action": "set_state", "target": "MILL-L1-01", "state": "running"}
```
Valid states: `running`, `idle`, `stopped`, `maintenance`, `fault`

**Inject a fault**
```json
{"action": "inject_fault", "target": "MILL-L1-01", "fault_type": "overtemp"}
```

Targeting options:
- Single machine: `"target": "MILL-L1-01"`
- Entire line: `"target": "line:L2"`
- All machines: `"target": "all"`

Available fault types:

| Fault Type      | Code | Severity |
|-----------------|------|----------|
| `overtemp`      | E001 | critical |
| `high_vibration`| E002 | warning  |
| `low_oil`       | E003 | warning  |
| `spindle_fault` | E005 | critical |
| `estop`         | E007 | critical |
| `feed_jam`      | E009 | critical |
| `tool_wear`     | E006 | info     |
| `comm_loss`     | E008 | warning  |
| `low_coolant`   | E010 | warning  |
| `motor_thermal` | E011 | critical |
| `encoder_loss`  | E012 | critical |

**Acknowledge faults**
```json
{"action": "ack_faults", "target": "all"}
```

**Put machine in maintenance**
```json
{"action": "maintenance", "target": "GRND-L1-04"}
```

### OPC UA Server

Exposes the full plant hierarchy at `opc.tcp://localhost:4840/factory/`. Each machine publishes the following nodes:

```
Objects/FactoryFloor/Line_{id}/{machine_id}/
  ├── State
  ├── Temperature_C
  ├── Vibration_mm_s
  ├── Power_kW
  ├── OilPressure_bar
  ├── CycleTime_s
  ├── Throughput_pph
  ├── OEE_pct
  ├── TotalCycles
  ├── HoursSinceMaintenance
  └── ActiveFaultCount
```

### MQTT Publisher

Publishes telemetry to a Mosquitto broker every second using the following topic structure:

```
factory/{line_id}/{machine_id}/telemetry   — full JSON blob
factory/{line_id}/{machine_id}/state       — state string
factory/{line_id}/{machine_id}/{tag}       — individual tag
factory/alerts/{line_id}/{machine_id}      — fault events (QoS 2)
factory/summary                            — plant-level summary
```

### AI Brain

`sim/ai_brain.py` runs an autonomous loop every 45 seconds. It sends a plant state summary to Ollama, which returns a JSON array of commands that are executed directly on the plant — simulating an AI operator making decisions. If Ollama is unavailable or returns malformed JSON, the cycle is skipped gracefully.

### Machine Simulation

All machines share a common base (`sim/machines/base.py`) with:

- Realistic telemetry using Gaussian noise
- Aging model: fault probability increases with hours since last maintenance
- State machine: `running → idle → stopped → fault → maintenance → warming_up`
- Auto-recovery from critical faults after 30–120 seconds
- OEE calculation: availability × performance × quality

Machine-specific behavior is defined in `sim/machines/types.py` for: Mill, Lathe, Grinder, Press, Drill, CNC, and Conveyor.

### Project Structure

```
factory-hybrid/
├── main.py                        Entry point
├── requirements.txt               Python dependencies
├── docker-compose.yml             Mosquitto MQTT broker
├── mosquitto.conf                 MQTT broker config
├── config/
│   └── plant_config.yaml          Plant layout (lines, machines, ports)
├── sim/
│   ├── plant.py                   Plant + ProductionLine + tick loop
│   ├── opcua_server.py            OPC UA server (asyncua)
│   ├── mqtt_publisher.py          MQTT publisher (aiomqtt)
│   ├── ai_brain.py                Autonomous Ollama AI loop
│   ├── edge_io.py                 Edge I/O device simulation
│   └── machines/
│       ├── base.py                BaseMachine, MachineState, fault library
│       └── types.py               Machine type implementations
└── dashboard/
    ├── server.py                  FastAPI app (REST, WebSocket, commands)
    └── static/
        └── index.html             Dashboard UI
```

---

## Troubleshooting

### Dashboard shows no data / WebSocket not connecting

- Confirm `python main.py` is running and shows no startup errors.
- Check that port 3000 is not already in use: `lsof -i :3000`
- Try a hard-refresh (`Ctrl+Shift+R`) to clear any cached state.

### MQTT connection errors at startup

```
MQTTConnectError: Connection refused
```

- Ensure the Mosquitto container is running: `docker-compose ps`
- If it exited, check logs: `docker-compose logs mosquitto`
- Restart it: `docker-compose up -d mosquitto`

### OPC UA server fails to start

```
OSError: [Errno 48] Address already in use
```

- Another process is using port 4840. Find and stop it: `lsof -i :4840`
- Or change the port in `config/plant_config.yaml` under `opcua.endpoint`.

### AI Brain not responding / chat panel silent

- Verify Ollama is running: `ollama list` should return at least one model.
- Start it if needed: `ollama serve`
- Confirm a model is available: `ollama pull llama3`
- Check the terminal output — if Ollama returns bad JSON, the brain logs a warning and skips the cycle. This is expected behavior.

### `ModuleNotFoundError` on startup

- Ensure the virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Port conflicts summary

| Port | Service    | Fix                                    |
|------|------------|----------------------------------------|
| 3000 | Dashboard  | `lsof -i :3000` → kill the process    |
| 4840 | OPC UA     | `lsof -i :4840` → kill the process    |
| 1883 | MQTT       | `docker-compose restart mosquitto`     |
| 11434| Ollama     | `ollama serve` to start                |
