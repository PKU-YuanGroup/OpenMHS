# Facts and tags for gh.nsls2/pamila

Every fact cites the pinned clone at commit `62a439b6be7cb72353575183a7fea26b45a35394`: `vendor_doc` (a text file
of the clone such as `README.md` or `docs/*.md`) or `upstream_code` (`path/in/clone.py:LINE`, including the clone's
`src/` layout). The same facts are written into `driver.py`; the reference file is generated from the driver, not
from this page.

Tags: `pamila`, `bluesky`, `ophyd`, `middle-layer`, `epics`, `sensor`, `read-only-list`.

## Facts

| fact | source | ref |
|---|---|---|
| `MiddleLayerVariableListBase` is the common base of the read-only and writable variable lists. | upstream_code | `src/pamila/middle_layer/var_list.py:116` |
| `MiddleLayerVariableListRO` sets `read_only` to `True` and is constructed from a `MiddleLayerVariableListROSpec`. | upstream_code | `src/pamila/middle_layer/var_list.py:569-574` |
| `MiddleLayerVariableListRO.put`, `set`, `set_and_wait` and `change_set_wait_method` raise `ReadOnlyError`. | upstream_code | `src/pamila/middle_layer/var_list.py:582-592` |
| `get_all_mlv_count` returns the number of all member variables. | upstream_code | `src/pamila/middle_layer/var_list.py:460-461` |
| `get_all_mlv_names` returns the names of all member variables. | upstream_code | `src/pamila/middle_layer/var_list.py:463-464` |
| `get_mlv_names` returns a copy of the enabled variable names. | upstream_code | `src/pamila/middle_layer/var_list.py:466-467` |
| `get_enabled_mlvs` refreshes the enabled status and returns the enabled member variables. | upstream_code | `src/pamila/middle_layer/var_list.py:261-263` |
| `get_enabled_status` returns a deep copy of the enabled-status list. | upstream_code | `src/pamila/middle_layer/var_list.py:319-320` |
| `put_enabled_status` requires one status per member, returns when unchanged, and otherwise replaces the status list and reinitializes the enabled members. | upstream_code | `src/pamila/middle_layer/var_list.py:322-336` |
| `get` reads every enabled member variable and tries to build one quantity array, leaving the list when the dimensions differ. | upstream_code | `src/pamila/middle_layer/var_list.py:352-428` |
| `enable_parallel_get` and `disable_parallel_get` set the list flag and propagate it to the member PV objects. | upstream_code | `src/pamila/middle_layer/var_list.py:170-176` |
| The list starts with one `True` enabled status per member variable. | upstream_code | `src/pamila/middle_layer/var_list.py:144` |
| The read-only list spec carries the member variables and a `parallel_get_enabled` flag. | upstream_code | `src/pamila/middle_layer/var_list.py:105-113` |
| A machine unit conversion is built from the `repr_units` of the deployment element definition. | upstream_code | `src/pamila/facility_configs/loader.py:96-103` |
| A PAMILA device spec carries its components and its get and put action specs. | upstream_code | `src/pamila/device/base.py:32-40` |
| The PAMILA machine module requires the `PAMILA_FACILITY` environment variable at import. | upstream_code | `src/pamila/machine.py:8-13` |
| The MLVL example loads a machine configuration from `examples/demo_generated/<facility>`. | upstream_code | `examples/nb_gen/03_mlvl.py:23` |

## Scope

The selected entry is `pamila.middle_layer.var_list:MiddleLayerVariableListRO`, a concrete class. It is a named,
ordered collection of middle-layer variables. The driver exposes:

- reads: member count, all member names, enabled member names, the enabled-status list, the enabled values and their
  representation units;
- `cap.sensing.read.v1`: the enabled values, optionally selected by member name.

Model review: the author's version also served the local enabled-status list through `put_enabled_status` as
`cap.device.configure.v1` and the list's parallel-get switch (`var_list.py:170-176`) as
`x-cap.nsls2.enable_parallel_get.v1` and `x-cap.nsls2.disable_parallel_get.v1`, and bound `disable_parallel_get` as
the e-stop to meet the card's R1 floor. The switch only decides whether `get` first starts the member PV reads in
parallel (`var_list.py:356-371`); it stops nothing, so it is not a stop. The review removed the write, both actions
and the e-stop and made the package R0 (data only). The card's R1 floor comes from the scan's
`cap.device.configure.v1`, which this read-only class cannot serve; with a capability-class override to
`cap.sensing.read.v1` the package passes the gate (checked on a scratch copy of the card), and until then it fails
only G3.RISK_FLOOR.

The card's helper is `OphydDriver`, but the selected class is not an ophyd Device and declares no `Component`
signals; the OphydDriver grammar cannot bind it. The package is a direct `Driver` over the entry class
(`RESULT.json` records the card deviation). The card's suggested `set_and_wait` methods are not exposed: on this
read-only class they raise `ReadOnlyError` (`var_list.py:588-589`).

The source names the list's member variables and their units in the deployment's facility configuration
(`facility_configs/loader.py:96-103`, `device/base.py:32-40`). The clone's examples use
`examples/demo_generated/<facility>` (`examples/nb_gen/03_mlvl.py:23`), but that directory is not present in the
clone; the operator generates it. The package therefore declares no fixed member names, PV names, units or numeric
bounds. `value_units` reports the unit that each upstream quantity carries.

## Not covered

- The writable `MiddleLayerVariable.set_and_wait` and `MiddleLayerVariableStatusList.set_and_wait` paths are not
  served. They need a pint quantity in the unit of a configured device representation, and the selected read-only
  class refuses them. The package does not claim a setpoint capability or a physical stop it cannot reach.
- The upstream PyAT simulator is not used. `sim_interface/pyat.py` needs PyAT and a generated facility configuration;
  no generated configuration is shipped. The fake is an in-memory API-preserving stand-in, not a recording.
- No generated facility configuration, PV name, engineering unit or numeric setpoint bound is asserted as a fact;
  all of them are deployment data.

## Fake and hardware backends

`fake.py` implements the upstream method surface over three placeholder member variables (`PLACEHOLDER_MLV_A`,
`PLACEHOLDER_MLV_B`, `PLACEHOLDER_MLV_C`) with placeholder values and units. Those names, values and units are test
data, not Facts, Limits or deployment defaults.

`native.py` is the hardware factory. It sets `PAMILA_FACILITY` before importing `pamila`, loads the operator's
facility configuration through `load_machine`, selects an existing read-only list by name or builds one from the
given read-only member names, and waits once for its connection with the operator-given timeout. It was never
imported or run: no hardware was attached and no facility configuration was generated. The factory sets the
process-wide `PAMILA_FACILITY` variable and PAMILA's process-wide machine mode (`LIVE` or `SIMULATOR`), so it needs a
dedicated interpreter.

## Safety

The selected class is read-only: it refuses `put`, `set` and `set_and_wait` with `ReadOnlyError`
(`var_list.py:582-592`). Since the model review the package serves reads only and declares risk R0, no write, no
native stop and no `estop_physical_ref`: an e-stop latches the endpoint against further commands and stops nothing
physical (on the hardware backend the runtime reports it `SAFE_STATE_UNREACHED`, `no_stop_path`, because only the
software latch exists). The machine setpoints of the accelerator are written by the writable middle-layer classes,
which the clone gives no stop for; they stay out of scope.

## Licence

The card and `driver.lock.json` record BSD-3-Clause, the registry's reading of the clone's `LICENSE` file. No
additional licence review was performed by this model-written package.
