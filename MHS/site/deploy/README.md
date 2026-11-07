# Deploy the OpenMHS website

The project website is **https://mhs.openai4s.org**.
The workflow template `MHS/site/deploy/.github/workflows/pages.yml` is ready for this domain.
Deployment is not enabled in this publication; copy the template to `.github/workflows/pages.yml` when ready.

## Build and verify locally

```bash
python3 MHS/sdk/tools/sync_data.py
python3 MHS/registry/build_index.py
python3 MHS/site/build.py --release --site-url https://mhs.openai4s.org --out /tmp/openmhs-site
python3 MHS/site/check.py --site /tmp/openmhs-site --site-url https://mhs.openai4s.org --fresh
python3 MHS/site/serve.py 8080 --site /tmp/openmhs-site
```

The build writes `CNAME` for the project domain, canonical links and a sitemap. It publishes the schema files at
`/schema/0.9/`, matching the SDK's schema identifiers. Existing `/schema/*.schema.json` download links also work.
Missing registry data is reported directly; the build does not invent catalog records.

## GitHub Pages

Use GitHub Actions as the Pages source and `mhs.openai4s.org` as the custom domain.
The domain's DNS must point to `PKU-YuanGroup.github.io`. The workflow builds registry indexes, verifies links,
assets and source digests, and deploys the generated artifact. Generated site output is not committed.

## Other hosts

Use `--site-url` with your deployment URL; builds for other hosts do not write the project's CNAME.
The generated directory works with any static host. `_headers` contains suggested HTTP security headers.
