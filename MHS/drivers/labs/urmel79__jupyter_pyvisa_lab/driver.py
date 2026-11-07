"""OpenMHS driver for gh.urmel79/jupyter_pyvisa_lab: the Benning MM12 digital multimeter over serial frames.

A direct Driver (decorated methods) over ``Benning_MM12_class:Benning_MM12_Serial``.  DEVIATION FROM THE CARD: the
card's ``family:scpi`` / ``helper:ScpiDriver`` shape does not fit this device.  The upstream sends fixed binary
frames (``55 55 00 00 AA`` and ``55 55 01 00 AB``, Benning_MM12_class.py:15-16), not text commands, so a command
table cannot reproduce the bytes and gate G7 cannot find them in the clone.  This package is therefore a direct
driver with a ``native.py`` factory.

The device is read-only.  The only public operations the upstream exposes are the identity query and the two
display queries:

* reads: the model, serial number, model ID and firmware version from ``getDeviceInfos``; the active measuring
  function, the value in SI base units, the SI base unit, the value in display units and the display unit from the
  two measurement methods;
* ``cap.sensing.read.v1``: one action that returns the measurement channels currently shown on the display, with the
  optional ``fields`` input selecting a subset.  The device has no settable function or range, so the action reports
  whatever the front-panel knob selects; it does not switch modes;
* no write, no actuator and no native stop: the MM12 is a read-only meter.  There is no Limit because no write or
  numeric invoke input exists.  ``device_kind`` is ``sensor`` because that is the resource kind the catalogue class
  ``cap.sensing.read.v1`` binds (sensor, sensor.imu or sensor.force_torque); it does not bind ``instrument.dmm``.
  The upstream is a DMM, but a DMM is a measurement sensor too, and the catalogue's generic read class is the only
  class that carries the device's free-form ``function``/``value``/``unit`` result.

The two measurement methods read the same display frame.  ``getMeasurement_baseUnits`` converts the value with the
function's range table and returns the function's SI base unit; ``getMeasurement_humanUnits`` decodes the scope code
and returns the value in the unit shown on the display.  Both are exposed because the card's hints name both, and
the action reports both so a caller can use the fixed base unit or the display unit.

Every Fact cites a line of the clone at the pinned commit 418a7f6bbef16a7c30ece599f8367fe5585291d9.  This package is
model-authored and unreviewed; the hardware backend was never opened and the fake is a recording stand-in, not a
recording of an instrument.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, read


class BenningMM12(Driver):
    device_id = "benning-mm12"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R0"
    native = "Benning_MM12_class:Benning_MM12_Serial"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBenningMM12"}
    vendor, model = "Benning", "MM12 digital multimeter"
    display_name = "Benning MM12 digital multimeter"
    tags = ["multimeter", "dmm", "benning", "serial", "measurement"]
    facts = [
        Fact("The module is a wrapper class for the DMM Benning MM12", source="upstream_code",
             ref="Benning_MM12_class.py:6"),
        Fact("The information request is the fixed frame 55 55 00 00 AA and the display request is 55 55 01 00 AB",
             source="upstream_code", ref="Benning_MM12_class.py:15-16"),
        Fact("The function table maps codes 0x00 to 0x31 to a measuring mode and an SI base unit",
             source="upstream_code", ref="Benning_MM12_class.py:21-72"),
        Fact("The range multiplier tables are indexed by the range code and differ per measuring function",
             source="upstream_code", ref="Benning_MM12_class.py:74-144"),
        Fact("getDeviceInfos sends the information frame, reads 57 bytes and validates the reply 0x55550034",
             source="upstream_code", ref="Benning_MM12_class.py:282-301"),
        Fact("getDeviceInfos returns the model name, serial number, model ID and firmware version",
             source="upstream_code", ref="Benning_MM12_class.py:303-337"),
        Fact("getMeasurement_baseUnits sends the display frame, reads 17 bytes and validates the reply 0x5555010C",
             source="upstream_code", ref="Benning_MM12_class.py:340-359"),
        Fact("The MSB of the function and range codes marks auto or manual selection and is masked before lookup",
             source="upstream_code", ref="Benning_MM12_class.py:369-381"),
        Fact("getMeasurement_baseUnits returns the function name, the value and its SI base unit",
             source="upstream_code", ref="Benning_MM12_class.py:458-460"),
        Fact("The display unit is bits 7..3 and the display multiplier is bits 2..0 of the scope code",
             source="upstream_code", ref="Benning_MM12_class.py:500-508"),
        Fact("getMeasurement_humanUnits returns the value in the unit shown on the display",
             source="upstream_code", ref="Benning_MM12_class.py:486-513"),
        Fact("The three-byte measurement value is decoded as an unsigned little-endian integer (signed=False)",
             source="upstream_code", ref="Benning_MM12_class.py:267-274"),
        Fact("The comment above the three-byte measurement field calls it a 24bit signed integer",
             source="upstream_code", ref="Benning_MM12_class.py:453-456"),
        Fact("The serial port is opened at 9600 baud, 8 data bits, no parity, one stop bit and a 2 s timeout",
             source="upstream_code", ref="Benning_MM12_class.py:193"),
        Fact("openConnection and closeConnection are the open and close methods of the serial port",
             source="upstream_code", ref="Benning_MM12_class.py:203-233"),
    ]

    # -- the two native queries, each with its failure branch ---------------------------------------------------
    def _infos(self):
        data = self.native.getDeviceInfos()
        if not data:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "getDeviceInfos returned no data; the MM12 information reply did not validate")
        return data

    def _base(self):
        data = self.native.getMeasurement_baseUnits()
        if not data:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "getMeasurement_baseUnits returned no data; the MM12 display reply did not validate")
        return data

    def _human(self):
        data = self.native.getMeasurement_humanUnits()
        if not data:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "getMeasurement_humanUnits returned no data; the MM12 display reply did not validate")
        return data

    # -- reads: identity ----------------------------------------------------------------------------------------
    @read("device_model", type="string", description="Model name reported by getDeviceInfos")
    def device_model(self):
        return str(self._infos()["model"][1])

    @read("device_serial", type="string", description="Serial number reported by getDeviceInfos")
    def device_serial(self):
        return str(self._infos()["serial"][1])

    @read("model_id", type="integer", description="Model ID reported by getDeviceInfos")
    def model_id(self):
        return int(self._infos()["id"][1])

    @read("firmware_version", description="Firmware version reported by getDeviceInfos (the integer divided by 100)")
    def firmware_version(self):
        return float(self._infos()["fw"][1])

    # -- reads: the display --------------------------------------------------------------------------------------
    @read("function", type="string", description="Measuring function currently shown on the MM12 display")
    def measurement_function(self):
        return str(self._base()["function"])

    @read("value_base", description="Measured value converted to the SI base unit of the active function")
    def value_base(self):
        return float(self._base()["value"])

    @read("base_unit", type="string", description="SI base unit of the active measuring function")
    def base_unit(self):
        return str(self._base()["unit"])

    @read("value_display", description="Measured value in the unit shown on the MM12 display")
    def value_display(self):
        return float(self._human()["value"])

    @read("display_unit", type="string", description="Unit shown on the MM12 display")
    def display_unit(self):
        return str(self._human()["unit"])

    # -- the one capability: the generic sensing read class -------------------------------------------------------
    @action(cap="cap.sensing.read.v1",
            description="Read the measurement currently shown by the MM12; the device has no settable function or "
                        "range, so the front-panel selection is reported, not changed",
            input={"fields": Field(
                type="array", items="string",
                description="Channel names to return: function, value_base, base_unit, value_display and display_unit. "
                            "Omit the input to return every channel")})
    def read_display(self, fields=None):
        base = self._base()
        human = self._human()
        values = {
            "function": str(base["function"]),
            "value_base": float(base["value"]),
            "base_unit": str(base["unit"]),
            "value_display": float(human["value"]),
            "display_unit": str(human["unit"]),
        }
        if fields is not None:
            wanted = {str(name) for name in fields}
            values = {name: value for name, value in values.items() if name in wanted}
        return {"values": values}

    def teardown(self):
        self.native.closeConnection()
