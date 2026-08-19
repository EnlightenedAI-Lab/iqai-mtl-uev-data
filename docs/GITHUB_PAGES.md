# GitHub Pages

Publish only the optimized delivery site (`_site`), never the 782 MB source GeoJSON or the V1 uncompressed cell dump.

## Branch deployment (no workflow file)

The environment token lacks `workflow` scope, so GitHub Actions cannot be used. Pages can still be published from the `gh-pages` branch at `/` (root).

1. Build: `python scripts/build_delivery.py`
2. Publish the contents of `_site` to orphan branch `gh-pages`.
   Do not add `cache/`, `dist/`, or any file larger than 100 MB.
3. Repository setting (manual if the API is denied):
   Settings → Pages → Build and deployment → Source: **Deploy from a branch**
   Branch: `gh-pages` / `/` (root)

Expected public base:

`https://enlightenedai-lab.github.io/iqai-mtl-uev-data/data`

Proof: `https://enlightenedai-lab.github.io/iqai-mtl-uev-data/`

Runtime clients still take `IQAI_MTL_UEV_DATA_BASE_URL`. Do not hard-code the host in Spatial V2.

`.nojekyll` is included so GitHub Pages does not run Jekyll on `.json.gz` assets.
