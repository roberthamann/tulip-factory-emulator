import random
from .base import BaseMachine, gauss


class MillingMachine(BaseMachine):
    nominal_throughput = 45.0
    machine_type_label = "CNC Mill"

    def __init__(self, machine_id, line_id):
        super().__init__(machine_id, "mill", line_id)
        self.spindle_speed_rpm = 0.0
        self.feed_rate_mm_min = 0.0
        self.depth_of_cut_mm = 0.0
        self.coolant_flow_lpm = 0.0

    def _machine_specific_running(self, dt):
        self.spindle_speed_rpm = abs(gauss(8000, 300))
        self.feed_rate_mm_min = abs(gauss(500, 40))
        self.depth_of_cut_mm = abs(gauss(2.5, 0.15))
        self.coolant_flow_lpm = abs(gauss(12.0, 0.8))

    def to_dict(self):
        d = super().to_dict()
        d["telemetry"].update({
            "spindle_speed_rpm": round(self.spindle_speed_rpm),
            "feed_rate_mm_min": round(self.feed_rate_mm_min),
            "depth_of_cut_mm": round(self.depth_of_cut_mm, 2),
            "coolant_flow_lpm": round(self.coolant_flow_lpm, 1),
        })
        return d


class Lathe(BaseMachine):
    nominal_throughput = 60.0
    machine_type_label = "CNC Lathe"

    def __init__(self, machine_id, line_id):
        super().__init__(machine_id, "lathe", line_id)
        self.spindle_speed_rpm = 0.0
        self.chuck_pressure_bar = 0.0
        self.cutting_speed_m_min = 0.0

    def _machine_specific_running(self, dt):
        self.spindle_speed_rpm = abs(gauss(1200, 100))
        self.chuck_pressure_bar = abs(gauss(6.5, 0.2))
        self.cutting_speed_m_min = abs(gauss(180, 15))

    def to_dict(self):
        d = super().to_dict()
        d["telemetry"].update({
            "spindle_speed_rpm": round(self.spindle_speed_rpm),
            "chuck_pressure_bar": round(self.chuck_pressure_bar, 2),
            "cutting_speed_m_min": round(self.cutting_speed_m_min, 1),
        })
        return d


class Grinder(BaseMachine):
    nominal_throughput = 55.0
    machine_type_label = "Surface Grinder"

    def __init__(self, machine_id, line_id):
        super().__init__(machine_id, "grinder", line_id)
        self.wheel_speed_rpm = 0.0
        self.table_speed_mm_min = 0.0
        self.grinding_force_n = 0.0
        self.spark_intensity = 0.0

    def _machine_specific_running(self, dt):
        self.wheel_speed_rpm = abs(gauss(3600, 50))
        self.table_speed_mm_min = abs(gauss(3000, 200))
        self.grinding_force_n = abs(gauss(450, 30))
        self.spark_intensity = abs(gauss(0.65, 0.1))

    def to_dict(self):
        d = super().to_dict()
        d["telemetry"].update({
            "wheel_speed_rpm": round(self.wheel_speed_rpm),
            "table_speed_mm_min": round(self.table_speed_mm_min),
            "grinding_force_n": round(self.grinding_force_n, 1),
            "spark_intensity": round(self.spark_intensity, 3),
        })
        return d


class Press(BaseMachine):
    nominal_throughput = 80.0
    machine_type_label = "Hydraulic Press"

    def __init__(self, machine_id, line_id):
        super().__init__(machine_id, "press", line_id)
        self.press_force_kn = 0.0
        self.hydraulic_pressure_bar = 0.0
        self.stroke_position_mm = 0.0

    def _machine_specific_running(self, dt):
        self.press_force_kn = abs(gauss(250, 20))
        self.hydraulic_pressure_bar = abs(gauss(180, 10))
        self.stroke_position_mm = abs(gauss(150, 5))

    def to_dict(self):
        d = super().to_dict()
        d["telemetry"].update({
            "press_force_kn": round(self.press_force_kn, 1),
            "hydraulic_pressure_bar": round(self.hydraulic_pressure_bar, 1),
            "stroke_position_mm": round(self.stroke_position_mm, 1),
        })
        return d


class DrillPress(BaseMachine):
    nominal_throughput = 70.0
    machine_type_label = "Drill Press"

    def __init__(self, machine_id, line_id):
        super().__init__(machine_id, "drill", line_id)
        self.spindle_speed_rpm = 0.0
        self.feed_rate_mm_rev = 0.0
        self.thrust_force_n = 0.0

    def _machine_specific_running(self, dt):
        self.spindle_speed_rpm = abs(gauss(2400, 150))
        self.feed_rate_mm_rev = abs(gauss(0.15, 0.02))
        self.thrust_force_n = abs(gauss(800, 60))

    def to_dict(self):
        d = super().to_dict()
        d["telemetry"].update({
            "spindle_speed_rpm": round(self.spindle_speed_rpm),
            "feed_rate_mm_rev": round(self.feed_rate_mm_rev, 3),
            "thrust_force_n": round(self.thrust_force_n, 1),
        })
        return d


class CNCRouter(BaseMachine):
    nominal_throughput = 40.0
    machine_type_label = "CNC Router"

    def __init__(self, machine_id, line_id):
        super().__init__(machine_id, "cnc", line_id)
        self.x_position_mm = 0.0
        self.y_position_mm = 0.0
        self.z_position_mm = 0.0
        self.spindle_load_pct = 0.0

    def _machine_specific_running(self, dt):
        self.x_position_mm = abs(gauss(500, 200))
        self.y_position_mm = abs(gauss(300, 100))
        self.z_position_mm = abs(gauss(50, 20))
        self.spindle_load_pct = abs(gauss(65, 10))

    def to_dict(self):
        d = super().to_dict()
        d["telemetry"].update({
            "x_position_mm": round(self.x_position_mm, 2),
            "y_position_mm": round(self.y_position_mm, 2),
            "z_position_mm": round(self.z_position_mm, 2),
            "spindle_load_pct": round(self.spindle_load_pct, 1),
        })
        return d


class Conveyor(BaseMachine):
    nominal_throughput = 120.0
    machine_type_label = "Conveyor Belt"

    def __init__(self, machine_id, line_id):
        super().__init__(machine_id, "conveyor", line_id)
        self.belt_speed_m_min = 0.0
        self.belt_tension_n = 0.0
        self.load_kg = 0.0

    def _machine_specific_running(self, dt):
        self.belt_speed_m_min = abs(gauss(12.0, 0.5))
        self.belt_tension_n = abs(gauss(1200, 80))
        self.load_kg = abs(gauss(45, 10))

    def to_dict(self):
        d = super().to_dict()
        d["telemetry"].update({
            "belt_speed_m_min": round(self.belt_speed_m_min, 2),
            "belt_tension_n": round(self.belt_tension_n, 1),
            "load_kg": round(self.load_kg, 1),
        })
        return d


# Registry for factory construction
MACHINE_REGISTRY = {
    "mill": MillingMachine,
    "lathe": Lathe,
    "grinder": Grinder,
    "press": Press,
    "drill": DrillPress,
    "cnc": CNCRouter,
    "conveyor": Conveyor,
}
