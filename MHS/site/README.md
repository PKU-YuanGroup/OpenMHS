# OpenMHS website

An offline static-site generator for [OpenMHS — Model Hardware Standard](https://mhs.openai4s.org).
It renders the specification, schemas, capability catalog, device registry and SDK documentation.
Python 3.10+; no third-party packages or network access during the build.

```bash
python3 MHS/registry/build_index.py
python3 MHS/site/build.py --release --site-url https://mhs.openai4s.org
python3 MHS/site/check.py --site-url https://mhs.openai4s.org --fresh
python3 MHS/site/serve.py 8080
```

`build.py` accepts `--out DIR` and `--site-url URL` (or `OPENMHS_SITE_URL`). Without a URL, the output also works
from `file://`. Registry inputs must exist; missing data produces an error with the command that generates it.

`check.py` verifies internal links and fragments, local assets, JSON and JSON-LD, canonical URLs, schema and
capability identifiers, sitemap entries, download integrity and source freshness. It places no editorial
restrictions on language, organization metadata or notices.

`assets/` contains local styles and scripts. `deploy/` holds static-host configuration and the Pages workflow
template. Deployment can be enabled later; see [deployment instructions](deploy/README.md).
Project identifiers come from `MHS/sdk/src/mhs/_ids.py`. The build publishes schemas at `/schema/0.9/` and
writes the project's CNAME when the site URL is `https://mhs.openai4s.org`.
