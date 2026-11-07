OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# OpenMHS: specification, schemas, SDK and registry

OpenMHS is an open, versioned, machine-checkable contract between **agents that
reason** and **equipment that acts**. It lets an AI agent, or a plain Python
program, discover a device it has never seen, understand what that device can
do and what those actions mean physically, execute actions under a safety
envelope that the endpoint enforces, and obtain verifiable evidence of what
actually happened.

OpenMHS composes with MCP rather than competing with it: MCP standardises how a
model reaches *tools*; OpenMHS describes what a *tool that moves matter* means
and how it is kept within its limits.

**Status: 0.9, first public preview (SDK `0.9.0.dev0`).** This tree contains the specification text,
JSON Schemas, a standard-library-only reference SDK, deterministic reference
endpoints, a conformance suite, a capability catalogue, a registry of public
repositories and an offline static site. It is research software, not an
approved standard, and **not a safety certification or a safety-rated control
channel**; see [Status and disclaimers](#status-and-disclaimers).

## What OpenMHS addresses

1. **Integration is bespoke.** Every instrument ships its own SDK, transport
   and vocabulary. OpenMHS gives drivers one contract, so an agent host does
   not need a translator per device.
2. **Agents cannot know what is safe.** Limits, hazards, interlocks and
   permits are machine-readable, travel in-band and are enforced by the
   endpoint, not by the model.
3. **Simulation and hardware are different universes.** Both get one
   contract, with an explicitly declared `mode` and a fidelity contract, so a
   simulator can be used without pretending to be hardware.

The control surfaces are the wire protocol (JSON-RPC 2.0 over stdio or
HTTP/SSE), an MCP projection for existing MCP hosts, a CLI and a Python code
API. Devices run in `hardware`, `hybrid`, `simulated` or `replay` mode.

## Layout

| Path | Contents |
|---|---|
| [`spec/`](spec/) | Specification text; start with the reading guide in [`spec/README.md`](spec/README.md). Also the capability catalogue [`spec/capabilities.json`](spec/capabilities.json) and the error registry [`spec/errors.json`](spec/errors.json). [Appendix D](spec/appendix-d-anthropic-mhs.md) records how OpenMHS relates to Anthropic's MHS research preview. |
| [`schema/`](schema/) | JSON Schema 2020-12 definitions (device, capability, adapter, bindings, receipt, permit, snapshot, evidence bundle, registry record and index, conformance report, endpoint descriptor) with [examples](schema/examples/). |
| [`sdk/`](sdk/) | The Python SDK (distribution `openmhs`, import `mhs`): schema validator, canonical JSON, protocol, client, endpoint runtime, bridges, reference endpoints, conformance suite, MCP projection and CLI. The interface contract is [`sdk/INTERFACE.md`](sdk/INTERFACE.md). |
| [`registry/`](registry/) | One record per catalogued repository, family recipes, index files, and the generator and validator ([`registry/README.md`](registry/README.md)). |
| [`drivers/`](drivers/) | Driver packages, one per upstream repository; four exemplars show the pattern ([`drivers/README.md`](drivers/README.md)). |
| [`handoff/`](handoff/) | The kit for turning the registry into driver packages with a model, one repository at a time: prompt, playbook, waves, sandbox and review rules, tools ([`handoff/README.md`](handoff/README.md)). |
| [`conformance/`](conformance/) | Self-issued conformance reports for the reference endpoints. |
| [`site/`](site/) | Offline static-site generator, checker, preview server and deploy notes. |

## How to run the reference endpoints

The SDK is standard-library-only and runs on Python 3.10+. From the
repository root:

```sh
export PYTHONPATH="$PWD/MHS/sdk/src"

# 1. Start a deterministic simulated workcell over HTTP (also supports --stdio)
python3 -m mhs.reference conveyor --port 7400

# 2. In another shell, talk to it
DEV=mhs://localhost:7400/lab/conveyor-workcell
python3 -m mhs.cli devices --endpoint http://127.0.0.1:7400
python3 -m mhs.cli devices --endpoint http://127.0.0.1:7400 --device "$DEV" --json
python3 -m mhs.cli read workcell --endpoint http://127.0.0.1:7400 --device "$DEV"
python3 -m mhs.cli call --endpoint http://127.0.0.1:7400 --device "$DEV" \
                       --capability cap.world.step.v1 --input '{"ticks":10}'
```

Other reference endpoints:

```sh
python3 -m mhs.reference lab      --port 7400   # liquid handler + plate reader + sample mover
python3 -m mhs.reference arm      --port 7400   # 2-DOF analytic arm with a fidelity contract
python3 -m mhs.reference replay   --port 7400   # read-only replay of an evidence bundle
```

All reference endpoints are deterministic simulations; none controls
hardware. The HTTP descriptor is at
`http://127.0.0.1:7400/.well-known/mhs.json` and the RPC path is
`/mhs/v1/rpc`.

### Python code API

```python
from mhs import connect

DEVICE = "mhs://localhost:7400/lab/conveyor-workcell"

with connect("http://127.0.0.1:7400") as client:
    client.open_session(
        device_ids=[DEVICE],
        capabilities=["cap.world.step.v1", "cap.world.state.v1"],
        mode="simulated",
        ttl_s=600,
    )
    receipt = client.invoke("cap.world.step.v1", {"ticks": 10})
    state = client.read("workcell")
```

Receipts are returned as dicts for `rejected`, `failed` and `unknown`
outcomes; the client raises `MHSError` only for transport, protocol,
authentication and session-level failures. A physical rejection is evidence,
not an exception ([`sdk/INTERFACE.md`](sdk/INTERFACE.md)).

### MCP

```sh
python3 -m mhs.mcp --endpoint http://127.0.0.1:7400   # MCP stdio server projecting an endpoint
```

Each bound capability appears as an MCP tool, callable from any MCP host
([`sdk/docs/mcp-projection.md`](sdk/docs/mcp-projection.md)).

## How to run conformance

```sh
export PYTHONPATH="$PWD/MHS/sdk/src"
python3 -m mhs.conformance --endpoint http://127.0.0.1:7400 \
    --profile MHS-Sim --level CL3 --out report.json
```

The produced `report.json` validates against
[`schema/conformance-report.schema.json`](schema/conformance-report.schema.json)
and its digest can be recomputed offline. A conformance report is a
behavioural test result, not a certification.

## How to validate the data contracts

```sh
export PYTHONPATH="$PWD/MHS/sdk/src"
python3 - <<'PY'
import glob, json
from mhs.schema import default_store
store = default_store()
for path in sorted(glob.glob("MHS/schema/examples/*.json")):
    data = json.load(open(path))
    name = data.get("$schema", "").rsplit("/", 1)[-1]
    errors = store.validate(data, name)
    print(path, "OK" if not errors else errors)
PY
```

The schema store looks in `$MHS_SCHEMA_DIR`, then the schemas packaged with
the SDK, then this checkout. Schema `$id`s live under
`https://openmhs.invalid/schema/0.9/` (a placeholder until the project has its
own domain); documents that still use the pre-0.9 prefix are accepted for
reading during 0.9.

## Status and disclaimers

**OpenMHS is not a safety certification and not a safety-rated channel.**
Every endpoint must report that it is not certified, and a hardware emergency
stop must exist independently of OpenMHS.

- The specification is a **0.9 development draft**, published for review and
  expected to change.
- Registry records are **declared or statically scanned** unless their
  evidence state says otherwise; "listed in the registry" does not mean
  "supported".
- Simulation conformance does not establish equivalence to physical
  hardware; the fidelity contract and its declared gaps are part of the
  answer.
- OpenMHS does not provide real-time control, safety certification or
  regulatory compliance.
- Wire identifiers (`mhs.*` methods, `MHS.*` error codes, `mhs_version: "1.0"`
  meaning wire revision 1) are kept unchanged during 0.x.

## License

Code, schemas and tooling: **MIT** ([`LICENSE`](../LICENSE),
[`NOTICE`](../NOTICE)). Specification text and registry data: **CC BY 4.0**
([`LICENSE-docs`](../LICENSE-docs)). Quoted third-party text, including the
quotations of Anthropic material in appendix D, is not licensed by this
project.

## Security

Report vulnerabilities and safety defects privately as described in
[`SECURITY.md`](../SECURITY.md).
