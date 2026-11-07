# Facts and tags for gh.aicell-lab/hamilton-control

Every fact cites its source at commit `a857bd9a1f91d140a90d6a2cd29b01c50b23106a`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The driver's `facts` list is the machine-readable copy; this
page mirrors it.

| fact | source | ref |
|---|---|---|
| The project controls the Hamilton Vantage liquid handler using PyLabRobot on a Raspberry Pi 5 | vendor_doc | README.md:3 |
| try.py builds a PyLabRobot LiquidHandler over the Vantage backend and a VantageDeck | upstream_code | try.py:4-5 |
| The clone contains a concrete PyLabRobot Incubator front end | upstream_code | pylabrobot/incubators/incubator.py:23 |
| Incubator.setup awaits the backend setup and then registers the racks | upstream_code | pylabrobot/incubators/incubator.py:62-64 |
| Incubator.get_num_free_sites sums the free sites of every rack | upstream_code | pylabrobot/incubators/incubator.py:66-67 |
| Incubator.fetch_plate_to_loading_tray fetches the named plate and moves it to the loading tray | upstream_code | pylabrobot/incubators/incubator.py:76-85 |
| Incubator.take_in_plate moves the loading-tray plate into a chosen site | upstream_code | pylabrobot/incubators/incubator.py:115-133 |
| Incubator.set_temperature delegates to the backend set_temperature | upstream_code | pylabrobot/incubators/incubator.py:135-136 |
| Incubator.get_temperature delegates to the backend get_temperature | upstream_code | pylabrobot/incubators/incubator.py:139-140 |
| Incubator.open_door and close_door delegate to the backend | upstream_code | pylabrobot/incubators/incubator.py:142-146 |
| Incubator.start_shaking takes a frequency and delegates to the backend | upstream_code | pylabrobot/incubators/incubator.py:148-149 |
| Incubator.stop_shaking delegates to the backend stop_shaking | upstream_code | pylabrobot/incubators/incubator.py:151-152 |
| The Cytomat backend's set_temperature raises NotImplementedError | upstream_code | pylabrobot/incubators/cytomat/cytomat.py:370-371 |
| Cytomat.get_temperature returns the incubation query's actual value | upstream_code | pylabrobot/incubators/cytomat/cytomat.py:359-360 |
| Machine.stop calls backend.stop and is the lifecycle teardown, not a motion stop | upstream_code | pylabrobot/machines/machine.py:67-70 |
| HamiltonLiquidHandler.stop fails every waiting task and clears the queue; it writes no stop command | upstream_code | pylabrobot/liquid_handling/backends/hamilton/base.py:98-102 |
| Vantage subclasses HamiltonLiquidHandler | upstream_code | pylabrobot/liquid_handling/backends/hamilton/vantage.py:342 |

Tags: `incubator`, `cytomat`, `pylabrobot`, `temperature`, `shaking`, `plate-transfer`, `hamilton-control`.

## Limits

The clone states no temperature or shaking range for a deployed incubator. `cap.thermal.setpoint.v1
target_temperature` and `x-cap.aicell-lab.start_shaking.v1 frequency` are therefore `Limit.operator_required`; every
call is refused with `MHS.SAFETY.LIMITS_UNSET` until an operator overlay supplies the bounds. The example overlay in
`site-limits.example.json` is illustrative only, not a device fact.

## Safety and scope (model review, 2026-11-05)

The author's e-stop and `safe_state=True` action stopped the shaker and then called `options['safe_stop']`, a
"deployment-supplied independent power-cut relay" callable that no line of the clone shows; the fake made it a no-op,
so the SDK reported an achieved safe state for an invented stop. It is removed. The e-stop now sends
`Incubator.stop_shaking` (`pylabrobot/incubators/incubator.py:151-152`), the only stop-like call of the front end,
and then reports `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held; the shaker-stop action is an ordinary action.
No line of the clone stops a plate transfer, the door or temperature control, and `Machine.stop` is teardown.

The package is blocked. The repository's device is the Hamilton Vantage liquid handler (`README.md:3`, `try.py:4-5`);
its vendored backend has no stop command (`HamiltonLiquidHandler.stop` only fails waiting tasks,
`pylabrobot/liquid_handling/backends/hamilton/base.py:98-102`). The Incubator front end served here is vendored
PyLabRobot library code that no file of the repository outside the vendored copy uses. The served temperature setpoint
cannot work with the clone's only concrete incubator backend (`Cytomat.set_temperature` raises `NotImplementedError`,
`pylabrobot/incubators/cytomat/cytomat.py:370-371`), while the fake sets the temperature to the target at once.
