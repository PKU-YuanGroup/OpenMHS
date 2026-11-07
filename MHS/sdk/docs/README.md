OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# OpenMHS SDK documentation

Guides for the OpenMHS SDK (`MHS/sdk/`, distribution `openmhs`, import name `mhs`, specification 0.9). The SDK
interface is [`../INTERFACE.md`](../INTERFACE.md), generated from the code by
`python3 -m mhs.driver --print-interface`. The specification is in [`../../spec/`](../../spec/) and the JSON
schemas are in [`../../schema/`](../../schema/).

| Document | Contents |
|---|---|
| [driver-authoring.md](driver-authoring.md) | writing a per-repository driver package: layout, Driver API, return/error/cancellation contract, limits and provenance, fakes, the acceptance gate and troubleshooting by gate id |
| [bridges.md](bridges.md) | the canonical grammar of the bridge families (`python-object`, `serial`, `scpi`, `gymnasium`, `mujoco`) behind the family drivers and `mhs-adapter.json` |
| [gym-live-routes.md](gym-live-routes.md) | Gymnasium backends with asynchronous environments (owned event loop, remote stop, settled close) and dm_env environments; see also [simulation-timing.md](simulation-timing.md) and [gym-checkpoints.md](gym-checkpoints.md) |
| [sim-host.md](sim-host.md) | Gymnasium backends built and driven in an isolated simulator host process (contained exits, bounded calls, a declared stop confirmed by a declared read-back, settled close) |
| [reference-endpoints.md](reference-endpoints.md) | the four reference endpoints: protocol fixtures (not driver templates), their verbs, reports and known drift |
| [conformance.md](conformance.md) | the conformance suite: levels, test ids, report format and digest |
| [mcp-projection.md](mcp-projection.md) | the MCP projection for MCP hosts |
| [reports/](reports/) | conformance reports and the recording that the reference endpoints cite |

Quick start, from the repository root:

```sh
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=MHS/sdk/src
python3 -m mhs.driver check MHS/sdk/examples/thermostat --backend fake    # the acceptance gate on the tutorial
python3 -m mhs.driver --print-interface | diff - MHS/sdk/INTERFACE.md     # the interface file is current
python3 -m mhs.conformance --reference conveyor --profile MHS-Sim --level CL4 --out "$(mktemp -d)/report.json"
python3 -m unittest discover -s MHS/sdk/tests/driver -t MHS/sdk
```
