# Deployment kit — OpenMHS site

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

The generated site is fully static: no functions, no database, no runtime and
no external asset host. This directory holds the files the build copies into
the output, plus a GitHub Pages workflow template.

| File | Purpose |
|---|---|
| `robots.txt` | Crawl policy. The build appends `Sitemap: <site-url>/sitemap.xml` when a site URL is given. |
| `_headers` | Cloudflare Pages / Netlify-style headers: CSP, HSTS, frame denial, permissions policy and cache policy (assets revalidate hourly because filenames are not content-hashed). |
| `.github/workflows/pages.yml` | GitHub Actions template: build for the Pages URL, run `check.py`, deploy. |
| `README.md` | This runbook. |

There is **no committed domain**. The site URL is a build parameter
(`--site-url` or `$OPENMHS_SITE_URL`); without it the build emits no canonical
links and no sitemap, and the site still works from `file://` or any static
host. Never deploy to, or claim, a domain you do not control.

## 1. Build and verify

```bash
python3 MHS/registry/build_index.py      # the registry aggregates are git-ignored; a fresh clone has none
python3 MHS/site/build.py --release \
    --site-url https://<owner>.github.io/<repo> --out /tmp/openmhs-site
python3 MHS/site/check.py --site /tmp/openmhs-site \
    --site-url https://<owner>.github.io/<repo> --fresh
python3 MHS/site/serve.py 8080 --site /tmp/openmhs-site    # local preview
```

- `--release` fails instead of falling back to the synthetic registry when
  `MHS/registry/index.json` is missing.
- `check.py` fails on broken links or fragments, missing assets, duplicate
  ids, external resource loads, invalid JSON or JSON-LD, an Organization
  JSON-LD node, a page without the non-affiliation notice, a capability id
  that is not in `MHS/spec/capabilities.json`, a download manifest without
  source digests, or canonical/sitemap URLs outside `--site-url`. With
  `--fresh` it also fails when the downloads or the page sources no longer match the checkout.

The output is deterministic and idempotent for a fixed source tree and site
URL. The build uses only the Python standard library and makes no network
requests.

## 2. GitHub Pages (recommended)

1. Copy `deploy/.github/workflows/pages.yml` to the repository root as
   `.github/workflows/pages.yml`.
2. In **Settings → Pages**, choose **GitHub Actions** as the source.
3. The workflow asks Pages for its base URL, builds the registry aggregates,
   builds with `--release --site-url <that URL>`, runs `check.py --fresh` and
   deploys the result.
4. Optional custom domain that **you own**: set it in **Settings → Pages →
   Custom domain**, add the DNS records GitHub shows for it, and enable
   **Enforce HTTPS** once the certificate is issued. With the Actions source
   no `CNAME` file is needed in the repository; the Pages base URL then
   reflects the custom domain.

## 3. Other static hosts (Cloudflare Pages, Netlify, any web server)

1. Build command: `python3 MHS/registry/build_index.py && python3 MHS/site/build.py --release --site-url "$OPENMHS_SITE_URL" --out dist-site`
   with `OPENMHS_SITE_URL` set to the URL you will serve, for example
   `https://docs.example.org` on a domain you control.
2. Output directory: `dist-site`.
3. `_headers` is applied by hosts that support the format. Check with
   `curl -sI <your-url>/ | grep -i content-security-policy`; HSTS is sent by
   `_headers`, so only serve over HTTPS.
4. On a plain web server, translate `_headers` into the server's own header
   configuration.

Only one host should serve the canonical URL. Point any other deployment at a
staging hostname and build it with that hostname as `--site-url`.

## 4. Security posture

- No third-party scripts, fonts, analytics or CDNs are loaded. The Content
  Security Policy allows no third-party origins.
- The only storage is the `mhs-theme` key in `localStorage`; there are no
  cookies and no network calls from the playground.
- `frame-ancestors 'none'` plus `X-Frame-Options: DENY` prevent embedding.
- The registry and SDK pages are static; no credentials are present in the
  generated output.
- Run `check.py` in CI before every deploy.

## 5. Rollback

Every deploy is a complete static snapshot. Redeploy a previous commit with the
same build command, or roll back the deployment in the host's dashboard. There
is no database migration and no runtime state to restore.
