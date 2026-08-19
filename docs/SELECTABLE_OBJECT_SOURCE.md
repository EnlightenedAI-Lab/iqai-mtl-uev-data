# Selectable object source — evaluation unit

Contract for World Object Acquisition. This repository does not modify that engine.

```js
{
  contract: "iqai.selectable-object-source.v1",
  objectClass: "evaluation_unit",
  label: "EVALUATION UNIT",
  provider: "Ville de Montréal",
  dataset: "Unités d'évaluation foncière",
  datasetId: "4ad6baea-4d2c-460f-a8bf-5d000db498f7",
  identityField: "source_id",
  overlap: "container",
  selectable: true,
  legalNote: "Municipal evaluation unit. Not legal cadastre and not proof of ownership."
}
```

Use `createSelectableObjectSource({ baseUrl })` from `src/runtime/evaluation-units-source.js`.

Viewport queries use the **display** fabric (simplified geometry, stable representative `ID_UEV`).

Exact resolution:

- `source.getById(id)`
- `selectable.acquire(id)` — preferred handoff
- `queryByGeometry` / `queryEvaluationUnitsWithinGeometry` — exact source geometry and original publisher attributes

`toAcquiredObject(feature)` is for an **exact** feature (after `getById` / `acquire` / geometry query). It returns:

- objectClass
- sourceId (`ID_UEV`)
- provider / dataset
- geometry
- sourceAttributes (original publisher fields)
- provenance
- legalNote

Configure `baseUrl` from `IQAI_MTL_UEV_DATA_BASE_URL`. Do not hard-code a host in Spatial V2.
