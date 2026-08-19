# IQAI Montréal evaluation units

Isolated Data Fabric worktree for Ville de Montréal **Unités d'évaluation foncière**.

This is a municipal evaluation-unit dataset. It is **not** legal cadastre and **not** proof of ownership.

## Official source

- Catalogue: https://donnees.montreal.ca/dataset/unites-evaluation-fonciere
- Dataset id: `4ad6baea-4d2c-460f-a8bf-5d000db498f7`
- Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Publisher: Ville de Montréal — Service des finances et de l'évaluation foncière

IQAI downloads the current official GeoJSON zip once (`scripts/build_package.py`), then builds a dual-fabric static delivery (`scripts/build_delivery.py`). Generated cells are not committed to `main`.

## Delivery fabrics (v1.1)

**Display fabric** — zoom-dependent simplified footprints for drawing. The browser does not decode citywide full-resolution polygons to paint a broad map.

**Exact object fabric** — `ID_UEV`, exact source geometry, original publisher attributes, provenance. Fetched on demand for close zoom, hit/acquisition, Inspector, and `queryWithinGeometry`.

## Local build

```bash
pip install -r requirements.txt
python scripts/build_package.py
python scripts/build_delivery.py
python -m http.server 4191 --directory _site
```

Do not re-run `build_package.py` unless the accepted V1 source package in `dist/` is missing. Delivery rebuilds from `dist/`.

Proof page: http://127.0.0.1:4191/

Runtime clients must take a configurable base URL, for example:

```js
createEvaluationUnitSource({
  baseUrl: globalThis.IQAI_MTL_UEV_DATA_BASE_URL || "./data"
})
```

Public delivery (when GitHub Pages is enabled from `gh-pages`):

`https://enlightenedai-lab.github.io/iqai-mtl-uev-data/data`

## Tests

```bash
node --test tests/evaluation-units-source.test.js
```

After the local server is up:

```bash
node tests/live-validate.mjs http://127.0.0.1:4191/data
```

## Object acquisition handoff

`createSelectableObjectSource()` exposes:

- `objectClass`: `evaluation_unit`
- official provider / dataset
- stable `source_id` (`ID_UEV`)
- display candidates from `queryByExtent`
- exact geometry + original source attributes via `acquire(id)` / `getById`
- provenance

It does not modify the World Object Acquisition engine.

## Attribution

Données © Ville de Montréal — Unités d'évaluation foncière (CC BY 4.0).
IQAI static spatial package is a derived partition for viewport access; it is not an official municipal service.
