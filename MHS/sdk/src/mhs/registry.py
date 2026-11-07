"""Load and query an OpenMHS registry (static index of packages and their integration plan).

The registry is a mirrorable JSON index (``MHS/registry/index.json``,
``index.jsonl``, ``records.csv``) or the directory of per-record JSON files it
is built from (``MHS/registry/repos/<track>/<owner>__<repo>.json``).  The
aggregates are git-ignored build outputs, so a checkout without them loads the
per-record files.  This module is a thin reader for hosts and for the CLI; it
never writes and never talks to the network.

Public API::

    from mhs.registry import Registry, PackageRecord

    registry = Registry.load("MHS/registry")
    registry.packages                 # list[PackageRecord]
    record = registry.get("gh.owner/repo")
    matches = registry.search(query="conveyor", capability="cap.motion.*")
    queue = registry.search(dispatchable=True, wave=2)
    record.repo_url, record.family, record.strategy, record.blocked_on, record.summary()

``PackageRecord`` is a ``dict`` subclass, so it is JSON-serialisable and works
anywhere a plain record dict was previously returned.
"""

from __future__ import annotations

import csv
import fnmatch
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = ["PackageRecord", "Registry", "load_registry"]


class PackageRecord(dict):
    """One registry record with attribute-style accessors.

    The record keeps every original field (including vendor ``x-`` keys) and
    adds read-only helpers for the fields hosts and the CLI use most.  Missing
    values are ``None`` (or an empty list for list-valued fields), never a
    ``KeyError``.
    """

    # -- identity -----------------------------------------------------
    @property
    def package_id(self) -> str | None:
        value = self.get("package_id") or self.get("record_id")
        return str(value) if value is not None else None

    @property
    def title(self) -> str | None:
        return _opt_str(self.get("title"))

    @property
    def repo_url(self) -> str | None:
        return _opt_str(self.get("repo_url"))

    @property
    def owner(self) -> str | None:
        return _opt_str(self.get("owner"))

    @property
    def repo(self) -> str | None:
        return _opt_str(self.get("repo"))

    @property
    def description(self) -> str | None:
        return _opt_str(self.get("description"))

    @property
    def track(self) -> str | None:
        return _opt_str(self.get("track"))

    @property
    def tier(self) -> str | None:
        return _opt_str(self.get("tier"))

    @property
    def ring(self) -> int | None:
        value = self.get("ring")
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def license(self) -> str | None:  # noqa: A003 - registry field name
        return _opt_str(self.get("license"))

    @property
    def local_path(self) -> str | None:
        return _opt_str(self.get("local_path"))

    @property
    def stars(self) -> int:
        value = self.get("stars")
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0

    # -- families / adapter ------------------------------------------
    @property
    def families(self) -> list[str]:
        raw = self.get("families")
        if isinstance(raw, list) and raw:
            return [str(item) for item in raw]
        family = self.get("family")
        return [str(family)] if family else []

    @property
    def family(self) -> str | None:
        families = self.families
        return families[0] if families else None

    @property
    def adapter(self) -> dict[str, Any]:
        value = self.get("adapter")
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def adapter_state(self) -> str | None:
        return _opt_str(self.adapter.get("state"))

    @property
    def adapter_bridge(self) -> str | None:
        return _opt_str(self.adapter.get("bridge"))

    @property
    def manifest_ref(self) -> str | None:
        """Path of the generated adapter manifest, if the registry has one."""
        return _opt_str(self.adapter.get("manifest") or self.adapter.get("manifest_ref"))

    @property
    def has_manifest(self) -> bool:
        if isinstance(self.get("has_manifest"), bool):
            return bool(self["has_manifest"])
        return bool(self.manifest_ref)

    # -- capability / evidence ---------------------------------------
    @property
    def capabilities(self) -> list[str]:
        raw = self.get("capabilities_offered")
        return [str(item) for item in raw] if isinstance(raw, list) else []

    @property
    def modes(self) -> list[str]:
        raw = self.get("modes")
        return [str(item) for item in raw] if isinstance(raw, list) else []

    @property
    def interfaces(self) -> list[str]:
        raw = self.get("interfaces")
        return [str(item) for item in raw] if isinstance(raw, list) else []

    @property
    def languages(self) -> list[str]:
        raw = self.get("languages")
        return [str(item) for item in raw] if isinstance(raw, list) else []

    @property
    def tags(self) -> list[str]:
        raw = self.get("tags")
        return [str(item) for item in raw] if isinstance(raw, list) else []

    @property
    def evidence(self) -> dict[str, Any]:
        value = self.get("evidence")
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def evidence_state(self) -> str | None:
        return _opt_str(self.evidence.get("state"))

    @property
    def trust(self) -> str | None:
        return _opt_str(self.get("trust"))

    @property
    def conformance(self) -> dict[str, Any]:
        value = self.get("conformance")
        return dict(value) if isinstance(value, Mapping) else {}

    @property
    def simulation(self) -> bool:
        return bool(self.get("simulation")) if self.get("simulation") is not None else "simulated" in self.modes

    @property
    def hardware_free(self) -> bool:
        return bool(self.get("hardware_free"))

    # -- integration plan (triage decision, wave, rank, licence) ------
    def _integration(self, key: str) -> Any:
        integration = self.get("integration")
        value = integration.get(key) if isinstance(integration, Mapping) else None
        return value if value is not None else self.get(key)

    @property
    def strategy(self) -> str | None:
        """direct-driver, family-config, bridge-runtime, reference, skip or untriaged."""
        return _opt_str(self._integration("strategy"))

    @property
    def role(self) -> str | None:
        return _opt_str(self._integration("role"))

    @property
    def reason_code(self) -> str | None:
        return _opt_str(self._integration("reason_code"))

    @property
    def blocked_on(self) -> list[str]:
        raw = self.get("blocked_on")
        return [str(item) for item in raw] if isinstance(raw, list) else []

    @property
    def wave(self) -> int | None:
        value = self.get("wave")
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def rank(self) -> int | None:
        value = self.get("rank")
        return int(value) if isinstance(value, int) and not isinstance(value, bool) else None

    @property
    def quarantine(self) -> bool:
        return bool(self.get("quarantine"))

    @property
    def variant_of(self) -> str | None:
        return _opt_str(self.get("variant_of"))

    @property
    def source_commit(self) -> str | None:
        """The pinned upstream commit (``source.commit``, or ``commit`` in an index projection)."""
        source = self.get("source")
        value = source.get("commit") if isinstance(source, Mapping) else None
        return _opt_str(value if value is not None else self.get("commit"))

    @property
    def license_spdx(self) -> str | None:
        return _opt_str(self.get("license_spdx"))

    @property
    def license_class(self) -> str | None:
        return _opt_str(self.get("license_class"))

    @property
    def task_card(self) -> str | None:
        """Path of the task card relative to the registry directory (``tasks/<track>/<owner>__<repo>.json``)."""
        if self.get("task_card"):
            return str(self["task_card"])
        if self.track and self.owner and self.repo:
            return f"tasks/{self.track}/{self.owner}__{self.repo}.json"
        return None

    @property
    def dispatchable(self) -> bool:
        """True when the package is a driver task now: direct-driver or family-config, nothing blocks it, not
        quarantined, and its driver package has not passed the gate yet (adapter state ``runnable``)."""
        return (self.strategy in ("direct-driver", "family-config") and not self.blocked_on
                and not self.quarantine and self.adapter_state != "runnable")

    # -- query helpers ----------------------------------------------
    def offers_capability(self, pattern: str) -> bool:
        """True when one of ``capabilities_offered`` matches ``pattern``.

        ``pattern`` may be an exact id, a class prefix (``cap.motion``) or a
        glob (``cap.motion.*``).  The match is symmetric enough for CLI use:
        ``cap.motion.*`` finds ``cap.motion.joint.v1`` and an exact id finds
        itself.
        """
        if not pattern:
            return True
        needle = str(pattern)
        for capability in self.capabilities:
            if capability == needle:
                return True
            if fnmatch.fnmatchcase(capability, needle):
                return True
            if needle.endswith(".*") and capability.startswith(needle[:-1]):
                return True
            if capability.startswith(needle + "."):
                return True
        return False

    def matches(
        self,
        *,
        query: str | None = None,
        capability: str | None = None,
        family: str | None = None,
        mode: str | None = None,
        track: str | None = None,
        tier: str | Sequence[str] | None = None,
        ring: int | None = None,
        license: str | None = None,  # noqa: A002 - filter name
        evidence: str | None = None,
        adapter_state: str | None = None,
        strategy: str | Sequence[str] | None = None,
        wave: int | None = None,
        dispatchable: bool | None = None,
    ) -> bool:
        """Return True when the record satisfies every supplied filter."""
        if strategy is not None:
            strategies = {strategy} if isinstance(strategy, str) else set(strategy)
            if self.strategy not in strategies:
                return False
        if wave is not None and self.wave != wave:
            return False
        if dispatchable is not None and self.dispatchable != bool(dispatchable):
            return False
        if capability and not self.offers_capability(capability):
            return False
        if family and family not in self.families:
            return False
        if mode and mode not in self.modes:
            return False
        if track and self.track != track:
            return False
        if tier is not None:
            tiers = {tier} if isinstance(tier, str) else set(tier)
            if self.tier not in tiers:
                return False
        if ring is not None and self.ring != ring:
            return False
        if license and self.license != license:
            return False
        if evidence and self.evidence_state != evidence:
            return False
        if adapter_state and self.adapter_state != adapter_state:
            return False
        if query:
            needle = str(query).strip().lower()
            if needle:
                haystack = " ".join(
                    str(self.get(key) or "")
                    for key in (
                        "package_id",
                        "repo_url",
                        "title",
                        "description",
                        "owner",
                        "repo",
                        "local_path",
                    )
                )
                haystack += " " + " ".join(self.tags)
                haystack += " " + " ".join(self.capabilities)
                haystack += " " + " ".join(self.interfaces)
                haystack += " " + " ".join(self.families)
                if needle not in haystack.lower():
                    return False
        return True

    def summary(self) -> dict[str, Any]:
        """Compact, JSON-ready view for search results and UIs."""
        return {
            "package_id": self.package_id,
            "title": self.title,
            "repo_url": self.repo_url,
            "track": self.track,
            "owner": self.owner,
            "families": self.families,
            "tier": self.tier,
            "ring": self.ring,
            "modes": self.modes,
            "adapter": {
                "state": self.adapter_state,
                "bridge": self.adapter_bridge,
                "manifest": self.manifest_ref,
            },
            "evidence": {"state": self.evidence_state},
            "capabilities_offered": self.capabilities,
            "strategy": self.strategy,
            "role": self.role,
            "reason_code": self.reason_code,
            "blocked_on": self.blocked_on,
            "wave": self.wave,
            "rank": self.rank,
            "quarantine": self.quarantine,
            "variant_of": self.variant_of,
            "source_commit": self.source_commit,
            "license_spdx": self.license_spdx,
            "license_class": self.license_class,
            "task_card": self.task_card,
            "trust": self.trust,
            "local_path": self.local_path,
        }

    def to_dict(self) -> dict[str, Any]:
        """Return a plain deep-copied dict."""
        return json.loads(json.dumps(dict(self), ensure_ascii=False, default=str))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"PackageRecord({self.package_id!r}, family={self.family!r}, tier={self.tier!r})"


def _opt_str(value: Any) -> str | None:
    return str(value) if value is not None else None


class Registry:
    """One registry index (``index.json``) or a directory of record files."""

    def __init__(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        path: str | None = None,
        stats: Mapping[str, Any] | None = None,
        generated_at: str | None = None,
    ) -> None:
        self._packages: list[PackageRecord] = [
            record if isinstance(record, PackageRecord) else PackageRecord(dict(record))
            for record in records
            if isinstance(record, Mapping)
        ]
        self.path = path
        self.generated_at = generated_at
        self.stats = dict(stats) if stats else self._compute_stats()
        self._by_id: dict[str, PackageRecord] = {}
        for record in self._packages:
            if record.package_id:
                self._by_id[record.package_id] = record

    # -- loading -----------------------------------------------------
    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> "Registry":
        """Load ``index.json``, ``index.jsonl``, ``records.csv`` or a directory.

        ``path=None`` discovers the repository registry from ``$MHS_REGISTRY``,
        the current working directory, or the SDK checkout.
        """
        target = _resolve_target(path)
        if target is None:
            raise FileNotFoundError(
                "no MHS registry found; pass a path or set $MHS_REGISTRY"
            )
        if target.is_dir():
            return cls._load_dir(target)
        return cls._load_file(target)

    @classmethod
    def _load_dir(cls, target: Path) -> "Registry":
        for name in ("index.json", "index.jsonl", "records.json"):
            candidate = target / name
            if candidate.is_file():
                return cls._load_file(candidate)
        # the aggregates are git-ignored build outputs: read the per-record files
        # (repos/** of an OpenMHS registry; task cards and overrides are not records)
        base = target / "repos" if (target / "repos").is_dir() else target
        records: list[dict[str, Any]] = []
        for candidate in sorted(base.rglob("*.json")):
            if candidate.name in ("index.json", "source_manifest.json"):
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, Mapping) or "card_version" in data:
                continue
            if data.get("record_type") == "package" or "package_id" in data:
                records.append(dict(data))
            elif isinstance(data.get("records"), list):
                records.extend(
                    dict(item) for item in data["records"] if isinstance(item, Mapping)
                )
        csv_path = target / "records.csv"
        if not records and csv_path.is_file():
            records = _load_csv(csv_path)
        if not records:
            raise ValueError(f"{target} contains no MHS registry records")
        generated = max((str(r.get("updated_at") or "") for r in records), default="") or None
        return cls(records, path=str(target), generated_at=generated)

    @classmethod
    def _load_file(cls, target: Path) -> "Registry":
        suffix = target.suffix.lower()
        if suffix == ".csv":
            return cls(_load_csv(target), path=str(target))
        text = target.read_text(encoding="utf-8")
        if suffix == ".jsonl":
            records = []
            for line in text.splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))
            return cls(records, path=str(target))
        data = json.loads(text)
        if isinstance(data, Mapping) and isinstance(data.get("records"), list):
            return cls(
                data.get("records") or [],
                path=str(target),
                stats=data.get("stats") or {},
                generated_at=data.get("generated_at"),
            )
        if isinstance(data, list):
            return cls(data, path=str(target))
        if isinstance(data, Mapping) and (
            data.get("record_type") == "package" or "package_id" in data
        ):
            return cls([data], path=str(target))
        raise ValueError(f"{target} is not an MHS registry index")

    # -- access ------------------------------------------------------
    @property
    def packages(self) -> list[PackageRecord]:
        """All package records (``PackageRecord`` is a ``dict`` subclass)."""
        return list(self._packages)

    @property
    def records(self) -> list[PackageRecord]:
        """Backwards-compatible alias of :attr:`packages`."""
        return self.packages

    def __len__(self) -> int:
        return len(self._packages)

    def __iter__(self) -> Iterable[PackageRecord]:
        return iter(self._packages)

    def __getitem__(self, index: int) -> PackageRecord:
        return self._packages[index]

    def get(self, package_id: str) -> PackageRecord | None:
        return self._by_id.get(str(package_id))

    def families(self) -> list[str]:
        return sorted({family for record in self._packages for family in record.families})

    # -- search ------------------------------------------------------
    def search(
        self,
        *,
        query: str | None = None,
        track: str | None = None,
        family: str | None = None,
        tier: str | Sequence[str] | None = None,
        mode: str | None = None,
        evidence: str | None = None,
        ring: int | None = None,
        license: str | None = None,  # noqa: A002 - filter name
        capability: str | None = None,
        adapter_state: str | None = None,
        limit: int | None = None,
        strategy: str | Sequence[str] | None = None,
        wave: int | None = None,
        dispatchable: bool | None = None,
    ) -> list[PackageRecord]:
        """Filter records; all filters are ANDed, ``query`` is substring match.

        ``dispatchable=True`` with ``wave`` selects the driver tasks of one wave;
        results keep registry order (sort by :attr:`PackageRecord.rank` for the
        dispatch order).
        """
        results = [
            record
            for record in self._packages
            if record.matches(
                query=query,
                track=track,
                family=family,
                tier=tier,
                mode=mode,
                evidence=evidence,
                ring=ring,
                license=license,
                capability=capability,
                adapter_state=adapter_state,
                strategy=strategy,
                wave=wave,
                dispatchable=dispatchable,
            )
        ]
        if limit is not None:
            results = results[: max(0, int(limit))]
        return results

    # -- claims / stats ---------------------------------------------
    def conformance_claims(self) -> list[dict[str, Any]]:
        claims = []
        for record in self._packages:
            claim = record.conformance
            if claim.get("level"):
                claims.append(
                    {
                        "package_id": record.package_id,
                        "profile": claim.get("profile"),
                        "level": claim.get("level"),
                        "issuer_kind": claim.get("issuer_kind"),
                        "report_digest": claim.get("report_digest"),
                    }
                )
        return claims

    def _compute_stats(self) -> dict[str, Any]:
        by_track: dict[str, int] = {}
        by_tier: dict[str, int] = {}
        by_family: dict[str, int] = {}
        by_evidence: dict[str, int] = {}
        by_strategy: dict[str, int] = {}
        with_manifest = 0
        dispatchable = 0
        for record in self._packages:
            if record.strategy:
                by_strategy[record.strategy] = by_strategy.get(record.strategy, 0) + 1
            dispatchable += int(record.dispatchable)
            if record.track:
                by_track[record.track] = by_track.get(record.track, 0) + 1
            if record.tier:
                by_tier[record.tier] = by_tier.get(record.tier, 0) + 1
            for family in record.families:
                by_family[family] = by_family.get(family, 0) + 1
            if record.evidence_state:
                by_evidence[record.evidence_state] = by_evidence.get(record.evidence_state, 0) + 1
            with_manifest += int(record.has_manifest)
        return {
            "total": len(self._packages),
            "with_manifest": with_manifest,
            "by_track": by_track,
            "by_tier": by_tier,
            "by_family": by_family,
            "by_evidence": by_evidence,
            "by_strategy": by_strategy,
            "dispatchable": dispatchable,
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Registry({len(self._packages)} records, path={self.path!r})"


def _load_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            record = dict(row)
            for key in ("modes", "languages", "interfaces", "build_systems", "blocked_on"):
                if key in record and isinstance(record[key], str):
                    record[key] = [item for item in record[key].split("|") if item]
            for key in ("ring", "wave", "rank"):
                if key in record:
                    try:
                        record[key] = int(record[key])
                    except (TypeError, ValueError):
                        record.pop(key, None)
            for key in ("quarantine", "simulation", "hardware_free"):
                if key in record and isinstance(record[key], str):
                    record[key] = record[key].strip().lower() == "true"
            if record.get("variant_of") == "":
                record["variant_of"] = None
            if "capability_count" in record:
                record.pop("capability_count", None)
            rows.append(record)
    return rows


def _resolve_target(path: str | os.PathLike[str] | None) -> Path | None:
    if path is not None:
        target = Path(path).expanduser()
        if target.exists():
            return target
        # A relative path is often given from a different working directory.
        for base in (Path.cwd(), *_module_roots()):
            candidate = (base / target).expanduser()
            if candidate.exists():
                return candidate
        return target  # let the caller report the missing path
    env = os.environ.get("MHS_REGISTRY")
    if env:
        candidate = Path(env).expanduser()
        if candidate.exists():
            return candidate
    for base in (Path.cwd(), *_module_roots()):
        candidate = base / "MHS" / "registry"
        if candidate.is_dir():
            return candidate
        candidate = base / "registry"
        if candidate.is_dir() and (candidate / "index.json").exists():
            return candidate
    return None


def _module_roots() -> list[Path]:
    here = Path(__file__).resolve()
    return [parent for parent in here.parents]


def load_registry(path: str | os.PathLike[str] | None = None) -> Registry:
    """Convenience wrapper around :meth:`Registry.load`."""
    return Registry.load(path)
