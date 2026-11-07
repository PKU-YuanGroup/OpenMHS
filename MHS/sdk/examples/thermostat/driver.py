"""OpenMHS tutorial driver: the synthetic TH-1 thermostat (see README.md).

The tutorial has no upstream repository: its "clone" is vendor/ inside this
package (task.json "upstream": null), so the gate reads the vendor manual and
SDK from there.  A real driver package pins an upstream repository and cites
lines of that clone.  Every Limit and Fact cites its source.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, interlock, read, write


class Thermostat(Driver):
    device_id = "tutorial-thermostat"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "thermo.controller:Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeController"}
    vendor, model = "OpenMHS tutorial", "TH-1"
    tags = ["thermostat", "tutorial"]
    facts = [
        Fact("The heater accepts setpoints from 5 to 80 Cel", source="vendor_doc", ref="MANUAL.md:9"),
        Fact("emergency_off() cuts heater power and latches the controller", source="upstream_code",
             ref="thermo/controller.py:39"),
    ]
    safe_state = "heater off, fan at idle"
    # R2 hardware: an independent hardware e-stop (SAFE-045); heater_off below is the safe-state action too.
    estop_physical_ref = "MANUAL.md:15"

    @read("temperature", unit="Cel", description="Measured zone temperature")
    def temperature(self):
        return self.native.read_temperature()

    @read("setpoint", unit="Cel", description="Heater setpoint")
    def setpoint(self):
        return self.native.get_setpoint()

    @write("setpoint", unit="Cel", description="Heater setpoint",
           limit=Limit(min=5, max=80, source="vendor_doc", ref="MANUAL.md:9"))
    def set_setpoint(self, value):
        self.native.set_setpoint(value)

    @write("zone_trim", type="array", items="number", length=2, unit="K", delta=True,
           description="Offset of the front and back zones from the setpoint",
           limit=Limit(min=[-5, -3], max=[5, 3], names=["front", "back"], source="upstream_code",
                       ref="thermo/controller.py:7"))
    def set_zone_trim(self, value):
        self.native.set_zone_trim(value[0], value[1])

    @write("fan_speed", unit="/min", description="Fan speed",
           limit=Limit.operator_required("the manual gives no fan speed range; the site sets it"))
    def set_fan_speed(self, value):
        self.native.set_fan_speed(value)

    @action(cap="cap.thermal.setpoint.v1", description="Drive the zone to a target temperature",
            input={"target_temperature": Field(description="Target zone temperature",
                                               limit=Limit(min=5, max=80, source="vendor_doc", ref="MANUAL.md:9"))})
    def go_to(self, target_temperature):
        self.native.set_setpoint(target_temperature)
        return {"setpoint": self.native.get_setpoint()}

    @action(name="x-cap.openmhs-tutorial.heater_off.v1", safe_state=True, description="Switch the heater off",
            output={"heater_off": Field("boolean", description="True once the heater is off")})
    def heater_off(self):
        self.native.heater_off()
        return {"heater_off": True}

    @estop
    def stop(self):
        self.native.emergency_off()

    @interlock("lid_closed", description="Zone lid closed", blocks=["cap.thermal.setpoint.v1"])
    def lid_closed(self):
        return self.native.lid_is_closed()
