# OpenMHS static site

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

The documentation site for OpenMHS. It is a deterministic static build with no
runtime dependencies, no external assets and no tracking. It works from
`file://` as well as from any static host. Every page opens with the
non-affiliation notice above and links to the secondary page *Relation to
Anthropic's MHS preview*.

## Build and verify

```bash
python3 MHS/site/build.py                     # writes MHS/site/_site/ (no site URL)
python3 MHS/site/build.py --out DIR --site-url https://docs.example.org
python3 MHS/site/build.py --release ...       # fail if MHS/registry/index.json is missing
python3 MHS/site/check.py [--site DIR] [--site-url URL] [--fresh]
python3 MHS/site/serve.py 8080 [--site DIR]   # preview at http://127.0.0.1:8080/
```

- **Site URL.** `--site-url` (or `$OPENMHS_SITE_URL`) sets the base for
  canonical links, `og:url`, JSON-LD URLs, `robots.txt` and `sitemap.xml`.
  There is no default host: without a URL the build writes no canonical links
  and no sitemap. No `CNAME` is ever written; a custom domain is a deployment
  setting (see [`deploy/README.md`](deploy/README.md)).
- **Output.** `--out DIR` builds elsewhere. The build only replaces a directory
  that is empty, is the default `_site/`, or carries the `.openmhs-site`
  marker of a previous build.
- **Release.** Without `MHS/registry/index.json` an ordinary build fills the
  registry explorer with clearly labelled synthetic records so the interface
  stays testable; `--release` refuses to do that.
- **Identifiers.** The project name, versions and the non-affiliation sentence
  come from `MHS/sdk/src/mhs/_ids.py`.

Inputs (read-only for the generator):

| Input | Used for |
|---|---|
| `MHS/spec/*.md` | specification browser (one page per document; long documents are split at a section boundary to stay under the 100 KB budget) |
| `MHS/spec/capabilities.json` | capability catalogue, schema viewer and download |
| `MHS/schema/*.json` + `examples/` | schema reference, links from the specification, schema bundle |
| `MHS/registry/index.json` | registry explorer and per-package detail pages |
| `MHS/registry/manifests/**` | raw adapter manifest snippets on detail pages, copied into the output |
| `MHS/registry/families/*.md` | one bridge-family recipe page per family |
| `MHS/conformance/reports/*.json` | reference conformance evidence and raw report downloads |
| `MHS/sdk/README.md`, `MHS/sdk/docs/*.md`, `MHS/sdk/INTERFACE.md` | SDK overview, guides and interface contract |
| `integration/openai4s/DESIGN.md` | OpenAI4S host integration design (when present) |
| `MHS/spec/appendix-d-anthropic-mhs.md` | the `/anthropic-mhs/` page on the relation to Anthropic's preview |
| `LICENSE`, `LICENSE-docs`, `NOTICE` | licence files shipped inside the download bundles |

The generated pages are all relative-linked. The build is **byte-for-byte
idempotent** for a fixed source tree and site URL: it contains no wall-clock
values, and the two ZIP bundles use fixed timestamps.

## Output

The output contains the home page, the specification browser, the registry
explorer and one detail page per package, the capability catalogue and schema
viewer, family recipes, conformance, SDK, host, playground, governance,
downloads, about, search and 404 pages. It also emits `assets/`,
`favicon.svg`, `robots.txt`, `_headers`, `.nojekyll`, the `.openmhs-site`
marker and, with a site URL, `sitemap.xml`.

`download/download-manifest.json` records the size and SHA-256 of every
download and, under `inputs`, the SHA-256 of every source file the downloads
were built from.

Every non-explorer HTML page is below 100 KB uncompressed. The only pages above
the budget are the registry explorer and its generated detail pages, which are
excluded by design.

## What `check.py` verifies

`check.py` is a static checker, not a browser test. It fails on broken links
or fragments, missing local assets, duplicate ids, external resource loads,
path-absolute links, invalid JSON, JSON-LD or data assets, an `Organization`
JSON-LD node, any page without the non-affiliation notice, canonical or
sitemap URLs outside the site URL, a capability id outside the catalogue
(`cap.internal.*` and `cap.x.*` are reserved namespaces; specification pages
may name only the two example ids listed in `SPEC_EXAMPLE_IDS`), a download
whose digest does not match, a download manifest without input digests or
without page-source digests, or with bundle members that are not recorded
inputs, and pages over the size budget. A site that is stale against the
current sources is a warning, or an error with `--fresh`. Staleness covers the
download inputs and the page sources (specification text, SDK guides,
conformance reports, site assets and deploy files, the generator itself).

## Deploy

See [`deploy/README.md`](deploy/README.md): GitHub Pages (workflow template in
`deploy/.github/workflows/pages.yml`) or any static host, always with a URL
you control.

## Constraints

The site is standard-library-only: no npm, no pip installs, no external fonts,
no CDNs, no analytics. The playground is a local JavaScript reference model and
makes no network requests. The only client storage is the `mhs-theme` key in
`localStorage`.
