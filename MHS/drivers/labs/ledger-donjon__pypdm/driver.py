"""OpenMHS driver for gh.ledger-donjon/pypdm: an AlphANOV PDM pulsed laser source over its binary serial link.

A direct Driver (decorated methods) over the upstream device class ``pypdm.pdm:PDM``.  The card named a SerialDriver,
but the PDM protocol is framed binary: every frame is a length byte, the device address, a numeric command id, the
data and an XOR checksum (pypdm/pdm.py:220-233), and the upstream builds each frame from parts at run time.  A command
table cannot reproduce those bytes and gate G7 cannot find them as text in the clone, so this package is a direct
Driver over the upstream class (DEVIATION FROM THE CARD, in RESULT.json notes).  Every call here is a plain ``def``.

* reads: the device address and protocol version, the laser activation flag and the interlock status, the measured
  temperature, the diode current in mA and in percent of the maximum, the maximum pulse and mean currents, the offset
  current, the pulse repetition frequency, the pulse width and the delay, the pulsed/continuous mode, the current
  source, the synchronization source and the delay line type;
* one action writes the frequency and the current instructions and applies them; there is no write of the pulse width
  or the delay in this package (both are read only);
* the native ``apply`` after setting the activation instruction is the e-stop and, as ``disable_emission``, the
  safe-state action: the upstream destructor does the same for safety (pypdm/pdm.py:294-299).

Every Fact cites a line of the clone at the pinned commit (a059c30e5054a9e1276769c18c4f13e56a404a6a).  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read


class Pdm(Driver):
    device_id = "pdm"
    device_kind = "optics.laser"
    mode = "hardware"
    #: R2, above the card's floor: a laser above class 1 is R2 (MHS/spec/04-safety.md), and a class 3B or 4 source is R3.  The model review raised it; the hardware backend
    #: of this model-written package stays refused until a human signs reviewed_by.
    risk = "R2"
    native = "pypdm.pdm:PDM"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePdm"}
    vendor = "AlphANOV"
    model = "PDM pulsed laser source"
    display_name = "AlphANOV PDM laser source (pypdm.pdm:PDM)"
    tags = ["laser", "pulsed-laser", "laser-diode", "serial", "binary-protocol"]
    facts = [
        Fact("PyPDM controls AlphANOV PDM laser sources, supports PDM protocol version 3.4 to 3.7 and lets daisy-chained "
             "devices share one serial link", source="vendor_doc", ref="README.md:4"),
        Fact("The documentation lists the PDM properties that can be read or changed: sync source, delay line type, "
             "frequency, pulse width, delay, offset current, current percentage, current, temperature, maximum current, "
             "current source, interlock status, activation and mode",
             source="vendor_doc", ref="docs/getting_started.rst:72-89"),
        Fact("The link opens the serial port at 125000 baud and frames a command as length, address, command id, data "
             "and a checksum", source="upstream_code", ref="pypdm/pdm.py:169-233"),
        Fact("The checksum is the XOR of the frame bytes minus one, modulo 256",
             source="upstream_code", ref="pypdm/pdm.py:188-197"),
        Fact("A response is a length byte, a status byte, the data and a checksum; a status other than OK raises "
             "StatusError", source="upstream_code", ref="pypdm/pdm.py:199-218"),
        Fact("The PDM constructor validates the protocol version: major 3 and minor 4 to 7",
             source="upstream_code", ref="pypdm/pdm.py:278-288"),
        Fact("The class states its bounds: MAX_DELAY 15000 ps, MAX_PULSE_WIDTH 1275000 ps and MAX_FREQUENCY 250000000 Hz",
             source="upstream_code", ref="pypdm/pdm.py:255-260"),
        Fact("The offset current setter refuses a value below 0 or above 150 mA",
             source="upstream_code", ref="pypdm/pdm.py:443-445"),
        Fact("The current percentage setter refuses a value below 0 or above 100",
             source="upstream_code", ref="pypdm/pdm.py:462-465"),
        Fact("The current in mA is current_percentage times maximum_current divided by 100",
             source="upstream_code", ref="pypdm/pdm.py:470-483"),
        Fact("The maximum pulse current and the maximum mean current are read from the device and cached",
             source="upstream_code", ref="pypdm/pdm.py:501-534"),
        Fact("InterlockStatus.CLOSED is 0 (the laser can pulse) and InterlockStatus.OPEN is 1 (it cannot pulse)",
             source="upstream_code", ref="pypdm/pdm.py:89-93"),
        Fact("The mode command reads the continuous or pulsed hardware switch: 0 for pulsed and 1 for continuous",
             source="upstream_code", ref="pypdm/pdm.py:579-592"),
        Fact("The activation is a boolean instruction and apply() makes the pending instructions effective",
             source="upstream_code", ref="pypdm/pdm.py:563-578"),
        Fact("apply() sends the APPLY_ALL_INSTRUCTIONS command, which makes all settings in volatile memory "
             "effective", source="upstream_code", ref="pypdm/pdm.py:601-606"),
        Fact("The destructor sets the activation to False and calls apply() for safety",
             source="upstream_code", ref="pypdm/pdm.py:294-299"),
        Fact("The synchronization sources are EXTERNAL_TTL_LVTTL 0, EXTERNAL_LVDS 1 and INTERNAL 2; the delay line "
             "types are NONE 0 and INTERNAL 1; the current sources are ANALOG 0 and NUMERIC 1",
             source="upstream_code", ref="pypdm/pdm.py:131-157"),
    ]
    safe_state = "laser activation set to False and applied (the upstream destructor's safety action)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("address", type="integer",
          description="Device address the PDM answers on (the address byte of every frame)")
    def address(self):
        return self.native.read_address()

    @read("protocol_version", type="string",
          description="PDM protocol version string the device reported, for example 3.7")
    def protocol_version(self):
        return self.native.read_protocol_version()

    @read("activation", type="boolean",
          description="True when the laser activation instruction is set (emission commanded); apply() makes it "
                      "effective")
    def activation(self):
        return self.native.activation

    @read("interlock_closed", type="boolean",
          description="True when the interlock status is closed, i.e. the laser can pulse")
    def interlock_closed(self):
        return self.native.interlock_status.value == 0

    @read("temperature", unit="Cel", description="Temperature of the PDM head in degrees Celsius")
    def temperature(self):
        return self.native.temperature

    @read("current", unit="mA", description="Diode current in mA, computed from the current percentage and the "
                                            "maximum pulse current")
    def current(self):
        return self.native.current

    @read("current_percentage", unit="%", description="Diode current as a percentage of the maximum pulse current")
    def current_percentage(self):
        return self.native.current_percentage

    @read("maximum_current", unit="mA", description="Maximum pulse current of this PDM, in mA")
    def maximum_current(self):
        return self.native.maximum_current

    @read("maximum_mean_current", unit="mA", description="Maximum mean current of this PDM, in mA")
    def maximum_mean_current(self):
        return self.native.maximum_mean_current

    @read("offset_current", unit="mA", description="Offset current in mA")
    def offset_current(self):
        return self.native.offset_current

    @read("frequency", type="integer", unit="Hz", description="Pulse repetition frequency in Hz")
    def frequency(self):
        return self.native.frequency

    @read("pulse_width", type="integer", unit="ps", description="Pulse width in ps")
    def pulse_width(self):
        return self.native.pulse_width

    @read("delay", type="integer", unit="ps", description="Delay between the synchronization signal and the pulse, in ps")
    def delay(self):
        return self.native.delay

    @read("operating_mode", type="string", enum=["pulsed", "continuous"],
          description="State of the continuous or pulsed hardware switch")
    def operating_mode(self):
        return self.native.mode.name.lower()

    @read("current_source", type="string", enum=["analog", "numeric"],
          description="Current source: numeric means the software sets the diode current")
    def current_source(self):
        return self.native.current_source.name.lower()

    @read("sync_source", type="string", enum=["external_ttl_lvttl", "external_lvds", "internal"],
          description="Synchronization source of the pulse generator")
    def sync_source(self):
        return self.native.sync_source.name.lower()

    @read("delay_line_type", type="string", enum=["none", "internal"],
          description="Delay line type of the pulse generator")
    def delay_line_type(self):
        return self.native.delay_line_type.name.lower()

    # -- the one action that writes -----------------------------------------------------------------------------
    @action(name="x-cap.ledger-donjon.configure_pulse.v1",
            description="Write the pulse frequency and the diode current instructions and apply them to the device",
            input={
                "frequency": Field("integer", unit="Hz", description="Pulse repetition frequency in Hz",
                                   limit=Limit(min=1, max=250000000, source="upstream_code",
                                               ref="pypdm/pdm.py:260-397")),
                "current_percentage": Field("number", unit="%", description="Diode current as a percentage of the "
                                                                          "maximum pulse current",
                                            limit=Limit(min=0, max=100, source="upstream_code",
                                                        ref="pypdm/pdm.py:462-465")),
                "offset_current": Field("number", unit="mA", description="Offset current in mA",
                                        limit=Limit(min=0, max=150, source="upstream_code",
                                                    ref="pypdm/pdm.py:443-445")),
            },
            output={
                "frequency": Field("integer", unit="Hz", description="Frequency the device holds after the apply"),
                "current_percentage": Field("number", unit="%", description="Current percentage the device holds "
                                                                           "after the apply"),
                "offset_current": Field("number", unit="mA", description="Offset current the device holds after the "
                                                                        "apply"),
            })
    def configure_pulse(self, frequency, current_percentage, offset_current):
        self.native.frequency = frequency
        self.native.current_percentage = current_percentage
        self.native.offset_current = offset_current
        self.native.apply()
        return {
            "frequency": self.native.frequency,
            "current_percentage": self.native.current_percentage,
            "offset_current": self.native.offset_current,
        }

    # -- safety -------------------------------------------------------------------------------------------------------
    @action(name="x-cap.ledger-donjon.disable_emission.v1", safe_state=True,
            description="Clear the laser activation instruction and apply it (the native safe state); it takes no input",
            output={"activation": Field("boolean", description="False once the laser activation is cleared")})
    def disable_emission(self):
        self.native.activation = False
        self.native.apply()
        return {"activation": self.native.activation}

    @estop
    def stop(self):
        """The native stop: clear the activation instruction, then apply it."""
        self.native.activation = False
        self.native.apply()
