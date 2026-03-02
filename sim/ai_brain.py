import asyncio
import json
import time

import httpx

from sim.plant import Plant

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "mistral"


class AIBrain:
    def __init__(self, plant: Plant, interval: int = 45):
        self.plant = plant
        self.interval = interval  # seconds between autonomous decisions

    async def run(self):
        await asyncio.sleep(10)  # let the plant warm up first
        while True:
            try:
                await self._tick()
            except Exception as e:
                print(f"[AI Brain] Error: {e}")
            await asyncio.sleep(self.interval)

    async def _tick(self):
        summary = self.plant.summary()
        machines = [
            {
                "id": m.machine_id,
                "type": m.machine_type,
                "state": m.state.value,
                "temp": round(m.temperature, 1),
                "vibration": round(m.vibration, 2),
                "oee": m.oee,
                "hours_since_maint": round(m.hours_since_maintenance, 0),
                "tool_wear_pct": round(m.tool_wear_pct, 1),
                "active_faults": len(m.errors),
            }
            for m in self.plant.all_machines
        ]

        prompt = f"""You are an AI plant manager for a manufacturing floor simulation.

Current plant summary: {json.dumps(summary)}
Machine states: {json.dumps(machines)}

Generate 1-3 realistic autonomous factory events to inject right now. Consider:
- Machines with high hours_since_maint (>400h) are more fault-prone
- High temperature (>75C) + high vibration (>4 mm/s) often precede failures
- Cascade failures: if an upstream machine faults, downstream machines should go idle
- Natural cycling: some idle machines should return to running
- Tool wear >80% on mills/lathes should trigger tool_wear fault
- Occasionally acknowledge and clear resolved faults

Available fault_types: overtemp, high_vibration, low_oil, cycle_timeout,
spindle_fault, tool_wear, estop, comm_loss, feed_jam, low_coolant,
motor_thermal, encoder_loss

Available actions:
  set_state    → state: running | idle | stopped | maintenance | fault
  inject_fault → fault_type: one of the above
  ack_faults   → clears errors and returns machine to idle
  maintenance  → sets maintenance state and resets maintenance timer

Targets: a specific machine ID, "line:L1" / "line:L2" / "line:L3", or "all"

Respond ONLY with a valid JSON array of command objects. No explanation, no markdown.
Example: [{{"action": "inject_fault", "target": "MILL-L1-01", "fault_type": "overtemp"}}]
Return [] if no events are needed this cycle."""

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            raw = resp.json()["message"]["content"]

        # Strip markdown code fences if present
        clean = raw.replace("```json", "").replace("```", "").strip()
        commands = json.loads(clean)

        if commands:
            print(f"[AI Brain] Executing {len(commands)} autonomous event(s): {commands}")
            for cmd in commands:
                target = cmd.get("target", "")
                targets = self._resolve(target)
                for m in targets:
                    action = cmd.get("action", "")
                    if action == "set_state":
                        m.set_state(cmd.get("state", "idle"))
                    elif action == "inject_fault":
                        m.inject_fault(cmd.get("fault_type", "E002"))
                    elif action == "ack_faults":
                        m.acknowledge_faults()
                    elif action == "maintenance":
                        m.set_state("maintenance")
                        m.last_maintenance = time.time()

    def _resolve(self, target: str):
        if target == "all":
            return self.plant.all_machines
        if target.startswith("line:"):
            lid = target.split(":", 1)[1]
            line = next((l for l in self.plant.lines if l.line_id == lid), None)
            return line.machines if line else []
        m = self.plant.get_machine(target)
        return [m] if m else []
