"""OpenMHS driver for gh.biologytools/bioimager: the Cobolt laser of PythonMicroscope.

A direct Driver over the upstream device class
``PythonMicroscope.microscope.lights.cobolt:CoboltLaser``.  The upstream class is a serial device whose public
interface is the ``microscope.abc.LightSource`` contract:

* reads: whether the head reports emission on, the measured power and the power set point as fractions of the head
  maximum, and the five status lines of ``get_status()``;
* writes: the power set point (the native ``power`` property, which the upstream clips to [0, 1]) and the emission
  state (the native ``enable``/``disable`` methods);
* the safe-state action ``x-cap.biologytools.disable_laser.v1`` and the e-stop both call the native ``disable()``,
  which sends ``l0`` (cobolt.py:132-136).

No text file of the clone states the maximum optical power of a head: the constructor reads it from the device with
``gmlp?`` (cobolt.py:65).  This driver therefore exposes power as the upstream's fraction of that maximum, whose
[0, 1] contract is stated in the upstream code (abc.py:1232-1244), and never invents a milliwatt bound.

The clone does not state the laser class.  Cobolt's datasheets and owner's manuals class the 04-01 series heads as
Class 3B (IEC 60825-1) and higher-power heads as Class 4, so a model review declared the device and its emission write
R3 (MHS/spec/04-safety.md: class 3B+ laser), above the card's R1 floor; the safe-state action stays callable without a
permit (SAFE-029).

Every Fact cites a line of the clone at the pinned commit
149b45255d628cc4118b3829cd7c5b10c9c6cb07.  This package is model-authored and unreviewed: it is checked on the fake
backend only.  The loader refuses its hardware backend while ``reviewed_by`` is null because it is R3.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class CoboltLaserDriver(Driver):
    device_id = "bioimager-cobolt"
    device_kind = "optics.laser"
    mode = "hardware"
    risk = "R3"
    native = "PythonMicroscope.microscope.lights.cobolt:CoboltLaser"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCoboltLaser"}
    vendor, model = "Cobolt", "diode-pumped laser (PythonMicroscope CoboltLaser)"
    display_name = "Cobolt laser (PythonMicroscope)"
    tags = ["laser", "light-source", "cobolt", "serial"]
    safe_state = "laser emission off (the native disable sends l0)"
    facts = [
        Fact("CoboltLaser is a diode-pumped laser and supports only TriggerMode.SOFTWARE",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:37-43"),
        Fact("The constructor sends sn?, @cobas 0 to disable autostart and gmlp? to read the maximum power",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:57-65"),
        Fact("The serial connection is 115200 baud, 8 data bits, one stop bit and no parity by default",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:47-56"),
        Fact("get_status queries l?, p?, pa?, f? and hrs? and returns the five replies with their labels",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:87-99"),
        Fact("clearFault sends cf and returns get_status()", source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:82-85"),
        Fact("initialize sends @cobasdr 0 (leave direct-control mode) and @cob1 (force autostart)",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:108-115"),
        Fact("_do_enable sends l1 and returns False unless get_is_on() then reports emission on",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:117-130"),
        Fact("disable sends l0", source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:132-136"),
        Fact("get_is_on sends l? and treats the reply b'1' as emission on", source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:138-142"),
        Fact("_get_power_mw returns 0.0 while emission is off, otherwise reads pa? in W and returns 1000 times it",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:144-154"),
        Fact("_set_power_mw writes @cobasp with the power in W to four decimals and accepts any non-negative value",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:156-162"),
        Fact("_do_set_power multiplies the fraction by the head maximum and _do_get_power divides by it",
             source="upstream_code",
             ref="PythonMicroscope/microscope/lights/cobolt.py:164-168"),
        Fact("LightSource.power is the fraction of maximum power in the [0, 1] interval and its setter clips to it",
             source="upstream_code",
             ref="PythonMicroscope/microscope/abc.py:1232-1244"),
    ]

    # -- reads ------------------------------------------------------------------------------------------------
    @read("emission", type="boolean",
          description="True while the laser head reports emission on (native get_is_on, l?)")
    def emission(self):
        return self.native.get_is_on()

    @read("power", unit="1",
          description="Measured optical power as a fraction of the head maximum (native power property)")
    def power(self):
        return self.native.power

    @read("power_setpoint", unit="1",
          description="Power set point as a fraction of the head maximum (native get_set_power)")
    def power_setpoint(self):
        return self.native.get_set_power()

    @read("status", type="array", items="string", length=5,
          description="The five status lines returned by the native get_status")
    def status(self):
        return self.native.get_status()

    # -- writes -----------------------------------------------------------------------------------------------
    @write("power_setpoint", unit="1",
           description="Power set point as a fraction of the head maximum; the native property clips to [0, 1]",
           limit=Limit(min=0, max=1, source="upstream_code",
                       ref="PythonMicroscope/microscope/abc.py:1232-1244"))
    def set_power_setpoint(self, value):
        self.native.power = value
        return self.native.get_set_power()

    @write("emission", type="boolean", risk="R3",
           description="Turn laser emission on with the native enable() or off with the native disable()")
    def set_emission(self, value):
        if value:
            self.native.enable()
            if not self.native.get_is_on():
                raise DriverFailed("MHS.DEVICE.FAULTED",
                                   "the laser did not report emission on after enable()")
        else:
            self.native.disable()
        return self.native.get_is_on()

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.biologytools.disable_laser.v1", safe_state=True,
            description="Disable laser emission through the native disable(); it takes no input",
            output={"emission": Field("boolean",
                                      description="False once the laser reports emission off")})
    def disable_laser(self):
        self.native.disable()
        return {"emission": self.native.get_is_on()}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then the driver sends the native disable (l0)."""
        self.native.disable()
