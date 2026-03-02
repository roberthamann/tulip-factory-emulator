# ACME Factory Simulation — Project Guide for Claude Code

## What This Project Is
A hybrid AI-dynamic manufacturing plant simulator. It exposes real OPC UA and MQTT
endpoints, serves a live factory floor dashboard, and uses Ollama (local LLM) for
both the in-dashboard chat panel and an autonomous AI brain loop that drives
realistic factory behavior.

## How to Run
```bash
# 1. Start MQTT broker
docker-compose up -d mosquitto

# 2. Start local LLM (separate terminal)
ollama serve

# 3. Activate venv and start the backend
source venv/bin/activate
python main.py
```

## Restart Policy
- After editing any .py file → Ctrl+C then `python main.py`
- After editing dashboard/static/index.html → hard-refresh browser (Ctrl+Shift+R)
- After editing config/plant_config.yaml → Ctrl+C then `python main.py`

## File Map
```
factory-hybrid/
├── main.py                        Entry point — wires all services together
├── requirements.txt               Python dependencies
├── mosquitto.conf                 MQTT broker config
├── docker-compose.yml             Docker services (Mosquitto only)
├── CLAUDE.md                      This file
├── config/
│   └── plant_config.yaml          Plant layout: lines, machines, ports
├── sim/
│   ├── plant.py                   Plant + ProductionLine classes, tick loop
│   ├── opcua_server.py            OPC UA server (asyncua, port 4840)
│   ├── mqtt_publisher.py          MQTT publisher (aiomqtt, port 1883)
│   ├── ai_brain.py                Autonomous Ollama AI loop (every 45s)
│   └── machines/
│       ├── base.py                BaseMachine, MachineState enum, fault library
│       └── types.py               Mill, Lathe, Grinder, Press, Drill, CNC, Conveyor
└── dashboard/
    ├── server.py                  FastAPI: WebSocket, REST API, /api/command
    └── static/
        └── index.html             Full dashboard UI (HTML/CSS/JS, no framework)
```

## Key Ports
| Service    | Port  | Protocol        |
|------------|-------|-----------------|
| Dashboard  | 3000  | HTTP + WebSocket |
| OPC UA     | 4840  | opc.tcp         |
| MQTT       | 1883  | mqtt            |
| Ollama     | 11434 | HTTP            |

## API Endpoints
```
GET  /api/plant                  Full plant snapshot (JSON)
GET  /api/machine/{id}           Single machine telemetry
POST /api/command                Execute commands on the plant
WS   /ws                         Live plant state (pushed every tick)
```

## Command API — POST /api/command
Body: `{"commands": [...]}`

Supported command shapes:
```json
{"action": "set_state",    "target": "MILL-L1-01",   "state": "running|idle|stopped|maintenance|fault"}
{"action": "inject_fault", "target": "MILL-L1-01",   "fault_type": "overtemp|high_vibration|low_oil|spindle_fault|estop|feed_jam|tool_wear|comm_loss|low_coolant|motor_thermal|encoder_loss"}
{"action": "inject_fault", "target": "line:L2",      "fault_type": "high_vibration"}
{"action": "inject_fault", "target": "all",          "fault_type": "comm_loss"}
{"action": "ack_faults",   "target": "MILL-L1-01"}
{"action": "ack_faults",   "target": "all"}
{"action": "maintenance",  "target": "GRND-L1-04"}
```

## Machine IDs (from plant_config.yaml)
Line L1 — Precision Machining:  MILL-L1-01, LATHE-L1-02, LATHE-L1-03, GRND-L1-04
Line L2 — Heavy Fabrication:    GRND-L2-01, MILL-L2-02, PRESS-L2-03, DRILL-L2-04
Line L3 — CNC Assembly:         CNC-L3-01, CNC-L3-02, MILL-L3-03, LATHE-L3-04, CONV-L3-05

## Adding a New Machine Type
1. Add a class to sim/machines/types.py that extends BaseMachine
2. Override `nominal_throughput`, `machine_type_label`, and `_machine_specific_running()`
3. Add to `MACHINE_REGISTRY` dict at the bottom of types.py
4. Add to config/plant_config.yaml under a line's machines list
5. Restart main.py

## Adding a New API Endpoint
Edit dashboard/server.py. The `plant` object is already injected as a module-level variable.
Access machines via `plant.all_machines` or `plant.get_machine(id)`.

## MQTT Topic Structure
```
factory/{line_id}/{machine_id}/telemetry   — full JSON blob every second
factory/{line_id}/{machine_id}/state       — state string every second
factory/{line_id}/{machine_id}/{tag}       — individual telemetry tag
factory/alerts/{line_id}/{machine_id}      — fault events (QoS 2)
factory/summary                            — plant-level summary
```

## OPC UA Node Tree
```
Objects/
└── FactoryFloor/
    └── Line_{id}/
        └── {machine_id}/
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
            ├── ActiveFaultCount
            └── (machine-specific tags)
```

## Dashboard WebSocket Protocol
Server pushes JSON every tick:
```json
{
  "type": "plant_state",
  "summary": { "running": 8, "faulted": 1, "avg_oee_pct": 72.3, ... },
  "lines": [
    {
      "line_id": "L1",
      "name": "Precision Machining",
      "avg_oee": 74.1,
      "machines": [ { machine telemetry dict } ]
    }
  ]
}
```

## AI Brain (sim/ai_brain.py)
Calls Ollama every 45 seconds with a plant state summary.
Ollama returns a JSON array of commands which are executed directly on the plant.
If Ollama is slow or returns bad JSON, the cycle is skipped gracefully.
Interval is configurable: `AIBrain(plant, interval=45)`

## Common Tasks for Claude Code
- "Add a new production line" → edit plant_config.yaml + types.py if new machine type needed
- "Change dashboard colors" → edit CSS variables in dashboard/static/index.html
- "Add a REST endpoint" → edit dashboard/server.py
- "Make faults more frequent" → edit fault probability in sim/machines/base.py tick()
- "Add a new telemetry tag to a machine" → edit to_dict() in the machine class in types.py
- "Show OEE trend chart in dashboard" → edit index.html to add canvas + charting logic
- "Publish OEE to a dedicated MQTT topic" → edit sim/mqtt_publisher.py
