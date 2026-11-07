"""OpenMHS driver for gh.asvela/dlc-control: a Toptica DLCpro laser controller.

A direct Driver over the upstream class ``dlccontrol:DLCcontrol`` (a convenience wrapper around the Toptica
laser SDK).  The upstream class talks to the DLCpro over Ethernet and exposes the laser state and settings as
properties; the driver translates the subset that the clone documents and that the fake can reproduce without
the proprietary Toptica SDK.

* reads: emission state, emission button, diode-current enable, wavelength actual/setpoint, diode temperature
  actual/setpoint, the internal scan settings (enabled, output channel, frequency, amplitude, offset, start, end),
  the connection user level and the limits the wrapper queried from the device;
* writes: diode-current enable (the documented emission on/off control), scan on/off, wavelength setpoint, diode
  temperature setpoint and the internal scan frequency/amplitude/offset/start/end.  The wavelength, temperature and
  scan range limits are queried from the DLC by the upstream class, not stated in a text file, so they are
  ``Limit.operator_required`` and every such write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies
  the range of its unit.  The scan frequency is bounded by the wrapper's own 0.02 to 400 hard-coded range, cited
  from the clone;
* safety: the clone has no emergency-stop method; ``current_enabled`` is documented as the way to turn emission
  off.  The ``@estop`` and the ``x-cap.asvela.emission_off.v1`` safe-state action use that setter.  The package is
  R3 because the README warns that the module controls potentially Class 4 lasers; it is model-authored and
  unreviewed, so the loader refuses its hardware backend until a human sets ``reviewed_by`` in driver.lock.json.

``set_parameters`` is not implemented upstream (it raises NotImplementedError) and ``read_parameters`` only parses
a JSON file, so neither is exposed.  ``set_user_level`` is not exposed because the upstream service level asks for
interactive confirmation on stdin and a per-unit service password.

Every Fact cites a line of the clone at the pinned commit
eba98c139581e73dce32c0b196f41b253f6009f8.  Nothing in this module imports or runs the upstream package.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class DlcControlDriver(Driver):
    device_id = "dlc-control"
    device_kind = "optics.laser"
    mode = "hardware"
    risk = "R3"
    native = "dlccontrol:DLCcontrol"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDlcControl"}
    vendor, model = "Toptica", "DLCpro"
    display_name = "Toptica DLCpro laser controller (dlccontrol.DLCcontrol)"
    tags = ["laser", "dlcpro", "toptica", "emission", "scan"]
    facts = [
        Fact("The README warns that this module controls potentially Class 4 lasers.",
             source="vendor_doc", ref="README.md:8"),
        Fact("The README describes a convenience wrapper around the Toptica laser SDK for controlling a Toptica "
             "CTL laser with a DLCpro.", source="vendor_doc", ref="README.md:6"),
        Fact("DLCcontrol controls a Toptica DLCpro over an Ethernet connection.",
             source="upstream_code", ref="dlccontrol.py:99-100"),
        Fact("DLCcontrol builds the Toptica SDK NetworkConnection and DLCpro in __init__ and calls open() unless "
             "open_on_init is false.", source="upstream_code", ref="dlccontrol.py:155-159"),
        Fact("emission, emission_button and current_enabled read the DLC emission state, the emission button and "
             "the diode current enable; the current_enabled setter is documented as controlling emission on/off.",
             source="upstream_code", ref="dlccontrol.py:455-476"),
        Fact("The service user level prompts for interactive confirmation on stdin and uses a per-unit service "
             "password.", source="upstream_code", ref="dlccontrol.py:200-215"),
        Fact("get_user_level reads the connection user level; the set_user_level docstring says 3 is normal, "
             "2 maintenance and 1 service.", source="upstream_code", ref="dlccontrol.py:185-220"),
        Fact("wavelength_actual and wavelength_setpoint read the laser wavelength; the setpoint setter checks the "
             "range queried by get_limits_from_dlc.", source="upstream_code", ref="dlccontrol.py:480-506"),
        Fact("temp_actual and temp_setpoint read the diode temperature; the setpoint setter checks the range "
             "queried by get_limits_from_dlc.", source="upstream_code", ref="dlccontrol.py:510-536"),
        Fact("The internal scan settings are enabled, output channel, frequency, amplitude, offset, start and end.",
             source="upstream_code", ref="dlccontrol.py:301-309"),
        Fact("get_limits_from_dlc queries the piezo voltage, current clip, wavelength and temperature ranges; it "
             "hard-codes the scan frequency bounds 0.02 and 400 and notes that the maximum was not found in the "
             "manual.", source="upstream_code", ref="dlccontrol.py:253-290"),
        Fact("The scan_frequency setter checks the value against the fmin and fmax bounds.",
             source="upstream_code", ref="dlccontrol.py:676-681"),
        Fact("The scan range is the piezo voltage range for the PC output and the current range for the CC output; "
             "OutA and OutB have no range check.", source="upstream_code", ref="dlccontrol.py:330-339"),
        Fact("freq_per_sec documents scan_freq in Hz and peak_to_peak in Vpp.",
             source="upstream_code", ref="dlccontrol.py:741-759"),
        Fact("OutputChannel enumerates PC, CC, OutA and OutB; InputChannel enumerates Fine1, Fine2, Fast3 and "
             "Fast4.", source="upstream_code", ref="dlccontrol.py:75-91"),
        Fact("set_parameters is not implemented: it raises NotImplementedError.",
             source="upstream_code", ref="dlccontrol.py:416-421"),
        Fact("read_parameters only loads parameters from a JSON file; it does not read the instrument.",
             source="upstream_code", ref="dlccontrol.py:405-414"),
        Fact("close() only calls self.dlc.close().", source="upstream_code", ref="dlccontrol.py:180-183"),
    ]
    safe_state = "laser emission off: the DLCpro diode current is disabled (current_enabled = False)"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("emission", type="boolean", description="Emission status reported by the DLCpro")
    def emission(self):
        return bool(self.native.emission)

    @read("emission_button", type="boolean", description="Status of the emission button on the DLCpro console")
    def emission_button(self):
        return bool(self.native.emission_button)

    @read("current_enabled", type="boolean", description="True while the laser diode current is enabled")
    def current_enabled(self):
        return bool(self.native.current_enabled)

    @read("wavelength_actual", unit="nm", description="Actual wavelength reported by the laser")
    def wavelength_actual(self):
        value = self.native.wavelength_actual
        return None if value is None else float(value)

    @read("wavelength_setpoint", unit="nm", description="Wavelength setpoint of the laser")
    def wavelength_setpoint(self):
        value = self.native.wavelength_setpoint
        return None if value is None else float(value)

    @read("temp_actual", unit="Cel", description="Actual diode temperature")
    def temp_actual(self):
        value = self.native.temp_actual
        return None if value is None else float(value)

    @read("temp_setpoint", unit="Cel", description="Diode temperature setpoint")
    def temp_setpoint(self):
        value = self.native.temp_setpoint
        return None if value is None else float(value)

    @read("scan_enabled", type="boolean", description="True while the internal scan is enabled")
    def scan_enabled(self):
        return bool(self.native.scan_enabled)

    @read("scan_output_channel", type="string", enum=["PC", "CC", "OutA", "OutB"],
          description="Output channel the internal scan is directed to")
    def scan_output_channel(self):
        return self.native.scan_output_channel.name

    @read("scan_frequency", unit="Hz", description="Internal scan frequency")
    def scan_frequency(self):
        return float(self.native.scan_frequency)

    @read("scan_amplitude", unit="1",
          description="Internal scan amplitude in the native unit of the selected output: V for PC, mA for CC")
    def scan_amplitude(self):
        return float(self.native.scan_amplitude)

    @read("scan_offset", unit="1",
          description="Internal scan offset in the native unit of the selected output: V for PC, mA for CC")
    def scan_offset(self):
        return float(self.native.scan_offset)

    @read("scan_start", unit="1",
          description="Internal scan start in the native unit of the selected output: V for PC, mA for CC")
    def scan_start(self):
        return float(self.native.scan_start)

    @read("scan_end", unit="1",
          description="Internal scan end in the native unit of the selected output: V for PC, mA for CC")
    def scan_end(self):
        return float(self.native.scan_end)

    @read("user_level", type="integer",
          description="User level of the connection: 3 normal, 2 maintenance, 1 service")
    def user_level(self):
        level = self.native.get_user_level()
        return int(getattr(level, "value", level))

    @read("device_limits", type="object",
          description="The wavelength, temperature, voltage, current and scan frequency ranges the wrapper queried")
    def device_limits(self):
        return self.native.get_limits_from_dlc()

    # -- writes -------------------------------------------------------------------------------------------------
    @write("current_enabled", type="boolean", risk="R3",
           description="Diode current enable")
    def set_current_enabled(self, value):
        self.native.current_enabled = bool(value)

    @write("scan_enabled", type="boolean", description="Scan enable")
    def set_scan_enabled(self, value):
        self.native.scan_enabled = bool(value)

    @write("wavelength_setpoint", unit="nm", description="Wavelength setpoint",
           limit=Limit.operator_required(
               "the wrapper queries the wavelength range from the DLC in get_limits_from_dlc and no text file "
               "states it; the site supplies the range of its laser in nm"))
    def set_wavelength_setpoint(self, value):
        if not self.native.wl_control_available:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the DLC reports that it has no wavelength control")
        self.native.wavelength_setpoint = float(value)

    @write("temp_setpoint", unit="Cel", description="Diode temperature",
           limit=Limit.operator_required(
               "the wrapper queries the temperature range from the DLC in get_limits_from_dlc and no text file "
               "states it; the site supplies the range of its diode in Cel"))
    def set_temp_setpoint(self, value):
        if not self.native.temp_control_available:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the DLC reports that it has no diode temperature control")
        self.native.temp_setpoint = float(value)

    @write("scan_frequency", unit="Hz", description="Scan frequency",
           limit=Limit(min=0.02, max=400, unit="Hz", source="upstream_code", ref="dlccontrol.py:267-268",
                       reason="the wrapper hard-codes its scan frequency bounds; the comment says the maximum was "
                              "not found in the manual"))
    def set_scan_frequency(self, value):
        self.native.scan_frequency = float(value)

    @write("scan_amplitude", unit="1",
           description="Scan amplitude (V/mA)",
           limit=Limit.operator_required(
               "the wrapper checks the scan amplitude against the range it queries from the DLC (piezo voltage "
               "or current clip) and no text file states that range; the site supplies it in the native unit of "
               "the selected scan output"))
    def set_scan_amplitude(self, value):
        self.native.scan_amplitude = float(value)

    @write("scan_offset", unit="1",
           description="Scan offset (V/mA)",
           limit=Limit.operator_required(
               "the wrapper checks the scan offset against the range it queries from the DLC (piezo voltage or "
               "current clip) and no text file states that range; the site supplies it in the native unit of the "
               "selected scan output"))
    def set_scan_offset(self, value):
        self.native.scan_offset = float(value)

    @write("scan_start", unit="1",
           description="Scan start (V/mA)",
           limit=Limit.operator_required(
               "the wrapper checks the scan start against the range it queries from the DLC (piezo voltage or "
               "current clip) and no text file states that range; the site supplies it in the native unit of the "
               "selected scan output"))
    def set_scan_start(self, value):
        self.native.scan_start = float(value)

    @write("scan_end", unit="1",
           description="Scan end (V/mA)",
           limit=Limit.operator_required(
               "the wrapper checks the scan end against the range it queries from the DLC (piezo voltage or "
               "current clip) and no text file states that range; the site supplies it in the native unit of the "
               "selected scan output"))
    def set_scan_end(self, value):
        self.native.scan_end = float(value)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.asvela.emission_off.v1", safe_state=True,
            description="Disable the laser diode current (the documented emission off control)",
            output={"current_enabled": Field("boolean",
                                             description="False once the diode current is disabled")})
    def emission_off(self):
        self.native.current_enabled = False
        if self.native.current_enabled:
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               "the DLC still reports the diode current enabled after it was disabled")
        return {"current_enabled": False}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="current_enabled")
    def stop_emission(self):
        """Disable the diode current; the clone documents no other native stop."""
        self.native.current_enabled = False
