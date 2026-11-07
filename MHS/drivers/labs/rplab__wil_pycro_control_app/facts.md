# Facts and tags for gh.rplab/wil_pycro_control_app

Every fact cites its source at commit `dc2f18836064c0e2391d96f0d72734e2a24764f8`.  The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver,
not from this page.

| fact | source | ref |
|---|---|---|
| The XY stage and focus device labels are read from the Micro-Manager core when stage.py is imported, beside the hard-coded ASI labels ASI-XYStage and XStage | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:10-14 |
| send_serial_command_to_stage sends a serial command to the ASI Tiger console only after core.wait_for_device(XY_STAGE_NAME) returns | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:51-57 |
| The X and Z stages are swapped, so the X-axis speed is set with the Z-axis SPEED command | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:68-71 |
| set_x_position takes x_pos in micrometres, waits for the XY stage, sets the default X speed and sends M Z=<int(x_pos)*TO_TENTHS>, the ASI MOVE command in tenths of microns | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:217-227 |
| set_y_position takes y_pos in micrometres, waits for the XY stage, sets the default Y speed and sends M Y=<int(y_pos)*TO_TENTHS> | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:230-239 |
| set_z_position takes z_pos in micrometres, waits for the Z stage, sets the default Z speed and passes z_pos unchanged to core.set_position(Z_STAGE_NAME, z_pos) | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:251-260 |
| get_x_position, get_y_position and get_z_position wait for their stage and return the core position truncated to int | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:263-293 |
| move_stage moves Z before XY when the current X is greater than the target X, and XY before Z otherwise; its comment says this keeps capillaries from hitting the objective and that the conditions should match the geometry of the holder | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:191-214 |
| wait_for_xy_stage and wait_for_z_stage block on the Micro-Manager core until the stage is not busy | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:39-49 |
| reset_stage sends RESET through send_serial_command_to_stage; its docstring says RESET resets the current flash memory of the Tiger console, most notably the origin (to its current position) and the joystick settings, and marks the function DEPRECATED | upstream_code | WIL_Pycro_Control_App/hardware/stage.py:321-334 |
| general_exception_handle runs a hardware function up to two times, logging each exception; after the second failure it prints a message and raises GeneralHardwareException | upstream_code | WIL_Pycro_Control_App/hardware/exceptions_handle.py:25-42 |
| Importing the hardware package sets the camera to its default mode and initializes the PLC state, suppressing GeneralHardwareException | upstream_code | WIL_Pycro_Control_App/hardware/__init__.py:5-11 |
| default_mode stops sequence acquisition, turns live mode off and sets the camera trigger mode, acquire mode and exposure | upstream_code | WIL_Pycro_Control_App/hardware/camera.py:55-74 |
| init_plc_state programs the PLC circuit used in z-stack acquisition and lsrm, whose pulse is sent to the camera as an external trigger | upstream_code | WIL_Pycro_Control_App/hardware/plc.py:55-97 |
| utils.pycro constructs the pycromanager Studio and Core objects when it is imported | upstream_code | WIL_Pycro_Control_App/utils/pycro.py:25-26 |
| init_logger creates a logs directory in the current directory and calls logging.basicConfig with a DEBUG log file there | upstream_code | WIL_Pycro_Control_App/utils/init_logger.py:11-16 |
| _abort_acquisition, called when an acquisition is aborted or fails, stops sequence acquisition, clears the circular buffer, sets the default camera properties and resets the joystick | upstream_code | WIL_Pycro_Control_App/acquisition/acquisition_class.py:182-196 |

Limits: X, Y, Z travel and the focus target are `Limit.operator_required`.  No text file of the
clone states a stage travel: the XY stage and focus device names come from the Micro-Manager core
(`WIL_Pycro_Control_App/hardware/stage.py:10-14`), so the connected stage may be configured
differently.  `site-limits.example.json` shows an example-only operator overlay; until a site
supplies its own overlay, every position write and the focus target are refused
`MHS.SAFETY.LIMITS_UNSET`.  The writes move one axis each and do not use `move_stage`, whose
Z/XY ordering keeps capillaries from hitting the objective (`stage.py:191-214`); a per-axis box
envelope does not reproduce that ordering.

Safety: the package is R1 hardware with no stop.  The clone has no stage halt; its only
stop-like function, `reset_stage`, sends the ASI RESET command, which resets the console's flash
memory, origin and joystick settings and is marked deprecated (`stage.py:321-334`), and it is sent
only after the XY stage stops being busy (`stage.py:51-57`).  The `@estop` sends nothing and
raises `MHS.SAFETY.SAFE_STATE_UNREACHED`; the latch refuses new commands while a move already sent
continues.  Nothing in this package can stop a move that was already sent, and the clone
documents no independent physical stop.

Tags: microscope, stage, focus, asi, micro-manager, imaging

## Model review (claude-opus-5-5, a model and not a human, 2026-11-05)

- The author bound `reset_stage` as the e-stop, so the gate passed with an e-stop that does not
  stop: RESET is not documented as a halt, waits for the XY stage first, so it cannot interrupt
  an XY move, and, by its docstring, resets the origin to the current position, so every later
  position and the operator envelope would refer to a shifted frame.  A failed e-stop is retried in the background until a reset (0.25 s doubling to
  5 s), which would have re-sent RESET each time.  The reviewer made the `@estop` send nothing
  and raise `SAFE_STATE_UNREACHED`, rewrote `safe_state`, and changed the e-stop test cases to
  expect that with the latch held and no RESET reaching the backend.  The gate now fails
  G6.ESTOP_FAILED and G8 SAFE-028, and the package is blocked (`NO_HARDWARE_FREE_PATH`).
- Facts corrected: the device-label fact no longer infers that the stage model is a deployment
  property (the serial path hard-codes the ASI labels); the X/Z swap is cited where the clone says
  it (`stage.py:68-71`), not on `set_x_position`.  Facts added: the serial path's XY wait, the
  upstream retry wrapper, the import-time effects of the hardware package (camera default mode,
  PLC programming, pycromanager construction, logging setup) and the upstream abort path, which
  stops camera acquisition and resets the joystick but sends no stage command.
- Every upstream hardware function prints to stdout when its second attempt fails
  (`exceptions_handle.py:39-42`), at import as well; that would corrupt an MHS server on stdio.
- The fake now keeps a Z target unchanged as `core.set_position` does (`stage.py:258`) and
  truncates only on read; a case checks a fractional focus target.
- Not covered, as the author noted: the camera entry symbol (`hardware/camera.py`); its snap
  waits for an image with no bound (`camera.py:127-128`) and image retrieval lives in
  `utils/pycro.py:317-324`.
- The clone has no LICENSE file (the card: NOASSERTION, publication review required).
