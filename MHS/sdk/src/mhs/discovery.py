"""Find MHS endpoints: ``MHS_ENDPOINTS``, ``~/.mhs/endpoints.json`` and ``/.well-known/mhs.json``.

::

    from mhs.discovery import discover

    for endpoint in discover():                 # env + file, HTTP endpoints probed
        print(endpoint.status, endpoint.target, endpoint.devices)

Sources, in this order (an endpoint listed twice is reported once, with both
sources):

1. ``MHS_ENDPOINTS``: comma-separated entries, each an ``http(s)://`` URL, an
   ``mhs://host[:port]`` endpoint id (HTTP, port 7400 by default) or
   ``stdio:<launch command>`` (split like a shell line, so its words are
   separated by spaces: the variable is split at commas first, and the comma
   form ``stdio:python3,-m,...`` is accepted only by :func:`parse_target`,
   that is ``-e`` and ``targets=``);
2. the endpoints file, ``~/.mhs/endpoints.json`` (or ``path=`` /
   ``MHS_ENDPOINTS_FILE``), validated against ``endpoints.schema.json``.  An
   invalid file raises :class:`EndpointsFileError`; a missing file is no error.

Every HTTP endpoint is then probed with ``GET /.well-known/mhs.json`` (no
token is sent; the descriptor route is public).  A stdio endpoint is never
launched by discovery: it is ``not_probed`` until you connect to it.

**Discovered does not mean trusted.**  An entry in an environment variable or
a file, and a descriptor an endpoint serves about itself, are claims.  Nothing
here authenticates an endpoint, opens a session or grants anything:
:attr:`Endpoint.trusted` is always ``False``.  Hosts still authenticate
(bearer tokens, TLS), apply their own allow-lists, and only an operator arms
hardware.
"""

from __future__ import annotations

import json
import os
import shlex
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

__all__ = [
    "DEFAULT_ENDPOINTS_FILE",
    "ENV_ENDPOINTS",
    "ENV_ENDPOINTS_FILE",
    "Endpoint",
    "EndpointsFileError",
    "WELL_KNOWN_PATH",
    "discover",
    "endpoints_from_env",
    "find_device",
    "parse_target",
    "probe",
    "read_endpoints_file",
    "token_of",
]

ENV_ENDPOINTS = "MHS_ENDPOINTS"
ENV_ENDPOINTS_FILE = "MHS_ENDPOINTS_FILE"
DEFAULT_ENDPOINTS_FILE = "~/.mhs/endpoints.json"
WELL_KNOWN_PATH = "/.well-known/mhs.json"
_MAX_DESCRIPTOR_BYTES = 1024 * 1024


class EndpointsFileError(ValueError):
    """The endpoints file is not JSON or does not match ``endpoints.schema.json``."""

    def __init__(self, path: str, problems: Sequence[str]):
        self.path = path
        self.problems = list(problems)
        super().__init__(f"{path}: " + "; ".join(self.problems[:5]))


@dataclass
class Endpoint:
    """One discovered endpoint (a claim, never trusted)."""

    transport: str  #: ``http`` or ``stdio``
    url: str | None = None  #: base URL of an HTTP endpoint
    command: list[str] | None = None  #: launch command of a stdio endpoint
    name: str | None = None
    sources: list[str] = field(default_factory=list)  #: ``argument``, ``env``, ``file``
    cwd: str | None = None
    token_file: str | None = None
    endpoint_id: str | None = None
    devices: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    #: ``reachable``, ``unreachable``, ``invalid_descriptor``, ``not_probed``
    status: str = "not_probed"
    descriptor: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    #: Always ``False``: discovery authenticates nothing.
    trusted: bool = False

    @property
    def target(self) -> str | list[str]:
        """What :func:`mhs.connect` takes: the URL, or the launch command (argv)."""
        return self.url if self.transport == "http" else list(self.command or [])

    @property
    def key(self) -> str:
        return self.url if self.transport == "http" else " ".join(self.command or [])

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "transport": self.transport,
            "target": self.key,
            "status": self.status,
            "trusted": False,
            "sources": list(self.sources),
        }
        for key in ("url", "command", "name", "cwd", "token_file", "endpoint_id", "error"):
            value = getattr(self, key)
            if value is not None:
                out[key] = value
        out["devices"] = list(self.devices)
        if self.tags:
            out["tags"] = list(self.tags)
        if self.descriptor is not None:
            out["descriptor"] = self.descriptor
        if self.warnings:
            out["warnings"] = list(self.warnings)
        return out


def parse_target(text: str) -> tuple[str, str | None, list[str] | None]:
    """``(transport, url, command)`` of an endpoint target string; ``ValueError`` for anything else.

    ``http(s)://host:port`` and ``mhs://host[:port]`` (port 7400 by default)
    are HTTP; ``stdio:<command>`` is a launch command, split like a shell
    line, or at commas when it has no space (``stdio:python3,-m,mhs.reference,lab,--stdio``);
    ``mhs+stdio://<argv,...>`` is the comma-separated argv form ``mhs.client.connect`` accepts.
    """
    value = str(text).strip()
    if value.startswith(("http://", "https://")):
        return "http", value.rstrip("/"), None
    if value.startswith("mhs://"):
        authority = value[len("mhs://"):].split("/", 1)[0]
        if not authority:
            raise ValueError(f"{text!r} has no host")
        if ":" not in authority.rsplit("]", 1)[-1]:
            authority += ":7400"
        return "http", f"http://{authority}", None
    if value.startswith("mhs+stdio://"):
        command = [part for part in value[len("mhs+stdio://"):].split(",") if part]
        if not command:
            raise ValueError(f"{text!r} has no launch command")
        return "stdio", None, command
    if value.startswith("stdio:"):
        rest = value[len("stdio:"):].strip()
        command = shlex.split(rest) if " " in rest else [part for part in rest.split(",") if part]
        if not command:
            raise ValueError(f"{text!r} has no launch command")
        return "stdio", None, command
    raise ValueError(f"{text!r} is not an endpoint (http(s)://..., mhs://host[:port] or stdio:<command>)")


def endpoints_from_env(value: str | None = None) -> list[Endpoint]:
    """The entries of ``MHS_ENDPOINTS`` (or ``value``); an unparsable entry raises ``ValueError``."""
    raw = os.environ.get(ENV_ENDPOINTS, "") if value is None else value
    found: list[Endpoint] = []
    for token in str(raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        transport, url, command = parse_target(token)
        found.append(Endpoint(transport=transport, url=url, command=command, sources=["env"]))
    return found


def _file_path(path: str | os.PathLike[str] | None) -> Path:
    if path is not None:
        return Path(path).expanduser()
    return Path(os.environ.get(ENV_ENDPOINTS_FILE) or DEFAULT_ENDPOINTS_FILE).expanduser()


def read_endpoints_file(path: str | os.PathLike[str] | None = None) -> list[Endpoint]:
    """The endpoints of the endpoints file (``[]`` when it does not exist).

    The file is validated against ``endpoints.schema.json``; a file that is
    not JSON or does not validate raises :class:`EndpointsFileError` (a broken
    configuration is reported, never half-read).  A relative ``token_file`` or
    ``cwd`` is resolved against the file's directory.
    """
    target = _file_path(path)
    if not target.exists():
        return []
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EndpointsFileError(str(target), [f"cannot be read as JSON: {exc}"]) from exc
    from .schema import default_store

    problems = default_store().validate(document, "endpoints.schema.json")
    if problems:
        raise EndpointsFileError(str(target), problems)
    base = target.parent
    found: list[Endpoint] = []
    for entry in document.get("endpoints") or []:
        transport = str(entry["transport"])
        url = str(entry["url"]).rstrip("/") if transport == "http" else None
        command = [str(part) for part in entry.get("command") or []] if transport == "stdio" else None

        def resolved(key: str) -> str | None:
            value = entry.get(key)
            return str(base / Path(value).expanduser()) if isinstance(value, str) else None

        found.append(Endpoint(
            transport=transport, url=url, command=command, name=entry.get("name"), sources=["file"],
            cwd=resolved("cwd"), token_file=resolved("token_file"), endpoint_id=entry.get("endpoint_id"),
            devices=[str(item) for item in entry.get("devices") or []],
            tags=[str(item) for item in entry.get("tags") or []],
        ))
    return found


def probe(endpoint: Endpoint, *, timeout: float = 2.0) -> Endpoint:
    """Read the endpoint's ``/.well-known/mhs.json`` (HTTP only) and record what it says.

    ``status`` becomes ``reachable`` (descriptor valid against
    ``endpoint-descriptor.schema.json``), ``invalid_descriptor`` (the endpoint
    answered something else; ``error.mhs_code`` ``MHS.TRANSPORT.PROTOCOL_ERROR``)
    or ``unreachable`` (``MHS.TRANSPORT.UNAVAILABLE``).  A stdio endpoint is
    left ``not_probed``: discovery never launches a process.  The descriptor
    is the endpoint's own claim; the endpoint stays untrusted.
    """
    if endpoint.transport != "http" or not endpoint.url:
        endpoint.status = "not_probed"
        return endpoint
    url = endpoint.url + WELL_KNOWN_PATH
    try:
        request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(_MAX_DESCRIPTOR_BYTES + 1)
    except urllib.error.HTTPError as exc:
        exc.close()
        endpoint.status = "invalid_descriptor"
        endpoint.error = {"mhs_code": "MHS.TRANSPORT.PROTOCOL_ERROR",
                          "message": f"GET {WELL_KNOWN_PATH} answered HTTP {exc.code}"}
        return endpoint
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        endpoint.status = "unreachable"
        endpoint.error = {"mhs_code": "MHS.TRANSPORT.UNAVAILABLE", "message": f"cannot reach {url}: {reason}"}
        return endpoint
    try:
        if len(body) > _MAX_DESCRIPTOR_BYTES:
            raise ValueError("the descriptor exceeds 1 MiB")
        descriptor = json.loads(body.decode("utf-8"))
        from .schema import default_store

        problems = default_store().validate(descriptor, "endpoint-descriptor.schema.json") \
            if isinstance(descriptor, dict) else ["not a JSON object"]
        if problems:
            raise ValueError("; ".join(problems[:3]))
    except (UnicodeDecodeError, ValueError) as exc:
        endpoint.status = "invalid_descriptor"
        endpoint.error = {"mhs_code": "MHS.TRANSPORT.PROTOCOL_ERROR",
                          "message": f"{url} is not an endpoint descriptor: {exc}"[:500]}
        return endpoint
    endpoint.status = "reachable"
    endpoint.descriptor = descriptor
    claimed = str(descriptor.get("endpoint_id"))
    if endpoint.endpoint_id and endpoint.endpoint_id != claimed:
        endpoint.warnings.append(f"the configured endpoint_id {endpoint.endpoint_id} differs from the "
                                 f"descriptor's {claimed}")
    endpoint.endpoint_id = claimed
    listed = [str(item) for item in descriptor.get("devices") or []]
    missing = [item for item in endpoint.devices if item not in listed]
    if missing:
        endpoint.warnings.append(f"configured devices not served by the endpoint: {', '.join(missing)}")
    endpoint.devices = listed
    return endpoint


def discover(*, targets: Sequence[str] = (), env: str | None = None, path: str | os.PathLike[str] | None = None,
             use_env: bool = True, use_file: bool = True, probe_http: bool = True,
             timeout: float = 2.0) -> list[Endpoint]:
    """Every configured endpoint, HTTP ones probed (see the module docstring).

    ``targets`` are extra endpoint strings (source ``argument``) listed first;
    ``env`` replaces the value of ``MHS_ENDPOINTS``; ``path`` the endpoints
    file.  The result is in source order with duplicates merged.  Raises
    :class:`EndpointsFileError` for an invalid file and ``ValueError`` for an
    unparsable target or ``MHS_ENDPOINTS`` entry.
    """
    found: list[Endpoint] = []
    for text in targets:
        transport, url, command = parse_target(text)
        found.append(Endpoint(transport=transport, url=url, command=command, sources=["argument"]))
    if use_env:
        found.extend(endpoints_from_env(env))
    if use_file:
        found.extend(read_endpoints_file(path))
    merged: dict[str, Endpoint] = {}
    for item in found:
        known = merged.get(item.key)
        if known is None:
            merged[item.key] = item
            continue
        known.sources.extend(source for source in item.sources if source not in known.sources)
        for key in ("name", "cwd", "token_file", "endpoint_id"):
            if getattr(known, key) is None and getattr(item, key) is not None:
                setattr(known, key, getattr(item, key))
        known.devices.extend(device for device in item.devices if device not in known.devices)
        known.tags.extend(tag for tag in item.tags if tag not in known.tags)
    endpoints = list(merged.values())
    if probe_http:
        http = [item for item in endpoints if item.transport == "http"]
        if http:
            with ThreadPoolExecutor(max_workers=min(8, len(http))) as pool:
                list(pool.map(lambda item: probe(item, timeout=timeout), http))
    return endpoints


def find_device(device_id: str, endpoints: Sequence[Endpoint]) -> Endpoint | None:
    """The first endpoint that lists ``device_id`` (exact id) among its devices."""
    for endpoint in endpoints:
        if device_id in endpoint.devices:
            return endpoint
    return None


def token_of(endpoint: Endpoint) -> str | None:
    """The bearer token named by ``endpoint.token_file`` (``None`` without one).

    A token file that cannot be read raises ``MHS.AUTH.UNAUTHENTICATED`` naming the file and the endpoint;
    nothing is sent to the endpoint.
    """
    if not endpoint.token_file:
        return None
    try:
        return Path(endpoint.token_file).expanduser().read_text(encoding="utf-8").strip() or None
    except OSError as exc:
        from .errors import MHSError

        raise MHSError("MHS.AUTH.UNAUTHENTICATED",
                       f"cannot read token_file {endpoint.token_file!r} of endpoint {endpoint.key!r}: "
                       f"{exc.strerror or exc}",
                       {"token_file": endpoint.token_file, "endpoint": endpoint.key}) from exc
