# Code files

OpenMHS is an independent open-source project, not affiliated with or endorsed
by Anthropic.

A code file is a plain Python script that chains device commands, across one
or more devices and endpoints, so a procedure runs without reasoning at every
step: explore with the agent, freeze what worked into a file, then loop it.
The endpoint still enforces every limit, interlock, permit and e-stop rule; a
code file has no more authority than the same calls made one by one.

The helper is `mhs.run.lab`; the runner is `mhs run`, which writes a ledger
of everything the script did. Examples below use the reference `lab`
endpoint (three simulated devices: `liquid-handler`, `sample-mover`,
`plate-reader`):

```bash
export PYTHONPATH=MHS/sdk/src
python3 -m mhs serve lab --port 7401 &
```

## 1. Explore

Find the devices, their capabilities, inputs, limits and state with the CLI
(or the same through the MCP tools `mhs__devices`, `mhs__inspect` and
`mhs__read`), and try single commands:

```bash
python3 -m mhs devices -e http://127.0.0.1:7401
python3 -m mhs describe -e http://127.0.0.1:7401 --device sample-mover
python3 -m mhs read bench -e http://127.0.0.1:7401 --device sample-mover
python3 -m mhs call -e http://127.0.0.1:7401 --device sample-mover -c cap.sample.move.v1 -i '{"plate_id": "plate-001", "to": "reader"}'
python3 -m mhs call -e http://127.0.0.1:7401 --device sample-mover -c cap.sample.move.v1 -i '{"plate_id": "plate-001", "to": "liquid_handler"}'
```

Each `call` prints its receipt. Note the capability ids and the inputs that
completed; a `rejected` receipt names the field and the limit, a `failed` one
the device's reason (a plate already at its destination, for example).

## 2. Freeze

Write the steps that worked into a function in a file. `lab()` connects to
each endpoint once and gives every device its own handle with its own session
(opened in the device's own mode). With `check=True`, the default, any
receipt other than `completed` (or work still `running`) raises
`MHSRejected`, so the file stops at the first refusal instead of carrying on.

```python
# assay.py
import sys

from mhs.run import lab

PLATE = "plate-001"


def assay(bench, volume_ul=50):
    """One assay: transfer, move the plate to the reader, measure, move it back."""
    bench["liquid-handler"].invoke("cap.fluid.transfer.v1",
                                   {"source_well": "A1", "destination_well": "B1", "volume_ul": volume_ul})
    bench["sample-mover"].invoke("cap.sample.move.v1", {"plate_id": PLATE, "to": "reader"})
    spectrum = bench["plate-reader"].invoke("cap.measure.spectrum.v1", {"plate_id": PLATE, "wavelengths_nm": [562]})
    bench["sample-mover"].invoke("cap.sample.move.v1", {"plate_id": PLATE, "to": "liquid_handler"})
    return spectrum["output"]


if __name__ == "__main__":
    with lab(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7401") as bench:
        print(assay(bench)["measurement_index"])
```

```bash
python3 -m mhs run assay.py http://127.0.0.1:7401
```

## 3. Loop

Reuse the frozen function in a loop with an explicit end condition. Never
retry a physical command blindly: a refusal is final (the run stops with exit
1), and after a lost response (`MHS.OUTCOME.TIMEOUT` / `UNKNOWN`, exit 3) read
the device state and retry only with the same `command_id`.

```python
# loop.py
import sys

from assay import assay
from mhs.run import lab

ENDPOINT = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7401"
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 3

with lab(ENDPOINT) as bench:
    for run in range(RUNS):
        output = assay(bench, volume_ul=20)
        print(run, output["measurement_index"])
```

```bash
python3 -m mhs run loop.py http://127.0.0.1:7401 3
```

`mhs run` puts the script's directory first on `sys.path`, so `loop.py`
imports `assay.py` from beside it.

To stop everything from inside a file, call `bench.estop("reason")` (every
device of the lab, no session needed). It tries every device even when one
stop fails, then raises that error with `data["errors"]` (the devices not
confirmed stopped) and `data["receipts"]`. `python3 -m mhs estop -e <url>`
does the same from another terminal. Releasing the latch is an operator's
`mhs reset`, never part of a code file.

## The `lab()` helper

```python
lab(*targets, check=True, ledger=True, mode=None, ttl_s=600, token=None, principal=None)
```

| Target | Devices it adds |
|---|---|
| `"http://host:port"`, `"mhs://host:port"`, `"stdio:<command>"`, an argv list | every device of that endpoint |
| an `MHSServer` in this process, an open `MHSClient` | every device it serves (an open client is not closed by the lab) |
| a device id or a unique part of one (`"sample-mover"`) | that device: from an endpoint already named in the call, else found through `MHS_ENDPOINTS` / `~/.mhs/endpoints.json` (`mhs.discovery.discover`) |

`token` is sent only to the endpoints named in the call. A discovered
endpoint is a claim, not a trusted server: it gets only the `token_file` of
its own endpoints-file entry, never `token`. A device that two discovered
endpoints list raises `MHS.HOST.DEVICE_AMBIGUOUS`; name its endpoint instead.

`bench[name]` (or `bench.device(name)`) takes a full device id or a unique
part of it; an ambiguous name raises `MHS.HOST.DEVICE_AMBIGUOUS`, an unknown
one `MHS.DEVICE.UNKNOWN`. `bench.devices` is a dict of handles by device id,
`bench.receipts` every receipt the handles returned. A handle
(`mhs.client.DeviceHandle`) has `invoke`/`call`, `write`, `read`, `wait`,
`cancel`, `operations`, `snapshot`, `restore`, `safety`, `manifest` and
`estop`. `check=False` returns rejected receipts instead of raising.

## The ledger

Every run leaves `.mhs-run/<run id>.json` in the directory it started in (a
script that calls `os.chdir()` does not move it; `mhs run` restores the
working directory afterwards). Under
`mhs run` it records every client the script uses (`lab()` or plain
`mhs.connect`); a `lab()` used outside `mhs run` writes its own ledger when it
closes (`ledger=False` turns that off, `ledger="dir"` moves it; a lab that is
never closed writes it at interpreter exit with outcome `unclosed`).

| Field | Content |
|---|---|
| `ledger_version` | `1` |
| `run_id` | a ULID, also the file name |
| `script`, `script_sha256`, `argv` | the code file, the SHA-256 of its bytes, its arguments |
| `endpoints[]` | `{endpoint_id, target, transport}` of every endpoint used |
| `receipt_ids[]`, `receipts[]` | every receipt: `{receipt_id, command_id, endpoint_id, device_id, capability_id, status, error_code?, operation_id?}` |
| `lost[]` | requests sent without a response: `{method, code, command_id, may_have_effect, endpoint_id}` |
| `started_at`, `ended_at` | RFC 3339 times |
| `outcome` | `completed`, `rejected`, `failed`, `cancelled`, `unknown` (a receipt raised by `check=True`), `error`, `exited`, `interrupted` or `unclosed` |
| `error`, `exit_code` | how the run ended |
| `sdk` | `{name, version, spec}` |

`mhs run` exits with the CLI table: 0 the script finished, 1 a receipt was
not completed or the script raised, 3 transport error, 4 authentication
error (also a receipt refused with `MHS.AUTH.*`), the script's own
`sys.exit` code otherwise.

The ledger is checked against the endpoint's own evidence: the hash chain of
the exported bundle is verified, and every ledger receipt of that endpoint
must be in it with the same command id, device, capability and status. The
check fails (`valid: false`, exit 1) with its `reasons`: `chain_invalid`,
`missing_receipts`, `mismatched_receipts`, `endpoint_not_in_ledger` (the
endpoint is not among the ledger's `endpoints`) or `no_receipts_for_endpoint`
(the ledger has final receipts, none of them from this endpoint), so a check
against the wrong endpoint never passes by checking nothing.

```bash
python3 -m mhs evidence -e http://127.0.0.1:7401 --ledger .mhs-run/<run id>.json
```

In Python: `mhs.run.verify_ledger(ledger_path, client.export_evidence())`.
