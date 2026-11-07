# Facts and tags for gh.janelia-python/zaber_device_python

Every fact cites its source at commit `2fec6746359b35acd4cf0c121cff03da8ae0a062`: `upstream_code` for code or a
comment of the clone, `vendor_doc` for documentation text. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ZaberStage maps one actuator alias per device to each of the x, y and z axes; set_x_axis, set_y_axis and set_z_axis select the actuator by its alias | upstream_code | zaber_device/zaber_device.py:826-849 |
| get_positions returns each configured axis position in microsteps multiplied by that axis's microstep size | upstream_code | zaber_device/zaber_device.py:922-937 |
| move_x_absolute, move_y_absolute and move_z_absolute divide the requested position by the axis's microstep size before sending it to the actuator | upstream_code | zaber_device/zaber_device.py:989-1012 |
| The microstep size is set on the stage object with set_x_microstep_size, set_y_microstep_size and set_z_microstep_size; the stage does not read it from the device | upstream_code | zaber_device/zaber_device.py:1128-1156 |
| The travel is set on the stage object with set_x_travel, set_y_travel and set_z_travel; the stage does not read it from the device | upstream_code | zaber_device/zaber_device.py:1158-1185 |
| The README tells the operator to look up the microstep size and the travel range of the connected actuator model on the Zaber website and set them on the stage | vendor_doc | README.org:171-231 |
| ZaberStage.home calls home on every device in the chain | upstream_code | zaber_device/zaber_device.py:959-962 |
| ZaberStage.stop calls stop on every device in the chain | upstream_code | zaber_device/zaber_device.py:984-987 |
| ZaberDevice.stop sends command 23, which stops the actuator by preempting a move | upstream_code | zaber_device/zaber_device.py:368-372 |
| Stored-position addresses are bounded by POSITION_ADDRESS_MIN = 0 and POSITION_ADDRESS_MAX = 15 | upstream_code | zaber_device/zaber_device.py:35-36 |
| get_actuator_ids returns the actuator id reported by each device for the configured axes | upstream_code | zaber_device/zaber_device.py:1108-1126 |
| ZaberDevice.homed reads the home-status bit (1 << 7) of each actuator mode | upstream_code | zaber_device/zaber_device.py:524-530 |
| ZaberStage.homed selects the configured axes from the device home status | upstream_code | zaber_device/zaber_device.py:964-982 |

Limits:

* Stored-position addresses are bounded to 0 to 15 in `driver.py` from `POSITION_ADDRESS_MIN` and
  `POSITION_ADDRESS_MAX` (`zaber_device/zaber_device.py:35-36`).
* The microstep size and travel of each axis are `Limit.operator_required`: the clone does not read either from the
  device, and the README sends the operator to the Zaber website for the connected actuator model
  (`README.org:171-231`). Until the site overlay supplies them, every write is refused
  `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example overlay, not a claim about any stage.
* Absolute and relative move inputs are `Limit.operator_required` for the same reason: the travel of this stage is
  set by the operator, not stated in the clone.

Stage unit: the upstream stage has no fixed physical unit. The microstep size the operator sets defines the unit of
positions, travel and moves; the README's `0.49609375e-3` makes them millimetres for a T-LSR450B
(`README.org:183-205`). The driver declares the dimensionless UCUM unit `1` and the operator overlay supplies the
bounds in the same unit.

Safety: the e-stop (`@estop`, native `stop`) and the safe-state action `cap.motion.stop.v1` both call
`ZaberStage.stop`, which sends command 23 to every device in the chain. No line of the clone documents an independent
hardware e-stop, so `estop_physical_ref` is not set. The driver is R1.

Tags: zaber, linear-stage, motion, serial
