#!/usr/bin/env python3
"""Verify a generated OpenMHS site.

Fails (exit 1) on broken internal links or fragments, missing local assets,
duplicate DOM ids, external resource references, path-absolute links that would
break file://, invalid JSON/JSON-LD/data assets, canonical or sitemap URLs outside
the site URL, missing required files, an invalid sitemap, a bad download
digest, a download manifest without SHA-256 digests of its source inputs, a
capability id that is not in ``MHS/spec/capabilities.json``, or any
non-explorer HTML page over 100 KB.

    python3 MHS/site/check.py [--site DIR] [--site-url URL] [--capabilities FILE]
                              [--fresh] [--verbose]

``--site`` defaults to ``MHS/site/_site``.  The site URL defaults to
``$OPENMHS_SITE_URL`` and otherwise is inferred from the home page's canonical
link; a site built without a URL must have no canonical links and no sitemap.
``--fresh`` also fails when the recorded digests (the download inputs and the
page sources: specification text, SDK guides, conformance reports, site assets
and the generator) no longer match the sources in this checkout (a stale
build); without it staleness is a warning.

This is a static checker. It does not run a browser or a JavaScript engine.
"""

from __future__ import annotations

import argparse
import hashlib
import html.parser
import importlib.util
import json
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
MHS = HERE.parent
WORKSPACE = MHS.parent
DEFAULT_SITE = HERE / "_site"
DEFAULT_CAPABILITIES = MHS / "spec" / "capabilities.json"
IDS_FILE = MHS / "sdk" / "src" / "mhs" / "_ids.py"
SITE = DEFAULT_SITE
SIZE_BUDGET = 100 * 1024
# Capability ids: ``cap.<segment>(.<segment>)*.v<N>``, not part of x-cap.* or a path.
CAP_ID_RE = re.compile(r"(?<![A-Za-z0-9_.\-/])cap\.(?:[a-z0-9_]+\.)+v[0-9]+(?![A-Za-z0-9_])")
# Reserved namespaces that are not catalogue classes: receipts of protocol
# methods (cap.internal.*) and vendor extensions (cap.x.*).
CAP_RESERVED_PREFIXES = ("cap.internal.", "cap.x.")
# Ids the specification text names on purpose although the catalogue has no such class (a forbidden example and a
# version-two illustration).  Allowed on spec pages only.
SPEC_EXAMPLE_IDS = frozenset({"cap.motion.move.v1", "cap.fluid.aspirate.v2"})
CAP_SCAN_SUFFIXES = {".html", ".js", ".json", ".jsonl", ".md", ".txt", ".xml", ".csv", ".svg"}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


RESOURCE_RELS = {
    "stylesheet", "icon", "preload", "modulepreload", "manifest",
    "apple-touch-icon", "mask-icon", "prefetch", "prerender",
}
RESOURCE_TAGS = {
    "script": ("src",),
    "img": ("src", "srcset"),
    "source": ("src", "srcset"),
    "iframe": ("src",),
    "video": ("src", "poster"),
    "audio": ("src",),
    "track": ("src",),
    "object": ("data",),
    "embed": ("src",),
    "input": ("src",),
    "use": ("href", "xlink:href"),
}


class PageParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[tuple[str, str]] = []          # (kind, target)
        self.resources: list[tuple[str, str]] = []      # (label, target)
        self.lang = ""
        self.title = ""
        self.has_main = False
        self.has_skip = False
        self.has_viewport = False
        self.description = ""
        self.canonical = ""
        self.jsonld: list[str] = []
        self.inline_styles: list[str] = []
        self.inline_scripts: list[str] = []
        self._in_title = False
        self._in_style = False
        self._in_script = False
        self._script_type = ""
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.lang = attrs.get("lang", "")
        if "id" in attrs:
            self.ids.append(attrs["id"])
            if attrs["id"] == "main":
                self.has_main = True
        if attrs.get("class") and "skip-link" in attrs["class"]:
            self.has_skip = True
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            name = (attrs.get("name") or "").lower()
            if name == "description":
                self.description = attrs.get("content", "")
            if name == "viewport":
                self.has_viewport = True
        if tag == "link":
            rels = {r.strip().lower() for r in (attrs.get("rel") or "").split()}
            href = attrs.get("href") or ""
            if "canonical" in rels:
                self.canonical = href
            if rels & RESOURCE_RELS:
                self.resources.append(("link:" + ",".join(sorted(rels)), href))
        if tag == "a" and attrs.get("href"):
            self.links.append(("a", attrs["href"]))
        for attr_name in RESOURCE_TAGS.get(tag, ()):
            value = attrs.get(attr_name)
            if value:
                if attr_name == "srcset":
                    for candidate in value.split(","):
                        part = candidate.strip().split()
                        if part:
                            self.resources.append((tag + ":srcset", part[0]))
                else:
                    self.resources.append((tag + ":" + attr_name, value))
        if attrs.get("style"):
            self.inline_styles.append(attrs["style"])
        if tag == "style":
            self._in_style = True
            self._buffer = []
        if tag == "script":
            self._in_script = True
            self._script_type = (attrs.get("type") or "").lower()
            self._buffer = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_style:
            self._buffer.append(data)
        if self._in_script:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "style" and self._in_style:
            self.inline_styles.append("".join(self._buffer))
            self._in_style = False
        if tag == "script" and self._in_script:
            if self._script_type == "application/ld+json":
                self.jsonld.append("".join(self._buffer))
            else:
                self.inline_scripts.append("".join(self._buffer))
            self._in_script = False


def is_remote(target: str) -> bool:
    return target.startswith(("http://", "https://", "//"))


def host_of(target: str) -> str:
    try:
        return urlsplit(target if "//" in target else "//" + target).hostname or ""
    except ValueError:
        return ""


SELF_HOSTS: set[str] = set()


def is_self_host(target: str) -> bool:
    return bool(SELF_HOSTS) and host_of(target) in SELF_HOSTS


def normalize_base(url: str) -> str:
    """Return a site URL without its trailing slash ("" when unset)."""
    return (url or "").strip().rstrip("/")


def jsonld_types(node) -> list[str]:
    """Return every ``@type`` value found anywhere in a JSON-LD payload."""
    found: list[str] = []
    if isinstance(node, dict):
        kind = node.get("@type")
        if isinstance(kind, str):
            found.append(kind)
        elif isinstance(kind, list):
            found.extend(k for k in kind if isinstance(k, str))
        for value in node.values():
            found.extend(jsonld_types(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(jsonld_types(value))
    return found


def load_catalogue_ids(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("capabilities", []) if isinstance(data, dict) else data
    ids: set[str] = set()
    for item in items or []:
        if isinstance(item, dict):
            cap_id = item.get("capability_id") or item.get("id")
            if isinstance(cap_id, str):
                ids.add(cap_id)
    return ids


def check_css_urls(css: str, source: str, base_dir: Path, errors: list[str]) -> None:
    for url in re.findall(r"@import\s+(?:url\()?['\"]?([^'\")\s;]+)", css):
        if is_remote(url):
            errors.append(f"{source}: external CSS @import {url!r}")
        elif not (base_dir / url.split("?")[0]).resolve().is_file():
            errors.append(f"{source}: CSS @import references missing file {url!r}")
    for match in re.findall(r"url\((['\"]?)([^)'\"]+)\1\)", css):
        asset = match[1].strip()
        if not asset or asset.startswith(("data:", "#")):
            continue
        if is_remote(asset):
            errors.append(f"{source}: external CSS url() {asset!r}")
        elif not (base_dir / asset.split("?")[0].split("#")[0]).resolve().is_file():
            errors.append(f"{source}: CSS references missing asset {asset!r}")


def check(
    site: Path | None = None,
    *,
    site_url: str | None = None,
    capabilities: Path | None = None,
    fresh: bool = False,
    verbose: bool = False,
) -> int:
    global SITE
    SITE = (site or DEFAULT_SITE).resolve()
    if not SITE.is_dir():
        print(f"missing build output: {SITE}", file=sys.stderr)
        print("run: python3 MHS/site/build.py [--out DIR]", file=sys.stderr)
        return 1

    errors: list[str] = []
    warnings: list[str] = []
    pages: list[Path] = sorted(SITE.rglob("*.html"))
    total_bytes = 0
    html_bytes = 0
    largest: list[tuple[int, str]] = []
    ids_by_page: dict[str, set[str]] = {}
    area_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"files": 0, "bytes": 0, "pages": 0, "html": 0}
    )
    external_hosts: Counter[str] = Counter()
    external_resource_count = 0
    duplicate_reports: set[str] = set()
    page_meta: dict[str, PageParser] = {}

    base = normalize_base(site_url if site_url is not None else os.environ.get("OPENMHS_SITE_URL", ""))
    if not base and (SITE / "index.html").is_file():
        home = PageParser()
        try:
            home.feed((SITE / "index.html").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - reported again in the page loop
            pass
        base = normalize_base(home.canonical)
    SELF_HOSTS.clear()
    if base:
        if not base.startswith(("https://", "http://")):
            errors.append(f"site URL is not an absolute http(s) URL: {base!r}")
        host = host_of(base)
        if host:
            SELF_HOSTS.add(host)
        if base.startswith("http://") and host not in ("127.0.0.1", "localhost", "::1"):
            warnings.append(f"site URL is not HTTPS: {base!r}")
    jsonld_type_counts: Counter[str] = Counter()

    all_files = [p for p in SITE.rglob("*") if p.is_file()]
    for path in all_files:
        rel = path.relative_to(SITE).as_posix()
        area = rel.split("/")[0] if "/" in rel else "root"
        size = path.stat().st_size
        total_bytes += size
        area_stats[area]["files"] += 1
        area_stats[area]["bytes"] += size

    for page in pages:
        rel = page.relative_to(SITE).as_posix()
        area = rel.split("/")[0] if "/" in rel else "root"
        size = page.stat().st_size
        html_bytes += size
        area_stats[area]["pages"] += 1
        area_stats[area]["html"] += size
        largest.append((size, rel))
        try:
            text = page.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"{rel}: not valid UTF-8")
            continue
        if "\x00" in text:
            errors.append(f"{rel}: contains NUL characters")
        parser = PageParser()
        try:
            parser.feed(text)
        except Exception as exc:  # noqa: BLE001 - parser errors are page errors
            errors.append(f"{rel}: HTML parse failed: {exc}")
            continue
        page_meta[rel] = parser
        ids_by_page[rel] = set(parser.ids)
        for element_id, count in Counter(parser.ids).items():
            if count > 1:
                duplicate_reports.add(f"{element_id}:{rel}")
                errors.append(f"{rel}: duplicate id #{element_id} ({count} occurrences)")

        if not parser.lang:
            errors.append(f"{rel}: missing <html lang>")
        if not parser.title.strip():
            errors.append(f"{rel}: missing <title>")
        if not parser.description:
            errors.append(f"{rel}: missing meta description")
        if not parser.has_main:
            errors.append(f'{rel}: missing <main id="main">')
        if not parser.has_skip:
            errors.append(f"{rel}: missing skip link")
        if not parser.has_viewport:
            warnings.append(f"{rel}: missing viewport meta")
        if base:
            if rel not in ("404.html", "search/index.html") and not parser.canonical:
                warnings.append(f"{rel}: missing canonical link")
            if parser.canonical and not parser.canonical.startswith(base + "/"):
                errors.append(f"{rel}: canonical is outside the site URL {base!r}: {parser.canonical!r}")
        elif parser.canonical:
            errors.append(f"{rel}: canonical link {parser.canonical!r} but the site has no site URL")

        for payload in parser.jsonld:
            try:
                document = json.loads(payload)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel}: invalid JSON-LD ({exc})")
                continue
            types = jsonld_types(document)
            jsonld_type_counts.update(types)

        for css in parser.inline_styles:
            check_css_urls(css, rel, page.parent, errors)

        for kind, target in parser.links:
            if not target or target.startswith(("mailto:", "tel:", "javascript:", "data:")):
                continue
            if is_remote(target):
                external_hosts[host_of(target)] += 1
                if target.startswith("http://"):
                    warnings.append(f"{rel}: insecure external anchor {target!r}")
                continue
            if target.startswith("//"):
                errors.append(f"{rel}: protocol-relative link {target!r}")
            elif target.startswith("/") and not target.startswith("//"):
                errors.append(f"{rel}: path-absolute link breaks file:// ({target!r})")

        for label, target in parser.resources:
            if not target or target.startswith(("data:", "#")):
                continue
            if is_remote(target):
                if is_self_host(target):
                    errors.append(f"{rel}: absolute resource reference {target!r} ({label})")
                else:
                    external_resource_count += 1
                    errors.append(f"{rel}: external resource {target!r} ({label})")
                continue
            if target.startswith("//"):
                external_resource_count += 1
                errors.append(f"{rel}: protocol-relative resource {target!r} ({label})")
                continue
            if target.startswith("/"):
                errors.append(f"{rel}: path-absolute resource breaks file:// ({target!r})")
                continue
            parts = urlsplit(target)
            path = unquote(parts.path)
            if not path:
                continue
            resolved = (page.parent / path).resolve()
            try:
                resolved.relative_to(SITE.resolve())
            except ValueError:
                errors.append(f"{rel}: resource escapes site root: {target!r}")
                continue
            if resolved.is_dir():
                resolved = resolved / "index.html"
            if not resolved.is_file():
                errors.append(f"{rel}: missing local resource {target!r} ({label})")
                continue
            if resolved.suffix == ".css":
                check_css_urls(
                    resolved.read_text(encoding="utf-8", errors="replace"),
                    rel, resolved.parent, errors,
                )

    # Internal links: resolve targets and verify fragments.
    for page in pages:
        rel = page.relative_to(SITE).as_posix()
        parser = page_meta.get(rel)
        if not parser:
            continue
        for kind, target in parser.links:
            if not target or target.startswith(("mailto:", "tel:", "javascript:", "data:")):
                continue
            if is_remote(target):
                continue
            if target.startswith("#"):
                path = ""
                fragment = unquote(target[1:])
                target_rel = rel
            elif target.startswith(("/", "//")):
                continue
            else:
                parts = urlsplit(target)
                path = unquote(parts.path)
                fragment = unquote(parts.fragment)
                if not path:
                    target_rel = rel
                else:
                    resolved = (page.parent / path).resolve()
                    try:
                        resolved.relative_to(SITE.resolve())
                    except ValueError:
                        errors.append(f"{rel}: link escapes site root: {target!r}")
                        continue
                    if resolved.is_dir():
                        resolved = resolved / "index.html"
                    if not resolved.is_file():
                        errors.append(f"{rel}: broken link {target!r}")
                        continue
                    target_rel = resolved.relative_to(SITE.resolve()).as_posix()
            if fragment and target_rel.endswith(".html"):
                target_ids = ids_by_page.get(target_rel)
                if target_ids is None:
                    target_page = SITE / target_rel
                    if target_page.is_file():
                        target_parser = PageParser()
                        try:
                            target_parser.feed(target_page.read_text(encoding="utf-8", errors="replace"))
                            target_ids = set(target_parser.ids)
                        except Exception:  # noqa: BLE001
                            target_ids = set()
                    else:
                        target_ids = set()
                if fragment not in target_ids:
                    errors.append(f"{rel}: broken fragment {target!r} (no #{fragment} in {target_rel})")

    # JSON files and generated JS data payloads.
    data_files = sorted(SITE.rglob("*.json"))
    for path in data_files:
        rel = path.relative_to(SITE).as_posix()
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{rel}: invalid JSON ({exc})")
    for name in ("registry-data.js", "capabilities-data.js", "search-index.js", "market-data.js"):
        path = SITE / "assets" / name
        if not path.is_file():
            errors.append(f"missing data asset: assets/{name}")
            continue
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^window\.MHS_[A-Z_]+ = (.*);\s*$", text, re.S)
        if not match:
            errors.append(f"assets/{name}: unexpected wrapper")
            continue
        try:
            json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            errors.append(f"assets/{name}: invalid JSON payload ({exc})")

    # Downloads: digest manifest, source-input digests and zip integrity.
    manifest_path = SITE / "download" / "download-manifest.json"
    stale_inputs: list[str] = []
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for entry in manifest.get("files", []):
                path = SITE / "download" / entry["path"]
                if not path.is_file():
                    errors.append(f"download manifest references missing file {entry['path']}")
                    continue
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if "sha256:" + digest != entry.get("sha256"):
                    errors.append(f"download manifest digest mismatch for {entry['path']}")
            inputs = manifest.get("inputs")
            input_digests: set[str] = set()
            if not isinstance(inputs, list) or not inputs:
                errors.append("download-manifest.json: no 'inputs' with SHA-256 digests of the source files")
                inputs = []
            seen_inputs: set[str] = set()
            for entry in inputs:
                source = entry.get("path") if isinstance(entry, dict) else None
                digest = entry.get("sha256") if isinstance(entry, dict) else None
                if not isinstance(source, str) or not source or source.startswith("/") or ".." in source.split("/"):
                    errors.append(f"download-manifest.json: bad input path {source!r}")
                    continue
                if source in seen_inputs:
                    errors.append(f"download-manifest.json: duplicate input {source}")
                seen_inputs.add(source)
                if not isinstance(digest, str) or not DIGEST_RE.match(digest):
                    errors.append(f"download-manifest.json: input {source} has no sha256 digest")
                    continue
                input_digests.add(digest)
                local = WORKSPACE / source
                if not local.is_file():
                    stale_inputs.append(f"{source} (missing in this checkout)")
                elif "sha256:" + hashlib.sha256(local.read_bytes()).hexdigest() != digest:
                    stale_inputs.append(source)
            page_sources = manifest.get("page_sources")
            if not isinstance(page_sources, list) or not page_sources:
                errors.append("download-manifest.json: no 'page_sources' with SHA-256 digests of the files the pages were rendered from")
                page_sources = []
            for entry in page_sources:
                source = entry.get("path") if isinstance(entry, dict) else None
                digest = entry.get("sha256") if isinstance(entry, dict) else None
                if not isinstance(source, str) or not source or source.startswith("/") or ".." in source.split("/"):
                    errors.append(f"download-manifest.json: bad page source path {source!r}")
                    continue
                if not isinstance(digest, str) or not DIGEST_RE.match(digest):
                    errors.append(f"download-manifest.json: page source {source} has no sha256 digest")
                    continue
                local = WORKSPACE / source
                if not local.is_file():
                    stale_inputs.append(f"{source} (missing in this checkout)")
                elif "sha256:" + hashlib.sha256(local.read_bytes()).hexdigest() != digest:
                    stale_inputs.append(source)
            # Every bundled source file must be one of the recorded inputs.
            for entry in manifest.get("files", []):
                path = SITE / "download" / entry.get("path", "")
                if not path.is_file():
                    continue
                if path.suffix == ".zip":
                    try:
                        with zipfile.ZipFile(path) as zf:
                            for member in zf.namelist():
                                if member == "NOTICE.txt" or member.endswith("/"):
                                    continue
                                member_digest = "sha256:" + hashlib.sha256(zf.read(member)).hexdigest()
                                if member_digest not in input_digests:
                                    errors.append(f"{entry['path']}: member {member} is not a recorded input")
                    except zipfile.BadZipFile:
                        pass  # reported below
                elif entry.get("path") != "download-manifest.json" and entry.get("sha256") not in input_digests:
                    errors.append(f"download {entry['path']} is not a recorded input")
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError) as exc:
            errors.append(f"download-manifest.json: invalid or malformed ({exc})")
    if stale_inputs:
        message = (f"the site is stale against this checkout: {len(stale_inputs)} source file(s) changed, "
                   f"e.g. {', '.join(stale_inputs[:3])}")
        (errors if fresh else warnings).append(message)

    # Capability ids: every cap.* id served anywhere must exist in the
    # catalogue.  The specification pages may cite exactly the ids in
    # SPEC_EXAMPLE_IDS as hypothetical or forbidden examples ("do not invent
    # cap.motion.move.v1"); no other unknown id is accepted on any page.
    cap_path = capabilities or DEFAULT_CAPABILITIES
    if not cap_path.is_file():
        cap_path = SITE / "spec" / "capabilities.json"
    catalogue: set[str] = set()
    if cap_path.is_file():
        try:
            catalogue = load_catalogue_ids(cap_path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"capability catalogue {cap_path} unreadable ({exc})")
    else:
        errors.append("no capability catalogue to check capability ids against")
    unknown_caps: dict[str, str] = {}
    cap_mentions = 0
    if catalogue:
        for path in all_files:
            rel = path.relative_to(SITE).as_posix()
            if path.suffix not in CAP_SCAN_SUFFIXES:
                continue
            in_spec_prose = rel.startswith("spec/") and rel.endswith(".html")
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for cap_id in CAP_ID_RE.findall(text):
                cap_mentions += 1
                if cap_id in catalogue or cap_id.startswith(CAP_RESERVED_PREFIXES):
                    continue
                if in_spec_prose and cap_id in SPEC_EXAMPLE_IDS:
                    continue
                unknown_caps.setdefault(cap_id, rel)
    for cap_id, rel in sorted(unknown_caps.items()):
        errors.append(f"{rel}: capability id {cap_id} is not in {cap_path.name}")

    for path in sorted(SITE.rglob("*.zip")):
        try:
            with zipfile.ZipFile(path) as zf:
                bad = zf.testzip()
                if bad:
                    errors.append(f"{path.relative_to(SITE)}: corrupt member {bad}")
        except zipfile.BadZipFile:
            errors.append(f"{path.relative_to(SITE)}: not a valid zip archive")

    # Required files.
    required = [
        "index.html", "404.html", "favicon.svg", "assets/style.css", "assets/app.js",
        "assets/search.js", "assets/playground.js", "assets/registry.js",
        "assets/capabilities.js", "assets/market.js", "robots.txt", "_headers",
        "download/download-manifest.json", "market/index.html", "market/index.json",
    ]
    if base:
        required.append("sitemap.xml")
    for name in required:
        if not (SITE / name).is_file():
            errors.append(f"missing required output: {name}")

    # Sitemap: every URL resolves, no noindex page, and indexable pages are listed.
    sitemap_path = SITE / "sitemap.xml"
    sitemap_paths: set[str] = set()
    if sitemap_path.is_file() and not base:
        errors.append("sitemap.xml present but the site has no site URL (sitemaps need absolute URLs)")
    elif sitemap_path.is_file():
        xml = sitemap_path.read_text(encoding="utf-8")
        robots = SITE / "robots.txt"
        if robots.is_file() and f"Sitemap: {base}/sitemap.xml" not in robots.read_text(encoding="utf-8"):
            warnings.append("robots.txt does not point at the sitemap")
        for loc in re.findall(r"<loc>(.*?)</loc>", xml):
            if not loc.startswith(base + "/"):
                errors.append(f"sitemap: foreign URL {loc!r}")
                continue
            path = loc[len(base):].lstrip("/")
            if not path:
                path = "index.html"
            if path.endswith("/"):
                path += "index.html"
            target = SITE / path
            if not target.is_file():
                errors.append(f"sitemap: URL does not resolve to a file: {loc}")
            sitemap_paths.add(path)
        for rel in ("search/index.html", "404.html"):
            if rel in sitemap_paths:
                errors.append(f"sitemap: noindex page listed: {rel}")
        for page in pages:
            rel = page.relative_to(SITE).as_posix()
            if rel in ("404.html", "search/index.html"):
                continue
            if rel.startswith("registry/repo/"):
                continue
            if rel not in sitemap_paths:
                warnings.append(f"sitemap: indexable page missing: {rel}")

    # Size budget: every page except the registry explorer stays under 100 KB.
    for size, rel in largest:
        is_explorer = rel == "registry/index.html" or rel.startswith("registry/repo/")
        if size > SIZE_BUDGET and not is_explorer:
            errors.append(f"{rel}: {size / 1024:.1f} KiB exceeds the 100 KiB page budget")

    largest.sort(reverse=True)
    print(f"pages: {len(pages):,}   total size: {total_bytes / (1024*1024):.1f} MiB   "
          f"HTML: {html_bytes / (1024*1024):.1f} MiB   json files: {len(data_files):,}")
    print("size by area:")
    print(f"  {'area':<14} {'files':>6} {'bytes':>10} {'pages':>6} {'HTML':>10}")
    for area in sorted(area_stats, key=lambda a: -area_stats[a]["bytes"]):
        stat = area_stats[area]
        print(f"  {area:<14} {stat['files']:>6} {stat['bytes']/1024:>9.1f}K {stat['pages']:>6} {stat['html']/1024:>9.1f}K")
    print("largest pages:")
    for size, rel in largest[:8]:
        print(f"  {size/1024:8.1f} KiB  {rel}")
    if external_hosts:
        print("external anchors (allowed; not loaded): " + ", ".join(f"{h} ({n})" for h, n in external_hosts.most_common(5)))
    print(f"site URL: {base + '/' if base else '(none: no canonical links, no sitemap)'}")
    print(f"JSON-LD types: {', '.join(f'{k} ({v})' for k, v in jsonld_type_counts.most_common()) or 'none'}")
    print(f"capability ids checked: {cap_mentions} mentions, {len(unknown_caps)} unknown "
          f"(catalogue {cap_path.relative_to(WORKSPACE) if cap_path.is_relative_to(WORKSPACE) else cap_path})")
    print(f"external resource loads: {external_resource_count}   warnings: {len(warnings)}")
    for warning in warnings[:8]:
        print(f"  ! {warning}")
    if warnings and verbose:
        for warning in warnings[8:]:
            print(f"  ! {warning}")
    if errors:
        print(f"ERRORS: {len(errors)}", file=sys.stderr)
        for error in errors[:50]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  … and {len(errors) - 50} more", file=sys.stderr)
        return 1
    print("OK: links, fragments, local assets, ids, JSON/JSON-LD, "
          "capability ids, sitemap, downloads and input digests, and size budget verified")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check.py", description="Verify a generated OpenMHS site.")
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE,
                        help="site output directory (default: %(default)s)")
    parser.add_argument("--site-url", default=None,
                        help="expected site URL (default: $OPENMHS_SITE_URL, else the home page's canonical link)")
    parser.add_argument("--capabilities", type=Path, default=None,
                        help=f"capability catalogue (default: {DEFAULT_CAPABILITIES})")
    parser.add_argument("--fresh", action="store_true",
                        help="fail when the recorded input digests do not match this checkout")
    parser.add_argument("--verbose", action="store_true", help="print every warning")
    args = parser.parse_args(argv)
    return check(args.site.expanduser(), site_url=args.site_url, capabilities=args.capabilities,
                 fresh=args.fresh, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
