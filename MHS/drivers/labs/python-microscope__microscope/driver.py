"""OpenMHS driver for gh.python-microscope/microscope: a Cobolt laser over its serial line.

A direct Driver (decorated methods) over the upstream device class
``microscope.lights.cobolt:CoboltLaser``.  The upstream class owns a ``serial.Serial`` connection and talks to
the controller with short ASCII commands; every call here is a plain ``def``, so each method calls
``self.native`` directly.

* reads: whether emission is on (``l?``), whether the device object is enabled, the power set point and the
  measured output power (both as a fraction of the head's maximum power, the [0, 1] interval the clone
  normalises to), and the status lines (emission, target power, measured power, fault, head operating hours);
* one write: the power set point, inside the [0, 1] interval the upstream ``LightSource.power`` property states;
* actions: switch emission on (the native ``enable``) and off (the native ``disable``, also the safe-state
  action); the native ``disable`` is the e-stop;
* the laser only supports software trigger in bulb mode, and the upstream trigger raises
  ``IncompatibleStateError`` in that mode, so no trigger capability is exposed.

Every Fact cites a line of the clone at the pinned commit (47c13d0342dca476a279f2de2da5b84ce2162326).  This
package is model-authored and unreviewed: it is checked on the fake backend only, and nothing ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class CoboltLaser(Driver):
    device_id = "cobolt-laser"
    device_kind = "optics.laser"
    mode = "hardware"
    #: R2, above the card's floor: a laser above class 1 is R2 (MHS/spec/04-safety.md), and a class 3B or 4 head is R3.  The model review raised it; the hardware backend
    #: of this model-written package stays refused until a human signs reviewed_by.
    risk = "R2"
    native = "microscope.lights.cobolt:CoboltLaser"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCoboltLaser"}
    vendor = "Cobolt"
    model = "Cobolt diode-pumped laser (04 series)"
    display_name = "Cobolt laser (microscope.lights.cobolt:CoboltLaser)"
    tags = ["laser", "light-source", "serial"]
    facts = [
        Fact("The laser is opened on a serial line at 115200 baud, 8N1 with a 0.1 s timeout; the constructor "
             "queries the serial number (sn?), disables autostart (@cobas 0) and reads the head's maximum "
             "power in mW (gmlp?)",
             source="upstream_code", ref="microscope/lights/cobolt.py:46-66"),
        Fact("initialize() disables direct control (@cobasdr 0) and forces autostart on (@cob1)",
             source="upstream_code", ref="microscope/lights/cobolt.py:109-114"),
        Fact("Emission is turned on with the l1 command after get_is_on() confirms it, and get_is_on() reads l? "
             "and returns True when the reply is b'1'",
             source="upstream_code", ref="microscope/lights/cobolt.py:118-141"),
        Fact("The native disable sends the l0 command and returns its reply; it does not clear the Device.enabled "
             "flag that enable() sets",
             source="upstream_code", ref="microscope/lights/cobolt.py:131-135"),
        Fact("get_status sends l?, p?, pa?, f? and hrs? and returns each reply as a status line",
             source="upstream_code", ref="microscope/lights/cobolt.py:86-98"),
        Fact("A power fraction is converted to mW of the head's maximum power and written as '@cobasp <watts>' "
             "with four decimals; the comment states that there is no minimum power and any non-negative "
             "number is accepted",
             source="upstream_code", ref="microscope/lights/cobolt.py:156-164"),
        Fact("The LightSource power property is in the [0, 1] interval, and its setter clips the argument to "
             "that interval before reaching _do_set_power",
             source="upstream_code", ref="microscope/abc.py:1245-1249"),
        Fact("OnlyTriggersBulbOnSoftwareMixin fixes trigger_type to SOFTWARE and trigger_mode to BULB, and its "
             "_do_trigger raises IncompatibleStateError ('trigger does not make sense in trigger mode bulb, only "
             "enable')",
             source="upstream_code", ref="microscope/_utils.py:108-140"),
    ]
    safe_state = "emission off (the native disable sends 'l0')"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("is_on", type="boolean", description="True while the laser reports that emission is on (the l? query)")
    def is_on(self):
        return self.native.get_is_on()

    @read("enabled", type="boolean",
          description="True while the device object is enabled (the Device.enabled flag enable() sets)")
    def enabled(self):
        return self.native.get_is_enabled()

    @read("power", unit="1",
          description="Power set point as a fraction of the head's maximum power (the [0, 1] interval)")
    def power(self):
        return self.native.get_set_power()

    @read("measured_power", unit="1",
          description="Measured output power as a fraction of the head's maximum power (0 while emission is off)")
    def measured_power(self):
        return self.native.power

    @read("status", type="array", items="string",
          description="Status lines the laser reports: emission on, target power, measured power, fault and head "
                      "operating hours")
    def status(self):
        return self.native.get_status()

    # -- the one write ------------------------------------------------------------------------------------------
    @write("power", unit="1",
           description="Power set point as a fraction of the head's maximum power; the native call writes it as "
                       "a watt value of the head's maximum power",
           limit=Limit(min=0, max=1, source="upstream_code", ref="microscope/abc.py:1245-1247"))
    def set_power(self, value):
        self.native.power = value
        return self.native.get_set_power()          # the value the light source stored as its set point

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.python-microscope.enable_emission.v1",
            description="Switch the laser emission on (the native enable)",
            output={"is_on": Field("boolean", description="True once the laser reports that emission is on")})
    def enable_emission(self):
        self.native.enable()
        return {"is_on": self.native.get_is_on()}

    @action(name="x-cap.python-microscope.disable_emission.v1", safe_state=True,
            description="Switch the laser emission off (the native disable, the safe state); it takes no input",
            output={"is_on": Field("boolean", description="False once the laser reports that emission is off")})
    def disable_emission(self):
        self.native.disable()
        return {"is_on": self.native.get_is_on()}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends 'l0'."""
        self.native.disable()
