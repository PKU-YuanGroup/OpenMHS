#!/usr/bin/env python3
"""Build the registry aggregates from the committed records (stdlib only, no corpus needed).

    index.json    metadata, stats, one trimmed record per package and the site projection
    index.jsonl   the same trimmed records, one JSON object per line
    records.csv   one row per package for spreadsheets

The per-repo files ``repos/<track>/<owner>__<repo>.json`` are the source of
truth; the aggregates are derived from them and are git-ignored
(``MHS/registry/.gitignore``), so a per-repo change never conflicts on a
multi-megabyte file (OSS-11).  CI (or anyone) rebuilds them:

    python3 MHS/registry/build_index.py            # write the three files
    python3 MHS/registry/build_index.py --check    # exit 1 when they are missing or stale

``build_registry.py`` calls :func:`build` after regenerating the records.
Output is byte-stable: ``generated_at`` is the newest ``updated_at`` of the
records, never the wall clock.
"""

from __future__ import annotations

import csv
import glob
import io
import json
import os
import sys
from collections import Counter, OrderedDict
from typing import Any, Iterable, Mapping

HERE = os.path.dirname(os.path.abspath(__file__))
REPOS_DIR = os.path.join(HERE, "repos")
INDEX_JSON = os.path.join(HERE, "index.json")
INDEX_JSONL = os.path.join(HERE, "index.jsonl")
RECORDS_CSV = os.path.join(HERE, "records.csv")
INDEX_VERSION = "0.9.0"
INDEX_DESC_LEN = 200
#: the site explorer loads index.json whole; keep it below this size
INDEX_BUDGET_BYTES = 8 * 1024 * 1024
DISPATCHABLE = ("direct-driver", "family-config")


def load_records(repos_dir: str = REPOS_DIR) -> list[dict[str, Any]]:
    records = []
    for path in sorted(glob.glob(os.path.join(repos_dir, "*", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            records.append(json.load(fh))
    return sort_records(records)


def sort_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(r) for r in records), key=lambda r: (r["track"], r["owner"].lower(), r["repo"].lower(),
                                                              r["owner"], r["repo"]))


def card_path(record: Mapping[str, Any]) -> str:
    return f"tasks/{record['track']}/{record['owner']}__{record['repo']}.json"


def dispatchable_now(record: Mapping[str, Any]) -> bool:
    """A driver task now: dispatchable strategy, nothing blocks it, not quarantined, and its driver package has
    not passed the gate yet (adapter state ``runnable``)."""
    integration = record.get("integration") or {}
    return (integration.get("strategy") in DISPATCHABLE and not record.get("blocked_on")
            and not record.get("quarantine") and (record.get("adapter") or {}).get("state") != "runnable")


def index_record(record: Mapping[str, Any]) -> "OrderedDict[str, Any]":
    integration = record.get("integration") or {}
    adapter = record.get("adapter") or {}
    out: "OrderedDict[str, Any]" = OrderedDict()
    for key in ("id", "registry_id", "package_id", "repo_url", "track", "owner", "repo", "title"):
        out[key] = record.get(key)
    out["description"] = (record.get("description") or "")[:INDEX_DESC_LEN]
    out["families"] = record.get("families") or []
    out["tier"] = record.get("tier")
    out["ring"] = record.get("ring")
    out["modes"] = record.get("modes") or []
    out["license"] = (record.get("license") or "")[:80]
    out["license_spdx"] = record.get("license_spdx")
    out["license_class"] = record.get("license_class")
    out["stars"] = record.get("stars", 0)
    out["languages"] = (record.get("languages") or [])[:3]
    out["interfaces"] = (record.get("interfaces") or [])[:4]
    out["evidence"] = {"state": (record.get("evidence") or {}).get("state"),
                       "read_by": (record.get("evidence") or {}).get("read_by")}
    out["adapter"] = {"state": adapter.get("state"), "bridge": adapter.get("bridge"),
                      "manifest": adapter.get("manifest_ref")}
    out["capabilities_offered"] = record.get("capabilities_offered") or []
    out["strategy"] = integration.get("strategy")
    out["role"] = integration.get("role")
    out["reason_code"] = integration.get("reason_code")
    out["effort"] = integration.get("effort")
    out["next_action"] = (integration.get("next_action") or "")[:150]
    out["blocked_on"] = record.get("blocked_on") or []
    out["wave"] = record.get("wave")
    out["rank"] = record.get("rank")
    out["quarantine"] = bool(record.get("quarantine"))
    out["variant_of"] = record.get("variant_of")
    out["commit"] = (record.get("source") or {}).get("commit")
    out["task_card"] = card_path(record)
    out["has_manifest"] = bool(adapter.get("manifest_ref"))
    out["local_path"] = record.get("local_path")
    return out


def site_record(record: Mapping[str, Any]) -> "OrderedDict[str, Any]":
    integration = record.get("integration") or {}
    return OrderedDict((
        ("id", record["package_id"]),
        ("owner", record["owner"]),
        ("repo", record["repo"]),
        ("track", record["track"]),
        ("family", (record.get("families") or ["other"])[0]),
        ("tier", record.get("tier")),
        ("ring", record.get("ring")),
        ("modes", record.get("modes") or []),
        ("license", (record.get("license") or "")[:60]),
        ("stars", record.get("stars", 0)),
        ("evidence", (record.get("evidence") or {}).get("state")),
        ("adapter", (record.get("adapter") or {}).get("state")),
        ("strategy", integration.get("strategy")),
        ("wave", record.get("wave")),
        ("capabilities", len(record.get("capabilities_offered") or [])),
        ("interfaces", (record.get("interfaces") or [])[:4]),
        ("summary", (record.get("description") or "")[:140]),
        ("repo_url", record.get("repo_url")),
    ))


def _counter(values: Iterable[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(v) for v in values).items()))


def compute_stats(records: Iterable[Mapping[str, Any]]) -> "OrderedDict[str, Any]":
    rs = list(records)
    integ = [r.get("integration") or {} for r in rs]
    stats: "OrderedDict[str, Any]" = OrderedDict()
    stats["total"] = len(rs)
    stats["by_track"] = _counter(r["track"] for r in rs)
    stats["by_family"] = _counter((r.get("families") or ["other"])[0] for r in rs)
    stats["by_tier"] = _counter(r.get("tier") for r in rs)
    stats["by_ring"] = _counter(r.get("ring") for r in rs)
    stats["by_mode"] = _counter(m for r in rs for m in (r.get("modes") or []))
    stats["dual_mode"] = sum(1 for r in rs if {"hardware", "simulated"} <= set(r.get("modes") or []))
    stats["by_license_class"] = _counter(r.get("license_class") for r in rs)
    stats["by_license"] = _counter(r.get("license_spdx") or r.get("license") for r in rs)
    stats["by_evidence"] = _counter((r.get("evidence") or {}).get("state") for r in rs)
    stats["by_effort"] = _counter(i.get("effort") for i in integ)
    stats["by_strategy"] = _counter(i.get("strategy") for i in integ)
    stats["by_role"] = _counter(i.get("role") for i in integ)
    stats["by_wave"] = _counter(r.get("wave") for r in rs)
    stats["dispatchable_now"] = sum(1 for r in rs if dispatchable_now(r))
    stats["blocked_on_helper"] = sum(1 for r in rs if any(str(b).startswith("helper:") for b in r.get("blocked_on") or []))
    stats["quarantine"] = sum(1 for r in rs if r.get("quarantine"))
    stats["variants"] = sum(1 for r in rs if r.get("variant_of"))
    stats["pinned_commits"] = sum(1 for r in rs if (r.get("source") or {}).get("commit"))
    stats["capability_claims"] = sum(len(r.get("capabilities_offered") or []) for r in rs)
    stats["manifests"] = sum(1 for r in rs if (r.get("adapter") or {}).get("manifest_ref"))
    return stats


def render(records: Iterable[Mapping[str, Any]], generated_at: str | None = None) -> dict[str, str]:
    """``{path: text}`` of the three aggregates."""
    rs = sort_records(records)
    generated = generated_at or max((r.get("updated_at") or "" for r in rs), default="")
    index_records = [index_record(r) for r in rs]
    index = OrderedDict((
        ("registry_version", INDEX_VERSION),
        ("generated_at", generated),
        ("generated_by", "MHS/registry/build_index.py"),
        ("source", "MHS/registry/repos/** (per-repo records); task cards in MHS/registry/tasks/**"),
        ("stats", compute_stats(rs)),
        ("records", index_records),
        ("site", [site_record(r) for r in rs]),
    ))
    texts = {INDEX_JSON: json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
             INDEX_JSONL: "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in index_records)}
    cols = ["id", "registry_id", "package_id", "track", "owner", "repo", "family", "tier", "ring", "modes",
            "strategy", "role", "reason_code", "wave", "rank", "blocked_on", "quarantine", "variant_of",
            "license_spdx", "license_class", "commit", "languages", "simulation", "hardware_free", "interfaces",
            "build_systems", "evidence_state", "adapter_state", "effort", "capability_count", "next_action",
            "repo_url", "local_path", "task_card"]
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(cols)
    for r in rs:
        integration = r.get("integration") or {}
        writer.writerow([
            r["id"], r["registry_id"], r["package_id"], r["track"], r["owner"], r["repo"],
            (r.get("families") or ["other"])[0], r.get("tier"), r.get("ring"), "|".join(r.get("modes") or []),
            integration.get("strategy", ""), integration.get("role", ""), integration.get("reason_code", ""),
            r.get("wave", ""), r.get("rank", ""), "|".join(r.get("blocked_on") or []),
            str(bool(r.get("quarantine"))).lower(), r.get("variant_of") or "", r.get("license_spdx", ""),
            r.get("license_class", ""), (r.get("source") or {}).get("commit", ""),
            "|".join(r.get("languages") or []), str(bool(r.get("simulation"))).lower(),
            str(bool(r.get("hardware_free"))).lower(), "|".join(r.get("interfaces") or []),
            "|".join(r.get("build_systems") or []), (r.get("evidence") or {}).get("state", ""),
            (r.get("adapter") or {}).get("state", ""), integration.get("effort", ""),
            len(r.get("capabilities_offered") or []), (integration.get("next_action") or "").replace("\n", " ")[:300],
            r.get("repo_url", ""), r.get("local_path", ""), card_path(r),
        ])
    texts[RECORDS_CSV] = buf.getvalue()
    return texts


def build(records: Iterable[Mapping[str, Any]] | None = None, generated_at: str | None = None,
          check: bool = False) -> list[str]:
    """Write (or with ``check`` compare) the aggregates; return the paths that differ."""
    texts = render(load_records() if records is None else records, generated_at)
    stale = []
    for path, text in texts.items():
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                same = fh.read() == text
        except OSError:
            same = False
        if same:
            continue
        stale.append(os.path.basename(path))
        if not check:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
    return stale


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build index.json, index.jsonl and records.csv from repos/**")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when an aggregate is stale")
    args = parser.parse_args(argv)
    records = load_records()
    if not records:
        print("[index] no records under MHS/registry/repos/", file=sys.stderr)
        return 2
    stale = build(records, check=args.check)
    if args.check:
        print(f"[index] {len(records)} records; stale aggregates: {', '.join(stale) or 'none'}")
        return 1 if stale else 0
    size = os.path.getsize(INDEX_JSON)
    print(f"[index] {len(records)} records; index.json {size / 1e6:.2f} MB; rewrote {', '.join(stale) or 'nothing'}")
    if size > INDEX_BUDGET_BYTES:
        print(f"[index] WARNING index.json exceeds the {INDEX_BUDGET_BYTES // (1024 * 1024)} MB budget", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
