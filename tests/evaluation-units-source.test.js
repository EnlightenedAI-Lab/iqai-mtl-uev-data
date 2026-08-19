import test from "node:test";
import assert from "node:assert/strict";
import { gzipSync } from "node:zlib";
import { createServer } from "node:http";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createEvaluationUnitSource,
  createSelectableObjectSource,
  cellsForBbox,
  displayLayerForBbox,
} from "../src/runtime/evaluation-units-source.js";

const root = dirname(fileURLToPath(import.meta.url));
const fixture = join(root, "fixtures", "package");

function startServer() {
  const server = createServer((req, res) => {
    try {
      const rel = decodeURIComponent(req.url.split("?")[0]).replace(/^\/+/, "");
      const gz = rel.endsWith(".gz");
      const packed = join(fixture, rel);
      const unpacked = gz ? join(fixture, rel.slice(0, -3)) : packed;
      const body = existsSync(packed)
        ? readFileSync(packed)
        : gz
          ? gzipSync(readFileSync(unpacked))
          : readFileSync(unpacked);
      res.writeHead(200, {
        "content-type": gz ? "application/gzip" : "application/json",
        "content-length": body.length,
      });
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

test("bbox selects display layer by span and only intersecting cells", () => {
  const manifest = JSON.parse(readFileSync(join(fixture, "manifest.json"), "utf8"));
  const downtown = [-73.57, 45.50, -73.56, 45.51];
  const layer = displayLayerForBbox(manifest, downtown);
  assert.equal(layer.id, "detail");
  const cells = cellsForBbox(layer.cells, downtown);
  assert.equal(cells.length, 1);
  assert.equal(cells[0].id, "d_0.01_53_15");
  const west = cellsForBbox(layer.cells, [-73.80, 45.45, -73.79, 45.46]);
  assert.equal(west.length, 0);
});

test("viewport query draws display footprints, caches cells, and does not expand stacked units", async () => {
  const { server, baseUrl } = await startServer();
  try {
    const source = createEvaluationUnitSource({ baseUrl });
    const first = await source.queryEvaluationUnits([-73.57, 45.50, -73.56, 45.51]);
    assert.equal(first.stale, false);
    assert.equal(first.fabric, "display");
    assert.equal(first.layer, "detail");
    assert.equal(first.count, 1);
    assert.deepEqual(first.cellsFetched, ["d_0.01_53_15"]);
    assert.equal(first.features[0].properties.source_id, "1001");
    assert.equal(first.features[0].properties.stack_count, 2);
    assert.equal(first.features[0].properties.source, undefined);

    const second = await source.queryEvaluationUnits([-73.57, 45.50, -73.56, 45.51]);
    assert.deepEqual(second.cellsCached, ["d_0.01_53_15"]);
    assert.ok(source.cacheSize() >= 1);
  } finally {
    server.close();
  }
});

test("getById resolves exact geometry, source attributes, and provenance", async () => {
  const { server, baseUrl } = await startServer();
  try {
    const source = createEvaluationUnitSource({ baseUrl });
    const resolved = await source.getById("1001");
    assert.equal(resolved.feature.properties.source_id, "1001");
    assert.equal(resolved.feature.geometry.type, "Polygon");
    assert.equal(resolved.feature.properties.source.ID_UEV, 1001);
    assert.equal(resolved.feature.properties.cubf_code, "1000");
    assert.equal(resolved.feature.properties.provenance.license, "CC-BY-4.0");

    const selectable = createSelectableObjectSource({ baseUrl });
    const acquired = await selectable.acquire("1002");
    assert.equal(acquired.objectClass, "evaluation_unit");
    assert.equal(acquired.sourceId, "1002");
    assert.equal(acquired.geometry.type, "Polygon");
    assert.equal(acquired.sourceAttributes.ID_UEV, 1002);
  } finally {
    server.close();
  }
});

test("geometry query uses exact fabric and returns ids, attributes, geometry, provenance, and CUBF rollup", async () => {
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
    assert.equal(result.fabric, "exact");
    assert.ok(result.count >= 1);
    assert.ok(result.sourceIds.includes("1001"));
    assert.equal(result.features[0].geometry.type, "Polygon");
    assert.ok(result.features[0].properties.source.ID_UEV);
    assert.ok(result.provenance.provider);
    assert.ok(result.cubf.some((row) => row.count >= 1));
    assert.match(result.note, /CUBF/);
  } finally {
    server.close();
  }
});
