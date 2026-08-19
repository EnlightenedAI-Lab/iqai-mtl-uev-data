import { createEvaluationUnitSource, createSelectableObjectSource } from "./evaluation-units-source.js";

const DATA_BASE =
  globalThis.IQAI_MTL_UEV_DATA_BASE_URL ||
  new URLSearchParams(location.search).get("data") ||
  "./data";

const source = createEvaluationUnitSource({ baseUrl: DATA_BASE });
const selectable = createSelectableObjectSource({ baseUrl: DATA_BASE });
const statsEl = document.getElementById("stats");
const selectedEl = document.getElementById("selected");
const provenanceEl = document.getElementById("provenance");

function dump(el, value) {
  el.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

source.getProvenance().then((prov) => dump(provenanceEl, prov || "provenance.json missing")).catch((err) => {
  dump(provenanceEl, String(err));
});

globalThis.require(["esri/Map", "esri/views/MapView", "esri/layers/GraphicsLayer", "esri/Graphic", "esri/geometry/support/webMercatorUtils"], (
  Map,
  MapView,
  GraphicsLayer,
  Graphic,
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

  let timer = null;
  let controller = null;

  function graphicFromFeature(feature) {
    const rings = feature.geometry.type === "Polygon"
      ? feature.geometry.coordinates
      : feature.geometry.coordinates.flat();
    const fill = Boolean(feature.properties.fill);
    return new Graphic({
      geometry: {
        type: "polygon",
        rings,
        spatialReference: { wkid: 4326 },
      },
      attributes: {
        source_id: feature.properties.source_id || null,
        fill,
        layer: feature.properties.layer,
      },
      symbol: {
        type: "simple-fill",
        color: fill
          ? [91, 163, 230, 0.10]
          : feature.properties.stacked
            ? [247, 201, 72, 0.18]
            : [91, 163, 230, 0.16],
        outline: { color: fill ? [91, 163, 230, 0.35] : [186, 220, 255, 0.9], width: fill ? 0.4 : 0.8 },
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
      for (const feature of result.features) {
        layer.add(graphicFromFeature(feature));
      }
      dump(statsEl, {
        fabric: result.fabric,
        layer: result.layer,
        cellsRequested: result.cellsRequested.length,
        cellsFetched: result.cellsFetched.length,
        cellsCached: result.cellsCached.length,
        bytes: result.bytes,
        featuresDecoded: result.featuresDecoded,
        ms: Math.round(performance.now() - started),
        cacheSize: source.cacheSize(),
        bbox: result.bbox,
        note: result.note,
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
    view.hitTest(event).then(async (hit) => {
      const graphic = hit.results.find((r) => r.graphic?.attributes)?.graphic;
      if (!graphic || graphic.attributes.fill || !graphic.attributes.source_id) {
        dump(selectedEl, graphic?.attributes?.fill
          ? "overview fill — zoom in for selectable ID_UEV"
          : "no unit");
        return;
      }
      dump(selectedEl, "resolving exact ID_UEV…");
      try {
        const resolved = await source.getById(graphic.attributes.source_id);
        if (!resolved) {
          dump(selectedEl, `no exact object for ${graphic.attributes.source_id}`);
          return;
        }
        const acquired = selectable.toAcquiredObject(resolved.feature);
        const props = resolved.feature.properties;
        dump(selectedEl, {
          objectClass: acquired.objectClass,
          sourceId: acquired.sourceId,
          sourceIdField: "ID_UEV",
          fabric: "exact",
          stacked: props.stacked,
          stackCount: props.stack_count,
          cubf: `${props.cubf_code || ""} ${props.cubf_label || ""}`.trim(),
          sourceAttributes: acquired.sourceAttributes,
          provenance: acquired.provenance,
          legalNote: acquired.legalNote,
        });
      } catch (err) {
        dump(selectedEl, String(err));
      }
    });
  });
});
