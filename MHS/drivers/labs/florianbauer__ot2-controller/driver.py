"""OpenMHS driver for gh.florianbauer/ot2-controller: an Opentrons OT-2 over the repository's SSH client.

The card names the python-object family.  This is a direct Driver over
``ot2_controller.feature_implementations.ot2controller_impl:Ot2ControllerImpl``, the repository's concrete
feature implementation: the native calls are the feature's own methods, and the e-stop reaches into the nested
Paramiko ``SSHClient`` the feature owns, which a config-only PythonObjectDriver binding cannot express, so the
shape is recorded as a deviation from the card in RESULT.json.

* reads: the connection description and the protocol files the upstream lists under ``/data/user_storage``;
* ``cap.process.run.v1``: run one uploaded protocol file, either simulated or executed.  The class's
  ``recipe_ref`` carries the protocol file name because the upstream ``RunProtocol`` identifies the file by name
  under ``/data/user_storage/``.

The built-in camera picture, camera movie, protocol upload and protocol removal are not bound here: the camera
catalogue class requires numeric width, height and exposure inputs, while the upstream command always captures a
fixed 640x480 JPEG and exposes no setting; upload/remove are not part of the card's primary run interface.

MODEL REVIEW (2026-11-05).  The author bound ``native.ssh.close()`` as the e-stop and as a ``safe_state=True``
action (``x-cap.florianbauer.abort_protocol.v1``) and declared ``estop_terminal``, so the SDK reported an achieved
safe state.  Closing the client is a disconnect, not a stop: the clone calls it "Close connection" in the
destructor (ot2controller_impl.py:159-161), ``RunProtocol`` starts ``python3 -m opentrons.execute`` with
``exec_command(cmd)`` (:116-119), and no line of the clone stops, pauses or aborts that remote process, so the
protocol may keep running on the OT-2.  The reviewer kept the close in the e-stop (it ends this driver's channel),
which now raises ``MHS.SAFETY.SAFE_STATE_UNREACHED``; removed the safe-state action (a disconnect exposed as a
capability) and ``estop_terminal`` (an SSH reconnection changes nothing on the device, CORE-087); refused protocol
names outside a plain file-name pattern, because the upstream inserts the name unquoted into a root shell command
(:114, :116); made a non-zero exit status a failed receipt and a missing status an unknown one (CORE-071); and
made the run non-cancellable, because a cancel request could not reach the remote process.  The package is blocked
(NO_HARDWARE_FREE_PATH): an R2 liquid handler without a source-backed stop.

Every Fact cites a line of the clone at the pinned commit eabc7fa6df1aea483d8438dbc540ccb3fffa6b67.  This package
is model-authored and unreviewed: its hardware backend is refused until a human sets ``reviewed_by`` in
driver.lock.json, and the acceptance gate runs the fake backend only.
"""

from __future__ import annotations

from mhs.driver import Driver, DriverFailed, Fact, Field, OutcomeUnknown, action, estop, read

IMPL = "ot2_controller/feature_implementations/ot2controller_impl.py"
FAULTED = "MHS.DEVICE.FAULTED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"

#: A plain protocol file name with the .py suffix the user guide asks for (doc/UserGuide.md:14).  The upstream
#: appends the name unquoted to USER_STORAGE_DIR in the command it passes to exec_command (ot2controller_impl.py:114,
#: 116, 119), so path separators, blanks and shell syntax are refused before any native call.
PROTOCOL_FILE = r"^[A-Za-z0-9][A-Za-z0-9._-]*\.py$"


class Ot2Controller(Driver):
    device_id = "ot2-controller"
    device_kind = "process.controller"
    mode = "hardware"
    risk = "R2"
    native = ("ot2_controller.feature_implementations.ot2controller_impl:"
              "Ot2ControllerImpl")
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOt2Controller"}
    vendor, model = "Opentrons", "OT-2"
    display_name = "Opentrons OT-2 SiLA 2 controller"
    tags = ["opentrons", "ot-2", "liquid-handler", "protocol-execution", "ssh", "sila2"]
    facts = [
        Fact("The repository is a SiLA 2 controller for an Opentrons OT-2 liquid handler",
             source="vendor_doc", ref="README.md:1-2"),
        Fact("The module sets the default private key path ~/.ssh/ot2_ssh_key, the login user root and the protocol "
             "directory /data/user_storage/", source="upstream_code", ref=f"{IMPL}:16-18"),
        Fact("The constructor loads an RSA private key from pkey_path or the default path, adds unknown host keys "
             "automatically (AutoAddPolicy) and connects to device_ip as DEVICE_USERNAME without a timeout argument",
             source="upstream_code", ref=f"{IMPL}:29-45"),
        Fact("get_Connection returns the device IP and the hex fingerprint of the loaded private key",
             source="upstream_code", ref=f"{IMPL}:49-50"),
        Fact("get_AvailableProtocols runs ls on USER_STORAGE_DIR and keeps the lines for which endswith('.py') "
             "holds, stripping each line only after that test", source="upstream_code", ref=f"{IMPL}:52-54"),
        Fact("get_CameraPicture captures one 640x480 frame from /dev/video0 with ffmpeg and downloads the JPEG "
             "over SCP", source="upstream_code", ref=f"{IMPL}:56-77"),
        Fact("RunProtocol appends ProtocolFile unquoted to USER_STORAGE_DIR in the command python3 -m "
             "opentrons.simulate when IsSimulating is true and python3 -m opentrons.execute otherwise, and passes "
             "that string alone to exec_command", source="upstream_code", ref=f"{IMPL}:110-119"),
        Fact("RunProtocol prints every remote stderr line and then every remote stdout line on the host's standard "
             "output", source="upstream_code", ref=f"{IMPL}:121-125"),
        Fact("RunProtocol returns the remote exit status and raises ValueError only when a simulated run's status "
             "is not 0", source="upstream_code", ref=f"{IMPL}:127-133"),
        Fact("The feature's abstract base declares get_Connection, get_AvailableProtocols, get_CameraPicture, "
             "UploadProtocol, RemoveProtocol, RunProtocol and CameraMovie, and no stop, pause or abort method",
             source="upstream_code", ref="ot2_controller/generated/ot2controller/ot2controller_base.py:12-94"),
        Fact("The destructor closes the SSH connection", source="upstream_code", ref=f"{IMPL}:159-161"),
        Fact("The command-line entry calls server.stop() on the SiLA server once Enter is pressed",
             source="upstream_code", ref="ot2_controller/__main__.py:70-78"),
        Fact("The protocol is identified by its uploaded file name including the .py suffix",
             source="vendor_doc", ref="doc/UserGuide.md:14"),
        Fact("A camera picture is a current JPEG of the deck taken with the built-in camera",
             source="vendor_doc", ref="doc/UserGuide.md:9"),
        Fact("Protocols executed directly on the robot hardware omit the initial calibration steps, and incorrect "
             "positioning of the pipettes may be the consequence", source="vendor_doc", ref="doc/UserGuide.md:82"),
        Fact("The SiLA server runs on a host computer that has to be connected to the OT-2 via SSH",
             source="vendor_doc", ref="README.md:54-55"),
    ]
    safe_state = ("None reached: the e-stop closes this driver's SSH client, the upstream's only teardown "
                  "(ot2controller_impl.py:159-161), and no line of the clone stops, pauses or aborts the remote "
                  "python3 -m opentrons.execute process, so the protocol may keep running on the OT-2 after the "
                  "e-stop and the e-stop is reported SAFE_STATE_UNREACHED with the latch held")

    # -- reads -------------------------------------------------------------------------------------------------
    @read("connection", type="string",
          description="Device IP and the hex fingerprint of the local SSH private key, formatted by the feature from "
                      "its own fields; it does not show whether the SSH session is open")
    def connection(self):
        return self.native.get_Connection(metadata={})

    @read("available_protocols", type="array", items="string",
          description="Protocol files the upstream lists under /data/user_storage/; its filter tests each ls line "
                      "before stripping the newline that Paramiko's readlines keeps (ot2controller_impl.py:54), so a "
                      "real OT-2 is expected to report an empty list")
    def available_protocols(self):
        return self.native.get_AvailableProtocols(metadata={})

    # -- protocol execution ------------------------------------------------------------------------------------
    @action(cap="cap.process.run.v1",
            description="Run (opentrons.execute) or, with dry_run, simulate (opentrons.simulate) one uploaded "
                        "protocol file on the OT-2 over SSH as root; exit status 0 completes, any other status "
                        "fails, and a run whose status never arrives is unknown (it may still be running)",
            long_running=True, cancellable=False,
            input={
                "recipe_ref": Field("string", max_length=512, pattern=PROTOCOL_FILE,
                                    description="File name of an uploaded protocol in /data/user_storage/ with its "
                                                ".py suffix; letters, digits, '.', '_' and '-' only, because the "
                                                "upstream inserts it unquoted into a shell command"),
                "dry_run": Field("boolean",
                                 description="True to run opentrons.simulate instead of opentrons.execute"),
            })
    def run_protocol(self, recipe_ref, dry_run=False):
        simulate = bool(dry_run)
        try:
            status = self.native.RunProtocol(recipe_ref, simulate, metadata={})
        except Exception as error:
            # The upstream raises a plain ValueError only for a simulation whose status is not 0
            # (ot2controller_impl.py:130-131); a subclass (UnicodeDecodeError while reading the remote output) is
            # not that.  A channel closed by the e-stop ends a simulation there too, and then no status is known.
            if simulate and type(error) is ValueError and not self.cancelled():
                raise DriverFailed(FAULTED, "opentrons.simulate did not report exit status 0 (a lost SSH channel "
                                            "ends the same way)") from error
            raise OutcomeUnknown("the SSH run ended without an exit status (channel closed, link failed or output "
                                 "unreadable); the protocol may still be running on the OT-2") from error
        status = int(status)
        if status == -1:
            # recv_exit_status (ot2controller_impl.py:127) gives -1 when the channel closed before the remote command
            # sent its exit status (Paramiko, outside the clone): the run's outcome is not known.
            raise OutcomeUnknown("no exit status arrived before the SSH channel closed; the protocol may still be "
                                 "running on the OT-2", native_code=status)
        if status != 0:
            raise DriverFailed(FAULTED, f"the protocol run exited with status {status}", native_code=status)
        return {"exit_code": status}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Close this driver's SSH client, then report the stop as unreached: the upstream has no stop."""
        self.native.ssh.close()
        raise DriverFailed(UNREACHED, "the upstream has no stop: closing the SSH client ends this driver's channel, "
                                      "and no line of the clone stops the opentrons.execute process on the OT-2")

    def teardown(self):
        self.native.ssh.close()
