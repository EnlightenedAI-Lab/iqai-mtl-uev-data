# GitHub Pages

The GitHub OAuth token in this environment lacks the `workflow` scope, so the
publish Action could not be pushed.

To publish the generated package:

1. Add a `workflow` scope token.
2. Restore `.github/workflows/publish.yml` from the local design: checkout, Python 3.12, `pip install -r requirements.txt`, `python scripts/build_package.py`, upload `_site` with `actions/upload-pages-artifact`, deploy with `actions/deploy-pages`.
3. Set Pages source to GitHub Actions.

Until then, serve locally:

```bash
python scripts/build_package.py
python -m http.server 4187 --directory _site
```

Runtime base URL: `IQAI_MTL_UEV_DATA_BASE_URL`.
