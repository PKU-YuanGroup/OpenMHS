OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# OpenMHS SDK (distribution `openmhs`, import `mhs`)

The reference Python SDK for **OpenMHS 0.9** (development draft). It is pure
standard library (Python 3.10+), has no runtime dependencies, and contains
both ends of the protocol: a strict endpoint runtime and a client for agents,
scripts, hosts and CI.

> **Safety notice.** OpenMHS is a software envelope around devices. It is not
> a safety-rated channel and never replaces a hardware emergency stop or a
> certified safety system. Every endpoint advertises
> `MHS.SAFETY.NOT_CERTIFIED` in `mhs.hello`.

Project identifiers (distribution name, SDK and specification versions, the
schema namespace) are defined once in [`src/mhs/_ids.py`](src/mhs/_ids.py).
The wire protocol keeps its 0.x identifiers: `mhs.*` methods, `MHS.*` error
codes and `mhs_version: "1.0"` (wire revision 1).

## Install

From a checkout, without installing anything:

```bash
export PYTHONPATH="$PWD/MHS/sdk/src"
python3 -m mhs.cli version
```

As a package. The JSON Schemas, the capability catalogue and the error
registry are edited in `MHS/schema/` and `MHS/spec/`; copy them into the
package before building, otherwise an installed SDK has no schemas:

```bash
python3 MHS/sdk/tools/sync_data.py            # writes src/mhs/_data/ (git-ignored)
python3 MHS/sdk/tools/sync_data.py --check    # exit 1 if _data/ has drifted
python3 -m pip install ./MHS/sdk              # console scripts: mhs, openmhs
mhs version
```

Building needs `setuptools>=77`; with pip's default build isolation it is
fetched from the package index. The schema store looks in this order:
`$MHS_SCHEMA_DIR`, the packaged `mhs/_data/schema`, then the checkout's
`MHS/schema/` (from a checkout whose schemas changed after the last sync, the
checkout wins and a warning is printed).

Schemas served to clients (`mhs.schema.get`, `GET /mhs/v1/schema/<ref>`) must
be looked up with `SchemaStore.resolve_public(ref)`, which accepts only a bare
file name such as `device.schema.json` or a full schema `$id`, and only
returns shipped schemas. `SchemaStore.load_path(path)` reads an arbitrary file
and is for local developer use only.

## Quick start: drive the conveyor simulator

```python
from mhs import connect
from mhs.canonical import ulid

client = connect(["python3", "-m", "mhs.reference", "conveyor", "--stdio"])
print(client.hello()["mhs_version"])                 # "1.0"

device = client.devices()[0]["device_id"]
client.open_session([device], mode="simulated", ttl_s=600)

print(client.read("workcell")["state"]["tick"])
receipt = client.invoke("cap.world.step.v1", {"ticks": 10})
print(receipt["status"], receipt["state_revision_after"])

# The same command_id + same input is idempotent: no second effect.
replay = client.invoke("cap.world.step.v1", {"ticks": 10},
                       command_id=receipt["command_id"])
assert replay["replayed"] is True

client.close()
```

Over loopback HTTP:

```bash
PYTHONPATH=MHS/sdk/src python3 -m mhs.reference conveyor --port 7400
PYTHONPATH=MHS/sdk/src python3 -m mhs.cli devices \
    --endpoint http://127.0.0.1:7400 --json
```

`connect()` accepts:

| Target | Transport |
|---|---|
| `["python3", "-m", "mhs.reference", "conveyor", "--stdio"]` | stdio NDJSON |
| `"http://127.0.0.1:7400"` / `"https://…"` | HTTP JSON-RPC (+ SSE) |
| `"mhs://localhost:7400"` | HTTP on port 7400 |
| `"stdio:python3,-m,mhs.reference,conveyor,--stdio"` | stdio (CLI form) |

## Client

`mhs.MHSClient` / `mhs.connect()` provide these calls. [`INTERFACE.md`](INTERFACE.md) is generated from the code
(`python3 -m mhs.driver --print-interface`) and lists the client and server surface by name only; the behaviour of each call
is in the specification ([`MHS/spec/core.md`](../spec/core.md)) and the guides in [`docs/`](docs/):

```python
client.hello() -> dict
client.devices() -> list[dict]                 # full manifests
client.inspect(device_id=None) -> dict
client.open_session(device_ids=None, capabilities=None, mode=None, ttl_s=600) -> dict
client.heartbeat(session_id=None) -> dict
client.close_session(session_id=None) -> dict
client.read(resource_id, device_id=None, fields=None) -> dict
client.invoke(capability_id, input=None, *, device_id=None, resource=None,
              expected_revision=None, deadline_ms=30000, permit_id=None,
              command_id=None, session_id=None) -> dict       # receipt
client.subscribe(streams, *, device_id=None, filter=None, rate_hz=None) -> str
client.events(subscription_id=None, timeout=1.0) -> list[dict]
client.cancel(operation_id, deadline_ms=5000) -> dict         # receipt
client.snapshot(device_id=None) -> dict
client.restore(snapshot, device_id=None) -> dict              # receipt
client.safety_status(device_id=None) -> dict
client.estop(reason, device_id=None) -> dict                  # receipt
client.reset(device_id=None) -> dict                          # receipt
client.permit(capability_id, input_digest, ttl_s=60, approvals=None) -> dict
client.export_evidence() -> dict
client.verify_evidence(bundle=None) -> dict
client.close()
```

The client also exposes lower-level `request(method, params)`, `batch(calls)`,
`get_schema(ref)`, `operations(device_id=None)`, `get_operation(id)` and
`unsubscribe(id)`.

**Receipts, not exceptions.** A rejected physical action is returned as a
receipt with `status: "rejected"` and a stable `error.mhs_code`; it is part of
the evidence chain. `MHSError` is reserved for transport, protocol, session and
authentication failures. Deadlines are enforced by the transports: a call never
hangs past its budget and surfaces `MHS.OUTCOME.TIMEOUT` or a running receipt
with an `operation_id`.

## Server

```python
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

device = Device(
    "mhs://localhost:7400/lab/example",
    "Example simulated device",
    mode="simulated",
    resources=[Resource("world", "world.sim",
                        state_schema={"type": "object"},
                        state={"tick": 0})],
    capabilities=[Capability("cap.world.step.v1", "world",
                             input_schema={"type": "object",
                                           "properties": {"ticks": {"type": "integer"}},
                                           "required": ["ticks"]},
                             constraints={"max_duration_ms": 5000},
                             exclusive=True)],
    safety=SafetyEnvelope(risk_class="R1",
                          estop={"kind": "software", "latching": True},
                          safe_state={"description": "stopped", "achieved_by": []}),
    bridge=my_bridge,          # Bridge implementation: call/read/...
    fidelity={"engine": "python", "fidelity_level": "F0",
              "determinism": {"kind": "exact"}, "snapshot_restore": True},
)
server = MHSServer(endpoint_id="mhs://localhost:7400", devices=[device])
server.run_stdio()                 # or server.run_http("127.0.0.1", 7400)
```

`MHSServer` owns sessions, grants, modes, safety-envelope enforcement,
interlocks, permits, revisions, command-id idempotency, exclusive leases,
operations, subscriptions, snapshots/restores and the hash-chained evidence
log. A bridge only translates device calls and exposes state; it never advances
a revision or makes a receipt. See `mhs/bridge/base.py` for the bridge
contract and `mhs/reference/conveyor.py` for a complete deterministic example.

Built-in transports:

* **stdio** — newline-delimited JSON-RPC on stdin/stdout, logs and readiness on
  stderr, bounded reads.
* **HTTP** — `POST /mhs/v1/rpc`, `GET /mhs/v1/events` (SSE),
  `GET /.well-known/mhs.json`, `GET /mhs/v1/schema/{ref}`. Threaded stdlib
  server; loopback by default.

## CLI

```text
mhs hello    --endpoint URL
mhs devices  --endpoint URL [--device ID] [--json]
mhs read     --endpoint URL RESOURCE [--device ID] [--json]
mhs call     --endpoint URL --capability cap.world.step.v1 --input '{"ticks": 10}'
mhs session  --endpoint URL [--device ID]
mhs safety   --endpoint URL [--device ID] [--estop REASON | --reset]
mhs evidence --endpoint URL [--verify]
mhs conform  --endpoint URL --profile MHS-Sim --level CL4
mhs registry --path MHS/registry --query conveyor --json
mhs serve    conveyor --port 7400
mhs version
```

`--endpoint` also accepts `stdio:python3,-m,mhs.reference,conveyor,--stdio`,
so the CLI can launch a local endpoint without a server.

## Registry

`mhs.registry.Registry` reads `MHS/registry/index.json`, `index.jsonl`,
`records.csv` or a directory of package records:

```python
from mhs.registry import Registry
registry = Registry.load("MHS/registry")
record = registry.get("gh.7jameslondon/magscope")
print(record.package_id, record.family, record.adapter_state)
for hit in registry.search(query="microscope", capability="cap.sensing.image.v1", limit=5):
    print(hit.summary())
```

`PackageRecord` is a `dict` subclass with accessors for every registry field,
so it is JSON-serialisable and backward compatible.

## Tests

```bash
PYTHONPATH=MHS/sdk/src python3 -m unittest discover -s MHS/sdk/tests -t MHS/sdk -v
PYTHONPATH=MHS/sdk/src python3 -m unittest discover -s MHS/sdk/tests/packaging -t MHS/sdk -v
```

The `packaging` tests cover the identifiers in `_ids.py`, the licence files,
`tools/sync_data.py`, traversal-safe schema lookup and the packaged-data
lookup from a copy of the package outside the repository.

The suite covers schema examples, canonical JSON/ULID/state hashes, evidence
tamper detection, the server↔client contract over stdio and HTTP, negative
safety cases, the CLI and the registry. No test uses the network beyond
loopback.

An end-to-end transcript (stdio and HTTP, including idempotent replay, e-stop
and an interlock rejection) is checked in at
[`docs/e2e-transcript.txt`](docs/e2e-transcript.txt).

## Layout

```text
MHS/sdk/src/mhs/
  _ids.py                                    # project identifiers, defined once
  client.py server.py cli.py registry.py     # core
  canonical.py errors.py protocol.py evidence.py
  schema/                                    # JSON Schema 2020-12 subset + store
  _data/                                     # generated by tools/sync_data.py (git-ignored)
  bridge/                                    # python-object, gymnasium, mujoco, replay
  reference/                                 # deterministic conveyor, lab, arm, replay endpoints
  conformance/                               # executable conformance suite
MHS/sdk/tools/sync_data.py                   # copies schemas and catalogues into _data/
```

## License

MIT License; see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
