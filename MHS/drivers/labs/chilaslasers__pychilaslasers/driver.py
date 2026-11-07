"""OpenMHS driver for gh.chilaslasers/pychilaslasers: a Chilas Atlas or Comet tunable laser.

A direct Driver (decorated methods) over the upstream device class ``pychilaslasers.laser:Laser``.  The upstream
class owns one serial connection and exposes its hardware components as attributes created in ``__init__``:
``laser.diode`` (the laser diode: drive current and emission state) and ``laser.tec`` (the thermo-electric cooler:
measured temperature, target temperature and TEC current).  Every call here is a plain ``def``; the upstream library
is synchronous.

* reads: the laser system output state, the model and calibration flags, the diode emission state, the diode drive
  current and its maximum, the measured TEC temperature, the TEC target temperature and the TEC current;
* one write: the laser system output state (``SYST:STAT 0`` or ``SYST:STAT 1``);
* actions: turn the system on, turn the system and the diode off (also the safe-state action), send one trigger
  pulse, set the diode drive current and set the TEC target temperature;
* the diode current and the TEC target have no numeric range in the clone: the component objects query the connected
  laser for their limits at construction time (``LSR:IMAX?``, ``TEC:CFG:TMIN?`` and ``TEC:CFG:TMAX?``), so both
  action inputs are ``Limit.operator_required``.  Every call that sets them is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the operator's ``site-limits.json`` supplies the range of the unit;
  ``site-limits.example.json`` shows the overlay.

Risk is R2: MHS-004 (``MHS/spec/04-safety.md``) classes a laser above class 1 as R2.  The clone states no IEC laser
class, so this package does not claim class 1 and does not claim R3 (no class 3B or 4 statement).  The independent
stop is the ``turn_off`` action declared ``safe_state=True``: it disables the system output and the diode emission.

Every Fact cites a line of the clone at the pinned commit (ec9470e0042ccb86edb196e9834508f38dbf1b1a).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class ChilasLaser(Driver):
    device_id = "chilas-laser"
    device_kind = "optics.laser"
    mode = "hardware"
    #: R2, above the card's R1 floor: a laser above class 1 is R2 (MHS-004 "Risk classes"); a class 3B or 4
    #: source would be R3, and the clone states no class.  The hardware backend of this unreviewed model-written
    #: package stays refused until a human signs reviewed_by in driver.lock.json.
    risk = "R2"
    native = "pychilaslasers.laser:Laser"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeLaser"}
    vendor, model = "Chilas", "Atlas / Comet tunable laser"
    display_name = "Chilas Atlas/Comet tunable laser (pychilaslasers.laser:Laser)"
    tags = ["laser", "tunable-laser", "photonic-integrated-circuit", "laser-diode", "tec", "serial"]
    facts = [
        Fact("PyChilasLasers is the Python library for controlling the Chilas Atlas and Comet tunable lasers",
             source="vendor_doc", ref="README.md:4"),
        Fact("The laser is powered on with a side button and a key switch before the library connects to it",
             source="vendor_doc", ref="docs/quickstart.md:65"),
        Fact("During initialization the Laser constructor turns the laser on to read component information such as "
             "maximum values", source="upstream_code", ref="src/pychilaslasers/laser.py:99-102"),
        Fact("Laser.system_state reads SYST:STAT? and writes SYST:STAT 0 or SYST:STAT 1",
             source="upstream_code", ref="src/pychilaslasers/laser.py:232-259"),
        Fact("Laser.turn_on sets the system state to True and Laser.turn_off sets it to False",
             source="upstream_code", ref="src/pychilaslasers/laser.py:555-567"),
        Fact("The diode drive current is read with LSR:ILEV? and written with LSR:ILEV",
             source="upstream_code", ref="src/pychilaslasers/laser_components/diode.py:76-106"),
        Fact("The diode minimum current is 0.0 mA, its maximum is read from LSR:IMAX?, and its unit is mA",
             source="upstream_code", ref="src/pychilaslasers/laser_components/diode.py:50-52"),
        Fact("The diode state is read with LSR:STAT? and written with LSR:STAT 0 or LSR:STAT 1",
             source="upstream_code", ref="src/pychilaslasers/laser_components/diode.py:56-74"),
        Fact("Diode.turn_off sets the emission state to False and Diode.turn_on sets it to True",
             source="upstream_code", ref="src/pychilaslasers/laser_components/diode.py:152-164"),
        Fact("The TEC target temperature is read with TEC:TTGT? and written with TEC:TTGT, and the unit is "
             "degrees Celsius", source="upstream_code", ref="src/pychilaslasers/laser_components/tec.py:57-83"),
        Fact("The TEC target range is read from the laser at construction time (TEC:CFG:TMIN? and TEC:CFG:TMAX?)",
             source="upstream_code", ref="src/pychilaslasers/laser_components/tec.py:50-52"),
        Fact("The measured TEC temperature is read with TEC:TEMP? and reported in degrees Celsius",
             source="upstream_code", ref="src/pychilaslasers/laser_components/tec.py:85-88"),
        Fact("The TEC current is read with TEC:ITEC? in mA", source="upstream_code",
             ref="src/pychilaslasers/laser_components/tec.py:104-111"),
        Fact("Laser.trigger_pulse delegates to Trigger.pulse, which writes DRV:CYC:TRIG 1 then DRV:CYC:TRIG 0",
             source="upstream_code", ref="src/pychilaslasers/laser_components/trigger.py:36-39"),
        Fact("Laser.model returns the calibration model (ATLAS or COMET) and Laser.calibrated reports whether "
             "calibration data is loaded", source="upstream_code", ref="src/pychilaslasers/laser.py:482-500"),
    ]
    safe_state = "laser system output off and diode emission disabled (SYST:STAT 0, LSR:STAT 0)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("system_state", type="boolean",
          description="True while the laser system output is enabled (SYST:STAT)")
    def system_state(self):
        return bool(self.native.system_state)

    @read("model", type="string",
          description="Model stored in the loaded calibration (ATLAS or COMET); Unknown without a calibration")
    def model_name(self):
        return str(self.native.model)

    @read("calibrated", type="boolean",
          description="True when calibration data is loaded, which enables tune and sweep mode")
    def calibrated(self):
        return bool(self.native.calibrated)

    @read("diode_enabled", type="boolean",
          description="True while the laser diode emission is enabled (LSR:STAT)")
    def diode_enabled(self):
        return bool(self.native.diode.state)

    @read("diode_current", unit="mA",
          description="Diode drive current in mA (LSR:ILEV)")
    def diode_current(self):
        return float(self.native.diode.get_current())

    @read("diode_max_current", unit="mA",
          description="Maximum diode drive current this laser reports (LSR:IMAX)")
    def diode_max_current(self):
        return float(self.native.diode.max_value)

    @read("tec_temperature", unit="Cel",
          description="Measured TEC temperature of the laser in degrees Celsius (TEC:TEMP)")
    def tec_temperature(self):
        return float(self.native.tec.get_temp())

    @read("tec_target", unit="Cel",
          description="TEC target temperature in degrees Celsius (TEC:TTGT)")
    def tec_target(self):
        return float(self.native.tec.get_target_temp())

    @read("tec_current", unit="mA",
          description="Current applied to the TEC driver in mA (TEC:ITEC)")
    def tec_current(self):
        return float(self.native.tec.current)

    # -- the write of the system output -------------------------------------------------------------------------
    @write("system_state", type="boolean",
           description="Laser system output: True enables it (SYST:STAT 1), False disables it (SYST:STAT 0)")
    def set_system_state(self, value):
        self.native.system_state = bool(value)
        return bool(self.native.system_state)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.chilaslasers.turn_on.v1",
            description="Enable the laser system output (SYST:STAT 1)",
            output={"system_state": Field("boolean",
                                          description="True once the laser reports the system output enabled")})
    def turn_on(self):
        self.native.turn_on()
        return {"system_state": bool(self.native.system_state)}

    @action(name="x-cap.chilaslasers.turn_off.v1", safe_state=True,
            description="Disable the laser system output and the diode emission (SYST:STAT 0, LSR:STAT 0); takes no "
                        "input",
            output={"system_state": Field("boolean",
                                          description="False once the laser reports the system output disabled"),
                    "diode_enabled": Field("boolean",
                                           description="False once the laser reports the diode emission disabled")})
    def turn_off(self):
        self.native.turn_off()
        self.native.diode.turn_off()
        return {"system_state": bool(self.native.system_state),
                "diode_enabled": bool(self.native.diode.state)}

    @action(name="x-cap.chilaslasers.trigger_pulse.v1",
            description="Send one trigger pulse (DRV:CYC:TRIG 1 then DRV:CYC:TRIG 0); takes no input",
            output={"triggered": Field("boolean", description="True after the trigger commands were sent")})
    def trigger_pulse(self):
        self.native.trigger_pulse()
        return {"triggered": True}

    @action(name="x-cap.chilaslasers.set_diode_current.v1",
            description="Set the diode drive current in mA (LSR:ILEV)",
            input={"current_ma": Field("number", unit="mA",
                                       description="Diode drive current in mA",
                                       limit=Limit.operator_required(
                                           "the maximum diode current is read from the connected laser at "
                                           "construction time (LSR:IMAX?, diode.py:51) and no text file of the "
                                           "clone states a numeric maximum; the operator supplies the rated range "
                                           "of this unit"))},
            output={"current_ma": Field("number", unit="mA",
                                        description="Diode drive current the laser reports after the write")})
    def set_diode_current(self, current_ma):
        self.native.diode.set_current(current_ma)
        return {"current_ma": float(self.native.diode.get_current())}

    @action(name="x-cap.chilaslasers.set_tec_target.v1",
            description="Set the TEC target temperature in degrees Celsius (TEC:TTGT)",
            input={"target_temp": Field("number", unit="Cel",
                                        description="TEC target temperature in degrees Celsius",
                                        limit=Limit.operator_required(
                                            "the TEC target range is read from the connected laser at construction "
                                            "time (TEC:CFG:TMIN? and TEC:CFG:TMAX?, tec.py:51-52) and no text file "
                                            "of the clone states a numeric range; the operator supplies the rated "
                                            "range of this unit"))},
            output={"target_temp": Field("number", unit="Cel",
                                         description="TEC target temperature the laser reports after the write")})
    def set_tec_target(self, target_temp):
        self.native.tec.set_target(target_temp)
        return {"target_temp": float(self.native.tec.get_target_temp())}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop(native="Laser.turn_off")
    def stop(self):
        """The native stop: the runtime latches first, then disables the system output and the diode emission."""
        self.native.turn_off()
        self.native.diode.turn_off()
