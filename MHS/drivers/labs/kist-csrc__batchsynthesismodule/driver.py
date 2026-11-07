"""OpenMHS driver for gh.kist-csrc/batchsynthesismodule: an IKA RET control-visc hotplate stirrer.

A direct Driver over the upstream class ``Stirrer.IKA_RET_Control_Visc:IKARETControlVisc``.  The upstream class
speaks the IKA serial command set (``IN_PV_1``, ``IN_SP_1``, ``OUT_SP_1``, ``START_1``, ``STOP_1``, ``START_4``,
``STOP_4``, ``START_80``, ``STOP_80``, ``START_90``, ``STOP_90``, ``RESET``; ``Stirrer/IKA_RET_Control_Visc.py:85-100``)
and returns every numeric answer as a ``(value, status)`` pair through its ``valueanswer`` pattern
(``Stirrer/IKA_RET_Control_Visc.py:79``), so this driver parses the first member of each answer.

* reads: sensor 1 (medium / external) temperature and set point, sensor 2 (hot plate) temperature, set point and
  safety set point, the heat-transfer-medium set point, the actual and target stirrer rate, pH and weight;
* writes through ``cap.device.configure.v1``: sensor 1 set point, sensor 2 set point and stirrer set point;
* ``cap.thermal.setpoint.v1``: set a medium target temperature and start the heater;
* extension actions for the heater, the stirrer, the pH meter, the weighing function, the native RESET and the
  combined safe state (STOP_1 and STOP_4);
* the native stop (STOP_1, then STOP_4) is ``@estop``; the same two commands form the safe-state action.

The clone documents a 340 Cel upper bound for ``controlTemperature`` and a 0 to 1700 rpm stirrer range
(``Stirrer/hotplate.py:45`` and ``:69``).  It states no range for the sensor 2 (hot plate) set point and none for the
medium target below the catalogue class envelope, so those two inputs are ``Limit.operator_required`` and the site
supplies them through ``site-limits.json`` (``site-limits.example.json`` is an example, not a claim about a unit).

This package is model-authored and unreviewed: it runs on the fake backend only.  The loader refuses the hardware
backend of a model-authored R2 driver until a human signs ``reviewed_by`` in ``driver.lock.json``.  The upstream
``SerialDevice`` itself raises OSError on an operating system other than Windows
(``Stirrer/serial_labware/serial_labware.py:104-108``), which is recorded in ``facts.md`` and ``RESULT.json``.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


def _value(answer):
    """First member of an upstream value answer: ``valueanswer`` captures the value and a status digit."""
    return float(answer[0])


def _integer(answer):
    """First member of an upstream value answer, rounded to the integer the stirrer setter accepts."""
    return int(round(float(answer[0])))


class IKARETControlVisc(Driver):
    device_id = "ika-ret-control-visc"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "Stirrer.IKA_RET_Control_Visc:IKARETControlVisc"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeIKARETControlVisc"}
    vendor, model = "IKA", "RET control-visc"
    display_name = "IKA RET control-visc hotplate stirrer"
    tags = ["hotplate", "stirrer", "ika", "serial", "thermal"]
    facts = [
        Fact("IKARETControlVisc is the class for the IKA RET control-visc hotplate stirrer and implements the "
             "English manual's serial command set",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:3-19"),
        Fact("The serial line is opened at 9600 baud with seven data bits, even parity and RTS/CTS flow control",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:68-72"),
        Fact("The command set uses IN_PV_1/IN_SP_1/OUT_SP_1 and START_1/STOP_1 for sensor 1, "
             "IN_PV_4/IN_SP_4/OUT_SP_4 and START_4/STOP_4 for the stirrer, START_80/STOP_80 for the pH meter, "
             "START_90/STOP_90 for weighing and RESET for the reset",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:85-100"),
        Fact("temperature_pv and temperature_sp address sensor 1, the medium (external) temperature sensor; "
             "the setter logs the set point in degrees Celsius",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:159-187"),
        Fact("stir_rate_pv and stir_rate_sp address the stirrer rate; the setter logs RPM and converts the value "
             "to an integer",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:118-157"),
        Fact("temperature_hot_plate_pv and temperature_hot_plate_sp address sensor 2, the hot plate temperature",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:283-308"),
        Fact("temperature_heat_transfer_medium_sp reads IN_SP_7",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:278-281"),
        Fact("get_ph reads IN_PV_80 and get_weight reads IN_PV_90; the weight needs the weighing function started "
             "and takes about four seconds to calibrate",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:334-341"),
        Fact("temperature_hot_plate_safety_sp reads the hot plate safety set point and has no setter",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:320-328"),
        Fact("controlTemperature documents the target temperature as room temperature to 340 Celsius",
             source="upstream_code", ref="Stirrer/hotplate.py:45"),
        Fact("controlStirrer documents the target stir rate as 0 to 1700 rpm",
             source="upstream_code", ref="Stirrer/hotplate.py:69"),
        Fact("controlStop stops the stirrer and then the heater",
             source="upstream_code", ref="Stirrer/hotplate.py:90-102"),
        Fact("set_watch_dog_temp, set_watch_dog_stir_rate, get_hot_plate_temp_current and get_viscosity_trend "
             "are empty methods in the upstream class and are not exposed",
             source="upstream_code", ref="Stirrer/IKA_RET_Control_Visc.py:264-276"),
        Fact("SerialDevice raises OSError on an operating system other than Windows",
             source="upstream_code", ref="Stirrer/serial_labware/serial_labware.py:104-108"),
        Fact("The command decorator queues each call to a background thread and blocks the caller until the reply "
             "is queued",
             source="upstream_code", ref="Stirrer/serial_labware/serial_labware.py:31-57"),
    ]
    safe_state = "heater off and stirrer off (STOP_1, then STOP_4)"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("medium_temperature", unit="Cel",
          description="Sensor 1 temperature, the medium (external temperature sensor)")
    def medium_temperature(self):
        return _value(self.native.temperature_pv)

    @read("hot_plate_temperature", unit="Cel", description="Sensor 2 temperature, the hot plate")
    def hot_plate_temperature(self):
        return _value(self.native.temperature_hot_plate_pv)

    @read("medium_setpoint", unit="Cel", description="Sensor 1 temperature set point")
    def medium_setpoint(self):
        return _value(self.native.temperature_sp)

    @read("hot_plate_setpoint", unit="Cel", description="Sensor 2 (hot plate) temperature set point")
    def hot_plate_setpoint(self):
        return _value(self.native.temperature_hot_plate_sp)

    @read("heat_transfer_medium_setpoint", unit="Cel",
          description="Set point of the heat transfer medium (IN_SP_7)")
    def heat_transfer_medium_setpoint(self):
        return _value(self.native.temperature_heat_transfer_medium_sp)

    @read("hot_plate_safety_setpoint", unit="Cel",
          description="Hot plate safety temperature set point (read only)")
    def hot_plate_safety_setpoint(self):
        return _value(self.native.temperature_hot_plate_safety_sp)

    @read("stir_rate", type="integer", unit="1/min", description="Actual stirrer rate in rpm")
    def stir_rate(self):
        return _integer(self.native.stir_rate_pv)

    @read("stir_rate_setpoint", type="integer", unit="1/min", description="Stirrer rate set point in rpm")
    def stir_rate_setpoint(self):
        return _integer(self.native.stir_rate_sp)

    @read("ph", description="pH value of the integrated pH meter (start it with set_ph_meter)")
    def ph(self):
        return _value(self.native.get_ph())

    @read("weight",
          description="Weight value of the integrated weighing function (the clone states no unit)")
    def weight(self):
        return _value(self.native.get_weight())

    # -- writes --------------------------------------------------------------------------------------------------
    @write("medium_setpoint", unit="Cel", description="Sensor 1 temperature set point",
           limit=Limit(max=340, source="upstream_code", ref="Stirrer/hotplate.py:45"))
    def set_medium_setpoint(self, value):
        self.native.temperature_sp = value
        return _value(self.native.temperature_sp)

    @write("hot_plate_setpoint", unit="Cel", description="Sensor 2 (hot plate) temperature set point",
           limit=Limit.operator_required(
               "no line of the clone states a range for the sensor 2 hot plate set point; the site sets the range "
               "of its unit"))
    def set_hot_plate_setpoint(self, value):
        self.native.temperature_hot_plate_sp = value
        return _value(self.native.temperature_hot_plate_sp)

    @write("stir_rate_setpoint", type="integer", unit="1/min", description="Stirrer rate set point in rpm",
           limit=Limit(min=0, max=1700, source="upstream_code", ref="Stirrer/hotplate.py:69"))
    def set_stir_rate_setpoint(self, value):
        self.native.stir_rate_sp = value
        return _integer(self.native.stir_rate_sp)

    # -- catalogued actions --------------------------------------------------------------------------------------
    @action(cap="cap.thermal.setpoint.v1",
            description="Set the sensor 1 medium temperature set point and switch the heater on",
            input={"target_temperature": Field(
                description="Target medium temperature",
                limit=Limit.operator_required(
                    "the catalogue class caps target_temperature at 300 Cel, below the 340 Cel the clone "
                    "documents, so the site binds the range of its unit"))})
    def heat_to(self, target_temperature):
        self.native.temperature_sp = target_temperature
        self.native.start_heater()
        return {"setpoint": _value(self.native.temperature_sp),
                "actual_temperature": _value(self.native.temperature_pv)}

    # -- extension actions ---------------------------------------------------------------------------------------
    @action(name="x-cap.kist-csrc.set_heater.v1", description="Start or stop the hot plate heater",
            input={"enabled": Field("boolean", description="True starts the heater, False stops it")},
            output={"enabled": Field("boolean", description="The state sent to the heater")})
    def set_heater(self, enabled):
        if enabled:
            self.native.start_heater()
        else:
            self.native.stop_heater()
        return {"enabled": bool(enabled)}

    @action(name="x-cap.kist-csrc.set_stirrer.v1", description="Start or stop the stirrer",
            input={"enabled": Field("boolean", description="True starts the stirrer, False stops it")},
            output={"enabled": Field("boolean", description="The state sent to the stirrer")})
    def set_stirrer(self, enabled):
        if enabled:
            self.native.start_stirrer()
        else:
            self.native.stop_stirrer()
        return {"enabled": bool(enabled)}

    @action(name="x-cap.kist-csrc.set_ph_meter.v1", description="Start or stop the integrated pH meter",
            input={"enabled": Field("boolean", description="True starts the pH meter, False stops it")},
            output={"enabled": Field("boolean", description="The state sent to the pH meter")})
    def set_ph_meter(self, enabled):
        if enabled:
            self.native.start_ph_meter()
        else:
            self.native.stop_ph_meter()
        return {"enabled": bool(enabled)}

    @action(name="x-cap.kist-csrc.set_weighing.v1", description="Start or stop the integrated weighing function",
            input={"enabled": Field("boolean", description="True starts weighing, False stops it")},
            output={"enabled": Field("boolean", description="The state sent to the weighing function")})
    def set_weighing(self, enabled):
        if enabled:
            self.native.start_weighing()
        else:
            self.native.stop_weighing()
        return {"enabled": bool(enabled)}

    @action(name="x-cap.kist-csrc.reset_hot_plate.v1", description="Send RESET to the hot plate",
            output={"reset": Field("boolean", description="True after RESET was sent")})
    def reset_hot_plate(self):
        self.native.reset_hot_plate()
        return {"reset": True}

    @action(name="x-cap.kist-csrc.stop_heating_and_stirring.v1", safe_state=True,
            description="Stop the heater and the stirrer (STOP_1 and STOP_4); the native safe state",
            output={"stopped": Field("boolean", description="True after both stop commands were sent")})
    def stop_heating_and_stirring(self):
        self.native.stop_heater()
        self.native.stop_stirrer()
        return {"stopped": True}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: STOP_1 and STOP_4; the runtime latches before calling this."""
        self.native.stop_heater()
        self.native.stop_stirrer()

    def teardown(self):
        self.native.close_connection()
