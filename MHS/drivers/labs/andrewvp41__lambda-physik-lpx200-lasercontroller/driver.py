"""OpenMHS driver for gh.andrewvp41/lambda-physik-lpx200-lasercontroller: the Lambda Physik LPX 200 laser.

A direct Driver over the upstream command builder ``LPX200:Control``.  The clone has no transport class: ``main``
opens a pyvisa resource (``ASRL4::INSTR``, CR terminators) and the module-level ``commRes`` sends every line with
``laser_instr.query``.  The lines are proprietary ASCII built from parts (``OPMODE=`` plus a value, ``MODE=`` plus
one of three mode names, ``REPRATE=`` plus a number), which a SCPI/Serial command table cannot reproduce without
changing the wire syntax; the card's ``family-config``/``ScpiDriver`` shape therefore became a direct driver with a
``native.py`` factory that opens the same pyvisa resource (RESULT.json records the deviation).

* reads: the operational mode, trigger mode, running mode, repetition rate, charging voltage, beam output energy,
  tube pressure and gas mixture;
* writes: repetition rate, charging voltage, beam output energy, running mode and trigger mode.  No text file of the
  clone states a numeric range for the rate, voltage or energy, so those three writes are ``operator_required`` and
  are refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the rated range of its unit
  (``site-limits.example.json`` is an example overlay, not a statement about a unit);
* actions: start emission (``OPMODE=ON``) and stop emission (``OPMODE=OFF``, also the safe-state action);
* the ``@estop`` sends ``OPMODE=OFF``, the command of the RUN STOP key when the laser is running.

Risk is R3: the clone reads and sets the charging high voltage of the laser (``HV`` in kV, LPX200.py:61 and 142;
README.md:71), and MHS-004 classes high voltage as R3.  The independent stop is the ``x-cap.andrewvp41.emission_off``
action declared ``safe_state=True``; the clone has no e-stop input of its own.  The backend method is
``evaluate`` because the upstream ``Control`` stores the module-level ``commRes`` query function in
``self.evaluate`` and calls it with the command text (LPX200.py:92, 98 and 283).  This package is model-authored and
unreviewed: the loader refuses its hardware backend until a human signs ``reviewed_by`` in driver.lock.json.

Every Fact and Limit cites a line of the clone at the pinned commit
abd240f534a93923342ae6bef374e9d9885b8776.  Nothing here imports or runs the upstream GUI.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


def _number_text(value: float) -> str:
    """The command text of a number in the way the keypad would append it: no exponent, no trailing zeros."""
    return f"{float(value):g}"


class Lpx200(Driver):
    device_id = "lpx200"
    device_kind = "optics.laser"
    mode = "hardware"
    #: R3, above the card's R0 floor: the device sets a charging high voltage (MHS-004 section 2.1 lists high
    #: voltage as R3).  A model-written R3 package never runs its hardware backend until reviewed_by is signed.
    risk = "R3"
    native = "LPX200:Control"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLpx200"}
    vendor, model = "Lambda Physik", "LPX 200"
    display_name = "Lambda Physik LPX 200 laser"
    tags = ["laser", "lpx200", "lambda-physik", "pyvisa", "serial"]
    facts = [
        Fact("The project is remote control software for controlling, monitoring and data collection on the LPX200 "
             "laser, mimicking the Lambda Physik handheld keypad", source="vendor_doc", ref="README.md:1-2"),
        Fact("The program opens the pyvisa resource ASRL4::INSTR and sets CR as both the write and the read "
             "termination, so the link is a line-oriented ASCII serial port", source="upstream_code",
             ref="LPX200.py:266-270"),
        Fact("commRes sends every command with laser_instr.query and answers 'Not a valid Command' when the query "
             "raises", source="upstream_code", ref="LPX200.py:251-256"),
        Fact("The status line queries MODE?, REPRATE?, HV?, EGY?, PRESSURE? and Menu?, and prints the values in Hz, "
             "kV, mJ and mbar; the third field of the Menu? reply is the gas mixture", source="upstream_code",
             ref="LPX200.py:61"),
        Fact("The running modes are HV, EGY PGR and EGY NGR", source="upstream_code", ref="LPX200.py:86"),
        Fact("The gas lines are BUFFER, HALOGEN, INERT and RARE", source="upstream_code", ref="LPX200.py:87"),
        Fact("The RUN STOP key reads OPMODE? and writes OPMODE=OFF when it is ON, otherwise OPMODE=ON",
             source="upstream_code", ref="LPX200.py:108-111"),
        Fact("The TRIG INT/EXT key reads TRIGGER? and writes TRIGGER=EXT when it is INT, otherwise TRIGGER=INT",
             source="upstream_code", ref="LPX200.py:113-118"),
        Fact("The MODE key sends MODE= followed by one of the running mode names", source="upstream_code",
             ref="LPX200.py:120-122"),
        Fact("The REP RATE key sends the REPRATE= prefix and the COUNTS SEL key sends the COUNTS= prefix",
             source="upstream_code", ref="LPX200.py:124-130"),
        Fact("The HV key builds HV= as the prefix of the value typed on the keypad", source="upstream_code",
             ref="LPX200.py:140-142"),
        Fact("The EGY key builds EGY= as the prefix of the value typed on the keypad", source="upstream_code",
             ref="LPX200.py:156-158"),
        Fact("The gas routines build OPMODE=NEW FILL, OPMODE=FLUSH <line> LINE, OPMODE=PURGE <line> LINE, "
             "OPMODE=PURGE RESERVOIR and OPMODE=ENERGY CAL", source="upstream_code", ref="LPX200.py:132-170"),
        Fact("The REPRATE value is specified in Hz, the HV value is the charging voltage, and the EGY value is the "
             "beam output energy specified in mJ", source="vendor_doc", ref="README.md:69-73"),
        Fact("The RUN STOP key starts and stops laser operation; when the laser is running, pressing it immediately "
             "stops laser emission", source="vendor_doc", ref="README.md:58-59"),
        Fact("The gas actions are required for maintenance and should only be carried out by correspondingly "
             "authorized and trained personnel", source="vendor_doc", ref="README.md:90"),
        Fact("LaserData.py queries opmode?, trigger?, reprate?, hv?, egy?, pressure?, mode? and menu?, and splits the "
             "menu reply into gas menu number, wavelength and gas mixture", source="upstream_code",
             ref="LaserData.py:19-25"),
    ]
    safe_state = "laser emission stopped with OPMODE=OFF (the RUN STOP stop command)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("operating_mode", type="string",
          description="Operational mode reported by OPMODE? (ON while laser operation is running)")
    def operating_mode(self):
        return self._query("OPMODE?")

    @read("trigger_mode", type="string", description="Trigger mode reported by TRIGGER? (INT or EXT)")
    def trigger_mode(self):
        return self._query("TRIGGER?")

    @read("mode", type="string",
          description="Running mode reported by MODE? (HV, EGY PGR or EGY NGR)")
    def running_mode(self):
        return self._query("MODE?")

    @read("repetition_rate", unit="Hz", description="Repetition rate reported by REPRATE?")
    def repetition_rate(self):
        return self._number("REPRATE?")

    @read("high_voltage", unit="kV", description="Charging voltage reported by HV?")
    def high_voltage(self):
        return self._number("HV?")

    @read("energy", unit="mJ", description="Beam output energy reported by EGY?")
    def energy(self):
        return self._number("EGY?")

    @read("pressure", unit="mbar", description="Laser tube pressure reported by PRESSURE?")
    def pressure(self):
        return self._number("PRESSURE?")

    @read("gas_mix", type="string",
          description="Gas mixture: the third field of the Menu? reply (gas menu number, wavelength, gas mixture)")
    def gas_mix(self):
        parts = self._query("Menu?").split()
        if len(parts) < 3:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the Menu? reply has fewer than three fields (gas menu number, wavelength, gas "
                               "mixture)")
        return parts[2]

    # -- writes -------------------------------------------------------------------------------------------------
    @write("repetition_rate", unit="Hz",
           description="Repetition rate for internally triggered operation, sent as REPRATE=",
           limit=Limit.operator_required(
               "no text file of the clone states the repetition-rate range of the LPX 200 (README.md:70 only names "
               "the unit Hz); the site supplies the rated range of its unit in Hz"))
    def set_repetition_rate(self, value):
        self._command(f"REPRATE={_number_text(value)}")
        return self._number("REPRATE?")

    @write("high_voltage", unit="kV",
           description="Charging voltage for HV constant mode, sent as HV=",
           limit=Limit.operator_required(
               "no text file of the clone states the charging-voltage range of the LPX 200 (README.md:71 only names "
               "the charging voltage; LPX200.py:61 shows the unit kV); the site supplies the rated range of its "
               "unit in kV"))
    def set_high_voltage(self, value):
        self._command(f"HV={_number_text(value)}")
        return self._number("HV?")

    @write("energy", unit="mJ",
           description="Beam output energy for energy constant mode, sent as EGY=",
           limit=Limit.operator_required(
               "no text file of the clone states the beam-energy range of the LPX 200 (README.md:72 only names the "
               "unit mJ); the site supplies the rated range of its unit in mJ"))
    def set_energy(self, value):
        self._command(f"EGY={_number_text(value)}")
        return self._number("EGY?")

    @write("mode", type="string",
           description="Running mode, sent as MODE= followed by the selected mode name",
           limit=Limit(allowed=["HV", "EGY PGR", "EGY NGR"], source="upstream_code", ref="LPX200.py:86",
                       reason="the clone lists exactly these three running mode names"))
    def set_mode(self, value):
        self._command(f"MODE={value}")
        return self._query("MODE?")

    @write("trigger_mode", type="string",
           description="Trigger mode, sent as TRIGGER=INT or TRIGGER=EXT",
           limit=Limit(allowed=["INT", "EXT"], source="upstream_code", ref="LPX200.py:113-118",
                       reason="the clone toggles between exactly these two trigger modes"))
    def set_trigger_mode(self, value):
        self._command(f"TRIGGER={value}")
        return self._query("TRIGGER?")

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.andrewvp41.emission_on.v1",
            description="Start laser operation with OPMODE=ON (the RUN STOP start command)",
            output={"operating_mode": Field("string",
                                            description="Operational mode reported after the command")})
    def emission_on(self):
        self._command("OPMODE=ON")
        return {"operating_mode": self._query("OPMODE?")}

    @action(name="x-cap.andrewvp41.emission_off.v1", safe_state=True,
            description="Stop laser emission with OPMODE=OFF (the RUN STOP stop command); takes no input",
            output={"operating_mode": Field("string",
                                            description="Operational mode reported after the command")})
    def emission_off(self):
        self._command("OPMODE=OFF")
        return {"operating_mode": self._query("OPMODE?")}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends OPMODE=OFF."""
        self._command("OPMODE=OFF")

    # -- private translation --------------------------------------------------------------------------------------
    def _query(self, command: str) -> str:
        reply = self.native.evaluate(command)
        if not isinstance(reply, str) or not reply.strip():
            raise DriverFailed("MHS.DEVICE.FAULTED", f"no reply to {command}")
        return reply.strip()

    def _number(self, command: str) -> float:
        text = self._query(command)
        try:
            return float(text.split()[0])
        except (IndexError, ValueError) as exc:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"{command} replied {text!r}, which is not a number") from exc

    def _command(self, line: str) -> None:
        self.native.evaluate(line)
