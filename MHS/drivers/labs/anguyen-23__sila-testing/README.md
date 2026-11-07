# Exemplar: gh.anguyen-23/sila-testing (a config-only Sila2Driver)

The sila2 family exemplar. The upstream repository is a SiLA 2 server development platform with nine instrument
servers; this package serves one of them, the PerkinElmer Opera Phenix wrapper, through its `PhenixImager` feature
(`servers/phenix_imager/PhenixImager.sila.xml`, implementation `PhenixImagerImpl`). The complete feature, eight
commands and seven properties, becomes nine `x-cap.anguyen-23.*` capabilities, six property reads and four local
execution diagnostics, with the feature's `Stop` as the e-stop. The package declares an R2 `hardware` device and runs
on its fake backend only: `Sila2Driver` refuses every non-fake backend before it resolves a factory, so the evidence is
`contract_checked` and never an MHS-Device level. `driver.lock.json` keeps `authored_by` kind `model` and
`reviewed_by: null`. The declaration follows the SDK's controlled fixture `MHS/sdk/tests/fixtures/sila2_phenix` for
the same pinned source; this package adds the real task card and clone, its own capability ids, source facts, an
example overlay, the gate prerequisite file and repository tests.

## Run the gate

```sh
PYTHONPATH=MHS/sdk/src python3 -m mhs.driver check MHS/drivers/labs/anguyen-23__sila-testing --backend fake
```

## What it demonstrates

| Pattern | Where |
|---|---|
| `sila2_config`: peer format, runtime label, an opaque endpoint, the feature FQI, the pin, and the FDL, proto and implementation paths with their SHA-256; G7 proves all fifteen members, kinds, fields, constraints, errors, source ranges and RPC names from these bytes | `CONFIG` in `declarations.py` |
| One member table entry per FDL command and property: `kind`, typed `input`/`output`/`intermediate`, `errors`, `effect`, `completion`, `source_ref` of the exact FDL block | `CONFIG['members']` |
| One command and one explicit `Action` per FDL command; effectful commands are permit-bound R2 with `Limit.operator_required` on every input | `CAPS`, `actions()` in `driver.py` |
| The observable command as a bounded stock operation (`long_running`, `max_duration_ms`, `cancellable`) whose confirmation, progress, intermediate and result stay separate | `RunAcquisitionProtocol` |
| Property reads plus the four local execution diagnostics (`execution_known`, `execution_uuid`, `acquisition_progress`, `last_progress_info`) | `reads`, `parameters` |
| A Binary property as a complete artifact (`artifact`, `media_type`) | `DisplayIcon` |
| The e-stop as the feature's Stop (`safety_bindings`) and its `safe_state=True` Action with output `stopped` | `safety_bindings`, `Stop` |
| Gate preparation by one explicit, permit-bound Connect (profile `sila2-controlled-phenix-connect-v1`), never a hidden setup | `fixtures/gate-prerequisites.json`, `site-limits.example.json` |
| A controlled peer that registers with its `PeerLease`, answers the controlled operations, follows the upstream simulation where tested, and has switches for the negative controls (acknowledgement-only Stop, cached or stale Idle, a Disconnect by another client during a run) | `fake.py`, `test_driver.py` |
| A native factory that refuses | `native.py` |

## Adapting it to another SiLA 2 feature

Copy the structure, not the content, and know the helper's limit first: gate G7 has exactly one static source profile,
this PhenixImager feature at commit `0b572380` (`MHS/sdk/src/mhs/driver/sila2_check.py`), and the gate prerequisite
profile is the same feature's Connect. A package for any other feature or pin fails `SILA_SOURCE_UNPROVEN` until the
SDK gains a reviewed source profile for it. Until then, record a source-verified DEVIATION FROM THE CARD to a direct
Driver over the repository's own client class, or stop `blocked` `HELPER_MISSING` with the source lines; the four
other SiLA cards of this registry were routed to direct drivers for that reason
(`MHS/registry/overrides/waiting-routing.json`). When a profile exists: read the FDL and the implementation, declare
every member with its exact FDL block, keep every effect permit-bound with an operator envelope, bind the feature's
own stop and say what it does not prove, and keep native backends refused.

## Files

| File | Role |
|---|---|
| `task.json` | the registry task card (input; a copy of `MHS/registry/tasks/labs/anguyen-23__sila-testing.json`) |
| `declarations.py` | `CONFIG`, the complete typed PhenixImager declaration with source hashes and FDL ranges |
| `driver.py` | the `Driver` declaration: commands, actions, reads, safety binding, facts |
| `fake.py` | `PhenixPeer`, the controlled peer used by the fake backend |
| `native.py` | the hardware factory; it refuses |
| `facts.md` | facts, limits, risk, scope and fake with their sources |
| `site-limits.example.json` | an example operator overlay for the operator-required inputs |
| `fixtures/conformance.json` | typed fake inputs for the conformance suite (an alternate host tests permit reuse) |
| `fixtures/gate-prerequisites.json` | the explicit Connect the gate sends before the dependent cases |
| `test_driver.py` | the gate call plus nine repository cases (eight through the stock loader, one native refusal) |
| `driver.lock.json` | pinned upstream, install, backends, `authored_by`, `reviewed_by` |
| `reference.json`, `REFERENCE.md` | generated: `python3 -m mhs.driver reference <dir>` |
| `RESULT.json` | `pass` with the gate digest, notes and catalogue requests |

## Honest limits of this package

- The fake speaks the SDK's controlled SiLA 2 profile, not gRPC: no SiLA client, metadata, TLS, server lifetime or
  Phenix timing is modelled, and the peer's `observe` retirement contract has no native equivalent.
- The safe state is proven for the controlled peer only. On a native Phenix the Stop is an RCI STOP sent with an empty
  barcode (rci_transport.py:241-243, pheniximager_impl.py:272) that waits up to 20 s for a reply (rci_transport.py:32,
  261-276, against the controlled peer's 500 ms stop budget) and only checks that the reply is not a REJECT
  (rci_transport.py:278-285); DeviceState is the cached status of the last
  progress or status reply (pheniximager_impl.py:158-162, rci_transport.py:287-301); a stopped real acquisition keeps
  its SiLA call waiting until progress 100 or TimeoutMinutes (pheniximager_impl.py:401-435), and the stage is ejected
  only after a completed run.
- The upstream server starts in simulation mode (pheniximager_impl.py:66; README.md:72). The fake follows that
  simulation where tested, with stated differences: it reaches one placeholder host (the simulation accepts any), it
  refuses unknown protocol names (the simulation runs any name), an acquisition completes on the second progress
  poll (the simulation takes 96 wells at 0.1 s), and it refuses every command except Stop while an acquisition runs.
- The upstream accepts commands during a run, Disconnect included (pheniximager_impl.py:207-215 checks only the
  connection), and Stop then raises NotConnected (pheniximager_impl.py:78-85, 263-265): a run that another client of
  the server disconnected cannot be stopped through the feature. A repository case models it (the e-stop stays
  unachieved and the latch holds). This package's own endpoint cannot interleave a Disconnect with a running
  acquisition (one ordinary lane; an unconfirmed acquisition fences new effects).
- Risk R2 is argued in `facts.md`; the installed light sources' laser class is not in the clone and must be confirmed
  by a human, who raises the package to R3 if needed.
- The repository has no licence file (`NOASSERTION`): the card says `publish_review: required`, and the package is not
  published or merged into a published tree before the owner decides.
- `check-report.json` is regenerated by every gate run and is not part of the package.
