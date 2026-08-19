import { createEvaluationUnitSource } from "./evaluation-units-source.js";

const DATA_BASE =
  globalThis.IQAI_MTL_UEV_DATA_BASE_URL ||
  new URLSearchParams(location.search).get("data") ||
  "./data";

const source = createEvaluationUnitSource({ baseUrl: DATA_BASE });
const statsEl = document.getElementById("stats");
const selectedEl = document.getElementById("selected");
const provenanceEl = document.getElementById("provenance");

function dump(el, value) {
  el.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

source.getProvenance().then((prov) => dump(provenanceEl, prov || "provenance.json missing")).catch((err) => {
  dump(provenanceEl, String(err));
});

globalThis.require(["esri/Map", "esri/views/MapView", "esri/layers/GraphicsLayer", "esri/Graphic", "esri/geometry/Polygon", "esri/geometry/support/webMercatorUtils"], (
  Map,
  MapView,
  GraphicsLayer,
  Graphic,
  Polygon,
  webMercatorUtils,
) => {
  const layer = new GraphicsLayer({ title: "Evaluation units" });
  const map = new Map({ basemap: "dark-gray-vector", layers: [layer] });
  const view = new MapView({
    container: "view",
    map,
    center: [-73.5673, 45.5017],
    zoom: 16,
    constraints: { rotationEnabled: false },
  });

  const byId = new Map();
  let timer = null;
  let controller = null;

  function graphicFromFeature(feature) {
    const rings = feature.geometry.type === "Polygon"
      ? feature.geometry.coordinates
      : feature.geometry.coordinates.flat();
    return new Graphic({
      geometry: {
        type: "polygon",
        rings,
        spatialReference: { wkid: 4326 },
      },
      attributes: {
        source_id: feature.properties.source_id,
        street: feature.properties.street,
        cubf_label: feature.properties.cubf_label,
        category: feature.properties.category,
      },
      symbol: {
        type: "simple-fill",
        color: feature.properties.stacked ? [247, 201, 72, 0.18] : [91, 163, 230, 0.16],
        outline: { color: [186, 220, 255, 0.9], width: 0.8 },
      },
    });
  }

  async function refresh() {
    const extent = webMercatorUtils.webMercatorToGeographic(view.extent);
    if (controller) controller.abort();
    controller = new AbortController();
    const started = performance.now();
    try {
      const result = await source.queryEvaluationUnits(extent, { signal: controller.signal });
      if (result.stale) return;
      layer.removeAll();
      byId.clear();
      for (const feature of result.features) {
        const graphic = graphicFromFeature(feature);
        byId.set(feature.properties.source_id, feature);
        layer.add(graphic);
      }
      dump(statsEl, {
        cellsRequested: result.cellsRequested,
        cellsFetched: result.cellsFetched,
        cellsCached: result.cellsCached,
        bytes: result.bytes,
        features: result.count,
        ms: Math.round(performance.now() - started),
        cacheSize: source.cacheSize(),
        bbox: result.bbox,
      });
    } catch (err) {
      if (err?.name === "AbortError") return;
      dump(statsEl, String(err));
    }
  }

  view.watch("extent", () => {
    clearTimeout(timer);
    timer = setTimeout(refresh, 180);
  });
  view.when(refresh);

  view.on("click", (event) => {
    view.hitTest(event).then((hit) => {
      const graphic = hit.results.find((r) => r.graphic?.attributes?.source_id)?.graphic;
      if (!graphic) {
        dump(selectedEl, "no unit");
        return;
      }
      const feature = byId.get(graphic.attributes.source_id);
      dump(selectedEl, {
        objectClass: feature.properties.object_class,
        sourceId: feature.properties.source_id,
        sourceIdField: feature.properties.source_id_field,
        address: [feature.properties.civic_from, feature.properties.street, feature.properties.suite].filter(Boolean).join(" "),
        cubf: `${feature.properties.cubf_code || ""} ${feature.properties.cubf_label || ""}`.trim(),
        category: feature.properties.category,
        stacked: feature.properties.stacked,
        stackCount: feature.properties.stack_count,
        source: feature.properties.source,
        derived: feature.properties.derived,
        provenance: feature.properties.provenance,
        legalNote: "Municipal evaluation unit. Not legal cadastre and not proof of ownership.",
      });
    });
  });
});
