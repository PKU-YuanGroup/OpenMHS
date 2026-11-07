# Facts and tags for gh.florianbauer/ot2-controller

Every fact cites a text file of the clone at commit `eabc7fa6df1aea483d8438dbc540ccb3fffa6b67`.  The same list
is in `driver.py`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a SiLA 2 controller for an Opentrons OT-2 liquid handler | vendor_doc | README.md:1-2 |
| The module sets the default private key path ~/.ssh/ot2_ssh_key, the login user root and the protocol directory /data/user_storage/ | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:16-18 |
| The constructor loads an RSA private key from pkey_path or the default path, adds unknown host keys automatically (AutoAddPolicy) and connects to device_ip as DEVICE_USERNAME without a timeout argument | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:29-45 |
| get_Connection returns the device IP and the hex fingerprint of the loaded private key | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:49-50 |
| get_AvailableProtocols runs ls on USER_STORAGE_DIR and keeps the lines for which endswith('.py') holds, stripping each line only after that test | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:52-54 |
| get_CameraPicture captures one 640x480 frame from /dev/video0 with ffmpeg and downloads the JPEG over SCP | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:56-77 |
| RunProtocol appends ProtocolFile unquoted to USER_STORAGE_DIR in the command python3 -m opentrons.simulate when IsSimulating is true and python3 -m opentrons.execute otherwise, and passes that string alone to exec_command | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:110-119 |
| RunProtocol prints every remote stderr line and then every remote stdout line on the host's standard output | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:121-125 |
| RunProtocol returns the remote exit status and raises ValueError only when a simulated run's status is not 0 | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:127-133 |
| The feature's abstract base declares get_Connection, get_AvailableProtocols, get_CameraPicture, UploadProtocol, RemoveProtocol, RunProtocol and CameraMovie, and no stop, pause or abort method | upstream_code | ot2_controller/generated/ot2controller/ot2controller_base.py:12-94 |
| The destructor closes the SSH connection | upstream_code | ot2_controller/feature_implementations/ot2controller_impl.py:159-161 |
| The command-line entry calls server.stop() on the SiLA server once Enter is pressed | upstream_code | ot2_controller/__main__.py:70-78 |
| The protocol is identified by its uploaded file name including the .py suffix | vendor_doc | doc/UserGuide.md:14 |
| A camera picture is a current JPEG of the deck taken with the built-in camera | vendor_doc | doc/UserGuide.md:9 |
| Protocols executed directly on the robot hardware omit the initial calibration steps, and incorrect positioning of the pipettes may be the consequence | vendor_doc | doc/UserGuide.md:82 |
| The SiLA server runs on a host computer that has to be connected to the OT-2 via SSH | vendor_doc | README.md:54-55 |

## Limits

No device text of the clone states a numeric range for a protocol file name or for the simulation flag, and this
driver exposes no other input.  The catalogue class restricts `recipe_ref` to at most 512 characters; the driver
narrows it further to a plain file name with the `.py` suffix (`^[A-Za-z0-9][A-Za-z0-9._-]*\.py$`), because the
upstream inserts the name unquoted into the command it passes to `exec_command` (`ot2controller_impl.py:114`,
`:116`, `:119`) and the user guide asks for the uploaded file name with its suffix (`doc/UserGuide.md:14`).  These
are schema constraints, not device limits, so the driver carries no `Limit` and needs no
`site-limits.example.json` overlay.  The `cap.process.run.v1` duration bound (86400000 ms) is the catalogue class's
declared execution constraint, not a number taken from this device.

## Safety

The upstream feature has no stop, cancel, abort or pause method (`ot2controller_base.py:12-94`).  The only native
teardown is `self.ssh.close()` in `__del__` (`ot2controller_impl.py:159-161`, commented "Close connection"); the
interactive `server.stop()` acts on the SiLA server (`ot2_controller/__main__.py:70-78`).  `RunProtocol` starts the
remote `python3 -m opentrons.execute` with `exec_command(cmd)` (`ot2controller_impl.py:116-119`), and no line of
the clone stops that remote process.  Closing the SSH client therefore ends this driver's channel only, and the
protocol may keep running on the OT-2.

Model review (2026-11-05): the author had bound the close as the e-stop and as the safe-state action
`x-cap.florianbauer.abort_protocol.v1` and declared `estop_terminal`, so the SDK reported an achieved safe state
for a disconnect.  The e-stop still closes the client, then raises `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch
held; the safe-state action is removed (a disconnect is driver teardown, not a capability), and so is
`estop_terminal`: an SSH reconnection changes nothing on the device, so it is not a new native session in the
sense of CORE-087.  The package is blocked (`NO_HARDWARE_FREE_PATH`): the gate fails G3 SAFE-045, because no line
of the clone documents an independent hardware stop and nothing achieves a safe state.

Run outcomes: exit status 0 completes; any other status is a failed receipt (`MHS.DEVICE.FAULTED` with the native
status), because the upstream returns an executed run's non-zero status instead of raising (`:127-133`) and
CORE-071 forbids reporting a failure through an output field.  A run whose status never arrives (-1 from
`recv_exit_status`, what Paramiko gives when the channel closes first) is unknown: the protocol may still be
running.  The run is not cancellable: a cancel request could not reach the remote process, and the author's
cancellable binding would have answered "cancelled" for a run that went on to its end.

## Fake

`fake.py` is a synthetic F0 stand-in, not a recording and not the upstream simulator (the clone has neither).
It keeps the upstream method names, the keyword-only `metadata` argument, the upstream protocol-list filter
(applied verbatim to an `ls` line that keeps its newline, so the list is empty), the exit-status return and the
`ValueError` of an unsuccessful simulation.  Closing the fake SSH client ends a fake run at once without a status
(-1); that models the driver's side of the channel only and is no evidence that an OT-2 stops.  Its connection
string, `ls` line, run duration, exit status and polling interval are test data marked `# placeholder`;
attributes starting with `_` are test knobs, not upstream members.

## Coverage

The package binds the primary protocol-run command and the two state reads.  The built-in camera picture and
movie, protocol upload and protocol removal are not bound: the camera catalogue class requires numeric width,
height and exposure inputs, while the upstream command always captures a fixed 640x480 JPEG and exposes no
setting; upload and removal are not part of the card's primary run interface.

Fidelity gaps: the upstream `get_AvailableProtocols` tests `line.endswith(".py")` before stripping the newline that
Paramiko's `readlines()` keeps (`ot2controller_impl.py:54`), so a real OT-2 is expected to report an empty list;
the driver does not repair that filter.  `RunProtocol` prints the remote output on the host's standard output
(`:121-125`), which would corrupt an MHS server talking over stdio.  A protocol file is named, not
content-addressed: the class note asks for an immutable recipe whose digest the receipt records, and the upstream
offers no digest.

## Tags

`opentrons`, `ot-2`, `liquid-handler`, `protocol-execution`, `ssh`, `sila2`
