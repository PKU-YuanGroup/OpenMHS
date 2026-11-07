# Facts and tags for gh.zhinst/zhinst-qcodes

Every fact cites the pinned clone at commit `042dd17a5bf492cc4c573e465b2bc399e68d3203`.
`upstream_code` refs name `path/in/clone:LINE`, or a bounded range where the statement
spans adjacent lines. The paths below are from the clone root:

- `PQSC.py` = `src/zhinst/qcodes/driver/devices/pqsc.py`
- `base.py` = `src/zhinst/qcodes/driver/devices/base.py`
- `device_creator.py` = `src/zhinst/qcodes/device_creator.py`

The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

Tags: `qcodes`, `zhinst`, `labone`, `pqsc`, `trigger-distributor`, `zsync`.

## Facts

| fact | source | ref |
|---|---|---|
| `PQSC` is the QCoDeS driver class for the Zurich Instruments PQSC. | upstream_code | PQSC.py:10-11 |
| `run()` starts sending out triggers and activates trigger generation over the ZSync ports. | upstream_code | PQSC.py:18-30 |
| `arm()` configures the execution engine and clears the register bank; `repetitions` and `holdoff` optionally set the number of triggers and the time between repeated triggers, and the hold-off has a minimum value and a granularity of 100 ns. | upstream_code | PQSC.py:149-181 |
| `arm_and_run()` combines arm and run and synchronizes between the device and the data server after arming and running. | upstream_code | PQSC.py:32-50 |
| `stop()` is documented to stop the trigger generation; `deep` (default True) performs a synchronization between the device and the data server after the disable, and the call forwards to the toolkit object. | upstream_code | PQSC.py:52-61 |
| A deep operation on a node blocks until the device has acknowledged it and returns the acknowledged value. | upstream_code | src/zhinst/qcodes/qcodes_adaptions.py:279-282 |
| zhinst-qcodes requires zhinst-toolkit>=1.4.0 and qcodes>=0.35.0. | upstream_code | pyproject.toml:22-27 |
| `wait_done()` waits until trigger generation and feedback processing is done, bounded by `timeout` in seconds, and raises `TimeoutError` when the sequence is not done before it. | upstream_code | PQSC.py:63-76 |
| `check_ref_clock()` checks whether the reference clock is locked successfully, bounded by `timeout` in seconds. | upstream_code | PQSC.py:78-93 |
| `get_idn()` returns the vendor, model, serial and firmware of the connected device. | upstream_code | base.py:48-55 |
| `factory_reset()` loads the factory default settings. | upstream_code | base.py:60-68 |
| `get_streamingnodes()` returns the streaming nodes available on the device. | upstream_code | base.py:88-90 |
| `set_transaction()` returns the toolkit transaction context manager that bundles node set commands; it is not a value setter. | upstream_code | base.py:92-112 |
| `serial` and `device_type` are properties of the instrument. | upstream_code | base.py:114-122 |
| The device-creator `PQSC` constructor creates a `ZISession` for host and port and connects the serial with `connect_device(serial, interface=interface)`. | upstream_code | device_creator.py:255-276 |

Limits: none are sourced from the clone. The optional `repetitions` and `holdoff`
arguments of `arm`/`arm_and_run` have no stated bounds (only a minimum value and a
granularity of 100 ns for the hold-off), and the `wait_done` timeout is a deployment
wait bound. The package therefore leaves the trigger count and hold-off to the
device configuration and marks the wait-done timeout
`Limit.operator_required(...)`; `site-limits.example.json` shows how a site fills it.

## Scope and deviation from the card

The card names the `QcodesDriver` family helper. That helper binds explicit
`self.<name> = Parameter(...)` assignments. In this repository
`ZIBaseInstrument.__init__` calls `init_nodetree` (`base.py:46`), which creates the
node Parameters in a loop from the connected device's LabOne node tree
(`src/zhinst/qcodes/qcodes_adaptions.py:772`). There is no explicit Parameter
assignment to cite, so the source proof of `QcodesDriver` cannot bind any field.
This package is a direct `Driver` over the card's entry class
`zhinst.qcodes.driver.devices.pqsc:PQSC`.

Served:

| field or action | access | unit | note |
|---|---|---|---|
| `device_type` | read | (string) | the upstream property |
| `serial` | read | (string) | the upstream property |
| `firmware` | read | (string) | `str(get_idn()["firmware"])`: the `system/fwrevision` node value as text (model review) |
| `streaming_nodes` | read | (string array) | the text form of each entry of `get_streamingnodes()`, whose entry type the clone does not show (model review) |
| `ref_clock_locked` | read | (boolean) | `check_ref_clock()`, with a 1 s read timeout instead of the upstream 30 s default |
| `x-cap.zhinst.pqsc_trigger.v1` | invoke | | `arm`, `run`, `arm_and_run`, `stop`, `factory_reset`; an optional `deep` flag is the synchronization flag of the upstream methods |
| `x-cap.zhinst.pqsc_wait_done.v1` | invoke | | `wait_done()` with an operator-bounded `timeout` |

NOT COVERED, each for a reason in the source:

- `set_transaction` (`base.py:92-112`) is a context manager for bundling node sets,
  not a device value or an action. The runtime has no transaction-shaped binding.
- `repetitions` and `holdoff` of `arm`/`arm_and_run` (`PQSC.py:44-46,175-177`): no
  source states their bounds. The package calls the methods without them, which the
  upstream documents as "not changed" (`PQSC.py:160-161,174-175`); an operator
  configures them in LabOne.
- `check_zsync_connection` and `find_zsync_worker_port` (`PQSC.py:95-147`) need a
  concrete ZSync port list or a toolkit instrument object, which this device-level
  package does not own; a wrong guessed port number would be a fabricated fact.
- The LabOne node-tree Parameters and their units: `init_nodetree` creates them from
  the connected device's node tree (`qcodes_adaptions.py:772`), not from a source
  line with a fixed name and range, so this package cannot cite a bound per node.

## Safety

The selected device is a trigger-generation device. The served operations only
enable, clear, or stop trigger generation and read identity and lock status; the
package writes no analog output, heater, laser, motion or high voltage. The risk is
R1, the card's floor. The native stop is `PQSC.stop(deep=True)` since the model
review (the author's `deep=False` returned before the documented synchronization,
so a completed e-stop proved only that the request was handed to the session): the
upstream method is documented to disable trigger generation and, with `deep`, to
synchronize the device and the data server after the disable (`PQSC.py:52-61`); the
clone documents a deep node operation as blocking until the device has acknowledged
it (`qcodes_adaptions.py:279-282`). The method forwards to the zhinst-toolkit object
(`PQSC.py:61`), which is not in the clone (`zhinst-toolkit>=1.4.0`, unpinned,
`pyproject.toml:22-27`), so the stop's effect is documented here, not proven from
code. A deep stop that outlasts the runtime's e-stop budget, or raises, is reported
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held and retried in the background.
The runtime latches the e-stop before it calls this method, so later actions are
refused until an operator reset. The stop does not call `factory_reset`; the device
configuration and the connected instruments are left as they were. It stops the
PQSC's trigger generation, not the connected instruments' own acquisition loops or
sequences. Whether the LabOne session tolerates the e-stop's call while another
thread waits in `wait_done` or a deep `arm`/`run` is not shown by the clone.

No physical emergency-stop reference is claimed: the clone documents no independent
hardware stop input, and none is invented. The package is model-authored and
unreviewed (`reviewed_by` is null); it has run on the fake backend only.

## Fake fidelity

`fake.py` is an analytic stand-in, not a recording. It implements only the upstream
class methods and properties this driver calls, keeps canned private state (each
value marked `# placeholder`) and records calls in `_calls`. It does not open a
LabOne session, does not read the node tree, does not model ZSync ports, trigger
counts, hold-off timing, feedback processing or the real reference-clock lock, and
`wait_done` returns immediately instead of waiting for a trigger sequence. A first
supervised hardware run must verify the identity, the streaming-node list, the
reference-clock state and the arm/run/stop sequence against the instrument.

## Hardware backend

`native.py` imports zhinst-qcodes only when an operator loads the hardware backend,
with the serial and the data-server host as explicit options. The selected class has
no session-opening constructor of its own; the factory constructs the upstream
subclass `zhinst.qcodes.device_creator:PQSC`, whose constructor creates the
`ZISession` and calls `connect_device` (`device_creator.py:255-276`). The returned
object is a `pqsc:PQSC` instance. Nothing was run: the package has never opened a
LabOne session.
