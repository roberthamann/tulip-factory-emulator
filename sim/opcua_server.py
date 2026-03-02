import asyncio
import logging
from asyncua import Server
from sim.plant import Plant

log = logging.getLogger(__name__)


class OPCUAServer:
    def __init__(self, plant: Plant, endpoint: str = "opc.tcp://0.0.0.0:4840/factory/"):
        self.plant = plant
        self.endpoint = endpoint
        self.server = None
        self._node_map: dict = {}  # machine_id -> {tag: node}

    async def start(self):
        self.server = Server()
        await self.server.init()
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name("Factory Simulation OPC UA Server")

        uri = "http://acme.factory/opcua"
        idx = await self.server.register_namespace(uri)
        objects = self.server.nodes.objects

        factory_node = await objects.add_object(idx, "FactoryFloor")

        for line in self.plant.lines:
            line_node = await factory_node.add_object(idx, f"Line_{line.line_id}")
            for machine in line.machines:
                m_node = await line_node.add_object(idx, machine.machine_id)
                self._node_map[machine.machine_id] = {}

                data = machine.to_dict()
                tags = {
                    "State": data["state"],
                    **{k: float(v) for k, v in data["telemetry"].items()},
                    "ActiveFaultCount": float(len(machine.errors)),
                }

                for tag, value in tags.items():
                    node = await m_node.add_variable(idx, tag, value)
                    await node.set_writable()
                    self._node_map[machine.machine_id][tag] = node

        await self.server.start()
        print(f"[OPC UA] Listening at {self.endpoint}")
        asyncio.create_task(self._update_loop())

    async def _update_loop(self):
        while True:
            for machine in self.plant.all_machines:
                nodes = self._node_map.get(machine.machine_id, {})
                data = machine.to_dict()
                updates = {
                    "State": data["state"],
                    **{k: float(v) for k, v in data["telemetry"].items()},
                    "ActiveFaultCount": float(len(machine.errors)),
                }
                for tag, value in updates.items():
                    node = nodes.get(tag)
                    if node:
                        try:
                            await node.write_value(value if isinstance(value, str) else float(value))
                        except Exception as e:
                            log.warning("[OPC UA] Failed to write %s/%s: %s", machine.machine_id, tag, e)
            await asyncio.sleep(1)
