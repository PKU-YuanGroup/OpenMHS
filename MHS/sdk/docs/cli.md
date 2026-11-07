# The `mhs` command line

OpenMHS is an independent open-source project, not affiliated with or endorsed
by Anthropic.

`mhs` is one of the three control surfaces, beside the MCP projection
([mcp-projection.md](mcp-projection.md)) and code files
([code-files.md](code-files.md)). It is a thin client: the endpoint enforces
every limit, interlock, permit and e-stop rule, so the CLI cannot do anything
another client could not.

From a checkout, run it as `python3 -m mhs` (the examples below do). After
`pip install ./MHS/sdk` the same commands are `mhs ...` (or `openmhs ...`).

```bash
export PYTHONPATH=MHS/sdk/src
python3 -m mhs --help
python3 -m mhs <command> --help
```

## Endpoints

Commands that talk to an endpoint take `-e/--endpoint`:

| Form | Meaning |
|---|---|
| `http://127.0.0.1:7400` | an HTTP endpoint |
| `mhs://lab-pc:7400` | the same, from an endpoint id (port 7400 by default) |
| `"stdio:python3 -m mhs serve MHS/sdk/examples/thermostat --stdio"` | launch a stdio endpoint for this one command (its state, including an e-stop latch, ends with the command) |

`--token-file FILE` sends the bearer token in FILE (HTTP only). `--json`
prints the machine-readable result; scripts must use it. Human output may
change between versions.

## Commands

| Command | What it does |
|---|---|
| `serve <target>` | serve a driver directory, an `mhs-adapter.json`, or a reference fixture (`conveyor`, `lab`, `arm`, `replay`) |
| `driver ...` | the driver package tools, same as `python3 -m mhs.driver` (`check`, `reference`, `new`, `export`, `catalog`) |
| `validate <dir or file>` | quick static check of a driver directory, or of a JSON document against its schema |
| `devices` | one line per device (`--json`: the full manifests) |
| `describe` (alias `inspect`) | per device: mode, risk, trust, e-stop, safe state, interlocks, verbs, effective limits, fidelity gaps, facts |
| `hello` | protocol negotiation and the device list |
| `read <resource>` | a resource's state |
| `write <resource> --patch JSON` | write named parameters (`cap.device.configure.v1`); prints the receipt |
| `call -c <capability> -i JSON` | one command; prints the receipt (`--wait` follows a running operation) |
| `session` | open a session that outlives the command (pass it to `read`/`write`/`call` as `--session-id`) |
| `estop [REASON]` | engage the e-stop; no session and no mode needed; every device unless `--device` |
| `status` | e-stop latch and interlocks, one line per device |
| `reset --operator-token-file FILE` | release a latched e-stop; an operator at an interactive terminal only |
| `evidence [--verify] [--ledger FILE]` | export the evidence bundle, verify it, and check a code-file ledger against it |
| `run script.py [args]` | run a code file and write its ledger (see [code-files.md](code-files.md)) |
| `discover` | list endpoints from `MHS_ENDPOINTS` and `~/.mhs/endpoints.json` and probe them |
| `conform <dir>` / `conform -e URL [--token-file FILE]` | run the conformance suite; prints the failing and the capping test ids |
| `registry` | query a local registry index |
| `version` | SDK, specification and protocol versions |

`safety` is the deprecated spelling of `status`, `estop` and `reset`.

`--device` takes a full device id or a unique part of it (`--device
sample-mover`). Without it, a command addresses the endpoint's only device, or
the one that serves the named resource or capability.

## Exit codes

One table for every command:

| Code | Meaning |
|---|---|
| 0 | success (a receipt that is `completed`, or `accepted`/`running` work) |
| 1 | the command ran but was refused or failed: a receipt that is `rejected`, `failed`, `cancelled` or `unknown`; an endpoint error such as `MHS.DEVICE.UNKNOWN`; a driver strict mode refuses; an invalid document |
| 2 | usage error: bad flags, `--input` that is not a JSON object, a missing file, an unsupported endpoint form |
| 3 | transport error: the endpoint cannot be reached (`MHS.TRANSPORT.UNAVAILABLE`, nothing was sent) or the response was lost (`MHS.OUTCOME.TIMEOUT`/`UNKNOWN`: the command may have run; reconcile by `command_id`) |
| 4 | authentication or authorisation: `MHS.AUTH.*`, a `reset` without an interactive operator, a hardware backend without `--allow-hardware` |
| 5 | `conform`: the required level was not achieved |
| 130 | interrupted |

Which row applies: a receipt gives 0 or 1 by its status, whatever its error
code (a receipt with status `unknown` is 1), except a refusal whose
`error.mhs_code` is `MHS.AUTH.*` (an operator-only reset sent with the client
token, `MHS.AUTH.HARDWARE_DISABLED`), which gives 4. Codes 3 and 4 otherwise
come from errors raised without a receipt. `estop` addresses several devices:
it exits 0 only when every device has a `completed` receipt, otherwise with
the code all its failures share (3 when only transport failed), else 1.

With `--json`, an error is printed on stdout as
`{"error": {"mhs_code", "message", "retryable", "data", "remediation"}}`;
without it, one line goes to stderr. With `--json`, stdout holds only the
JSON result; notes such as `conform`'s "below target" line go to stderr.

```bash
python3 -m mhs devices -e http://127.0.0.1:9 --json     # nothing listens there: MHS.TRANSPORT.UNAVAILABLE, exit 3
```

## Serving a driver

```bash
python3 -m mhs serve MHS/sdk/examples/thermostat --port 7400        # HTTP, fake backend
python3 -m mhs serve MHS/sdk/examples/thermostat --stdio            # newline-delimited JSON-RPC on stdin/stdout
python3 -m mhs serve MHS/sdk/examples/thermostat --mcp              # the MCP projection on stdin/stdout
python3 -m mhs serve lab --port 7401                                # a reference fixture
```

`serve` loads a driver directory or an `mhs-adapter.json` with
`mhs.adapter.load`, always in strict mode. Options:

| Option | Meaning |
|---|---|
| `--backend fake\|sim\|hardware` | default `fake`; `fake` and `sim` are served as `mode: simulated`; only `hardware` drives the device |
| `--allow-hardware` | operator decision: let the hardware backend start (it also needs `--state-dir`; a model-written R2+ driver needs a human `reviewed_by` in `driver.lock.json`) |
| `--arm` | operator decision: arm hardware actuation; without it hardware commands are refused with `MHS.AUTH.HARDWARE_DISABLED` |
| `--state-dir DIR` | keep the e-stop latch, the evidence chain and the command journal across restarts |
| `--site-limits FILE` | the operator overlay; it can only narrow limits |
| `--stdio` / `--port N` / `--mcp` | the transport (default: HTTP on port 7400; `--port 0` picks a free port) |
| `--host H` | HTTP bind address; anything but loopback needs `--token-file` |
| `--token-file FILE` | HTTP: clients must present this bearer token (principal kind `agent`) |
| `--operator-token-file FILE` | HTTP: the operator's token (principal kind `operator`); `mhs reset` uses it |
| `--mcp-config FILE`, `--operator-tools`, `--allow-external-sessions` | `--mcp` only: the host policy of the projection |

When a token file is configured, every HTTP request except
`/.well-known/mhs.json` needs a token, the e-stop included. Give every client
the client token.

The ready line (`{"mhs_ready": true, "url": ...}`) goes to stdout for HTTP and
to stderr for `--stdio`. SIGTERM and Ctrl-C close the endpoint cleanly.

## E-stop and reset

```bash
python3 -m mhs estop -e http://127.0.0.1:7400 "lid opened"     # every device; no --mode, no session
python3 -m mhs status -e http://127.0.0.1:7400
```

The e-stop latches before the driver is called; while latched every effectful
command is refused with `MHS.SAFETY.ESTOP_ENGAGED` (exit 1).

`--device NAME` (repeatable) stops only the named devices. Every name is
resolved first; a name that is unknown or ambiguous is reported, and every
other named device is still stopped. The output has one receipt line per
stopped device, one stderr line per failure and a final `NOT stopped: ...`
line; `--json` prints `{"receipts": [...], "errors": [{"device", "error"}]}`.

Releasing the latch is an operator's decision. `reset` needs the operator's
token file and a person at an interactive terminal: it prints the device's
latch and interlocks and asks the operator to type `reset`. With stdin not a
terminal (an agent, a script, a pipe) it refuses with exit 4 and sends
nothing. The endpoint also refuses a reset while any interlock is open or
unknown, and the device does not resume: a new command is needed.

```bash
python3 -c "import secrets; print(secrets.token_hex(16))" > client.token
python3 -c "import secrets; print(secrets.token_hex(16))" > operator.token
python3 -m mhs serve MHS/sdk/examples/thermostat --port 7400 --token-file client.token --operator-token-file operator.token &
python3 -m mhs estop -e http://127.0.0.1:7400 --token-file client.token
python3 -m mhs reset -e http://127.0.0.1:7400 --operator-token-file operator.token     # type: reset
```

## Reading, writing and calling

```bash
python3 -m mhs serve MHS/sdk/examples/thermostat --port 7400 &
python3 -m mhs devices -e http://127.0.0.1:7400
python3 -m mhs describe -e http://127.0.0.1:7400
python3 -m mhs read main -e http://127.0.0.1:7400
python3 -m mhs write main -e http://127.0.0.1:7400 --patch '{"setpoint": 40}'
python3 -m mhs call -e http://127.0.0.1:7400 -c cap.thermal.setpoint.v1 -i '{"target_temperature": 30}'
python3 -m mhs write main -e http://127.0.0.1:7400 --patch '{"setpoint": 400}'   # rejected: MHS.SAFETY.ENVELOPE_VIOLATION, exit 1
```

Each command opens its own session in the device's own mode and closes it.
`--input` and `--patch` also take `@file.json`.

## Checking a driver

```bash
python3 -m mhs validate MHS/sdk/examples/thermostat               # strict resolution, lock, fresh reference files
python3 -m mhs validate MHS/sdk/examples/thermostat/reference.json
python3 -m mhs driver check MHS/sdk/examples/thermostat --backend fake     # the acceptance gate (exit 0 = done)
python3 -m mhs conform MHS/sdk/examples/thermostat --level CL3
python3 -m mhs conform MHS/sdk/examples/thermostat --level CL4    # exit 5: capped at CL3 by FID-016, FID-025
```

`conform` runs a driver directory in process on its fake backend (`--backend
sim` for a simulator); `-e URL`, `--command CMD` and `--reference NAME` are
the other subjects. It prints the failing tests and the tests that cap the
level; `-o report.json` saves the report. On hardware or hybrid devices,
actuating tests need the operator's `--allow-actuation`. Over `-e` or
`--command` the negative tests (commands the endpoint must refuse) are also
skipped on hardware without it, because nothing could stop such a command
before the device if the endpoint failed to refuse it; in process the harness
blocks them at the bridge. A required test that is skipped caps the level.

## Discovery

```bash
MHS_ENDPOINTS=http://127.0.0.1:7400,mhs://lab-pc:7401 python3 -m mhs discover
python3 -m mhs discover --json
```

Sources are `MHS_ENDPOINTS` (comma-separated; `stdio:<command>` entries
separate their words with spaces and are listed but never launched) and
`~/.mhs/endpoints.json` (or
`$MHS_ENDPOINTS_FILE`, or `--file`), validated against
`endpoints.schema.json`; an invalid file is exit 2. Every HTTP endpoint is
probed with `GET /.well-known/mhs.json`. Discovered does not mean trusted:
discovery authenticates nothing, and every entry is reported `"trusted":
false`.

```json
{
  "openmhs": "0.9",
  "endpoints": [
    {"name": "bath", "transport": "http", "url": "http://10.0.0.5:7400", "token_file": "bath.token"},
    {"name": "thermostat", "transport": "stdio",
     "command": ["python3", "-m", "mhs", "serve", "MHS/sdk/examples/thermostat", "--stdio"]}
  ]
}
```

A relative `token_file` or `cwd` is resolved against the file's directory.
