import random
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


class MachineState(Enum):
    RUNNING = "running"
    IDLE = "idle"
    STOPPED = "stopped"
    FAULT = "fault"
    MAINTENANCE = "maintenance"
    WARMING_UP = "warming_up"


@dataclass
class MachineError:
    code: str
    message: str
    severity: str  # "info", "warning", "critical"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


FAULT_LIBRARY = [
    MachineError("E001", "Temperature exceeded threshold (88°C)", "critical"),
    MachineError("E002", "Vibration anomaly detected — bearing wear suspected", "warning"),
    MachineError("E003", "Oil pressure drop — check reservoir level", "warning"),
    MachineError("E004", "Cycle time exceeded nominal by >20%", "warning"),
    MachineError("E005", "Spindle drive fault — overcurrent protection triggered", "critical"),
    MachineError("E006", "Tool wear limit reached — replacement required", "info"),
    MachineError("E007", "Emergency stop activated", "critical"),
    MachineError("E008", "PLC communication timeout", "warning"),
    MachineError("E009", "Material feed jam detected", "critical"),
    MachineError("E010", "Coolant flow below minimum threshold", "warning"),
    MachineError("E011", "Drive motor thermal protection triggered", "critical"),
    MachineError("E012", "Axis encoder feedback lost", "critical"),
]

FAULT_BY_CODE = {f.code: f for f in FAULT_LIBRARY}
FAULT_NAMES = {
    "overtemp": "E001", "high_vibration": "E002", "low_oil": "E003",
    "cycle_timeout": "E004", "spindle_fault": "E005", "tool_wear": "E006",
    "estop": "E007", "comm_loss": "E008", "feed_jam": "E009",
    "low_coolant": "E010", "motor_thermal": "E011", "encoder_loss": "E012",
}


TELEMETRY_ATTR_MAP = {
    "temperature_c": "temperature",
    "vibration_mm_s": "vibration",
    "power_kw": "power_kw",
    "oil_pressure_bar": "oil_pressure",
    "cycle_time_s": "cycle_time",
    "throughput_pph": "throughput",
    "uptime_s": "uptime_s",
    "total_cycles": "total_cycles",
    "tool_wear_pct": "tool_wear_pct",
}


def gauss(mean: float, std: float) -> float:
    return random.gauss(mean, std)


class BaseMachine:
    nominal_throughput: float = 60.0
    machine_type_label: str = "Machine"

    def __init__(self, machine_id: str, machine_type: str, line_id: str):
        self.machine_id = machine_id
        self.machine_type = machine_type
        self.line_id = line_id

        self.state = MachineState.RUNNING if random.random() < 0.65 else (
            MachineState.IDLE if random.random() < 0.7 else MachineState.STOPPED
        )

        # Common telemetry
        self.temperature: float = 20.0 + random.uniform(0, 35)
        self.vibration: float = 0.0
        self.power_kw: float = 0.0
        self.oil_pressure: float = 0.0
        self.cycle_time: float = 12.0 + random.uniform(0, 4)
        self.throughput: float = 0.0
        self.uptime_s: float = random.uniform(0, 28800)
        self.total_cycles: float = random.uniform(0, 5000)
        self.failed_cycles: float = self.total_cycles * 0.02
        self.tool_wear_pct: float = random.uniform(0, 60)
        self.last_maintenance: float = time.time() - random.uniform(0, 86400 * 25)

        self.errors: List[MachineError] = []
        self.telemetry_overrides: Dict[str, float] = {}  # key -> value (locks slider)
        self._fault_recovery_task: Optional[float] = None  # timestamp when to recover

    @property
    def hours_since_maintenance(self) -> float:
        return (time.time() - self.last_maintenance) / 3600

    @property
    def oee(self) -> float:
        quality = 1.0 - (self.failed_cycles / max(self.total_cycles, 1))
        availability = {
            MachineState.RUNNING: 1.0,
            MachineState.IDLE: 0.5,
            MachineState.WARMING_UP: 0.3,
        }.get(self.state, 0.0)
        performance = min(1.0, self.throughput / max(self.nominal_throughput, 1))
        return round(quality * availability * performance * 100, 1)

    def inject_fault(self, fault_name_or_code: str) -> Optional[MachineError]:
        """Inject a fault by name (e.g. 'overtemp') or code (e.g. 'E001')."""
        code = FAULT_NAMES.get(fault_name_or_code, fault_name_or_code)
        template = FAULT_BY_CODE.get(code)
        if not template:
            # Unknown — create generic
            template = MachineError(code, f"Fault: {fault_name_or_code}", "warning")

        err = MachineError(template.code, template.message, template.severity)
        self.errors.append(err)

        if err.severity == "critical":
            self.state = MachineState.FAULT
            # Schedule auto-recovery in 30-120s
            self._fault_recovery_task = time.time() + random.uniform(30, 120)

        return err

    def set_state(self, new_state: str) -> bool:
        try:
            self.state = MachineState(new_state)
            if new_state != "fault":
                self._fault_recovery_task = None
                self.errors = []
            return True
        except ValueError:
            return False

    def acknowledge_faults(self):
        self.errors = []
        if self.state == MachineState.FAULT:
            self.state = MachineState.IDLE

    def tick(self, dt: float = 1.0):
        """Simulate one time step of dt seconds."""
        # Check fault recovery
        if self._fault_recovery_task and time.time() >= self._fault_recovery_task:
            self._fault_recovery_task = None
            self.state = MachineState.IDLE
            self.errors = []

        aging = 1.0 + max(0, (self.hours_since_maintenance - 400) / 200)

        if self.state == MachineState.RUNNING:
            self.uptime_s += dt
            self.temperature = min(92, self.temperature + gauss(0.02, 0.1))
            self.vibration = abs(gauss(2.5, 0.4 * aging))
            self.power_kw = abs(gauss(15, 1.5))
            self.oil_pressure = abs(gauss(3.5, 0.1))
            self.cycle_time = abs(gauss(12, 0.8))
            self.throughput = 3600 / max(self.cycle_time, 1)
            self.total_cycles += dt / max(self.cycle_time, 1)
            self.tool_wear_pct = min(100, self.tool_wear_pct + 0.003 * dt)
            self._machine_specific_running(dt)

            # Random state transitions
            if random.random() < 0.0003:
                self.state = MachineState.IDLE

            # Random faults
            if random.random() < 0.0006 * aging:
                self.inject_fault(random.choice(list(FAULT_NAMES.keys())))

        elif self.state == MachineState.IDLE:
            self.temperature = max(22, self.temperature - 0.08 * dt)
            self.vibration = abs(gauss(0.1, 0.03))
            self.power_kw = abs(gauss(1.5, 0.3))
            self.oil_pressure = 0.0
            self.throughput = 0.0
            if random.random() < 0.003:
                self.state = MachineState.RUNNING
            elif random.random() < 0.0005:
                self.state = MachineState.STOPPED

        elif self.state == MachineState.STOPPED:
            self.temperature = max(20, self.temperature - 0.04 * dt)
            self.vibration = 0.0
            self.power_kw = abs(gauss(0.3, 0.05))
            self.throughput = 0.0
            if random.random() < 0.001:
                self.state = MachineState.IDLE

        elif self.state == MachineState.FAULT:
            self.temperature = min(100, self.temperature + gauss(0.3, 0.1))
            self.vibration = abs(gauss(8.0, 2.0))
            self.power_kw = abs(gauss(22, 3))
            self.throughput = 0.0

        elif self.state == MachineState.MAINTENANCE:
            self.temperature = max(20, self.temperature - 0.1 * dt)
            self.vibration = abs(gauss(0.5, 0.2))
            self.power_kw = abs(gauss(2.0, 0.5))
            self.throughput = 0.0

        elif self.state == MachineState.WARMING_UP:
            self.temperature = min(45, self.temperature + 0.5 * dt)
            self.power_kw = abs(gauss(5, 0.5))
            self.throughput = 0.0

        # Apply telemetry overrides (user-locked sliders)
        for tkey, attr in TELEMETRY_ATTR_MAP.items():
            if tkey in self.telemetry_overrides:
                setattr(self, attr, self.telemetry_overrides[tkey])

    def _machine_specific_running(self, dt: float):
        """Override in subclasses for machine-specific telemetry."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "machine_id": self.machine_id,
            "machine_type": self.machine_type,
            "machine_type_label": self.machine_type_label,
            "line_id": self.line_id,
            "state": self.state.value,
            "telemetry": {
                "temperature_c": round(self.temperature, 2),
                "vibration_mm_s": round(self.vibration, 3),
                "power_kw": round(self.power_kw, 2),
                "oil_pressure_bar": round(self.oil_pressure, 2),
                "cycle_time_s": round(self.cycle_time, 2),
                "throughput_pph": round(self.throughput, 1),
                "oee_pct": self.oee,
                "uptime_s": round(self.uptime_s),
                "total_cycles": round(self.total_cycles),
                "tool_wear_pct": round(self.tool_wear_pct, 1),
                "hours_since_maintenance": round(self.hours_since_maintenance, 1),
            },
            "errors": [e.to_dict() for e in self.errors[-5:]],
            "timestamp": time.time(),
        }
