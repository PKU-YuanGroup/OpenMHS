# OpenMHS website

An offline static-site generator for [OpenMHS — Model Hardware Standard](https://mhs.openai4s.org).
It renders the specification, schemas, capability catalog, device registry, the device market and SDK documentation.
Python 3.10+; no third-party packages or network access during the build.

```bash
python3 MHS/registry/build_index.py
PYTHONPATH=MHS/sdk/src python3 -m mhs market build --check
python3 MHS/site/build.py --release --site-url https://mhs.openai4s.org
python3 MHS/site/check.py --site-url https://mhs.openai4s.org --fresh
python3 MHS/site/serve.py 8080
```

`build.py` accepts `--out DIR` and `--site-url URL` (or `OPENMHS_SITE_URL`). Without a URL, the output also works
from `file://`. Registry inputs must exist; missing data produces an error with the command that generates it.

The device market comes from `MHS/drivers/market.json` (`mhs market build`): `/market/` (search and filters over
`assets/market-data.js`, the same compact index as `/market/index.json`), one page per category under
`/market/categories/`, and one page per package at `/market/<track>/<folder>/` with its introduction, what it measures,
adjusts and does, its upstream source and the three install commands (OpenAI4S, standalone MHS endpoint, MCP host).
`/market/market.json` is a verbatim copy of the source file.

`check.py` verifies internal links and fragments, local assets, JSON and JSON-LD, canonical URLs, schema and
capability identifiers, sitemap entries, download integrity and source freshness. It places no editorial
restrictions on language, organization metadata or notices.

`assets/` contains local styles and scripts. `deploy/` holds static-host configuration. The site is deployed to
GitHub Pages by `.github/workflows/pages.yml`; see [deployment instructions](deploy/README.md).
Project identifiers come from `MHS/sdk/src/mhs/_ids.py`. The build publishes schemas at `/schema/0.9/` and
writes the project's CNAME when the site URL is `https://mhs.openai4s.org`.
