/**
 * Viewport and geometry queries against the static Montréal evaluation-unit package.
 * Works in the browser and in Node. Does not load the citywide file.
 */

const OBJECT_CLASS = "evaluation_unit";

function bboxIntersects(a, b) {
  return !(a[2] < b[0] || a[0] > b[2] || a[3] < b[1] || a[1] > b[3]);
}

function extentToBbox(extent) {
  if (!extent) throw new Error("extent is required");
  if (Array.isArray(extent) && extent.length >= 4) {
    return [Number(extent[0]), Number(extent[1]), Number(extent[2]), Number(extent[3])];
  }
  const xmin = extent.xmin ?? extent.xMin ?? extent.minX;
  const ymin = extent.ymin ?? extent.yMin ?? extent.minY;
  const xmax = extent.xmax ?? extent.xMax ?? extent.maxX;
  const ymax = extent.ymax ?? extent.yMax ?? extent.maxY;
  if ([xmin, ymin, xmax, ymax].some((v) => v == null || Number.isNaN(Number(v)))) {
    throw new Error("extent must expose xmin,ymin,xmax,ymax");
  }
  return [Number(xmin), Number(ymin), Number(xmax), Number(ymax)];
}

function joinUrl(base, path) {
  return `${String(base).replace(/\/+$/, "")}/${String(path).replace(/^\/+/, "")}`;
}

function walkCoords(value, out = []) {
  if (!value) return out;
  if (typeof value[0] === "number") {
    out.push([value[0], value[1]]);
    return out;
  }
  for (const item of value) walkCoords(item, out);
  return out;
}

function geomBbox(geom) {
  const pts = walkCoords(geom?.coordinates);
  if (!pts.length) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of pts) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  return [minX, minY, maxX, maxY];
}

function centroidOf(geom) {
  const pts = walkCoords(geom?.coordinates);
  if (!pts.length) return null;
  let sx = 0;
  let sy = 0;
  for (const [x, y] of pts) {
    sx += x;
    sy += y;
  }
  return [sx / pts.length, sy / pts.length];
}

function pointInRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / ((yj - yi) || 1e-12) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function polygonRings(geom) {
  if (!geom) return [];
  if (geom.type === "Polygon") return [geom.coordinates[0] || []];
  if (geom.type === "MultiPolygon") return (geom.coordinates || []).map((poly) => poly[0] || []);
  return [];
}

function geometryHitsBbox(geom, bbox) {
  const gb = geomBbox(geom);
  if (!gb || !bboxIntersects(gb, bbox)) return false;
  const pts = walkCoords(geom?.coordinates);
  if (pts.some((p) => p[0] >= bbox[0] && p[0] <= bbox[2] && p[1] >= bbox[1] && p[1] <= bbox[3])) {
    return true;
  }
  const c = centroidOf(geom);
  return Boolean(c && c[0] >= bbox[0] && c[0] <= bbox[2] && c[1] >= bbox[1] && c[1] <= bbox[3]);
}

function geometryHitsPolygon(geom, polygon) {
  const pb = geomBbox(polygon);
  const gb = geomBbox(geom);
  if (!pb || !gb || !bboxIntersects(gb, pb)) return false;
  const rings = polygonRings(polygon);
  const unitRings = polygonRings(geom);
  const pts = walkCoords(geom?.coordinates);
  if (pts.some(([x, y]) => rings.some((ring) => pointInRing(x, y, ring)))) return true;
  const other = walkCoords(polygon?.coordinates);
  if (other.some(([x, y]) => unitRings.some((ring) => pointInRing(x, y, ring)))) return true;
  const c = centroidOf(geom);
  return Boolean(c && rings.some((ring) => pointInRing(c[0], c[1], ring)));
}

function expandUnits(cellFc, provenance, objectClass) {
  const features = [];
  for (const feature of cellFc.features || []) {
    const props = feature.properties || {};
    for (const unit of props.units || []) {
      features.push({
        type: "Feature",
        geometry: feature.geometry,
        properties: {
          object_class: objectClass,
          object_class_label: props.object_class_label,
          source_id: unit.source_id,
          source_id_field: unit.source_id_field,
          stacked: Boolean(props.stacked),
          stack_count: props.unit_count,
          stack_source_ids: props.source_ids,
          cubf_code: unit.cubf_code,
          cubf_label: unit.cubf_label,
          category: unit.category,
          civic_from: unit.civic_from,
          civic_to: unit.civic_to,
          street: unit.street,
          suite: unit.suite,
          storeys: unit.storeys,
          dwellings: unit.dwellings,
          year_built: unit.year_built,
          land_area_m2: unit.land_area_m2,
          building_area_m2: unit.building_area_m2,
          municipality_code: unit.municipality_code,
          municipality_name: unit.municipality_name,
          borough_code: unit.borough_code,
          matricule83: unit.matricule83,
          source: unit.source,
          derived: {
            stack_count: props.unit_count,
            stack_source_ids: props.source_ids,
            municipality_name: unit.municipality_name,
          },
          provenance,
        },
      });
    }
  }
  return features;
}

function cubfRollup(features) {
  const by = new Map();
  for (const feature of features) {
    const code = feature.properties.cubf_code || "UNKNOWN";
    const current = by.get(code) || {
      cubf_code: code,
      cubf_label: feature.properties.cubf_label || null,
      count: 0,
    };
    current.count += 1;
    if (!current.cubf_label && feature.properties.cubf_label) {
      current.cubf_label = feature.properties.cubf_label;
    }
    by.set(code, current);
  }
  return [...by.values()].sort(
    (a, b) => b.count - a.count || String(a.cubf_code).localeCompare(String(b.cubf_code)),
  );
}

export function cellsForBbox(manifest, bbox) {
  return (manifest.cells || []).filter((cell) => bboxIntersects(cell.bbox, bbox));
}

export function createEvaluationUnitSource(options = {}) {
  const baseUrl = String(options.baseUrl || "").replace(/\/+$/, "");
  if (!baseUrl) throw new Error("baseUrl is required");
  const fetchImpl = options.fetchImpl || globalThis.fetch;
  if (!fetchImpl) throw new Error("fetch is not available");

  const cache = new Map();
  const inflight = new Map();
  let manifestPromise = null;
  let provenancePromise = null;
  let viewportGen = 0;

  async function loadJson(path, signal) {
    const url = joinUrl(baseUrl, path);
    const res = await fetchImpl(url, { signal });
    if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
    const headerBytes = Number(res.headers.get("content-length") || 0);
    const json = await res.json();
    return { json, bytes: headerBytes || JSON.stringify(json).length, url };
  }

  async function getManifest() {
    if (!manifestPromise) manifestPromise = loadJson("manifest.json").then((row) => row.json);
    return manifestPromise;
  }

  async function getProvenance() {
    if (!provenancePromise) {
      provenancePromise = loadJson("provenance.json")
        .then((row) => row.json)
        .catch(() => null);
    }
    return provenancePromise;
  }

  async function getCell(cell, signal) {
    if (cache.has(cell.id)) return { ...cache.get(cell.id), cached: true };
    if (inflight.has(cell.id)) return { ...(await inflight.get(cell.id)), cached: true };
    const pending = loadJson(cell.path, signal)
      .then((loaded) => {
        const row = { id: cell.id, json: loaded.json, bytes: loaded.bytes, url: loaded.url };
        cache.set(cell.id, row);
        inflight.delete(cell.id);
        return row;
      })
      .catch((err) => {
        inflight.delete(cell.id);
        throw err;
      });
    inflight.set(cell.id, pending);
    return { ...(await pending), cached: false };
  }

  async function queryCells(bbox, signal) {
    const [manifest, provenance] = await Promise.all([getManifest(), getProvenance()]);
    const wanted = cellsForBbox(manifest, bbox);
    const loaded = [];
    let bytes = 0;
    let cacheHits = 0;
    for (const cell of wanted) {
      const row = await getCell(cell, signal);
      loaded.push(row);
      bytes += row.bytes || 0;
      if (row.cached) cacheHits += 1;
    }
    const seen = new Set();
    const features = [];
    const objectClass = manifest.object_class || OBJECT_CLASS;
    for (const row of loaded) {
      for (const feature of expandUnits(row.json, provenance, objectClass)) {
        const id = feature.properties.source_id;
        if (seen.has(id)) continue;
        if (!geometryHitsBbox(feature.geometry, bbox)) continue;
        seen.add(id);
        features.push(feature);
      }
    }
    return {
      manifest,
      provenance,
      wanted,
      loaded,
      cacheHits,
      bytes,
      features,
    };
  }

  return {
    objectClass: OBJECT_CLASS,
    getManifest,
    getProvenance,
    cacheSize() {
      return cache.size;
    },
    async queryEvaluationUnits(extent, queryOptions = {}) {
      const bbox = extentToBbox(extent);
      const gen = ++viewportGen;
      const result = await queryCells(bbox, queryOptions.signal);
      if (queryOptions.viewport !== false && gen !== viewportGen) {
        return { stale: true, features: [], count: 0, cellsRequested: result.wanted.map((c) => c.id), bytes: 0 };
      }
      return {
        stale: false,
        objectClass: result.manifest.object_class,
        bbox,
        features: result.features,
        count: result.features.length,
        cellsRequested: result.wanted.map((c) => c.id),
        cellsFetched: result.loaded.filter((row) => !row.cached).map((row) => row.id),
        cellsCached: result.loaded.filter((row) => row.cached).map((row) => row.id),
        cacheHits: result.cacheHits,
        bytes: result.bytes,
        provenance: result.provenance,
        legalNote: result.manifest.legal_note,
      };
    },
    async queryEvaluationUnitsWithinGeometry(geometry, queryOptions = {}) {
      const bbox = geomBbox(geometry);
      if (!bbox) throw new Error("geometry has no coordinates");
      const result = await queryCells(bbox, queryOptions.signal);
      const features = result.features.filter((feature) => geometryHitsPolygon(feature.geometry, geometry));
      return {
        objectClass: result.manifest.object_class,
        geometry,
        bbox,
        features,
        count: features.length,
        sourceIds: features.map((feature) => feature.properties.source_id),
        cubf: cubfRollup(features),
        cellsRequested: result.wanted.map((c) => c.id),
        cellsFetched: result.loaded.filter((row) => !row.cached).map((row) => row.id),
        cellsCached: result.loaded.filter((row) => row.cached).map((row) => row.id),
        bytes: result.bytes,
        provenance: result.provenance,
        legalNote: result.manifest.legal_note,
        note: "CUBF aggregation uses official CODE_UTILISATION / LIBELLE_UTILISATION only. No population or socioeconomic estimates.",
      };
    },
  };
}

export function createSelectableObjectSource(options = {}) {
  const source = createEvaluationUnitSource(options);
  return {
    contract: "iqai.selectable-object-source.v1",
    objectClass: OBJECT_CLASS,
    label: "EVALUATION UNIT",
    provider: "Ville de Montréal",
    dataset: "Unités d'évaluation foncière",
    datasetId: "4ad6baea-4d2c-460f-a8bf-5d000db498f7",
    identityField: "source_id",
    overlap: "container",
    selectable: true,
    legalNote: "Municipal evaluation unit. Not legal cadastre and not proof of ownership.",
    queryByExtent: (extent, opts) => source.queryEvaluationUnits(extent, opts),
    queryByGeometry: (geometry, opts) => source.queryEvaluationUnitsWithinGeometry(geometry, opts),
    toAcquiredObject(feature) {
      const props = feature?.properties || {};
      return {
        objectClass: OBJECT_CLASS,
        sourceId: props.source_id,
        provider: "Ville de Montréal",
        dataset: "Unités d'évaluation foncière",
        geometry: feature.geometry,
        sourceAttributes: props.source || {},
        provenance: props.provenance || null,
        legalNote: "Municipal evaluation unit. Not legal cadastre and not proof of ownership.",
      };
    },
  };
}
