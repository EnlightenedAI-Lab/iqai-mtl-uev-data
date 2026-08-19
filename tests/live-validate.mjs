import { createEvaluationUnitSource } from "../src/runtime/evaluation-units-source.js";
import { resolve } from "node:path";

const downtown = [-73.578, 45.498, -73.555, 45.512];
const neighbourhood = [-73.62, 45.48, -73.54, 45.54];
const wider = [-73.65, 45.47, -73.52, 45.56];
const samplePolygon = {
  type: "Polygon",
  coordinates: [[
    [-73.571, 45.503],
    [-73.565, 45.503],
    [-73.565, 45.508],
    [-73.571, 45.508],
    [-73.571, 45.503],
  ]],
};

async function run(baseUrl) {
  const source = createEvaluationUnitSource({ baseUrl });
  const manifest = await source.getManifest();
  const totalCells = (manifest.cells || []).length;
  const views = [
    ["downtown", downtown],
    ["neighbourhood", neighbourhood],
    ["wider", wider],
  ];
  const report = { baseUrl, totalCells, views: [] };
  for (const [name, bbox] of views) {
    const started = Date.now();
    const result = await source.queryEvaluationUnits(bbox);
    report.views.push({
      name,
      cellsRequested: result.cellsRequested.length,
      cellsFetched: result.cellsFetched.length,
      bytes: result.bytes,
      features: result.count,
      ms: Date.now() - started,
      fullCityDownloaded: result.cellsRequested.length === totalCells,
    });
  }
  const cached = await source.queryEvaluationUnits(downtown);
  report.downtownRepeatCacheHits = cached.cacheHits;
  report.fullCityDownloadedOnOpen = report.views[0].fullCityDownloaded;
  const geomStarted = Date.now();
  const geom = await source.queryEvaluationUnitsWithinGeometry(samplePolygon);
  report.geometryQuery = {
    count: geom.count,
    sourceIdsSample: geom.sourceIds.slice(0, 8),
    cubfTop: geom.cubf.slice(0, 8),
    cellsRequested: geom.cellsRequested.length,
    ms: Date.now() - geomStarted,
    provenanceProvider: geom.provenance?.provider || geom.provenance?.attribution || null,
  };
  console.log(JSON.stringify(report, null, 2));
  if (report.fullCityDownloadedOnOpen) process.exitCode = 2;
}

const arg = process.argv[2];
if (!arg) {
  console.error("usage: node tests/live-validate.mjs <data-base-url>");
  process.exit(1);
}
if (!arg.startsWith("http")) {
  console.error("Use a local static server, not a file path:", resolve(arg));
  process.exit(1);
}
run(arg);
