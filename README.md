# OpenMHS — Model Hardware Standard

[Website and documentation](https://mhs.openai4s.org) · [OpenAI4S](https://github.com/PKU-YuanGroup/OpenAI4S) · [Playground](https://github.com/PKU-YuanGroup/OpenAI4S-Playground)

OpenMHS is the open-source Model Hardware Standard: an open draft contract between AI agents and the equipment they
operate: laboratory instruments, robots and the simulators that stand in for
them. It defines how a device describes itself (what it measures, what can be
adjusted, which actions exist, its limits and how it stops), how an agent
discovers and calls it, and what comes back.

The core ideas:

- **The endpoint enforces safety, not the model.** Limits, interlocks,
  permits and a latching emergency stop are evaluated by the endpoint before
  any physical effect.
- **Every action returns a receipt** (revision before and after, state hash,
  effects, approvals) that is chained into an evidence log you can verify
  offline. A command id makes retries idempotent.
- **Simulation is declared, never silent.** A simulator says that it is one
  and publishes a fidelity contract; it never claims to be hardware.
- **One contract, several control surfaces:** JSON-RPC over stdio or HTTP, an
  MCP projection for existing agent hosts, a CLI and a Python API.

The problem statement was inspired by Anthropic's MHS research preview. What
that preview publicly describes, what OpenMHS adopts, and what it does not
claim are documented in
[`MHS/spec/appendix-d-anthropic-mhs.md`](MHS/spec/appendix-d-anthropic-mhs.md).

> **Status: 0.9, first public preview (SDK `0.9.0.dev0`, 2026-11-06).** Research software; interfaces will
> change before 1.0. OpenMHS is **not a safety certification** and not a
> safety-rated control channel. It never replaces a hardware emergency stop or
> a risk assessment by the people operating the equipment.

## Repository layout

| Path | Contents |
|---|---|
| [`MHS/spec/`](MHS/spec/) | Specification text (reading order in [`MHS/spec/README.md`](MHS/spec/README.md)), the machine-readable capability catalogue `capabilities.json` and the error registry `errors.json`. |
| [`MHS/schema/`](MHS/schema/) | JSON Schema 2020-12 contracts and worked examples. |
| [`MHS/sdk/`](MHS/sdk/) | The Python SDK, distribution `openmhs`, import name `mhs`; standard library only. Endpoint runtime, client, schema validator, bridges, deterministic reference endpoints, conformance suite, MCP projection and CLI. |
| [`MHS/registry/`](MHS/registry/) | A catalogue of about 2,967 public lab-automation and robotics repositories, with the generator and validator that produce it. |
| [`MHS/drivers/`](MHS/drivers/) | Driver packages, one per upstream repository. Four exemplars (a lab instrument, a SCPI instrument, a robot arm, a simulator) show the pattern. |
| [`MHS/handoff/`](MHS/handoff/) | Driver package states, source review notes and validation tools. |
| [`tools/`](tools/) | Repository tools: fetch a pinned upstream clone, build the changelog index, check the open-source export. |
| [`MHS/conformance/`](MHS/conformance/) | Self-issued conformance reports for the reference endpoints. |
| [`MHS/site/`](MHS/site/) | Offline static-site generator, checker and local preview server. |
| [`integration/openai4s/`](integration/openai4s/) | Reference host example: the OpenAI4S agent host using OpenMHS endpoints through MCP. |

## Quick start

Python 3.10 or newer; no third-party packages.

```bash
export PYTHONPATH="$PWD/MHS/sdk/src"

# A deterministic simulated workcell on loopback HTTP
python3 -m mhs.reference conveyor --port 7400 &

python3 -m mhs.cli devices --endpoint http://127.0.0.1:7400
python3 -m mhs.conformance --endpoint http://127.0.0.1:7400 --profile MHS-Sim --level CL3
```

The reference endpoints are simulations; none of them controls hardware.

### The device market: 746 drivers ready to serve

Every driver package that passed its gate is in the market (`MHS/drivers/market.json`, browsable at
[mhs.openai4s.org/market](https://mhs.openai4s.org/market/)): 299 hardware drivers served on fake backends and 447
simulations, each with an introduction and a one-line command.

```bash
export PYTHONPATH="$PWD/MHS/sdk/src"
python3 -m mhs market search microscope
python3 -m mhs market show julabo
python3 -m mhs serve labs/tiagocoutinho__julabo --port 7400   # fake backend, no instrument
```

With [OpenAI4S](https://github.com/PKU-YuanGroup/OpenAI4S), which ships OpenMHS as a submodule, one command installs a
device into its Lab and the agent can use it: `openai4s lab add labs/tiagocoutinho__julabo`.

To install the SDK as a package, copy the schemas and catalogues into it
first:

```bash
python3 MHS/sdk/tools/sync_data.py
python3 -m pip install ./MHS/sdk
mhs version
```

To build and check the website locally (the site URL is a build parameter;
there is no default host):

```bash
python3 MHS/site/build.py --out /tmp/openmhs-site --site-url http://127.0.0.1:8080/
python3 MHS/site/check.py --site /tmp/openmhs-site
python3 MHS/site/serve.py 8080 --site /tmp/openmhs-site
```

## Driver packages

One upstream repository becomes one driver package: a small Python class that declares what the device reads, writes and
does, with every limit sourced from the upstream code or documentation. The package is done when one command passes:

```bash
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD/MHS/sdk/src"
python3 -m mhs.driver check MHS/sdk/examples/thermostat --backend fake        # the acceptance gate, G1 to G9
python3 -m mhs.driver catalog search temperature setpoint                      # find capability classes
```

A pass is `contract_checked` evidence on a fake backend. It is not a hardware conformance level and not a safety
certification, and a model-written driver for hardware at risk R2 or above cannot start its hardware backend until a human
signs `reviewed_by`. The guide for authors is
[`MHS/sdk/docs/driver-authoring.md`](MHS/sdk/docs/driver-authoring.md); the process for running a model over the registry's task
cards is [`MHS/handoff/README.md`](MHS/handoff/README.md). The gate reads the upstream clone of the package it checks; the
corpus itself is not part of this repository, and `python3 tools/fetch_clone.py <driver dir>` fetches just the one repository at
its pinned commit.

## Tests

```bash
export PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=MHS/sdk/src python3 -m unittest discover -s MHS/sdk/tests -t MHS/sdk
python3 -m unittest discover -s MHS/registry/tests
python3 MHS/site/check.py
python3 tools/oss_export_check.py --skip-suites     # the open-source tree: licences, no private paths, no impersonation
```

The OpenAI4S integration tests additionally need an OpenAI4S source checkout
on `PYTHONPATH`; see [`integration/openai4s/README.md`](integration/openai4s/README.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and
[`CHANGELOG.md`](CHANGELOG.md), whose first section lists the behaviour changes of this draft.

## Naming and compatibility

- Project identifiers (name, versions, schema namespace) are defined once in
  [`MHS/sdk/src/mhs/_ids.py`](MHS/sdk/src/mhs/_ids.py).
- Website: `https://mhs.openai4s.org`; schema namespace:
  `https://mhs.openai4s.org/schema/0.9/`. Earlier schema identifiers remain readable.
- Wire identifiers stay as they are during 0.x: methods `mhs.*`, error codes
  `MHS.*`, and `mhs_version: "1.0"`, which means *wire revision 1*. The Python
  import name stays `mhs`.

## Security, conduct and licensing

- Report vulnerabilities and safety defects privately; see
  [`SECURITY.md`](SECURITY.md). Safety defects are handled like security
  defects.
- Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md)
  (Contributor Covenant 2.1).
- Code, schemas and tooling: MIT License ([`LICENSE`](LICENSE),
  [`NOTICE`](NOTICE)). Specification text and registry data: CC BY 4.0
  ([`LICENSE-docs`](LICENSE-docs)).
- Quoted third-party text, including the quotations of Anthropic material in
  appendix D, is not licensed by this project. Repositories described by the
  registry keep their own licences.
