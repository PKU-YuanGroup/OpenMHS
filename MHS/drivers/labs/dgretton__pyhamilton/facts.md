# Facts and tags for gh.dgretton/pyhamilton

Every fact cites its source at commit `65938d05cc8f5a5a0d3186648add560439ab1cdd`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| HamiltonInterface is the main class that sets up and tears down the interface to a Hamilton robot and creates a Hamilton HSL background process plus a localhost connection | upstream_code | pyhamilton/interface.py:501-506 |
| start() launches the pyhamilton interpreter/OEM application and the local HTTP server, and is_open() returns the active flag | upstream_code | pyhamilton/interface.py:578-596 |
| stop() terminates the OEM process in normal mode, sets active to False and joins the server thread with a 1.0 s timeout | upstream_code | pyhamilton/interface.py:619-666 |
| start() opens the OEM application with a window for simulation, only sets active in simulating mode, starts a 32-bit server process in server mode, and otherwise starts a new OEM process (run_hamilton_process) | upstream_code | pyhamilton/interface.py:578-611 |
| is_open() returns True between start() and stop() | upstream_code | pyhamilton/interface.py:692-694 |
| initialize() sends the INITIALIZE command and waits up to 300 s for its response | upstream_code | pyhamilton/interface.py:868-884 |
| aspirate() refuses a command without a liquidClass and accepts at most 8 positions | upstream_code | pyhamilton/interface.py:906-911 |
| dispense() accepts at most 8 positions and uses the upstream default liquid class when none is given | upstream_code | pyhamilton/interface.py:962-967 |
| aspirate() and dispense() return AspirateResult or DispenseResult with liquidHeights and liquidVolumes | upstream_code | pyhamilton/interface.py:930-944 |
| move_by_seq() sends ISWAP_GET for the source sequence and ISWAP_PLACE for the target sequence, each with a 120 s response timeout | upstream_code | pyhamilton/interface.py:1350-1398 |
| set_labware_property() sends SET_LABWARE_PROPERTY with LabwareID, PropertyName and PropertyValue | upstream_code | pyhamilton/interface.py:1241-1258 |
| HamiltonServerThread.has_exited reports whether the local server thread has left its run loop | upstream_code | pyhamilton/interface.py:489-498 |
| The usable pipetting volume is derived from the installed tip type and the liquid class, not from a fixed robot bound | upstream_code | pyhamilton/liquid_class_db.py:306-333 |
| The project is developed for Hamilton STAR and STARlet on Windows; VANTAGE is supported with a plugin | vendor_doc | README.md:7 |
| The clone's tests mock HamiltonInterface.start and HamiltonInterface.stop; it ships no device simulator for these actions | upstream_code | tests/interface_tests.py:277-280 |
| The simulating flag only logs commands and returns no response data instead of emulating the robot | upstream_code | pyhamilton/interface.py:596-598 |

Limits: the two numeric action inputs (`volume` of aspirate and dispense) are `Limit.operator_required`. No text file
of the clone states a volume, flow or force envelope of a configured robot; `liquid_class_db.py:314` shows tip-type
nominal volumes (10, 50, 300 and 1000 uL), but the installed tip type and the liquid class decide which one applies,
and a tip-type table is a library default, not a bound of the robot. The site supplies its ranges in
`site-limits.json`; `site-limits.example.json` is an example overlay only, not a statement about any robot.

Safety: the e-stop `stop` and the safe-state action `x-cap.dgretton.shutdown_interface.v1` both call the native
`HamiltonInterface.stop()` (interface.py:619-674). The clone documents no independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver. The native
stop terminates the OEM process in normal mode and signals the local server thread; it is the only stop the clone
provides, and it is not a hardware emergency-stop button.

A safety reset only releases the latch (SAFE-042): the driver has no `@reset` hook, so the interface stays stopped.
`HamiltonInterface.start()` relaunches the OEM process (or the server or simulation process) that the stop terminated
(interface.py:578-611), and the clone does not say whether that start moves or initialises the instrument, so starting
the interface again is the declared re-enable `x-cap.dgretton.start_interface.v1` (`reenable=True`, CORE-086): a
command of its own, with no input, refused while the e-stop is latched and named in the reset receipt. Until
2026-11-05 the `@reset` hook called `start()` itself, which SAFE-042 forbids.

Catalogue: no catalogue class carries the Hamilton liquid class that `aspirate` requires together with the volume and
well (interface.py:909-911), so the package uses the extension ids `x-cap.dgretton.aspirate.v1`,
`x-cap.dgretton.dispense.v1` and `x-cap.dgretton.set_labware_property.v1`. `cap.sample.move.v1` binds only
`lab.sample` and `lab.labware` and cannot bind this `lab.liquid_handler`, so the plate move uses
`x-cap.dgretton.move_plate.v1`. No class starts or stops the Hamilton interface, so initialize, shutdown and the
re-enable `x-cap.dgretton.start_interface.v1` use extensions. Each extension is listed in `RESULT.json` `catalogue_requests`.

Coverage and fidelity gaps: this package drives single-channel aspirate and dispense on 96-well `Plate96` labware,
the iSWAP plate move by sequence, the INITIALIZE command and the interface lifecycle. It does not bind tip pickup or
eject, the 96-well and 384-quadrant commands, the gripper commands, `move_sequence`, `load_carrier`,
`unload_carrier`, `set_log_dir`, the ODTC thermal-cycler protocol or the device wrappers. The hardware adapter
constructs a `Plate96` for every labware name, so 384-well and other deck resources are not covered. The fake is an
in-memory stand-in written for this package; the clone ships only mocks (tests/interface_tests.py:277-280), and the
upstream `simulating` flag does not emulate the robot. The fake deliberately accepts commands while its interface is
stopped, unlike the real `send_command`, so the e-stop latch and reset can be exercised; the volume it reports is the
requested value, not a measurement.

Tags: liquid-handler, hamilton, venus, iswap, pipetting
