import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createEvaluationUnitSource, createSelectableObjectSource, cellsForBbox } from "../src/runtime/evaluation-units-source.js";

const root = dirname(fileURLToPath(import.meta.url));
const fixture = join(root, "fixtures", "package");

function startServer() {
  const server = createServer((req, res) => {
    try {
      const rel = decodeURIComponent(req.url.split("?")[0]).replace(/^\/+/, "");
      const body = readFileSync(join(fixture, rel));
      res.writeHead(200, { "content-type": "application/json" });
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end("missing");
    }
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
  });
}

test("bbox selects only intersecting cells", () => {
  const manifest = JSON.parse(readFileSync(join(fixture, "manifest.json"), "utf8"));
  const downtown = cellsForBbox(manifest, [-73.57, 45.50, -73.56, 45.51]);
  const west = cellsForBbox(manifest, [-73.80, 45.45, -73.79, 45.46]);
  assert.equal(downtown.length, 1);
  assert.equal(downtown[0].id, "c_0.01_43_16");
  assert.equal(west.length, 0);
});

test("viewport query returns source identities, caches cells, and aborts stale work", async () => {
  const { server, baseUrl } = await startServer();
  try {
    const source = createEvaluationUnitSource({ baseUrl });
    const first = await source.queryEvaluationUnits([-73.57, 45.50, -73.56, 45.51]);
    assert.equal(first.stale, false);
    assert.equal(first.count, 2);
    assert.deepEqual(first.cellsFetched, ["c_0.01_43_16"]);
    assert.equal(first.features[0].properties.object_class, "evaluation_unit");
    assert.ok(first.features[0].properties.source.ID_UEV);
    assert.equal(first.features[0].properties.provenance.license, "CC-BY-4.0");

    const second = await source.queryEvaluationUnits([-73.57, 45.50, -73.56, 45.51]);
    assert.deepEqual(second.cellsCached, ["c_0.01_43_16"]);
    assert.equal(source.cacheSize(), 1);

    const selectable = createSelectableObjectSource({ baseUrl });
    const acquired = selectable.toAcquiredObject(first.features[0]);
    assert.equal(acquired.objectClass, "evaluation_unit");
    assert.equal(acquired.sourceId, first.features[0].properties.source_id);
    assert.equal(acquired.geometry.type, "Polygon");
  } finally {
    server.close();
  }
});

test("geometry query returns ids, attributes, geometry, provenance, and CUBF rollup", async () => {
  const { server, baseUrl } = await startServer();
  try {
    const source = createEvaluationUnitSource({ baseUrl });
    const polygon = {
      type: "Polygon",
      coordinates: [[
        [-73.569, 45.501],
        [-73.561, 45.501],
        [-73.561, 45.508],
        [-73.569, 45.508],
        [-73.569, 45.501],
      ]],
    };
    const result = await source.queryEvaluationUnitsWithinGeometry(polygon);
    assert.ok(result.count >= 1);
    assert.ok(result.sourceIds.includes("1001"));
    assert.equal(result.features[0].geometry.type, "Polygon");
    assert.ok(result.provenance.provider);
    assert.ok(result.cubf.some((row) => row.count >= 1));
    assert.match(result.note, /CUBF/);
  } finally {
    server.close();
  }
});
