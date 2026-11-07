"""OpenMHS driver for gh.croningp/chemputersoftware: an IKA RET Control Visc hotplate stirrer.

A direct Driver over the upstream serial class
``platform_server.modules.serial_labware.IKA_RET_Stirrer.IKA_RET_Control_Visc:IKARETControlVisc``.  The upstream
methods are synchronous: each decorated ``@command`` method queues a command on the class's serial thread and waits
for the reply, so every method here is a plain ``def``.

* reads: the sensor-1 (medium) temperature, its set point, the stir rate and its set point, and pH;
* writes: the sensor-1 temperature set point and the stir rate set point.  No line of the clone states a range for
  either value, so both carry ``Limit.operator_required`` and are refused until the site overlay supplies the range
  of its unit (``site-limits.example.json`` shows the overlay);
* actions: a ``cap.thermal.setpoint.v1`` action that sets the sensor-1 set point and starts the heater, and extension
  actions that start/stop the heater and the stirrer.  ``x-cap.croningp.stop_hotplate.v1`` is the safe-state action:
  it sends ``STOP_1`` (heater) and ``STOP_4`` (stirrer);
* the native stop is two commands, ``STOP_1`` and ``STOP_4``; the e-stop and the safe-state action both send them.

Every Fact cites a line of the clone at the pinned commit (0f249ce8f7c30e99bdf54f67cbd012d48e91dd3b).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


def _reading(reply):
    """The first captured group of an upstream reply (``valueanswer`` returns a list), or a scalar."""
    if isinstance(reply, (list, tuple)):
        return float(reply[0])
    return float(reply)


class IKARETControlVisc(Driver):
    device_id = "ika-ret-control-visc"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = ("platform_server.modules.serial_labware.IKA_RET_Stirrer.IKA_RET_Control_Visc:"
              "IKARETControlVisc")
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeIKARETControlVisc"}
    vendor, model = "IKA", "RET Control Visc"
    display_name = "IKA RET Control Visc hotplate stirrer"
    tags = ["hotplate", "stirrer", "temperature-control", "serial"]
    facts = [
        Fact("The class controls an IKA RET Control Visc hotplate stirrer; the command implementation is based on the "
             "English manual version 20000004159, pages 31-34", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:14-19"),
        Fact("temperature_pv reads IN_PV_1, temperature_sp reads IN_SP_1, and the temperature_sp setter writes OUT_SP_1",
             source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:81-83"),
        Fact("The temperature_sp setter targets sensor 1, the medium (external) temperature, and logs the set point "
             "in degC", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:162-179"),
        Fact("The executioner reads temperature_sp[0] and temperature_pv[0] as floats and logs both in degC",
             source="upstream_code",
             ref="platform_server/tools/module_execution/stirrer_execution.py:73-84"),
        Fact("The executioner sets the hotplate temperature through temperature_sp and logs it in degC",
             source="upstream_code",
             ref="platform_server/tools/module_execution/stirrer_execution.py:115-125"),
        Fact("stir_rate_pv reads IN_PV_4, stir_rate_sp reads IN_SP_4, and the stir_rate_sp setter writes OUT_SP_4",
             source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:78-80"),
        Fact("The stir rate setter converts the value with int() and logs it in RPM", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:140-146"),
        Fact("START_1/STOP_1 start/stop the heater and START_4/STOP_4 start/stop the stirrer",
             source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:84-87"),
        Fact("start_heater sends START_TEMP, stop_heater sends STOP_TEMP, start_stirrer sends START_STIR, and "
             "stop_stirrer sends STOP_STIR", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:181-199"),
        Fact("get_ph sends GET_PH_PV", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:326-328"),
        Fact("GET_PH_PV is IN_PV_80", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:102"),
        Fact("The valueanswer pattern captures a number and a status from a reply", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:71"),
        Fact("The serial line is configured for 9600 baud, 7 data bits, even parity and RTS/CTS", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:60-64"),
        Fact("get_weight sends GET_WEIGHT_PV; the comment says it only works with start weight and takes about 4 "
             "seconds, and no line states the unit of the value", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:330-333"),
        Fact("GET_WEIGHT_PV is IN_PV_90", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:103"),
        Fact("set_watch_dog_temp, set_watch_dog_stir_rate and get_hot_plate_temp_current are stubs that return None",
             source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:256-268"),
        Fact("get_viscosity_trend is a stub that returns None", source="upstream_code",
             ref="platform_server/modules/serial_labware/IKA_RET_Stirrer/IKA_RET_Control_Visc.py:322-324"),
    ]
    safe_state = "heater off (STOP_1) and stirrer off (STOP_4); the set points are left unchanged"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("medium_temperature", unit="Cel",
          description="Medium temperature of sensor 1 (the external temperature sensor)")
    def medium_temperature(self):
        return _reading(self.native.temperature_pv)

    @read("temperature_setpoint", unit="Cel", description="Target temperature of sensor 1 (the medium sensor)")
    def temperature_setpoint(self):
        return _reading(self.native.temperature_sp)

    @read("stir_rate", unit="/min", description="Current stir rate in rpm")
    def stir_rate(self):
        return _reading(self.native.stir_rate_pv)

    @read("stir_rate_setpoint", unit="/min", description="Target stir rate in rpm")
    def stir_rate_setpoint(self):
        return _reading(self.native.stir_rate_sp)

    @read("ph", unit="1", description="pH process value")
    def ph(self):
        return _reading(self.native.get_ph())

    # -- writes -----------------------------------------------------------------------------------------------
    @write("temperature_setpoint", unit="Cel", description="Target temperature of sensor 1 (OUT_SP_1)",
           limit=Limit.operator_required(
               "no line of the clone states the temperature range of the RET Control Visc; the site supplies the "
               "range of its unit in site-limits.json"))
    def set_temperature_setpoint(self, value):
        self.native.temperature_sp = value
        return _reading(self.native.temperature_sp)      # the value the device stored

    @write("stir_rate_setpoint", unit="/min",
           description="Target stir rate in rpm (OUT_SP_4); the native setter converts it with int()",
           limit=Limit.operator_required(
               "no line of the clone states the stir rate range of the RET Control Visc; the site supplies the "
               "range of its unit in site-limits.json"))
    def set_stir_rate_setpoint(self, value):
        self.native.stir_rate_sp = value
        return _reading(self.native.stir_rate_sp)        # the value the device stored (truncated to an integer)

    # -- actions ----------------------------------------------------------------------------------------------
    @action(cap="cap.thermal.setpoint.v1",
            description="Set the sensor-1 temperature set point (OUT_SP_1) and start the heater (START_1)",
            input={"target_temperature": Field(
                description="Target temperature of sensor 1 (the medium sensor)",
                limit=Limit.operator_required(
                    "no line of the clone states the temperature range of the RET Control Visc; the site supplies "
                    "the range of its unit in site-limits.json"))})
    def set_temperature(self, target_temperature):
        self.native.temperature_sp = target_temperature
        self.native.start_heater()
        return {"setpoint": _reading(self.native.temperature_sp),
                "actual_temperature": _reading(self.native.temperature_pv)}

    @action(name="x-cap.croningp.start_heating.v1", description="Start the heater (START_1)",
            output={"heating": Field("boolean", description="True after the heater start command was sent")})
    def start_heating(self):
        self.native.start_heater()
        return {"heating": True}

    @action(name="x-cap.croningp.stop_heating.v1", description="Stop the heater (STOP_1)",
            output={"heating": Field("boolean", description="False after the heater stop command was sent")})
    def stop_heating(self):
        self.native.stop_heater()
        return {"heating": False}

    @action(name="x-cap.croningp.start_stirring.v1", description="Start the stirrer (START_4)",
            output={"stirring": Field("boolean", description="True after the stirrer start command was sent")})
    def start_stirring(self):
        self.native.start_stirrer()
        return {"stirring": True}

    @action(name="x-cap.croningp.stop_stirring.v1", description="Stop the stirrer (STOP_4)",
            output={"stirring": Field("boolean", description="False after the stirrer stop command was sent")})
    def stop_stirring(self):
        self.native.stop_stirrer()
        return {"stirring": False}

    @action(name="x-cap.croningp.stop_hotplate.v1", safe_state=True,
            description="Safe state: stop the heater (STOP_1) and the stirrer (STOP_4); it takes no input",
            output={"heating": Field("boolean", description="False after the heater stop command was sent"),
                    "stirring": Field("boolean", description="False after the stirrer stop command was sent")})
    def stop_hotplate(self):
        self.native.stop_heater()
        self.native.stop_stirrer()
        return {"heating": False, "stirring": False}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def emergency_stop(self):
        """The native stop: STOP_1 for the heater and STOP_4 for the stirrer."""
        self.native.stop_heater()
        self.native.stop_stirrer()
