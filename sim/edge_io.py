"""
Virtual Tulip Edge IO Device Emulator
======================================
Simulates: 8x GPIO (DI), 4x GPO (DO), 2x Analog In, 2x Light Kit, Serial
"""

import time
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class LightKitStrip:
    """One LED strip — 60 LEDs, each with RGB."""
    channel: int
    num_leds: int = 60
    mode: str = "off"          # off, solid, chase, pulse, pick_to_light
    color: str = "#00ff66"     # Primary color (hex)
    brightness: float = 1.0
    active_leds: List[int] = field(default_factory=list)  # For pick-to-light

    def to_dict(self) -> dict:
        return {
            "channel": self.channel,
            "mode": self.mode,
            "color": self.color,
            "brightness": round(self.brightness, 2),
            "num_leds": self.num_leds,
            "active_leds": self.active_leds,
        }


@dataclass
class SerialPort:
    """Virtual RS232/RS485 serial port — simulates barcode scanner."""
    port_type: str = "RS232"   # RS232 or RS485
    baud_rate: int = 9600
    last_data: str = ""
    last_timestamp: float = 0.0

    # Simulated barcode patterns
    BARCODE_PATTERNS = [
        "WO-2025-{:04d}",     # Work orders
        "PART-{:06d}",         # Part numbers
        "LOT-{:04d}-{:02d}",  # Lot IDs
        "BIN-{:02d}-{:03d}",  # Bin locations
        "SKU-{:08d}",          # SKU codes
    ]

    def simulate_scan(self) -> str:
        pattern = random.choice(self.BARCODE_PATTERNS)
        if pattern.count("{}") == 0:
            # Count format specs
            n_specs = pattern.count("{:")
            if n_specs == 1:
                data = pattern.format(random.randint(1, 9999))
            elif n_specs == 2:
                data = pattern.format(random.randint(1, 9999), random.randint(1, 99))
            else:
                data = pattern.format(random.randint(1, 99999999))
        else:
            data = pattern
        self.last_data = data
        self.last_timestamp = time.time()
        return data

    def to_dict(self) -> dict:
        return {
            "port_type": self.port_type,
            "baud_rate": self.baud_rate,
            "last_data": self.last_data,
            "last_timestamp": self.last_timestamp,
        }


class EdgeIODevice:
    """
    Full Edge IO emulator with all interfaces.

    GPIO Mapping (simulated sensors):
      DI0: Door sensor (break beam)
      DI1: Part present sensor
      DI2: Operator button 1
      DI3: Operator button 2
      DI4: Emergency stop status
      DI5: Cycle complete signal
      DI6: Material low sensor
      DI7: Safety curtain

    GPO Mapping (controllable outputs):
      DO0: Stack light green
      DO1: Stack light yellow
      DO2: Stack light red
      DO3: Buzzer
    
    Analog Mapping:
      AI0: Current clamp (4-20 mA → mapped to amps)
      AI1: Vibration sensor (mm/s RMS)

    Light Kit:
      LK0: Station indicator strip
      LK1: Pick-to-light strip
    """

    DI_LABELS = [
        "Door Sensor", "Part Present", "Button 1", "Button 2",
        "E-Stop Status", "Cycle Complete", "Material Low", "Safety Curtain"
    ]
    DO_LABELS = [
        "Stack Green", "Stack Yellow", "Stack Red", "Buzzer"
    ]
    AI_LABELS = ["Current Clamp (mA)", "Vibration (mm/s)"]

    def __init__(self, device_id: str = "EIO-01", linked_machine_id: str = None):
        self.device_id = device_id
        self.linked_machine_id = linked_machine_id  # Nearest machine for analog sim
        self.firmware_version = "OS60.3.1"
        self.boot_time = time.time()
        self.online = True

        # GPIO — 8 digital inputs
        self.digital_inputs: List[bool] = [False] * 8
        self._di_overrides: Dict[int, bool] = {}  # Manual overrides from UI

        # GPO — 4 digital outputs (controlled by Tulip / user)
        self.digital_outputs: List[bool] = [False] * 4

        # Analog inputs
        self.analog_inputs: List[float] = [0.0, 0.0]  # mA, mm/s

        # Light Kit — 2 strips
        self.light_kit: List[LightKitStrip] = [
            LightKitStrip(channel=0),
            LightKitStrip(channel=1),
        ]

        # Serial
        self.serial = SerialPort()

        # Simulation internals
        self._scan_timer = 0.0
        self._cycle_timer = 0.0
        self._door_timer = 0.0

    @property
    def uptime(self) -> float:
        return time.time() - self.boot_time

    def tick(self, dt: float, linked_machine: Any = None):
        """Advance simulation by dt seconds."""
        if not self.online:
            return

        t = time.time()
        self._cycle_timer += dt
        self._scan_timer += dt
        self._door_timer += dt

        # ── Digital Inputs (simulate sensor behavior) ─────────────
        # DI0: Door sensor — opens/closes periodically
        if 0 not in self._di_overrides:
            self.digital_inputs[0] = math.sin(self._door_timer * 0.15) > 0.7

        # DI1: Part present — pulses when machine is running
        if 1 not in self._di_overrides:
            if linked_machine and linked_machine.state.value == "running":
                self.digital_inputs[1] = math.sin(self._cycle_timer * 2.0) > 0.0
            else:
                self.digital_inputs[1] = False

        # DI2-DI3: Operator buttons — random presses
        if 2 not in self._di_overrides:
            self.digital_inputs[2] = random.random() < 0.003
        if 3 not in self._di_overrides:
            self.digital_inputs[3] = random.random() < 0.002

        # DI4: E-Stop — reflects machine fault state
        if 4 not in self._di_overrides:
            if linked_machine:
                self.digital_inputs[4] = linked_machine.state.value == "fault"
            else:
                self.digital_inputs[4] = False

        # DI5: Cycle complete — pulses periodically when running
        if 5 not in self._di_overrides:
            if linked_machine and linked_machine.state.value == "running":
                self.digital_inputs[5] = (int(self._cycle_timer * 10) % 50) == 0
            else:
                self.digital_inputs[5] = False

        # DI6: Material low — occasional trigger
        if 6 not in self._di_overrides:
            self.digital_inputs[6] = random.random() < 0.001

        # DI7: Safety curtain — normally False (safe)
        if 7 not in self._di_overrides:
            self.digital_inputs[7] = False

        # Apply manual overrides
        for pin, val in self._di_overrides.items():
            self.digital_inputs[pin] = val

        # ── Analog Inputs ─────────────────────────────────────────
        if linked_machine:
            tel = linked_machine.to_dict().get("telemetry", {})
            # AI0: Current clamp — correlates with power consumption
            power = tel.get("power_kw", 0)
            base_ma = 4.0 + (power / 15.0) * 16.0  # 4-20mA range
            noise = random.gauss(0, 0.3)
            self.analog_inputs[0] = round(max(4.0, min(20.0, base_ma + noise)), 2)

            # AI1: Vibration — correlates with machine vibration
            vib = tel.get("vibration_mm_s", 0)
            noise2 = random.gauss(0, 0.2)
            self.analog_inputs[1] = round(max(0.0, vib + noise2), 2)
        else:
            self.analog_inputs[0] = round(4.0 + random.gauss(0, 0.1), 2)
            self.analog_inputs[1] = round(max(0, random.gauss(1.0, 0.3)), 2)

        # ── Auto-update stack lights based on linked machine ──────
        if linked_machine:
            state = linked_machine.state.value
            self.digital_outputs[0] = state == "running"     # Green
            self.digital_outputs[1] = state == "idle"         # Yellow
            self.digital_outputs[2] = state == "fault"        # Red
            self.digital_outputs[3] = state == "fault"        # Buzzer on fault

            # Auto-update light kit channel 0 based on state
            lk0 = self.light_kit[0]
            if state == "running":
                lk0.mode = "solid"
                lk0.color = "#00ff66"
            elif state == "fault":
                lk0.mode = "pulse"
                lk0.color = "#ff3333"
            elif state == "idle":
                lk0.mode = "solid"
                lk0.color = "#ffcc00"
            elif state == "maintenance":
                lk0.mode = "chase"
                lk0.color = "#0099ff"
            else:
                lk0.mode = "off"

        # ── Serial: occasional barcode scan ───────────────────────
        if self._scan_timer > 8.0 + random.random() * 12.0:
            self.serial.simulate_scan()
            self._scan_timer = 0.0

    def set_digital_input(self, pin: int, value: bool):
        """Manual override a digital input pin."""
        if 0 <= pin < 8:
            self._di_overrides[pin] = value
            self.digital_inputs[pin] = value

    def clear_digital_input_override(self, pin: int):
        """Release manual override, return to simulation."""
        self._di_overrides.pop(pin, None)

    def set_digital_output(self, pin: int, value: bool):
        """Set a GPO output."""
        if 0 <= pin < 4:
            self.digital_outputs[pin] = value

    def set_light_kit(self, channel: int, mode: str = None, color: str = None,
                      brightness: float = None, active_leds: List[int] = None):
        """Control a light kit strip."""
        if 0 <= channel < 2:
            lk = self.light_kit[channel]
            if mode is not None:
                lk.mode = mode
            if color is not None:
                lk.color = color
            if brightness is not None:
                lk.brightness = max(0, min(1, brightness))
            if active_leds is not None:
                lk.active_leds = active_leds

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "device_type": "Edge IO",
            "firmware": self.firmware_version,
            "online": self.online,
            "uptime_s": round(self.uptime, 1),
            "linked_machine": self.linked_machine_id,
            "digital_inputs": {
                f"DI{i}": {"value": v, "label": self.DI_LABELS[i],
                            "override": i in self._di_overrides}
                for i, v in enumerate(self.digital_inputs)
            },
            "digital_outputs": {
                f"DO{i}": {"value": v, "label": self.DO_LABELS[i]}
                for i, v in enumerate(self.digital_outputs)
            },
            "analog_inputs": {
                f"AI{i}": {"value": v, "label": self.AI_LABELS[i]}
                for i, v in enumerate(self.analog_inputs)
            },
            "light_kit": [lk.to_dict() for lk in self.light_kit],
            "serial": self.serial.to_dict(),
        }
