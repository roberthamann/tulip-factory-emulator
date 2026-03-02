import asyncio
import json
import time
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Factory Simulation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Injected at startup by main.py
plant = None
edge_devices = []  # List of EdgeIODevice instances
_ws_clients: Set[WebSocket] = set()


# ─── WebSocket broadcast ──────────────────────────────────────────────────────

async def broadcast_plant_state():
    """Called every tick — pushes state to all connected dashboards."""
    if not _ws_clients or plant is None:
        return
    snapshot = {
        "type": "plant_state",
        "summary": plant.summary(),
        "lines": [line.to_dict() for line in plant.lines],
        "edge_devices": [eio.to_dict() for eio in edge_devices],
    }
    payload = json.dumps(snapshot)
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        while True:
            # Keep connection alive; actual data pushed by broadcast_plant_state()
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)


# ─── REST: plant snapshot ─────────────────────────────────────────────────────

@app.get("/api/plant")
def get_plant():
    if plant is None:
        raise HTTPException(503, "Plant not initialised")
    return {
        "summary": plant.summary(),
        "lines": [line.to_dict() for line in plant.lines],
    }


@app.get("/api/machine/{machine_id}")
def get_machine(machine_id: str):
    if plant is None:
        raise HTTPException(503, "Plant not initialised")
    m = plant.get_machine(machine_id)
    if not m:
        raise HTTPException(404, f"Machine '{machine_id}' not found")
    return m.to_dict()


# ─── REST: AI command endpoint ────────────────────────────────────────────────

class CommandRequest(BaseModel):
    commands: list  # list of action dicts from Claude


@app.post("/api/command")
async def execute_commands(body: CommandRequest):
    """
    Receives a list of structured commands from the browser (after Claude processes
    the user's natural language). Executes each command on the live plant.

    Supported command shapes:
      { "action": "set_state",     "target": "MILL-L1-01", "state": "idle" }
      { "action": "inject_fault",  "target": "MILL-L1-01", "fault_type": "overtemp" }
      { "action": "inject_fault",  "target": "line:L2",    "fault_type": "high_vibration" }
      { "action": "inject_fault",  "target": "all",        "fault_type": "comm_loss" }
      { "action": "ack_faults",    "target": "MILL-L1-01" }
      { "action": "ack_faults",    "target": "all" }
      { "action": "set_state",     "target": "line:L1",    "state": "stopped" }
      { "action": "maintenance",   "target": "GRND-L1-04" }
    """
    if plant is None:
        raise HTTPException(503, "Plant not initialised")

    results = []
    for cmd in body.commands:
        result = _execute_single(cmd)
        results.append(result)

    return {"executed": len(results), "results": results}


def _resolve_targets(target: str):
    """Resolve a target string to a list of machines."""
    if target == "all":
        return plant.all_machines
    if target.startswith("line:"):
        line_id = target.split(":", 1)[1]
        line = next((l for l in plant.lines if l.line_id == line_id), None)
        return line.machines if line else []
    m = plant.get_machine(target)
    return [m] if m else []


def _execute_single(cmd: dict) -> dict:
    action = cmd.get("action", "")
    target = cmd.get("target", "")
    machines = _resolve_targets(target)

    if not machines:
        return {"target": target, "status": "error", "message": "No machines found"}

    if action == "set_state":
        state = cmd.get("state", "idle")
        for m in machines:
            m.set_state(state)
        return {"target": target, "status": "ok", "action": f"set_state={state}", "count": len(machines)}

    elif action == "inject_fault":
        fault_type = cmd.get("fault_type", "E002")
        injected = []
        for m in machines:
            err = m.inject_fault(fault_type)
            if err:
                injected.append({"machine": m.machine_id, "fault": err.code})
        return {"target": target, "status": "ok", "action": "inject_fault", "injected": injected}

    elif action == "ack_faults":
        for m in machines:
            m.acknowledge_faults()
        return {"target": target, "status": "ok", "action": "ack_faults", "count": len(machines)}

    elif action == "set_telemetry":
        key = cmd.get("key", "")
        value = float(cmd.get("value", 0))
        for m in machines:
            m.telemetry_overrides[key] = value
        return {"target": target, "status": "ok", "action": "set_telemetry", "key": key, "value": value}

    elif action == "unlock_telemetry":
        for m in machines:
            m.telemetry_overrides.clear()
        return {"target": target, "status": "ok", "action": "unlock_telemetry", "count": len(machines)}

    elif action == "maintenance":
        for m in machines:
            m.set_state("maintenance")
            m.last_maintenance = time.time()
        return {"target": target, "status": "ok", "action": "maintenance", "count": len(machines)}

    else:
        return {"target": target, "status": "error", "message": f"Unknown action: {action}"}

# ─── REST: Edge IO endpoints ───────────────────────────────────────────────

@app.get("/api/edge-io")
def list_edge_devices():
    return [eio.to_dict() for eio in edge_devices]


@app.get("/api/edge-io/{device_id}")
def get_edge_device(device_id: str):
    eio = next((d for d in edge_devices if d.device_id == device_id), None)
    if not eio:
        raise HTTPException(404, f"Edge IO device '{device_id}' not found")
    return eio.to_dict()


class EdgeIOCommand(BaseModel):
    action: str
    pin: int = None
    value: bool = None
    channel: int = None
    mode: str = None
    color: str = None
    brightness: float = None
    active_leds: list = None


@app.post("/api/edge-io/{device_id}/command")
async def edge_io_command(device_id: str, body: EdgeIOCommand):
    eio = next((d for d in edge_devices if d.device_id == device_id), None)
    if not eio:
        raise HTTPException(404, f"Edge IO device '{device_id}' not found")

    action = body.action

    if action == "set_di":
        if body.pin is not None and body.value is not None:
            eio.set_digital_input(body.pin, body.value)
            return {"status": "ok", "action": "set_di", "pin": body.pin, "value": body.value}

    elif action == "clear_di_override":
        if body.pin is not None:
            eio.clear_digital_input_override(body.pin)
            return {"status": "ok", "action": "clear_di_override", "pin": body.pin}

    elif action == "set_do":
        if body.pin is not None and body.value is not None:
            eio.set_digital_output(body.pin, body.value)
            return {"status": "ok", "action": "set_do", "pin": body.pin, "value": body.value}

    elif action == "set_lightkit":
        if body.channel is not None:
            eio.set_light_kit(body.channel, body.mode, body.color, body.brightness, body.active_leds)
            return {"status": "ok", "action": "set_lightkit", "channel": body.channel}

    elif action == "toggle_online":
        eio.online = not eio.online
        return {"status": "ok", "action": "toggle_online", "online": eio.online}

    elif action == "trigger_scan":
        data = eio.serial.simulate_scan()
        return {"status": "ok", "action": "trigger_scan", "data": data}

    return {"status": "error", "message": f"Unknown action: {action}"}


app.mount("/", StaticFiles(directory="dashboard/static", html=True), name="static")

