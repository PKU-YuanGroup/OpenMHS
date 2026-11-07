"""OpenMHS driver for gh.steinkohl/korad_powersupply: a Korad KC3405P supply over UDP.

A direct Driver (decorated methods) over the upstream class ``korad:KC3405P`` (korad.py:28).  The upstream object
opens a UDP socket in its constructor (korad.py:33-36) and every method sends one line ``<COMMAND>\\r\\n``
(korad.py:38-41) built from a class-owned word and a channel number (``VOUT{channel}?``, korad.py:94), so a command
table cannot reproduce the interface and this package is a direct driver with a ``native.py`` factory.

* reads: the measured voltage and current of the controlled channel (``VOUT<channel>?`` / ``IOUT<channel>?``,
  korad.py:92-102), the voltage and current set points (``VSET<channel>?`` / ``ISET<channel>?``, korad.py:104-114),
  the overvoltage and overcurrent protection settings and their on/off states (korad.py:184-256), the channel's
  output state and regulation mode (korad.py:71-90), the device information document (korad.py:49-69) and the
  whole status document;
* writes: the two set points and the two protection settings.  No text of the clone states an output voltage,
  output current or protection range: the class constants are starting values, not bounds.  Each numeric write is
  therefore ``Limit.operator_required`` and is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range
  of its unit (``site-limits.example.json`` shows the overlay).  The output and protection on/off states are
  boolean writes;
* capabilities: ``cap.measure.voltage.v1`` and ``cap.measure.current.v1`` take one sample of the controlled channel;
* the native stop is ``KC3405P.disable_output(0)``: ``OUT1234:0`` disables all four outputs (korad.py:164-182);
  the ``x-cap`` action ``output_off`` is the safe-state action.  The e-stop and the safe-state action send the same
  ``OUT1234:0`` line through the native ``_send_command`` path (korad.py:38-41) instead of ``disable_output(0)``,
  which would wait for a ``STATUS?`` reply on a blocking receive (korad.py:43-44, 71-76).

The driver controls one channel of the four-channel supply; the channel is the backend option ``channel``
(default 1).  The other channels are not bound by this package.  Every Fact cites a line of the clone at the pinned
commit fd2e8b7c59a4dd9f9e609bdacf15b3d7bc1b3d5e.  This package is model-authored and unreviewed: the acceptance gate
checks the fake backend only and nothing here ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class KoradPowersupply(Driver):
    device_id = "korad-psu"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R2"
    native = "korad:KC3405P"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKC3405P"}
    vendor, model = "Korad", "KC3405P"
    display_name = "Korad KC3405P power supply (korad.KC3405P)"
    tags = ["power supply", "psu", "udp", "voltage", "current", "protection"]
    facts = [
        Fact("KC3405P is the class of the Korad KC3405 power supply controlled over Ethernet", source="vendor_doc",
             ref="README.md:2"),
        Fact("KC3405P opens a UDP socket and binds it to the configured port (constructor default 18190)",
             source="upstream_code", ref="korad.py:33-36"),
        Fact("_send_command sends the command followed by CRLF over the UDP socket", source="upstream_code",
             ref="korad.py:38-41"),
        Fact("get_device_info queries ':SYST:DEVINFO?' and reads eight reply lines into a dictionary",
             source="upstream_code", ref="korad.py:49-68"),
        Fact("get_status reads 'STATUS?' and maps its bits to CV/CC mode and on/off output for channels 1 to 4",
             source="upstream_code", ref="korad.py:71-90"),
        Fact("The measured voltage and current are queried with VOUT<channel>? and IOUT<channel>?",
             source="upstream_code", ref="korad.py:92-102"),
        Fact("The voltage and current setpoints are queried with VSET<channel>? and ISET<channel>?",
             source="upstream_code", ref="korad.py:104-114"),
        Fact("set_voltage writes VSET<channel>:<value> with three decimals and verifies the readback within 0.01 V",
             source="upstream_code", ref="korad.py:116-124"),
        Fact("set_current writes ISET<channel>:<value> with three decimals and verifies the readback within 0.01 A",
             source="upstream_code", ref="korad.py:126-134"),
        Fact("enable_output(0) writes OUT1234:1 and disable_output(0) writes OUT1234:0; a channel number writes "
             "OUT<channel>:1 or OUT<channel>:0", source="upstream_code", ref="korad.py:144-182"),
        Fact("The overcurrent protection setting is read with OCPSET<channel>? and written with "
             "OCPSET<channel>:<value>", source="upstream_code", ref="korad.py:184-197"),
        Fact("The overvoltage protection setting is read with OVPSET<channel>? and written with "
             "OVPSET<channel>:<value>", source="upstream_code", ref="korad.py:199-212"),
        Fact("OCP<channel>? reads the overcurrent protection state; OCP<channel>:1 and OCP<channel>:0 enable and "
             "disable it", source="upstream_code", ref="korad.py:214-234"),
        Fact("OVP<channel>? reads the overvoltage protection state; OVP<channel>:1 and OVP<channel>:0 enable and "
             "disable it", source="upstream_code", ref="korad.py:236-256"),
        Fact("get_settings reads the device information, the status and, for each channel 1 to 4, the protection "
             "settings and states, the voltage and current setpoints and the measured voltage and current",
             source="upstream_code", ref="korad.py:334-357"),
        Fact("The clone's _check_channel states that a channel must be between 1 and 4", source="upstream_code",
             ref="korad.py:21-25"),
        Fact("get_settings iterates the channels with range(1, 5)", source="upstream_code", ref="korad.py:338"),
    ]
    safe_state = "all outputs commanded off (OUT1234:0 sent through the native send path)"

    @property
    def channel(self):
        """The output channel this binding controls (backend option ``channel``, default 1)."""
        return int(self.options.get("channel", 1))

    def _named_channel(self, channel):
        """The controlled channel, after checking that a requested channel name agrees with it."""
        if channel is None:
            return self.channel
        text = str(channel).strip().lower()
        if text.startswith("ch"):
            text = text[2:]
        try:
            requested = int(text)
        except (TypeError, ValueError):
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"channel {channel!r} is not a channel of this binding (it controls channel {self.channel})") from None
        if requested != self.channel:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"the binding controls channel {self.channel}; a measurement of channel {requested} is not bound")
        return self.channel

    def _stop_all_outputs(self):
        """Send OUT1234:0 through the native send path, without waiting for a status reply."""
        self.native._send_command("OUT1234:0")

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("channel", type="integer",
          description="Output channel this binding controls (the backend option 'channel'; the clone states "
                      "channels 1 to 4)")
    def controlled_channel(self):
        return self.channel

    @read("voltage", unit="V",
          description="Measured output voltage of the controlled channel (VOUT<channel>?)")
    def voltage(self):
        return float(self.native.get_voltage(self.channel))

    @read("current", unit="A",
          description="Measured output current of the controlled channel (IOUT<channel>?)")
    def current(self):
        return float(self.native.get_current(self.channel))

    @read("voltage_setpoint", unit="V",
          description="Voltage set point of the controlled channel (VSET<channel>?)")
    def voltage_setpoint(self):
        return float(self.native.get_voltage_setting(self.channel))

    @read("current_setpoint", unit="A",
          description="Current set point of the controlled channel (ISET<channel>?)")
    def current_setpoint(self):
        return float(self.native.get_current_setting(self.channel))

    @read("overvoltage_protection_setpoint", unit="V",
          description="Overvoltage protection setting of the controlled channel (OVPSET<channel>?)")
    def overvoltage_protection_setpoint(self):
        return float(self.native.get_overvoltage_protection_setting(self.channel))

    @read("overcurrent_protection_setpoint", unit="A",
          description="Overcurrent protection setting of the controlled channel (OCPSET<channel>?)")
    def overcurrent_protection_setpoint(self):
        return float(self.native.get_overcurrent_protection_setting(self.channel))

    @read("overvoltage_protection_enabled", type="boolean",
          description="True while OVP<channel>? reports overvoltage protection enabled")
    def overvoltage_protection_enabled(self):
        return bool(self.native.get_ovp_status(self.channel))

    @read("overcurrent_protection_enabled", type="boolean",
          description="True while OCP<channel>? reports overcurrent protection enabled")
    def overcurrent_protection_enabled(self):
        return bool(self.native.get_ocp_status(self.channel))

    @read("output_enabled", type="boolean",
          description="True while the status byte reports the controlled channel's output on")
    def output_enabled(self):
        return self.native.get_status()[f"ch{self.channel}_output"] == "on"

    @read("regulation_mode", type="string",
          description="Regulation mode of the controlled channel from the status byte: cv or cc")
    def regulation_mode(self):
        return self.native.get_status()[f"ch{self.channel}_mode"]

    @read("device_info", type="object",
          description="Device information document returned by ':SYST:DEVINFO?'")
    def device_info(self):
        return self.native.get_device_info()

    @read("status", type="object",
          description="Status document of all four channels from 'STATUS?'")
    def status(self):
        return self.native.get_status()

    # -- writes --------------------------------------------------------------------------------------------------
    @write("voltage_setpoint", unit="V",
           description="Voltage set point of the controlled channel, written as VSET<channel>:<value>",
           limit=Limit.operator_required(
               "no text of the clone states an output voltage bound: set_voltage passes the value into "
               "VSET<channel> (korad.py:116-124) and the class constant _default_voltage is only a starting value; "
               "the site supplies the range of its installed supply"))
    def set_voltage_setpoint(self, value):
        self.native.set_voltage(self.channel, float(value))
        return float(self.native.get_voltage_setting(self.channel))

    @write("current_setpoint", unit="A",
           description="Current set point of the controlled channel, written as ISET<channel>:<value>",
           limit=Limit.operator_required(
               "no text of the clone states an output current bound: set_current passes the value into "
               "ISET<channel> (korad.py:126-134) and the class constant _default_current is only a starting value; "
               "the site supplies the range of its installed supply"))
    def set_current_setpoint(self, value):
        self.native.set_current(self.channel, float(value))
        return float(self.native.get_current_setting(self.channel))

    @write("overvoltage_protection_setpoint", unit="V",
           description="Overvoltage protection setting, written as OVPSET<channel>:<value>",
           limit=Limit.operator_required(
               "no text of the clone states an overvoltage protection bound: set_overvoltage_protection passes "
               "the value into OVPSET<channel> (korad.py:205-212) and the class constant _default_ovp is only a "
               "starting value; the site supplies the protection range of its installed supply"))
    def set_overvoltage_protection_setpoint(self, value):
        self.native.set_overvoltage_protection(self.channel, float(value))
        return float(self.native.get_overvoltage_protection_setting(self.channel))

    @write("overcurrent_protection_setpoint", unit="A",
           description="Overcurrent protection setting, written as OCPSET<channel>:<value>",
           limit=Limit.operator_required(
               "no text of the clone states an overcurrent protection bound: set_overcurrent_protection passes "
               "the value into OCPSET<channel> (korad.py:190-197) and the class constant _default_ocp is only a "
               "starting value; the site supplies the protection range of its installed supply"))
    def set_overcurrent_protection_setpoint(self, value):
        self.native.set_overcurrent_protection(self.channel, float(value))
        return float(self.native.get_overcurrent_protection_setting(self.channel))

    @write("overvoltage_protection_enabled", type="boolean",
           description="Enable (OVP<channel>:1) or disable (OVP<channel>:0) overvoltage protection")
    def set_overvoltage_protection_enabled(self, value):
        if value:
            self.native.enable_overvoltage_protection(self.channel)
        else:
            self.native.disable_overvoltage_protection(self.channel)
        return bool(self.native.get_ovp_status(self.channel))

    @write("overcurrent_protection_enabled", type="boolean",
           description="Enable (OCP<channel>:1) or disable (OCP<channel>:0) overcurrent protection")
    def set_overcurrent_protection_enabled(self, value):
        if value:
            self.native.enable_overcurrent_protection(self.channel)
        else:
            self.native.disable_overcurrent_protection(self.channel)
        return bool(self.native.get_ocp_status(self.channel))

    @write("output_enabled", type="boolean",
           description="Enable (OUT<channel>:1) or disable (OUT<channel>:0) the controlled channel's output")
    def set_output_enabled(self, value):
        if value:
            self.native.enable_output(self.channel)
        else:
            self.native.disable_output(self.channel)
        return self.native.get_status()[f"ch{self.channel}_output"] == "on"

    # -- capabilities --------------------------------------------------------------------------------------------
    @action(cap="cap.measure.voltage.v1",
            description="Read one measured output voltage sample of the controlled channel (VOUT<channel>?)",
            input={"dc": Field("boolean",
                               description="True for the DC output reading that VOUT<channel>? returns; the "
                                           "clone has no RMS query"),
                   "channel": Field("string",
                                    description="Channel name to check against the binding's controlled channel; "
                                                "omit it to measure the controlled channel")})
    def measure_voltage(self, dc=True, channel=None):
        if not dc:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                "the upstream get_voltage queries VOUT<channel>?, a DC output reading; an RMS measurement is not "
                "supported")
        target = self._named_channel(channel)
        return {"voltage": float(self.native.get_voltage(target))}

    @action(cap="cap.measure.current.v1",
            description="Read one measured output current sample of the controlled channel (IOUT<channel>?)",
            input={"channel": Field("string",
                                    description="Channel name to check against the binding's controlled channel; "
                                                "omit it to measure the controlled channel")})
    def measure_current(self, channel=None):
        target = self._named_channel(channel)
        return {"current": float(self.native.get_current(target))}

    @action(name="x-cap.steinkohl.output_off.v1", safe_state=True,
            description="Send OUT1234:0 to all four outputs through the native send path (the safe state); it takes "
                        "no input and does not wait for a status reply",
            output={"output_enabled": Field("boolean",
                                            description="False: the OUT1234:0 stop line was sent to all four "
                                                        "outputs without waiting for a status reply")})
    def output_off(self):
        self._stop_all_outputs()
        return {"output_enabled": False}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: OUT1234:0 goes to all four outputs through the native send path (korad.py:38-41)."""
        self._stop_all_outputs()
