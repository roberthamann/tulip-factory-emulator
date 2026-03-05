"use strict";
// opcua-bridge/bridge.js
// Polls the factory REST API (:3000) and re-exposes all machine data
// as an OPC UA server on :4841 for the Tulip Connector Host.
//
// Node tree mirrors the Python OPC UA server:
//   Objects / FactoryFloor / Line_{id} / {machine_id} / {tag}

const { OPCUAServer, Variant, DataType } = require("node-opcua");
const http = require("http");

const UPSTREAM = "http://localhost:3000/api/plant";
const PORT = 4841;
const POLL_MS = 1000;

// Live value cache: { [machineId]: { [tagName]: value } }
const cache = {};

function fetchPlant() {
  return new Promise((resolve, reject) => {
    http
      .get(UPSTREAM, (res) => {
        let raw = "";
        res.on("data", (chunk) => (raw += chunk));
        res.on("end", () => {
          try {
            resolve(JSON.parse(raw));
          } catch (e) {
            reject(e);
          }
        });
      })
      .on("error", reject);
  });
}

function tagsForMachine(machine) {
  return {
    State: machine.state,
    ...Object.fromEntries(
      Object.entries(machine.telemetry).map(([k, v]) => [k, typeof v === "string" ? v : Number(v)])
    ),
    ActiveFaultCount: machine.errors ? machine.errors.length : 0,
  };
}

async function buildNamespace(addressSpace, plant) {
  const ns = addressSpace.getOwnNamespace();

  const factoryNode = ns.addObject({
    organizedBy: addressSpace.rootFolder.objects,
    browseName: "FactoryFloor",
  });

  for (const line of plant.lines) {
    const lineNode = ns.addObject({
      organizedBy: factoryNode,
      browseName: `Line_${line.line_id}`,
    });

    for (const machine of line.machines) {
      const mNode = ns.addObject({
        componentOf: lineNode,
        browseName: machine.machine_id,
      });

      cache[machine.machine_id] = tagsForMachine(machine);

      for (const [tag, value] of Object.entries(cache[machine.machine_id])) {
        const isStr = typeof value === "string";
        const id = machine.machine_id; // capture for closure

        ns.addVariable({
          componentOf: mNode,
          browseName: tag,
          dataType: isStr ? "String" : "Double",
          minimumSamplingInterval: 1000,
          value: {
            get: () =>
              new Variant({
                dataType: isStr ? DataType.String : DataType.Double,
                value: cache[id][tag],
              }),
          },
        });
      }
    }
  }
}

async function main() {
  const server = new OPCUAServer({
    port: PORT,
    resourcePath: "/factory/",
    buildInfo: {
      productName: "Factory OPC UA Bridge",
      buildNumber: "1",
      buildDate: new Date(),
    },
  });

  await server.initialize();

  // Wait for factory sim to be ready
  let plant;
  while (!plant) {
    try {
      plant = await fetchPlant();
    } catch (_) {
      console.log("[bridge] Waiting for factory sim at", UPSTREAM, "...");
      await new Promise((r) => setTimeout(r, 2000));
    }
  }

  await buildNamespace(server.engine.addressSpace, plant);

  await server.start();
  console.log(
    `[bridge] OPC UA Bridge listening — opc.tcp://localhost:${PORT}/factory/`
  );

  // Poll loop — update cache values every second
  setInterval(async () => {
    try {
      const updated = await fetchPlant();
      for (const line of updated.lines) {
        for (const machine of line.machines) {
          if (!cache[machine.machine_id]) continue;
          Object.assign(cache[machine.machine_id], tagsForMachine(machine));
        }
      }
    } catch (_) {
      // Factory sim temporarily unreachable — serve stale values
    }
  }, POLL_MS);
}

main().catch((err) => {
  console.error("[bridge] Fatal:", err.message);
  process.exit(1);
});
