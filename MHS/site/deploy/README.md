# Deploy the OpenMHS website

The project website is **https://mhs.openai4s.org**.
Deployment is active: [`.github/workflows/pages.yml`](../../../.github/workflows/pages.yml) builds and deploys the site to
GitHub Pages on every push to `main` that touches `MHS/**` (or the workflow itself), and on demand (`workflow_dispatch`).

## Build and verify locally

```bash
python3 MHS/sdk/tools/sync_data.py
python3 MHS/registry/build_index.py
PYTHONPATH=MHS/sdk/src python3 -m mhs market build --check
python3 MHS/site/build.py --release --site-url https://mhs.openai4s.org --out /tmp/openmhs-site
python3 MHS/site/check.py --site /tmp/openmhs-site --site-url https://mhs.openai4s.org --fresh
python3 MHS/site/serve.py 8080 --site /tmp/openmhs-site
```

The build writes `CNAME` for the project domain, canonical links and a sitemap. It publishes the schema files at
`/schema/0.9/`, matching the SDK's schema identifiers. Existing `/schema/*.schema.json` download links also work.
Missing registry or market data is reported directly; the build does not invent catalog records.

The device market (`/market/`) is rendered from `MHS/drivers/market.json`, which `mhs market build` writes from the driver
packages whose gate passed. After a driver package changes, run `PYTHONPATH=MHS/sdk/src python3 -m mhs market build` and
commit the file; the workflow refuses a stale one (`--check`), and `check.py --fresh` notices a site built from an older one.

## GitHub Pages

Use GitHub Actions as the Pages source and `mhs.openai4s.org` as the custom domain.
The domain's DNS must point to `PKU-YuanGroup.github.io`. The workflow mirrors the SDK data, builds the registry
aggregates, checks that the market is current, builds the site into `_site`, verifies links, assets and source digests,
and deploys the generated artifact (`pages: write`, `id-token: write`, one deployment at a time in the `pages`
concurrency group). Generated site output is not committed.

## Other hosts

Use `--site-url` with your deployment URL; builds for other hosts do not write the project's CNAME.
The generated directory works with any static host. `_headers` contains suggested HTTP security headers.
