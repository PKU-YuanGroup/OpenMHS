"""OpenMHS driver for gh.martinhjelmare/leicacam: the LASAF CAM socket server of a Leica microscope.

A direct Driver (decorated methods) over the upstream client class leicacam.cam:CAM.  The upstream object owns a TCP
socket to the LASAF CAM server (127.0.0.1:8895 by default, src/leicacam/cam.py:45-46) and speaks /key:value messages
(src/leicacam/cam.py:351-378); every convenience method sends one command and waits for the reply that carries the
``cmd`` field of that command (src/leicacam/cam.py:210-343).

* one read: the CAM ``getinfo`` reply about the stage (src/leicacam/cam.py:339-343), returned as the /key:value text
  of the protocol, because no text of the clone names the fields of a reply;
* eight actions, one per convenience method the upstream exposes for the matrix scan: start, stop, pause, autofocus,
  enable and disable one scan field, enable and disable every scan field.  Each action reports the reply of the CAM
  server: ``acknowledged`` is true when the server answered with a message carrying the command, and ``reply`` is that
  message as /key:value text;
* the scan-field indices of ``enable`` and ``disable`` are integers no text of the clone bounds, so every one of them is
  ``Limit.operator_required``: the site states the layout of its experiment (``site-limits.example.json``) and until it
  does, every call of those two actions is refused MHS.SAFETY.LIMITS_UNSET;
* the native stop (the CAM ``stopscan`` command) is the e-stop and, as ``stop_matrix_scan``, the safe-state action.  The
  e-stop sends the command without waiting for the reply: the upstream ``stop_scan`` waits up to 60 minutes for the
  acknowledgement (src/leicacam/cam.py:171-198, 216-220) and an e-stop must not wait for the device.  The safe-state
  action runs inside an e-stop too, so it does not call ``stop_scan`` either: it sends the command and waits for the
  reply at most ``STOP_REPLY_WAIT_MIN`` (``wait_for`` counts its timeout in minutes, src/leicacam/cam.py:185-195).

Every Fact cites a line of the clone at the pinned commit 5c33a0d6daa179377390eccf40f1fc3e584b2dad.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and no hardware was attached (RESULT.json).
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

CAM = "src/leicacam/cam.py"

#: How long the safe-state action waits for the stopscan reply, in the minutes of ``CAM.wait_for`` (6 s).  A choice of
#: this driver, not a device fact: the action also runs inside an e-stop, which must not wait for the device.
STOP_REPLY_WAIT_MIN = 0.1

#: The reply of every action: what the CAM server answered to the command.
REPLY = {
    "acknowledged": Field("boolean", description="True when the CAM server answered with a message carrying the "
                                                 "command before the wait timeout"),
    "reply": Field("string", description="The answering CAM message as /key:value text (empty when no answer came)"),
}

#: The five indices of one scan field, each bounded only by the site (see the module docstring).
FIELD = {
    "slide": Field("integer", unit="1", description="Slide index of the scan field",
                   limit=Limit.operator_required(
                       "no text of the clone states the range of the slide index of the scan matrix; the site "
                       "states the layout of its experiment")),
    "wellx": Field("integer", unit="1", description="Well column index of the scan field",
                   limit=Limit.operator_required(
                       "no text of the clone states the range of the well column index of the scan matrix; the site "
                       "states the layout of its experiment")),
    "welly": Field("integer", unit="1", description="Well row index of the scan field",
                   limit=Limit.operator_required(
                       "no text of the clone states the range of the well row index of the scan matrix; the site "
                       "states the layout of its experiment")),
    "fieldx": Field("integer", unit="1", description="Field column index inside the well",
                    limit=Limit.operator_required(
                        "no text of the clone states the range of the field column index of the scan matrix; the "
                        "site states the layout of its experiment")),
    "fieldy": Field("integer", unit="1", description="Field row index inside the well",
                    limit=Limit.operator_required(
                        "no text of the clone states the range of the field row index of the scan matrix; the site "
                        "states the layout of its experiment")),
}


def _message_text(message) -> str:
    """The /key:value text of one CAM message, the form tuples_as_bytes writes (src/leicacam/cam.py:351-378)."""
    if not message:
        return ""
    return " ".join(f"/{key}:{value}" for key, value in message.items())


class LeicaCAM(Driver):
    device_id = "leicacam"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "leicacam.cam:CAM"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCAM"}
    vendor, model = "Leica Microsystems", "LASAF CAM socket interface"
    display_name = "Leica LASAF CAM server (leicacam.CAM)"
    tags = ["microscope", "leica", "lasaf", "cam", "matrix scan", "autofocus"]
    facts = [
        Fact("CAM messages are /key:value pairs joined by spaces, for example b'/cmd:val /cmd2:val2'",
             source="upstream_code", ref=f"{CAM}:364-370"),
        Fact("Every message carries the client prefix /cli:python-leicacam /app:matrix", source="upstream_code",
             ref=f"{CAM}:49-54"),
        Fact("start_scan sends /cmd:startscan and waits for the reply that carries cmd", source="upstream_code",
             ref=f"{CAM}:210-214"),
        Fact("stop_scan sends /cmd:stopscan and waits for the reply that carries cmd", source="upstream_code",
             ref=f"{CAM}:216-220"),
        Fact("autofocus_scan sends /cmd:autofocusscan and waits for the reply that carries cmd", source="upstream_code",
             ref=f"{CAM}:222-226"),
        Fact("pause_scan sends /cmd:pausescan and waits for the reply that carries cmd", source="upstream_code",
             ref=f"{CAM}:228-232"),
        Fact("enable sends /cmd:enable with slide, wellx, welly, fieldx, fieldy and value true", source="upstream_code",
             ref=f"{CAM}:243-251"),
        Fact("disable sends the same /cmd:enable command with value false", source="upstream_code",
             ref=f"{CAM}:264-272"),
        Fact("enable_all sends /cmd:enableall value true and disable_all sends the same command with value false",
             source="upstream_code", ref=f"{CAM}:276-286"),
        Fact("get_information sends /cmd:getinfo /dev:<about> and waits for the reply that carries cmd",
             source="upstream_code", ref=f"{CAM}:339-343"),
        Fact("wait_for waits timeout minutes (60 by default) and returns an empty OrderedDict when it is reached",
             source="upstream_code", ref=f"{CAM}:171-198"),
        Fact("A reply is parsed into an OrderedDict keyed by the /key:value field names", source="upstream_code",
             ref=f"{CAM}:408-436"),
        Fact("The CAM socket connects to 127.0.0.1 port 8895 by default", source="upstream_code", ref=f"{CAM}:45-46"),
        Fact("COMMANDS.md documents startscan as start matrix scan, stopscan as stop matrix scan, pausescan as toggle "
             "pause of matrix scan and autofocusscan as start matrix focus scan", source="vendor_doc",
             ref="COMMANDS.md:31-34"),
        Fact("COMMANDS.md documents enable as enable single scan field and disable as disable single scan field",
             source="vendor_doc", ref="COMMANDS.md:37-38"),
        Fact("COMMANDS.md documents getinfo as information about the stage, z-drive, COR-ring, job list, pattern list, "
             "scan status, experiment, position, load position and autofocus mode and position", source="vendor_doc",
             ref="COMMANDS.md:41"),
        Fact("The README connects with CAM() and prints the reply of cam.start_scan()", source="vendor_doc",
             ref="README.md:56-61"),
    ]
    safe_state = "matrix scan stopped (the CAM stopscan command)"

    # -- read ----------------------------------------------------------------------------------------------------
    @read("stage_information", type="string",
          description="The CAM reply about the stage (getinfo /dev:stage) as /key:value text")
    def stage_information(self):
        return _message_text(self.native.get_information("stage"))

    # -- matrix scan ---------------------------------------------------------------------------------------------
    @action(name="x-cap.martinhjelmare.start_matrix_scan.v1",
            description="Start the matrix scan (the CAM startscan command)",
            output=REPLY)
    def start_matrix_scan(self):
        return _receipt(self.native.start_scan())

    @action(name="x-cap.martinhjelmare.stop_matrix_scan.v1", safe_state=True,
            description="Stop the matrix scan (the CAM stopscan command), the safe state of the scan",
            output=REPLY)
    def stop_matrix_scan(self):
        self.native.send([("cmd", "stopscan")])
        return _receipt(self.native.wait_for("cmd", "stopscan", timeout=STOP_REPLY_WAIT_MIN))

    @action(name="x-cap.martinhjelmare.pause_matrix_scan.v1",
            description="Toggle the pause of the matrix scan (the CAM pausescan command)",
            output=REPLY)
    def pause_matrix_scan(self):
        return _receipt(self.native.pause_scan())

    @action(name="x-cap.martinhjelmare.autofocus_scan.v1",
            description="Start the matrix focus scan (the CAM autofocusscan command)",
            output=REPLY)
    def autofocus_scan(self):
        return _receipt(self.native.autofocus_scan())

    # -- scan fields ---------------------------------------------------------------------------------------------
    @action(name="x-cap.martinhjelmare.enable_scan_field.v1",
            description="Enable one scan field of the experiment matrix (the CAM enable command with value true)",
            input=FIELD, output=REPLY)
    def enable_scan_field(self, slide, wellx, welly, fieldx, fieldy):
        return _receipt(self.native.enable(slide, wellx, welly, fieldx, fieldy))

    @action(name="x-cap.martinhjelmare.disable_scan_field.v1",
            description="Disable one scan field of the experiment matrix (the CAM enable command with value false)",
            input=FIELD, output=REPLY)
    def disable_scan_field(self, slide, wellx, welly, fieldx, fieldy):
        return _receipt(self.native.disable(slide, wellx, welly, fieldx, fieldy))

    @action(name="x-cap.martinhjelmare.enable_all_scan_fields.v1",
            description="Enable every scan field of the experiment matrix (the CAM enableall command with value true)",
            output=REPLY)
    def enable_all_scan_fields(self):
        return _receipt(self.native.enable_all())

    @action(name="x-cap.martinhjelmare.disable_all_scan_fields.v1",
            description="Disable every scan field of the experiment matrix (the CAM enableall command with value false)",
            output=REPLY)
    def disable_all_scan_fields(self):
        return _receipt(self.native.disable_all())

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Send the CAM stopscan command; it does not wait for the reply (an e-stop must not wait for the device)."""
        self.native.send([("cmd", "stopscan")])

    def teardown(self):
        self.native.close()


def _receipt(message):
    """The action output of one CAM reply."""
    return {"acknowledged": bool(message), "reply": _message_text(message)}
