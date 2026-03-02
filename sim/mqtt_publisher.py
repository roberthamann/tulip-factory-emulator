import asyncio
import json
import time
from sim.plant import Plant

try:
    import aiomqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False


class MQTTPublisher:
    def __init__(self, plant: Plant, host: str = "localhost", port: int = 1883, edge_devices=None):
        self.plant = plant
        self.host = host
        self.port = port
        self.edge_devices = edge_devices or []

    async def run(self):
        if not MQTT_AVAILABLE:
            print("[MQTT] aiomqtt not installed — skipping MQTT publishing")
            return

        while True:
            try:
                async with aiomqtt.Client(self.host, self.port) as client:
                    print(f"[MQTT] Connected to {self.host}:{self.port}")
                    await self._publish_loop(client)
            except Exception as e:
                print(f"[MQTT] Connection error: {e} — retrying in 5s")
                await asyncio.sleep(5)

    async def _publish_loop(self, client):
        while True:
            for machine in self.plant.all_machines:
                data = machine.to_dict()
                base = f"factory/{machine.line_id}/{machine.machine_id}"

                # Full telemetry bundle
                await client.publish(f"{base}/telemetry", json.dumps(data), qos=0)

                # Individual tags (for fine-grained subscriptions)
                await client.publish(f"{base}/state", data["state"], qos=0)
                for key, val in data["telemetry"].items():
                    await client.publish(f"{base}/{key}", str(val), qos=0)

                # Fault alerts (QoS 2 — at least once guaranteed)
                for fault in data["errors"]:
                    if time.time() - fault["timestamp"] < 1.5:
                        await client.publish(
                            f"factory/alerts/{machine.line_id}/{machine.machine_id}",
                            json.dumps(fault),
                            qos=2,
                        )

            # Plant-level summary
            await client.publish("factory/summary", json.dumps(self.plant.summary()), qos=0)

            # Edge IO devices
            for eio in self.edge_devices:
                base = f"factory/edge-io/{eio.device_id}"
                # Full state bundle
                await client.publish(f"{base}/status", json.dumps(eio.to_dict()), qos=0)
                # Individual GPIO pins
                for i, val in enumerate(eio.digital_inputs):
                    await client.publish(f"{base}/gpio/di/{i}", str(int(val)), qos=0)
                for i, val in enumerate(eio.digital_outputs):
                    await client.publish(f"{base}/gpio/do/{i}", str(int(val)), qos=0)
                # Analog channels
                for i, val in enumerate(eio.analog_inputs):
                    await client.publish(f"{base}/analog/{i}", str(val), qos=0)
                # Light Kit
                for lk in eio.light_kit:
                    await client.publish(f"{base}/lightkit/{lk.channel}", json.dumps(lk.to_dict()), qos=0)
                # Serial — only if recent scan
                if eio.serial.last_data and (time.time() - eio.serial.last_timestamp) < 2.0:
                    await client.publish(f"{base}/serial/scan", eio.serial.last_data, qos=1)

            await asyncio.sleep(1)
