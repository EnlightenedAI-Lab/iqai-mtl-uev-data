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

`toAcquiredObject(feature)` returns:

- objectClass
- sourceId (`ID_UEV`)
- provider / dataset
- geometry
- sourceAttributes (original publisher fields)
- provenance
- legalNote

Configure `baseUrl` from `IQAI_MTL_UEV_DATA_BASE_URL`. Do not hard-code a host in Spatial V2.
