"""OpenMHS driver for gh.scopefoundry/hw_acton_spec: a Princeton Instruments / Acton spectrometer over RS-232.

A direct Driver (decorated methods) over the serial interface class ``acton_spec_interface:ActonSpectrometer``
(acton_spec_interface.py:7), one of the two AST entry symbols of the task card.  The card's other entry symbol,
``acton_spec:ActonSpectrometerHW`` (acton_spec.py:19), is the ScopeFoundry settings component: it creates the serial
class in ``connect()`` (acton_spec.py:61-68) and forwards every setting to it, so the serial class is the object that
owns the hardware commands.  The component itself needs ScopeFoundry at import time and adds no device command.

The clone calls the instrument a "Princeton Instruments / Acton 2300i Spectrometer plug-in" that uses the RS-232 or
USB-serial interface and was tested with Acton 2300i and 300 series spectrometers (README.md:4-8).  Its commands are
ASCII lines terminated by CR (acton_spec_interface.py:171-172); a reply is accepted only when it ends with
`` ok\\r\\n`` (acton_spec_interface.py:200).

* reads: the current wavelength (``?NM``), the last-move-done flag (``MONO-?DONE``), the grating number and name
  (``?GRATING``/``?GRATINGS``), the turret (``?TURRET``), the exit mirror (``EXIT-MIRROR ?MIRROR``), and the entrance
  and exit slit widths (``SIDE-ENT-SLIT ?MICRONS``/``SIDE-EXIT-SLIT ?MICRONS``);
* writes: the center wavelength through ``write_wl_fast`` (``GOTO``, the method the ScopeFoundry component connects
  center_wl to, acton_spec.py:75-78), the grating (``<n> GRATING``), both slit widths (``... <n> MICRONS``) and the
  exit mirror (``EXIT-MIRROR FRONT|SIDE``).  The clone states no wavelength range of a spectrometer: center_wl is
  ``Limit.operator_required`` and the site supplies the range of its unit;
* the native e-stop is ``close()``.  The clone has no stop or abort command; closing the serial link stops all
  further commands from this driver but does not halt a move already executing in the instrument.

The upstream ``write_turret`` only asserts a turret of 1 to 3 and sends no command (acton_spec_interface.py:95-97), and
``home_entrance_slit`` is a TODO that only holds the string ``SIDE-ENT-SLIT SHOME`` (acton_spec_interface.py:140-142),
so neither is exposed.  ``get_wl_calibration`` is a pure calculation on the ScopeFoundry component
(acton_spec.py:121-152), not a command of the serial class, so it is not exposed either.

Every Fact cites a line of the clone at the pinned commit a4e112406b7fd275a8d23048631a21f0a82758e7.  This package is
model-authored and unreviewed: it is checked on the fake backend only and nothing here ran on a spectrometer.
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write

SERIAL = "acton_spec_interface.py"
HW = "acton_spec.py"

#: Why the center wavelength has no sourced device range.
CENTER_REASON = (
    "no text of the clone states the wavelength range of a spectrometer; the only wavelength range in the clone "
    "is the ScopeFoundry center_wl setting vmin=-100 vmax=2000 (acton_spec.py:37), a component default rather than "
    "an instrument specification, so the site supplies the nm range of its unit"
)


class ActonSpectrometerDriver(Driver):
    device_id = "acton-spectrometer"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R1"
    native = "acton_spec_interface:ActonSpectrometer"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeActonSpectrometer"}
    vendor, model = "Princeton Instruments / Acton", "Acton 2300i / 300 series"
    display_name = "Acton spectrometer (acton_spec_interface:ActonSpectrometer)"
    tags = ["spectrometer", "monochromator", "acton", "princeton-instruments", "serial", "grating", "slit"]
    facts = [
        Fact("The clone is a Princeton Instruments / Acton 2300i spectrometer plug-in that uses the RS-232 or "
             "USB-serial interface and was tested with Acton 2300i and 300 series spectrometers",
             source="vendor_doc", ref="README.md:4-8"),
        Fact("The serial interface opens the port at 9600 baud, 8 data bits, no parity and one stop bit with a 5.0 s "
             "timeout", source="upstream_code", ref=f"{SERIAL}:16-17"),
        Fact("A command is written as ASCII followed by CR (\\r)", source="upstream_code",
             ref=f"{SERIAL}:171-172"),
        Fact("A reply is accepted only when it ends with ' ok\\r\\n'", source="upstream_code",
             ref=f"{SERIAL}:200"),
        Fact("read_done_status sends MONO-?DONE and returns the reply as a boolean", source="upstream_code",
             ref=f"{SERIAL}:29-31"),
        Fact("read_wl sends ?NM and parses the first token of the reply as a float in nm",
             source="upstream_code", ref=f"{SERIAL}:33-37"),
        Fact("write_wl sends '<wavelength> NM', write_wl_fast sends '<wavelength> GOTO' and write_wl_nonblock sends "
             "'<wavelength> >NM', each with three decimals", source="upstream_code", ref=f"{SERIAL}:39-53"),
        Fact("read_grating_info sends ?GRATINGS and parses one (number, name) line per grating; read_grating sends "
             "?GRATING and returns the current number; read_grating_name returns the entry of the current grating",
             source="upstream_code", ref=f"{SERIAL}:55-106"),
        Fact("write_grating requires 0 < grating < 10 and sends '<grating> GRATING'", source="upstream_code",
             ref=f"{SERIAL}:108-110"),
        Fact("read_turret sends ?TURRET and returns an integer; write_turret only asserts a turret of 1, 2 or 3 and "
             "sends no command", source="upstream_code", ref=f"{SERIAL}:90-97"),
        Fact("read_exit_mirror sends 'EXIT-MIRROR ?MIRROR'; write_exit_mirror accepts FRONT or SIDE and sends "
             "'EXIT-MIRROR <pos>'", source="upstream_code", ref=f"{SERIAL}:112-120"),
        Fact("read_entrance_slit sends 'SIDE-ENT-SLIT ?MICRONS', reports -1 for 'no motor' or 'no slit'; "
             "write_entrance_slit accepts 5 to 3000 um and sends 'SIDE-ENT-SLIT <n> MICRONS'",
             source="upstream_code", ref=f"{SERIAL}:122-137"),
        Fact("read_exit_slit sends 'SIDE-EXIT-SLIT ?MICRONS', reports -1 for 'no motor' or 'no slit'; "
             "write_exit_slit accepts 5 to 3000 um and sends 'SIDE-EXIT-SLIT <n> MICRONS'",
             source="upstream_code", ref=f"{SERIAL}:145-157"),
        Fact("home_entrance_slit is a TODO that only holds the string 'SIDE-ENT-SLIT SHOME' and sends no command",
             source="upstream_code", ref=f"{SERIAL}:140-142"),
        Fact("The ScopeFoundry component connects center_wl to read_wl/write_wl_fast, grating_id to "
             "read_grating/write_grating, grating_name to read_grating_name, entrance_slit and exit_slit to their "
             "read/write methods and exit_mirror to read_exit_mirror/write_exit_mirror",
             source="upstream_code", ref=f"{HW}:74-102"),
        Fact("The ScopeFoundry component declares center_wl in nm with vmin=-100 and vmax=2000 (a setting range, "
             "not a stated instrument range)", source="upstream_code", ref=f"{HW}:30-40"),
        Fact("The HardwareComponent computes a per-pixel wavelength calibration in get_wl_calibration/wl_p_calib "
             "from the grating_calibrations setting; it is a pure calculation on the component, not a method of "
             "the serial interface", source="upstream_code", ref=f"{HW}:121-152"),
        Fact("close() closes the serial port", source="upstream_code", ref=f"{SERIAL}:217-218"),
    ]
    safe_state = ("serial link closed (close()); no further motion, grating or slit command is sent, and a move "
                  "already executing in the instrument is not halted")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("center_wl", unit="nm", description="Current center wavelength in nm (native ?NM)")
    def center_wl(self):
        return float(self.native.read_wl())

    @read("done_status", type="boolean",
          description="True when the monochromator reports that the last move is done (native MONO-?DONE)")
    def done_status(self):
        return bool(self.native.read_done_status())

    @read("grating_id", type="integer", unit="1",
          description="Current grating number (native ?GRATING)")
    def grating_id(self):
        return int(self.native.read_grating())

    @read("grating_name", type="string",
          description="Name of the current grating from the native ?GRATINGS list")
    def grating_name(self):
        entry = self.native.read_grating_name()
        if isinstance(entry, (tuple, list)) and len(entry) > 1:
            return str(entry[1])
        return str(entry)

    @read("turret", type="integer", unit="1", description="Current turret number (native ?TURRET)")
    def turret(self):
        return int(self.native.read_turret())

    @read("exit_mirror", type="string",
          description="Exit mirror position: FRONT (CCD) or SIDE (APD)")
    def exit_mirror(self):
        return str(self.native.read_exit_mirror())

    @read("entrance_slit", type="integer", unit="um",
          description="Entrance slit width in um; -1 when the device reports no motor or no slit")
    def entrance_slit(self):
        return int(self.native.read_entrance_slit())

    @read("exit_slit", type="integer", unit="um",
          description="Exit slit width in um; -1 when the device reports no motor or no slit")
    def exit_slit(self):
        return int(self.native.read_exit_slit())

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("center_wl", unit="nm",
           description="Move to a center wavelength in nm through the native GOTO command (write_wl_fast)",
           limit=Limit.operator_required(CENTER_REASON))
    def set_center_wl(self, value):
        self.native.write_wl_fast(float(value))
        return float(self.native.read_wl())

    @write("grating_id", type="integer", unit="1",
           description="Select a grating number (1 to 9; the native ?GRATINGS list names the installed ones)",
           limit=Limit(allowed=list(range(1, 10)), unit="1", source="upstream_code", ref=f"{SERIAL}:109",
                       reason="write_grating asserts 0 < grating < 10, so the integer range is 1 to 9"))
    def set_grating_id(self, value):
        self.native.write_grating(int(value))
        return int(self.native.read_grating())

    @write("entrance_slit", type="integer", unit="um",
           description="Set the entrance slit width in um",
           limit=Limit(min=5, max=3000, unit="um", source="upstream_code", ref=f"{SERIAL}:136"))
    def set_entrance_slit(self, value):
        self.native.write_entrance_slit(int(value))
        return int(self.native.read_entrance_slit())

    @write("exit_slit", type="integer", unit="um",
           description="Set the exit slit width in um",
           limit=Limit(min=5, max=3000, unit="um", source="upstream_code", ref=f"{SERIAL}:156"))
    def set_exit_slit(self, value):
        self.native.write_exit_slit(int(value))
        return int(self.native.read_exit_slit())

    @write("exit_mirror", type="string",
           description="Select the exit mirror: FRONT (CCD) or SIDE (APD)",
           limit=Limit(allowed=["FRONT", "SIDE"], source="upstream_code", ref=f"{SERIAL}:119"))
    def set_exit_mirror(self, value):
        position = str(value).upper()
        self.native.write_exit_mirror(position)
        return str(self.native.read_exit_mirror())

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="close")
    def stop(self):
        """The native stop: close the serial link; the clone has no stop or abort command."""
        self.native.close()

    # -- lifecycle ------------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.close()
