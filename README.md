# ACME Factory Simulation

A hybrid manufacturing plant simulator that exposes real industrial protocols (OPC UA, MQTT), serves a live factory floor dashboard, and integrates with Tulip via an OPC UA bridge and Node-RED flows.

---

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Functionality](#functionality)
- [Troubleshooting](#troubleshooting)

---

## Overview

ACME Factory Simulation simulates a three-line manufacturing plant with 13 machines across precision machining, heavy fabrication, and CNC assembly lines. It is designed to be a realistic integration target for industrial dashboards, SCADA systems, and IoT platforms.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     main.py (entry point)               │
├────────────┬──────────────┬──────────────┬──────────────┤
│  FastAPI   │  OPC UA      │  MQTT        │  Edge IO     │
│  Dashboard │  Server      │  Publisher   │  Device      │
│  :3000     │  :4840       │  :1883       │  EIO-01      │
└────────────┴──────────────┴──────────────┴──────────────┘
                   │                │
        ┌──────────▼──────┐  ┌──────▼───────┐
        │  OPC UA Bridge  │  │  Node-RED    │
        │  opcua-bridge/  │  │  :1880       │
        │  :4841 (Tulip)  │  │  (Docker)    │
        └─────────────────┘  └──────────────┘
```

### Production Lines

| Line | Name               | Machines                                              |
|------|--------------------|-------------------------------------------------------|
| L1   | Precision Machining | MILL-L1-01, LATHE-L1-02, LATHE-L1-03, GRND-L1-04   |
| L2   | Heavy Fabrication  | GRND-L2-01, MILL-L2-02, PRESS-L2-03, DRILL-L2-04    |
| L3   | CNC Assembly       | CNC-L3-01, CNC-L3-02, MILL-L3-03, LATHE-L3-04, CONV-L3-05 |

### Key Ports

| Service          | Port  | Protocol         |
|------------------|-------|------------------|
| Dashboard        | 3000  | HTTP + WebSocket |
| OPC UA (sim)     | 4840  | opc.tcp          |
| OPC UA (bridge)  | 4841  | opc.tcp          |
| MQTT Broker      | 1883  | mqtt             |
| Node-RED         | 1880  | HTTP             |

---

## Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (Docker Desktop or Colima on macOS)

### Steps

**1. Clone the repository**

```bash
git clone <repo-url>
cd factory-hybrid
```

**2. Create a Python virtual environment and install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**3. Install Node.js dependencies for the OPC UA bridge**

```bash
cd opcua-bridge && npm install && cd ..
```

**4. Start everything**

```bash
./start.sh
```

`start.sh` will start Mosquitto and Node-RED via Docker, launch the OPC UA bridge, and
start the Python simulation with watchdog auto-restart. The dashboard will be available
at **http://localhost:3000**.

To stop all services:

```bash
pkill -f main.py && docker stop mosquitto nodered
```

### Restart Policy

| Change made                          | Action required     |
|--------------------------------------|---------------------|
| Any `.py` file                       | Re-run `./start.sh` |
| `dashboard/static/index.html`        | Hard-refresh browser (`Ctrl+Shift+R`) |
| `config/plant_config.yaml`           | Re-run `./start.sh` |

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

### Edge IO Device

`sim/edge_io.py` simulates an industrial edge I/O device (`EIO-01`) linked to the first machine on Line 1. It exposes 8 GPIO channels, analog inputs/outputs, a light kit, and a serial barcode scanner — all updated every simulation tick based on the linked machine's state. Accessible via the dashboard.

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
├── start.sh                       One-command startup script (with watchdog)
├── docker-compose.yml             Mosquitto + Node-RED (alternative to start.sh)
├── mosquitto.conf                 MQTT broker config
├── config/
│   └── plant_config.yaml          Plant layout (lines, machines, ports)
├── sim/
│   ├── plant.py                   Plant + ProductionLine + tick loop
│   ├── opcua_server.py            OPC UA server (asyncua, :4840)
│   ├── mqtt_publisher.py          MQTT publisher (aiomqtt, :1883)
│   ├── edge_io.py                 Edge I/O device simulation (EIO-01)
│   └── machines/
│       ├── base.py                BaseMachine, MachineState, fault library
│       └── types.py               Machine type implementations
├── dashboard/
│   ├── server.py                  FastAPI app (REST, WebSocket, commands)
│   └── static/
│       └── index.html             Dashboard UI
├── opcua-bridge/
│   └── bridge.js                  Node.js OPC UA bridge (:4840 → :4841)
└── nodered/
    └── flows.json                 Node-RED flow definitions
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

- Ensure the Mosquitto container is running: `docker ps | grep mosquitto`
- If it exited, restart it: `docker start mosquitto`
- Check logs: `docker logs mosquitto`

### OPC UA server fails to start

```
OSError: [Errno 48] Address already in use
```

- Another process is using port 4840. Find and stop it: `lsof -i :4840`
- Or change the port in `config/plant_config.yaml` under `opcua.endpoint`.

### OPC UA bridge not starting

- Confirm Node.js >=18 is installed: `node --version`
- Ensure dependencies are installed: `cd opcua-bridge && npm install`
- Check logs: `tail -f logs/opcua-bridge.log`

### `ModuleNotFoundError` on startup

- Ensure the virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

### Services keep restarting in a loop

`start.sh` includes watchdog processes that auto-restart crashed services. If you see
repeated restart messages, check the logs for the root cause:

```bash
tail -f logs/factory-sim.log
tail -f logs/opcua-bridge.log
```

### Port conflicts summary

| Port | Service        | Fix                                          |
|------|----------------|----------------------------------------------|
| 3000 | Dashboard      | `lsof -i :3000` → kill the process          |
| 4840 | OPC UA (sim)   | `lsof -i :4840` → kill the process          |
| 4841 | OPC UA (bridge)| `lsof -i :4841` → kill the process          |
| 1883 | MQTT           | `docker restart mosquitto`                   |
| 1880 | Node-RED       | `docker restart nodered`                     |
