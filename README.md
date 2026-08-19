# IQAI Montréal evaluation units

Isolated Data Fabric worktree for Ville de Montréal **Unités d'évaluation foncière**.

This is a municipal evaluation-unit dataset. It is **not** legal cadastre and **not** proof of ownership.

## Official source

- Catalogue: https://donnees.montreal.ca/dataset/unites-evaluation-fonciere
- Dataset id: `4ad6baea-4d2c-460f-a8bf-5d000db498f7`
- Licence: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Publisher: Ville de Montréal — Service des finances et de l'évaluation foncière

IQAI downloads the current official GeoJSON zip, partitions it into viewport cells, and serves those cells as static files. Generated cells are not committed to git.

## Local build

```bash
pip install -r requirements.txt
python scripts/build_package.py
python -m http.server 4173 --directory _site
```

Proof page: http://127.0.0.1:4173/

Runtime clients must take a configurable base URL, for example:

```js
createEvaluationUnitSource({
  baseUrl: globalThis.IQAI_MTL_UEV_DATA_BASE_URL || "./data"
})
```

## Tests

```bash
node --test tests/evaluation-units-source.test.js
```

After the local server is up:

```bash
node tests/live-validate.mjs http://127.0.0.1:4173/data
```

## Object acquisition handoff

`createSelectableObjectSource()` exposes:

- `objectClass`: `evaluation_unit`
- official provider / dataset
- stable `source_id`
- geometry
- original source attributes
- provenance

It does not modify the World Object Acquisition engine.

## Attribution

Données © Ville de Montréal — Unités d'évaluation foncière (CC BY 4.0).
IQAI static spatial package is a derived partition for viewport access; it is not an official municipal service.
