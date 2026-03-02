import asyncio
import yaml
import uvicorn
from pathlib import Path

from sim.plant import Plant
from sim.opcua_server import OPCUAServer
from sim.mqtt_publisher import MQTTPublisher
from sim.edge_io import EdgeIODevice
from sim.ai_brain import AIBrain
from dashboard.server import app, broadcast_plant_state
import dashboard.server as dashboard_module

CONFIG_PATH = Path(__file__).parent / "config" / "plant_config.yaml"


async def main():
    # Load config
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    # Build plant
    plant = Plant(config)
    dashboard_module.plant = plant

    # Create Edge IO device linked to first machine on Line 1
    first_machine_id = config["lines"][0]["machines"][0]["id"]
    edge_io = EdgeIODevice(device_id="EIO-01", linked_machine_id=first_machine_id)
    dashboard_module.edge_devices = [edge_io]

    # Edge IO tick callback
    def tick_edge_io():
        linked = plant.get_machine(edge_io.linked_machine_id)
        edge_io.tick(plant._tick_interval, linked)
    plant.on_tick(lambda: tick_edge_io())

    # Register broadcast as tick callback
    plant.on_tick(broadcast_plant_state)

    # Build services
    opcua = OPCUAServer(plant, config["opcua"]["endpoint"])
    mqtt = MQTTPublisher(plant, config["mqtt"]["host"], config["mqtt"]["port"], edge_devices=[edge_io])

    server_cfg = config["server"]
    uvicorn_config = uvicorn.Config(
        app,
        host=server_cfg["host"],
        port=server_cfg["port"],
        log_level="warning",
    )
    uvicorn_server = uvicorn.Server(uvicorn_config)

    print("=" * 60)
    print("  ACME Factory Simulation — Hybrid Stack")
    print("=" * 60)
    print(f"  Dashboard:  http://localhost:{server_cfg['port']}")
    print(f"  REST API:   http://localhost:{server_cfg['port']}/api/plant")
    print(f"  WebSocket:  ws://localhost:{server_cfg['port']}/ws")
    print(f"  OPC UA:     opc.tcp://localhost:4840/factory/")
    print(f"  MQTT:       mqtt://localhost:1883  (topic: factory/#)")
    print(f"  Edge IO:    {edge_io.device_id} → linked to {edge_io.linked_machine_id}")
    print("=" * 60)

    # Run all services concurrently
    brain = AIBrain(plant, interval=45)

    await asyncio.gather(
        plant.run(),
        opcua.start(),
        mqtt.run(),
        brain.run(),
        uvicorn_server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
