# Facts and tags for gh.czbiohub-sf/python-fish-sorter

Every fact cites the clone at commit `a8f2409fa6924b1aed83e1224c34a0528b5cb002`.  `vendor_doc` is
text documentation of the clone; `upstream_code` is code, a code comment or a shipped text
configuration of the clone.  The reference is generated from `driver.py`, not from this page.

| fact | source | ref |
|---|---|---|
| The hardware README lists CODESYS valve control code for use with Wago valve controllers among what the hardware directory includes | vendor_doc | hardware/README.md:3-5 |
| ValveController communicates with the Wago valve controller to actuate the pressure and vacuum valves; the Wago controller was programmed with CoDeSys to receive specific function codes | upstream_code | fish_sorter/hardware/valve_controller.py:7-11 |
| ValveController stores the config mapping it was given on self.config | upstream_code | fish_sorter/hardware/valve_controller.py:25 |
| ValveController._connect creates a ModbusTcpClient with the configured host and port, timeout=5 and retries=3 | upstream_code | fish_sorter/hardware/valve_controller.py:30-44 |
| read_register returns read_holding_registers of count registers at start_address + add_offset and re-raises any exception | upstream_code | fish_sorter/hardware/valve_controller.py:68-88 |
| write_register writes value to start_address + add_offset and returns the reply; on an exception it closes the client, reconnects and retries the same write once | upstream_code | fish_sorter/hardware/valve_controller.py:90-114 |
| The upstream valve test checks rr.isError() and ExceptionResponse after a read: a Modbus exception reply is not a Python exception but a valid Modbus message | upstream_code | fish_sorter/hardware/valve_test.py:80-96 |
| The upstream valve test writes a function code to 12288 + ADDRESS_OFFSET and reads the same register back | upstream_code | fish_sorter/hardware/valve_test.py:98-103 |
| The shipped pneumatic config sets start_address 12288 and the offsets draw time 0, expel time 2, function 4, function echo 6 and idle type 14 | upstream_code | fish_sorter/configs/hardware/pneumatic_config.json:9-17 |
| The shipped function codes are idle_atm 0, draw 2, expel 4, press_off 8, press_on 9, vac_on 16, vac_off 17 and func_idle 128 | upstream_code | fish_sorter/configs/hardware/pneumatic_config.json:18-28 |
| PickingPipette.connect creates a ZaberController unless one was passed, creates the ValveController and writes idle_atm to the func_idle_type register | upstream_code | fish_sorter/hardware/picking_pipette.py:72-79 |
| PickingPipette.idle ('Toggles to idle atmospheric pressure') writes func_idle to the function register | upstream_code | fish_sorter/hardware/picking_pipette.py:140-147 |
| PickingPipette.pressure(False) writes press_off and pressure(True) writes press_on | upstream_code | fish_sorter/hardware/picking_pipette.py:149-167 |
| PickingPipette.vacuum(False) writes vac_off and vacuum(True) writes vac_on | upstream_code | fish_sorter/hardware/picking_pipette.py:169-187 |
| PickingPipette.draw_time and expel_time write a time in ms to the draw-time and expel-time registers | upstream_code | fish_sorter/hardware/picking_pipette.py:189-211 |
| PickingPipette._pipette_wait sleeps in steps of max(0.05, t/3) and leaves its loop early when vc.read_register(address_offset) == 0; it writes nothing | upstream_code | fish_sorter/hardware/picking_pipette.py:213-229 |
| PickingPipette._valve_cmd writes the register and then calls _pipette_wait on the same offset | upstream_code | fish_sorter/hardware/picking_pipette.py:231-243 |
| PickingPipette.disconnect moves the pipette and homes x and y, then writes idle_atm to the func_idle_type register and closes both connections; it writes nothing to the function register | upstream_code | fish_sorter/hardware/picking_pipette.py:81-94 |
| pyproject.toml declares the licence 'BSD 3-Clause License, CERN Open Hardware Licence Version 2 - Weakly Reciprocal' | upstream_code | pyproject.toml:12 |

## The controller program (read from a binary file; no Fact cites it)

The repository ships the CoDeSys project of the valve controller,
`hardware/valve_control/FishSorterValveControl.pro` (CoDeSys 2.3, target "Wago 750-881").  It is a
binary file, so gate G4 cannot check a citation into it, and no Fact or limit cites it.  Its text is
readable with `strings` and says:

- the PC writes the draw time to `%MW0`, the expel time to `%MW2` and a function code to `%MW4`;
  `%MW0` and `%MW2` are declared `TIME` with initial values `T#15ms` and `T#50ms`; `%MW6` is the
  echo register (`FuncEcho`), and `%MW8` and `%MW10` hold two temperatures;
- "As soon as a valid code is received, the action associated with that code is executed": 2 draw,
  4 expel, 8 Press valve (#0) OFF, 9 Press valve ON, 16 Atmos valve (#1) OFF, 17 Atmos valve ON,
  128 "Atmos and Press valves are in their idle positions (Press is OFF, Atmos is ON)";
- "If a valid code is received, the program copies this code to %MW6 as an echo ... The PC can
  read back this echo, and must set it back to 0 afterwards";
- the sequencer's step actions: the Init step's exit copies `Func` to `FuncEcho`; `Press0`
  `Press := 0`, `Press1` `Press := 1`, `Atmos0` `Vacuum := 1`, `Atmos1` `Vacuum := 0`, `Idle`
  `Vacuum := 0; Press := 0`, and each of them `Func := 0`; the draw and expel sequences switch
  `Vacuum` or `Press` on for the set time after a 50 ms delay and end with `Vacuum := 0; Press := 0;
  Func := 0`.  The text shows no transition out of a running draw or expel sequence on a new code,
  so a code written during one is lost when the sequence's end clears `Func`.

What follows from it for this package: the upstream's `vac_on` (16) sets the program's `Vacuum`
output (the comment calls it "Atmos valve (#1) is OFF") and `vac_off` (17) clears it; the idle code
128 switches both outputs off, which is also the state each draw and expel ends in.  The program's
text declares no variable at `%MW14`, the register that the upstream's `connect` and `disconnect` write
`idle_atm` to (`func_idle_type`, offset 14), so those writes do not idle the valves with this
program; the upstream's `disconnect` logs "turning off pressure and vacuum" (picking_pipette.py:85)
but writes nothing to the function register.  Neither the upstream Python nor this driver clears
the echo register, so it can hold a stale code.

## Stop path

- `@estop` (`stop`): one write of `func_idle` to the function register; the Modbus reply is checked
  (`isError()`), and an exception reply makes the e-stop fail with the latch held.  It does not wait
  for the controller to take the code.
- The safe-state action `x-cap.czbiohub-sf.safe_pneumatics.v1`, which the runtime runs after the
  native stop, writes `func_idle` again and waits at most 0.5 s (package policy) until the function
  register reads 0 and the echo register holds the idle code.  If the controller does not take the
  code (it is not scanning, or a draw or expel sequence is running and its end clears the code), the
  action fails, the e-stop receipt is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED`, the latch stays and
  the runtime retries the stop path in the background.
- The other actions use the same confirmed path: a code the controller did not take is a failed
  command (`MHS.DEVICE.FAULTED`, the echo as `native_code`), a code still waiting after 0.5 s or whose
  registers cannot be read back after the write is `unknown`.
- What the confirmation proves: the controller program took the code.  It is not a sensed valve
  position: the clone has no valve-position read-back.
- Concurrency: the runtime calls reads, the e-stop and the safe-state action outside the driver
  lock, and `ValveController` may close and replace its client on any call (valve_controller.py:53-59,
  110-114), so the driver holds its own lock for each single Modbus read or write (never across a
  command's wait): the e-stop waits at most for the transaction in flight, which on a dead link can
  last as long as pymodbus's timeouts and the upstream's reconnect and retry (the receipt then fails
  at the e-stop budget with the latch held).  A command whose write is still inside that retry path
  when the e-stop lands can reach the controller after the stop's write; on a device without a
  declared re-enable the runtime does not wait for it.

## Scope

The driver binds the Wago pneumatic valve controller only.  The Zaber pipette stage is not covered:
`ZaberController` has no stop, abort or halt method (`zaber_controller.py:11-176`), `move_arm` passes
`timeout = 60` to the library's `move_relative` and `move_absolute` (`zaber_controller.py:149-152`;
the unit is the zaber_motion library's and is not stated in the clone), and its `_connect` homes every
stage when it opens in env `prod` (`zaber_controller.py:40-48`).  The clone cannot cancel a move in
flight.  `PickingPipette.disconnect` is not a stop: it moves the pipette, homes x and y and swings
the pipette before its idle write (`picking_pipette.py:81-94`).  The timed draw and expel functions
(codes 2 and 4) are not exposed; the draw and expel time registers are, as operator-limited writes,
and they change what a draw or expel started by another client (the upstream GUI) does.

## Instrument notes from the SOP (a PDF; not cited)

`SOPs/Fish sorter instrument SOP.pdf` sets the pressure box to 25 inHg of vacuum and 15 psi of
pressure, says that toggling the pressure valve on gives a steady air stream from the pipette tip,
and ends a run by toggling the power switch.  It documents no emergency stop for the pneumatics.

## Licence

The top-level `LICENSE` is BSD 3-Clause; `pyproject.toml` declares "BSD 3-Clause License, CERN Open
Hardware Licence Version 2 - Weakly Reciprocal", and `hardware-license.txt` is the CERN-OHL-W text.
The CoDeSys program sits in `hardware/`.  This package copies no file of the clone.

Tags: `fish sorter`, `pneumatics`, `pressure`, `vacuum`, `valve`, `wago`, `modbus`
