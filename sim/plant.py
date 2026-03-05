import asyncio
import time
from typing import List, Dict, Any
from .machines.base import BaseMachine
from .machines.types import MACHINE_REGISTRY


class ProductionLine:
    def __init__(self, line_id: str, name: str, machines: List[BaseMachine]):
        self.line_id = line_id
        self.name = name
        self.machines = machines

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_id": self.line_id,
            "name": self.name,
            "machines": [m.to_dict() for m in self.machines],
        }


class Plant:
    def __init__(self, config: dict):
        self.name = config["plant"]["name"]
        self.location = config["plant"]["location"]
        self.lines: List[ProductionLine] = []
        self._tick_interval = 1.0 / config["simulation"].get("tick_rate_hz", 1)
        self._running = False
        self._on_tick_callbacks = []
        self._build(config)

    def _build(self, config: dict):
        for line_cfg in config["lines"]:
            machines = []
            for m_cfg in line_cfg["machines"]:
                cls = MACHINE_REGISTRY.get(m_cfg["type"])
                if cls:
                    machines.append(cls(m_cfg["id"], line_cfg["id"]))
            self.lines.append(ProductionLine(line_cfg["id"], line_cfg["name"], machines))

    @property
    def all_machines(self) -> List[BaseMachine]:
        return [m for line in self.lines for m in line.machines]

    @property
    def machine_map(self) -> Dict[str, BaseMachine]:
        return {m.machine_id: m for m in self.all_machines}

    def get_machine(self, machine_id: str) -> BaseMachine | None:
        return self.machine_map.get(machine_id)

    def summary(self) -> Dict[str, Any]:
        all_m = self.all_machines
        states = [m.state.value for m in all_m]
        return {
            "plant_name": self.name,
            "total_machines": len(all_m),
            "running": states.count("running"),
            "idle": states.count("idle"),
            "stopped": states.count("stopped"),
            "faulted": states.count("fault"),
            "maintenance": states.count("maintenance"),
            "total_throughput_pph": round(sum(m.throughput for m in all_m), 1),
            "total_power_kw": round(sum(m.power_kw for m in all_m), 1),
            "active_alerts": sum(len(m.errors) for m in all_m),
            "timestamp": time.time(),
        }

    def on_tick(self, callback):
        self._on_tick_callbacks.append(callback)

    async def run(self):
        self._running = True
        last = time.time()
        while self._running:
            now = time.time()
            dt = now - last
            last = now
            for machine in self.all_machines:
                machine.tick(dt)
            for cb in self._on_tick_callbacks:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb()
                    else:
                        cb()
                except Exception as e:
                    print(f"Tick callback error: {e}")
            await asyncio.sleep(self._tick_interval)
