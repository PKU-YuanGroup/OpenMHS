# PyLabRobot liquid handlers: `PyLabRobotDriver`

`PyLabRobotDriver` (`mhs.driver.pylabrobot`) serves one PyLabRobot `LiquidHandler` front end, or an upstream object
that holds one, through a finite profile, `plr-liquid-handler-v1`. A package declares one immutable `PlrProfile`
and nothing else: every capability, schema and runtime map is generated, and the class may not define methods.
The runtime is the python-object bridge (`mhs.bridge.pylabrobot.PlrBridge`): every PyLabRobot coroutine runs on the
bridge's single event loop, inside its retained native execution (deadlines, cancellation, unknown outcomes and the
e-stop lanes are those of [PYTHON-NATIVE-RETENTION](../../changes/PYTHON-NATIVE-RETENTION.md)). No PyLabRobot code is
imported by the SDK, a fake or the gate; only a package's `native.py` (hardware) imports it, after a human review.

Exemplar: [`MHS/drivers/labs/oelemento__star-sim`](../../drivers/labs/oelemento__star-sim) (a simulated STARlet twin).

## When to use it

| The upstream is | Write |
|---|---|
| a PyLabRobot `LiquidHandler` (`lh.pick_up_tips`, `lh.aspirate`, `lh.dispense`, `lh.discard_tips` over a deck of named resources), directly or at an attribute of an upstream object | `PyLabRobotDriver` with a `PlrProfile` |
| another PyLabRobot machine (plate reader, incubator, scale, spectrophotometer, scanner) | a direct `Driver` or `PythonObjectDriver`; the PyLabRobot lifecycle below still applies |
| a class that only borrows PyLabRobot names (`aspirate(volume, location)`), a firmware protocol, or a remote service without a PyLabRobot front end | a direct `Driver`; say so in `RESULT.json` notes (`DEVIATION FROM THE CARD`) |

## The profile

```python
from mhs.driver import Limit, PlrLabware, PlrOperation, PlrProfile, PyLabRobotDriver


class StarSim(PyLabRobotDriver):
    device_id, device_kind, mode, risk = "star-sim", "lab.liquid_handler", "simulated", "R2"
    native = "star_sim.env:RobotEnv"
    backends = {"fake": ".fake:FakeRobotEnv"}
    safe_state = "..."
    plr_profile = PlrProfile(
        handler="lh", handler_ref="star_sim/env.py:60",
        setup="setup", setup_ref="star_sim/env.py:59", close="teardown", close_ref="star_sim/env.py:68",
        channels=8, channels_ref="star_sim/env.py:33",
        tip_tracking_ref="star_sim/lab.py:35", volume_tracking_ref="star_sim/lab.py:36",
        labware=(PlrLabware("tip_rack", "tip_rack", "star_sim/deck.py:47"),
                 PlrLabware("source_plate", "plate", "star_sim/deck.py:52")),
        operations={"x-cap.oelemento.transfer.v1": PlrOperation(
            "transfer", "star_sim/primitives.py:55-66",
            volume_limit=Limit(min=1, max=1000, source="upstream_code", ref="agent.py:53"))},
        well_pattern="^[A-H](?:[1-9]|1[0-2])$")
```

| Field | Rule | Gate G7 checks that the cited code shows |
|---|---|---|
| `handler`, `handler_ref` | attribute path from the backend object to the `LiquidHandler` (`""`: the object itself) | an assignment to the last name (`self.lh, ... = ...`) |
| `setup`, `setup_ref` | the coroutine that prepares the handler (`setup`); runs when the driver opens | a definition or call of the name |
| `close`, `close_ref` | the teardown (`stop`, `teardown`, `close`, `disconnect`); runs at close, never as a stop | a definition or call of the name |
| `channels`, `channels_ref` | the most channels one operation uses (1 to 96) | the integer literal |
| `tip_tracking_ref` | required by `transfer`/`mix`: the line that switches PyLabRobot tip tracking on | the call `set_tip_tracking(True)` |
| `volume_tracking_ref` | required by `tracked_volumes`: the line that switches volume tracking on | the call `set_volume_tracking(True)` |
| `labware` | `PlrLabware(name, kind, ref)`, `kind` `plate` or `tip_rack`; the finite allowlist an agent may name | the name as a call argument (`TipRack(name="tips")`), or a JSON `"name"` field |
| `operations` | `{x-cap id: PlrOperation(kind, ref, volume_limit=None)}`, `kind` `transfer`, `mix` or `tracked_volumes`; `ref` spans at most 40 lines | a call of every PyLabRobot method of the kind (`.aspirate(...)`...), for `transfer`/`mix` made on the handler (`env.lh.aspirate(...)`) |
| `volume_limit` | the default per-channel volume bound of `transfer`/`mix`; a `PlrOperation(volume_limit=...)` replaces it so each operation cites its own line. `Limit(min=, max=, source=, ref=)` on a line that shows both numbers (G4), or `Limit.operator_required(reason)` | (G4) |
| `cycles_limit` | the `mix` cycle bound, sourced or `Limit.operator_required` | (G4) |
| `well_pattern` | anchored regex of well and tip-spot names (default `A1` to `P24`) | |
| `stop` | `PlrStop(native, ref, description)`: a source-backed native stop, or `None` | a definition or call of the stop's name |
| `timeout_ms`, `setup_timeout_ms` | bounds of one operation and of `setup` (default 120000 ms each) | |

Every reference except an operation's names exactly one line. In a Python file the gate reads the cited code with
`ast`, so a comment, a docstring or a wide span that merely mentions a name does not count. A G7 finding is
`G7.PLR_REF` (the file or line does not exist, a one-line reference is a span, or an operation span exceeds 40
lines) or `G7.PLR_SOURCE` (the cited code does not show what the profile claims). The generic G7 check of the fake
against `native` runs as for any family. Read-only `parameters`
with `reads` getters on the backend object are allowed (the exemplar reads `tips.remaining`); writable parameters,
`commands`, `actions`, `writes`, `safety_bindings`, `native_setup` and `native_close` are generated and refused.

## Generated operations

Every operation is an `x-cap` extension (list it in `RESULT.json` `catalogue_requests`); the catalogue's single-well
`cap.fluid.*` classes need a stateful gate prerequisite profile this helper does not have.

| Kind | Steps (each awaited on the bridge loop) | Inputs | Output | Risk |
|---|---|---|---|---|
| `transfer` | `pick_up_tips` (fresh tips) -> `aspirate` -> `dispense` -> `discard_tips` | `tip_rack`, `source`, `source_wells[]`, `target`, `target_wells[]` (same count, at most `channels`), `volume` (uL per channel) | `transferred_volume`, `channels`, `tips` | R2 |
| `mix` | `pick_up_tips` -> (`aspirate` -> `dispense`) x `cycles` on the same wells -> `discard_tips` | `tip_rack`, `labware`, `wells[]`, `volume`, `cycles` | `mixed_volume`, `cycles`, `channels`, `tips` | R2 |
| `tracked_volumes` | `get_item(well).tracker.get_used_volume()` for each well | `labware`, `wells[]` | `volumes[]` (uL) | R0, verb `read` |

- **Fresh tips.** Like a cursor-based tip manager, the bridge takes the first run of adjacent rows (one per
  channel, channel 0 first) that all hold a tip, within one column of the named rack, scanning the columns in
  order (`num_items_x`, `num_items_y`, `get_item(...).tracker.has_tip`). After the pick-up it checks that those
  spots no longer report a tip; if tip tracking did not record it, the operation fails `MHS.DEVICE.FAULTED`.
- **Channel order and layout.** Well *i* is served by channel *i* (`use_channels=[0..n-1]`). The channels of a
  gantry head share one X position and run from the back row to the front, so the bridge accepts only wells in one
  column with strictly increasing rows and no well twice, for each well list of a call (gaps are allowed: `A1`,
  `C1`); anything else fails `MHS.CAPABILITY.INPUT_INVALID` before any native call. A device that can reach other
  layouts is not covered. Channel spacing and labware geometry are still the device's and PyLabRobot's to check.
- **Labware** is resolved with `handler.deck.get_resource(name)` and `get_item(identifier)`, only for declared
  names; a name of the wrong kind is refused by the input schema before admission.
- **Failures.** PyLabRobot's front end checks tips and tracked volumes before it calls its backend (the vendored
  copy at `labs/aicell-lab/hamilton-control`, `pylabrobot/liquid_handling/liquid_handler.py`, checks before
  `self.backend.aspirate(...)`), and its STAR backend reports firmware errors as `ChannelizedError`
  (`pylabrobot/liquid_handling/backends/hamilton/STAR.py`). So:
  - a front-end bookkeeping error (`NoTipError`, `HasTipError`, `TooLittleLiquidError`, `TooLittleVolumeError`,
    `CrossContaminationError`) means the step sent nothing: `failed` `MHS.DEVICE.PRECONDITION_UNMET` with
    `details.precondition` (`tip_mounted`, `channel_free`, `liquid_present`, `room_available`,
    `uncontaminated_tip`) and `details.completed_steps`;
  - any other error raised by a step (a timeout, an I/O error, a firmware error, an unexpected exception), also in
    the first step, may have reached the device: `unknown` `MHS.OUTCOME.UNKNOWN` with `details.step` and
    `details.completed_steps` and no native text. The python-object bridge then fences new effects
    (`MHS.DEVICE.NOT_READY`) until a confirmed native stop and an operator reset;
  - an error while resolving labware, before any step, keeps the python-object bridge's redacted
    `MHS.ADAPTER.SHIM_FAILED`; a request deadline that expires mid-step is `unknown` and fences the same way.
  Unequal or badly laid-out well lists are `failed` `MHS.CAPABILITY.INPUT_INVALID` before any native call.
- **No cleanup motion, and the recovery.** A failed or interrupted operation does not discard tips or return
  liquid: tips stay mounted and liquid stays where the last completed step left it. This is deliberate: a cleanup
  step would move the device after a failure or an e-stop, which nobody admitted. (Upstream protocol code often
  discards tips in a `finally` block; the helper does not.) The next `transfer` or `mix` then fails
  `PRECONDITION_UNMET` `channel_free`, and v1 has no operation that clears the head. Recovery is an operator's:
  clear the head at the device (or, for a simulated twin, restart the endpoint, which rebuilds the deck) and, for
  a hardware package, follow its reviewed restart procedure.
- **Tracked volumes** are PyLabRobot bookkeeping (declared or simulated volumes moved by the operations), never a
  liquid-level measurement.

## Safety

- **Risk.** Pipetting and gantry motion are R2 in the MHS-004 hazard table; the composite operations carry R2 in
  every mode. A hardware package declares `risk = "R2"` (or higher if the device has a further hazard).
- **The stop.** PyLabRobot's `Machine.stop()` closes the backend; it does not stop a running command, so the helper
  refuses it (and any `teardown`, `close`, `disconnect`, `shutdown`) as `plr_profile.stop`. A `PlrStop` must name a
  real native stop that a pinned line of the clone shows, and its `description` must say what it does not stop
  (for example, a firmware halt that discards queued commands while the sequence in progress completes). Without
  a `PlrStop`: the e-stop is the runtime's software latch, the hardware backend is refused before its factory runs
  (`MHS.DEVICE.NOT_READY`), and gate G3 refuses a hardware package (`G3.NO_ESTOP`). With one, a hardware R2 package
  still needs `estop_physical_ref` (SAFE-045): the helper binds no safe-state action. The loader refuses the
  hardware backend of an unreviewed model-written R2/R3 package in every case.
- **A bound stop may run more than once per e-stop.** It runs at the e-stop, on the bridge loop, even while a step
  is in flight (that step is not interrupted by the bridge and may complete afterwards). While native work is
  unsettled the attempt cannot confirm: the e-stop receipt is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` with
  `retrying: true`, and the server retries the stop in the background (after 0.25 s, doubling up to 5 s, SAFE-040)
  until the work has settled and a call confirms. A `PlrStop` must therefore be safe to send repeatedly; the unit
  tests pin two calls for one interrupted step.
- **The step fence.** Before each PyLabRobot step the bridge checks that no e-stop engaged (of the driver or of
  the bridge), the operation's cancel event is clear (the server sets it under its lock on an e-stop, a session
  close or an accepted cancellation, also when no native stop exists) and the bridge is not closing. A step that
  would start after any of these is never sent. A step already in progress is not interrupted by the bridge: only
  a native stop can act on it.
- **E-stop during an operation, and reset.** The latch engages, the operation ends `cancelled` and no later step
  is sent. With no bound stop the e-stop receipt is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED`
  (`bridge_reports_unsafe`): the in-flight step is honestly not confirmed stopped. On a device that declares a
  re-enable (CORE-086) the reason is `command_in_flight` while the operation's native work is still in flight; the
  stop path then runs again once it settled, and only that run confirms the stop. A reset is refused while the
  operation's native work runs (`MHS.SAFETY.RESET_REFUSED`). What follows depends on which ends first, as for every
  python-object bridge: usually the waiting caller observes the cancellation while the step is still in flight
  (it checks every 10 ms); that execution then stays uncertain, so new effects are refused and a reset needs a fresh
  confirmed native stop. With no bound stop only an endpoint restart recovers; with a bound stop the background
  retry confirms once the step has ended, and an operator reset is then accepted. If instead the step ended before
  the caller looked, the operation stops at the next step boundary, nothing is uncertain, and an operator reset is
  accepted once the operation has ended. Either way the tips and liquid stay where the last completed step left
  them (see the recovery above).
- **Setup moves hardware.** On a hardware backend, PyLabRobot `setup()` initializes the instrument (channels,
  arms); it runs when the driver opens, before any capability call. A reviewer decides whether that is acceptable.

## Fakes

`mhs.testing.pylabrobot` is a deterministic model of the front-end bookkeeping (`FakeLiquidHandler`, `FakeDeck`,
`FakePlate`, `FakeTipRack`, `well_names`): it enforces `setup()` first, tip presence per channel and spot, and
tracked liquid and free volume, with error names mirroring PyLabRobot's. A package fake keeps the upstream object's
shape (only methods the `native` class has, gate G7) and composes the model; every capacity and starting volume is
a placeholder. The gate's conformance suite repeats one valid payload on one endpoint, so give each operation an
`alternate` payload in `fixtures/conformance.json`; fresh-tip selection makes repeated payloads succeed until the
rack is empty, and a fake source plate needs placeholder liquid for a stateless transfer to complete (say so in the
notes and the fidelity `gaps` of a simulated package).

## Tool size

Each generated tool must stay within 2048 bytes (G8). The plate names appear twice in `transfer` (source and
target): ten plates with names of about 24 characters still fit; a larger deck fails `G8.TOOL_SIZE`. Declare only
the labware an agent needs.

## Not covered

A recovery operation that discards mounted tips (it would need its own review of when motion after a failure is
acceptable); explicit cancellation of a running operation (the operations declare no cancellation, so the server
refuses `mhs.operations.cancel` for them, see OPERATION-CANCELLABILITY; an e-stop or a session close stops them at
the next step boundary); single-step aspirate, dispense, tip pick-up and drop as separate capabilities (their
stateful preconditions need a reviewed gate prerequisite profile); the 96-head and 384-head operations; resource
moves (iSWAP, CoRe gripper); flow rates, offsets, liquid heights, blow-out air and liquid classes; troughs and other
non-itemized containers; operator-defined decks (labware names that no pinned line states); well layouts other than
one column per call; tip return instead of discard; any PyLabRobot machine other than `LiquidHandler`. Each needs its
own design and source evidence.
