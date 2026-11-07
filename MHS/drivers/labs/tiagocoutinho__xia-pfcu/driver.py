"""OpenMHS driver for gh.tiagocoutinho/xia-pfcu: an XIA PFCU-4 filter set and shutter controller.

DEVIATION FROM THE CARD: the card names the ``PythonObjectDriver`` helper.  The real interface is a Python object
whose commands are framed text (``!PFCU<module> <command>\\r``) and whose replies are multi-line status reports and
decoded enum lists; the class also has a sync/async protocol split.  A direct Driver over ``xia_pfcu.pfcu:PFCU``
expresses the reads, writes and actions without re-encoding those frames, so this package uses the direct shape.

The upstream class reaches the instrument through a connection object (``xia_pfcu/pfcu.py:23-25``).  ``native.py``
builds it with the ``syncio`` connection the README uses (``README.md:122-124``); every method here is therefore a
plain ``def`` and calls ``self.native`` synchronously.

* reads: the raw status report, the identity line, the four filter states, the reported decimation, the shutter
  mode, the shutter state and the two RS232 control flags;
* writes: the four filters (``IN``/``OUT``, ``xia_pfcu/pfcu.py:69-95``), the exposure decimation, the shutter mode
  (``2``/``4``) and exclusive RS232 control (``L``/``U``);
* ``cap.optics.shutter.v1``: open or close the focal-plane shutter;
* ``x-cap.tiagocoutinho.start_exposure.v1``: the fixed-length exposure.  No text file of the clone states a duration
  range, so that input is ``Limit.operator_required``: every call is refused ``MHS.SAFETY.LIMITS_UNSET`` until the
  site supplies the duration in ``site-limits.json`` (``site-limits.example.json`` shows the overlay);
* ``x-cap.tiagocoutinho.close_shutter.v1``: the safe-state action; the e-stop calls the same native close.  Closing
  the shutter terminates an exposure in progress (``xia_pfcu/pfcu.py:50-55``).  The clone documents no independent
  hardware e-stop, so ``estop_physical_ref`` is not set.

Every Fact cites a line of the clone at the pinned commit ed95e031f718c343842bc340f4ae91eb2cb6894a.  This package is
model-authored and unreviewed: it is checked on the fake backend only and nothing here ran on a device.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


def _filter_state(value):
    """A FilterStatus (or a fake's stand-in) as the lower-case state name the driver publishes."""
    name = getattr(value, "name", None)
    text = name if isinstance(name, str) else str(value)
    plain = text.replace("_", "").replace(" ", "").lower()
    return {
        "out": "out",
        "in": "in",
        "opencircuit": "open_circuit",
        "shortcircuit": "short_circuit",
    }.get(plain, text.lower())


def _shutter_state(info):
    """The shutter state a status report carries: open, closed or disabled."""
    return str(info["shutter_status"]).strip().lower()


class XiaPfcu(Driver):
    device_id = "pfcu"
    device_kind = "optics.shutter"
    mode = "hardware"
    risk = "R2"
    native = "xia_pfcu.pfcu:PFCU"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePFCU"}
    vendor, model = "XIA", "PFCU-4 (PF4)"
    display_name = "XIA PFCU-4 filter set and shutter controller"
    tags = ["filter-set", "shutter", "optical-path", "xia", "pfcu"]
    facts = [
        Fact("PFCU is a PFCU-4 Filter Set & Relay Control Unit", source="upstream_code",
             ref="xia_pfcu/pfcu.py:18-20"),
        Fact("The status parser reads four filter channels from the status report", source="upstream_code",
             ref="xia_pfcu/protocol.py:112-123"),
        Fact("set_filters accepts IN, I or 1 and OUT, O or 0 (case insensitive) per filter and '=' leaves a filter "
             "unchanged", source="upstream_code", ref="xia_pfcu/pfcu.py:69-95"),
        Fact("filters_status decodes each channel as FilterStatus Out=0, In=1, OpenCircuit=2, ShortCircuit=3",
             source="upstream_code", ref="xia_pfcu/protocol.py:11-15"),
        Fact("The status report carries the identity line, four channel states, the RS232 control flags, the shutter "
             "mode and status, and the exposure decimation", source="upstream_code",
             ref="xia_pfcu/protocol.py:108-138"),
        Fact("The exposure conversion starts at decimation 1 and states that 65_535 is the maximum decimation",
             source="upstream_code", ref="xia_pfcu/protocol.py:91-100"),
        Fact("start_exposure converts seconds to an exposure count and a decimation, sends the decimation command and "
             "then the exposure command", source="upstream_code", ref="xia_pfcu/protocol.py:87-105"),
        Fact("close_shutter immediately closes the PF2S2 shutter and terminates an exposure in progress; close and "
             "open only work when shutter mode is enabled", source="upstream_code", ref="xia_pfcu/pfcu.py:43-55"),
        Fact("enable_shutter enables the shutter commands and disable_shutter is the default condition at power-up",
             source="upstream_code", ref="xia_pfcu/pfcu.py:30-41"),
        Fact("Requests are framed as !PFCU<module> <command>\\r and replies start with %", source="upstream_code",
             ref="xia_pfcu/protocol.py:49-64"),
        Fact("The tango server opens the connection with eol=b';\\r\\n' and wraps PFCU with the configured module",
             source="upstream_code", ref="xia_pfcu/tango/server/pfcu.py:21-29"),
        Fact("The README exposes the serial line at 9600 baud", source="vendor_doc", ref="README.md:67"),
    ]
    safe_state = "shutter closed by the native close_shutter command, blocking the optical path"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("status", type="string", description="Raw status report the PFCU returns for the S command")
    def status(self):
        return self.native.status()

    @read("identity", type="string", description="Identity line the PFCU reports in its status")
    def identity(self):
        return str(self.native.info()["id"])

    @read("filter_a", type="string",
          description="Filter channel A state: in, out, open_circuit or short_circuit")
    def filter_a(self):
        return _filter_state(self.native.filters_status()[0])

    @read("filter_b", type="string",
          description="Filter channel B state: in, out, open_circuit or short_circuit")
    def filter_b(self):
        return _filter_state(self.native.filters_status()[1])

    @read("filter_c", type="string",
          description="Filter channel C state: in, out, open_circuit or short_circuit")
    def filter_c(self):
        return _filter_state(self.native.filters_status()[2])

    @read("filter_d", type="string",
          description="Filter channel D state: in, out, open_circuit or short_circuit")
    def filter_d(self):
        return _filter_state(self.native.filters_status()[3])

    @read("decimation", type="integer", unit="1",
          description="Exposure decimation the status report currently carries")
    def decimation(self):
        return int(self.native.info()["decimation"])

    @read("shutter_enabled", type="boolean",
          description="True while the shutter commands (open, close and exposure) are enabled")
    def shutter_enabled(self):
        return bool(self.native.info()["shutter_enabled"])

    @read("shutter_state", type="string",
          description="Shutter state from the status report: open, closed or disabled")
    def shutter_state(self):
        return _shutter_state(self.native.info())

    @read("remote_control_enabled", type="boolean",
          description="True while RS232 remote control is enabled")
    def remote_control_enabled(self):
        return bool(self.native.info()["remote_control_enabled"])

    @read("remote_control_only", type="boolean",
          description="True while the PFCU ignores its front panel and TTL controls (locked)")
    def remote_control_only(self):
        return bool(self.native.info()["remote_control_only"])

    # -- writes ------------------------------------------------------------------------------------------------
    @write("decimation", type="integer", unit="1",
           description="Exposure decimation sent with the D command",
           limit=Limit(min=1, max=65535, source="upstream_code", ref="xia_pfcu/protocol.py:91-100"))
    def set_decimation(self, value):
        self.native.set_decimation(value)
        return int(self.native.info()["decimation"])

    @write("filter_a", type="string",
           description="Insert ('in') or remove ('out') filter channel A, leaving the other channels unchanged",
           limit=Limit(allowed=["in", "out"], source="upstream_code", ref="xia_pfcu/pfcu.py:73-74"))
    def set_filter_a(self, value):
        return _filter_state(self.native.set_filters(a=value)[0])

    @write("filter_b", type="string",
           description="Insert ('in') or remove ('out') filter channel B, leaving the other channels unchanged",
           limit=Limit(allowed=["in", "out"], source="upstream_code", ref="xia_pfcu/pfcu.py:73-74"))
    def set_filter_b(self, value):
        return _filter_state(self.native.set_filters(b=value)[1])

    @write("filter_c", type="string",
           description="Insert ('in') or remove ('out') filter channel C, leaving the other channels unchanged",
           limit=Limit(allowed=["in", "out"], source="upstream_code", ref="xia_pfcu/pfcu.py:73-74"))
    def set_filter_c(self, value):
        return _filter_state(self.native.set_filters(c=value)[2])

    @write("filter_d", type="string",
           description="Insert ('in') or remove ('out') filter channel D, leaving the other channels unchanged",
           limit=Limit(allowed=["in", "out"], source="upstream_code", ref="xia_pfcu/pfcu.py:73-74"))
    def set_filter_d(self, value):
        return _filter_state(self.native.set_filters(d=value)[3])

    @write("shutter_enabled", type="boolean",
           description="Enable (2) or disable (4) the shutter commands; disabling is the power-up default")
    def set_shutter_enabled(self, value):
        if value:
            self.native.enable_shutter()
        else:
            self.native.disable_shutter()
        return bool(self.native.info()["shutter_enabled"])

    @write("remote_control_only", type="boolean",
           description="Lock (L) or unlock (U) exclusive RS232 control of the PFCU")
    def set_remote_control_only(self, value):
        if value:
            self.native.lock()
        else:
            self.native.unlock()
        return bool(self.native.info()["remote_control_only"])

    # -- actions -----------------------------------------------------------------------------------------------
    @action(cap="cap.optics.shutter.v1",
            description="Open or close the focal-plane shutter and report the state the status report reads back",
            input={"state": Field(description="Wanted shutter state: open or closed")})
    def set_state(self, state):
        if state == "open":
            self.native.open_shutter()
        else:
            self.native.close_shutter()
        return {"state": _shutter_state(self.native.info())}

    @action(name="x-cap.tiagocoutinho.start_exposure.v1",
            description="Start a fixed-length exposure with the native start_exposure; the duration is in seconds",
            input={"duration_s": Field("number", unit="s",
                                       description="Exposure duration in seconds",
                                       limit=Limit.operator_required(
                                           "no text file of the clone states the exposure duration range; the site "
                                           "sets the range of its shutter and detector"))},
            output={"duration_s": Field("number", unit="s",
                                        description="Exposure duration passed to the native start_exposure")})
    def start_exposure(self, duration_s):
        self.native.start_exposure(duration_s)
        return {"duration_s": duration_s}

    @action(name="x-cap.tiagocoutinho.close_shutter.v1", safe_state=True,
            description="Close the shutter (the native close_shutter, the safe state of the optical path); it takes "
                        "no input",
            output={"state": Field("string", enum=["open", "closed"],
                                   description="Shutter state after the close")})
    def close_shutter(self):
        self.native.close_shutter()
        return {"state": _shutter_state(self.native.info())}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop(native="close_shutter")
    def stop(self):
        """The native stop: the runtime latches first, then close_shutter blocks the optical path."""
        self.native.close_shutter()

    def teardown(self):
        self.native.protocol.conn.close()
