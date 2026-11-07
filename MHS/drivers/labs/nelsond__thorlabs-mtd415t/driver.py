"""OpenMHS driver for gh.nelsond/thorlabs-mtd415t: a Thorlabs MTD415T OEM temperature controller.

A direct Driver (decorated methods) over the upstream class
``thorlabs_mtd415t.mtd415t_device:MTD415TDevice``.  The card's ``decision`` is direct-driver; this package serves
the property reads and the catalogue measurement capability as a direct Driver, with no family-config table.  The
class talks to the controller over a serial line at 115200 baud (``thorlabs_mtd415t/mtd415t_device.py:55``) and
builds every request from a setting letter plus ``?`` or a decimal value (``mtd415t_device.py:70-78, 94-104``).

* reads: the product name and version, the unique device identifier, the measured temperature, the stored
  temperature setpoint, the TEC current and voltage, the TEC current limit, the error texts and the serial port
  state;
* one capability: ``cap.measure.temperature.v1`` returns the measured temperature (the clone's ``temp`` property,
  ``mtd415t_device.py:192-196``) with the runtime's sampling stamp.

The package is deliberately read-only.  The same class also writes a temperature setpoint
(``mtd415t_device.py:204-211``), a TEC current limit (``mtd415t_device.py:171-178``) and the PID gains, but every
such write is a heating/cooling actuation, which the catalogue places at R2 or above, and the clone exposes no
output-disable or stop command: there is no native safe state a heating driver could name.  This package binds no
setter, so its capability set is observational (R0, MHS/spec/04-safety.md) and the controller's stored regulation
stays exactly as the device holds it.  ``facts.md`` records the write paths and why they are not bound.

Every Fact cites a line of the clone at the pinned commit c53ec5c7db67f4cb47619d2ceaa4aead5e583923.  This package
is model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null): the acceptance gate runs the fake
backend only, and nothing here ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, action, read

DEVICE = "thorlabs_mtd415t/mtd415t_device.py"
SERIAL = "thorlabs_mtd415t/serial_device.py"


class MTD415T(Driver):
    device_id = "thorlabs-mtd415t"
    device_kind = "instrument.thermometer"
    mode = "hardware"
    risk = "R0"
    native = "thorlabs_mtd415t.mtd415t_device:MTD415TDevice"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMTD415TDevice"}
    vendor, model = "Thorlabs", "MTD415T OEM temperature controller"
    display_name = "Thorlabs MTD415T temperature controller"
    tags = ["thorlabs", "mtd415t", "temperature", "thermometer", "tec", "serial"]
    facts = [
        Fact("The class controls and configures the Thorlabs MTD415T digital temperature controller over a serial "
             "port", source="upstream_code", ref=f"{DEVICE}:30-32"),
        Fact("The constructor passes the port and baudrate 115200 to SerialDevice",
             source="upstream_code", ref=f"{DEVICE}:55"),
        Fact("SerialDevice opens the port with serial_for_url(port, baudrate=baudrate, **kwargs)",
             source="upstream_code", ref=f"{SERIAL}:22-24"),
        Fact("A query appends '?' to the setting name and retries once after 100 ms when the reply is "
             "'unknown command'", source="upstream_code", ref=f"{DEVICE}:70-78"),
        Fact("write appends a newline to the bytes and read returns one line of the serial port",
             source="upstream_code", ref=f"{SERIAL}:69-91"),
        Fact("idn queries the setting 'm' and strips the reply", source="upstream_code", ref=f"{DEVICE}:138"),
        Fact("uid queries the setting 'u' and strips the reply", source="upstream_code", ref=f"{DEVICE}:143"),
        Fact("temp queries 'Te' and divides the reply by 1000, so it is a temperature in degrees Celsius",
             source="upstream_code", ref=f"{DEVICE}:192-196"),
        Fact("temp_setpoint queries 'T' and divides the reply by 1000; the docstring states 5.000 to 45.000 "
             "degrees Celsius", source="upstream_code", ref=f"{DEVICE}:199-202"),
        Fact("The temperature setpoint setter validates the range 5 to 45 degrees Celsius and writes 'T' with the "
             "value in millidegrees", source="upstream_code", ref=f"{DEVICE}:204-211"),
        Fact("tec_current queries 'A' and divides the reply by 1000, so it is a current in amperes",
             source="upstream_code", ref=f"{DEVICE}:180-184"),
        Fact("tec_voltage queries 'U' and divides the reply by 1000, so it is a voltage in volts",
             source="upstream_code", ref=f"{DEVICE}:186-190"),
        Fact("tec_current_limit queries 'L' and divides the reply by 1000; its setter range is 0.2 to 2 amperes",
             source="upstream_code", ref=f"{DEVICE}:165-178"),
        Fact("error_flags queries 'E', decodes the reply as 16 binary digits and returns the bits with the least "
             "significant bit first", source="upstream_code", ref=f"{DEVICE}:145-150"),
        Fact("The error register bits are the MTD415T datasheet errors (not enabled, sensor, TEC, range and "
             "command errors)", source="upstream_code", ref=f"{DEVICE}:40-51"),
        Fact("errors returns the text of every error bit that is set", source="upstream_code",
             ref=f"{DEVICE}:152-163"),
        Fact("close closes the serial connection", source="upstream_code", ref=f"{SERIAL}:50-54"),
        Fact("is_open reports whether the serial port is open", source="upstream_code", ref=f"{SERIAL}:93-96"),
        Fact("The README describes the repository as a wrapper for the Thorlabs MTD415T OEM temperature controller "
             "module", source="vendor_doc", ref="README.md:3"),
    ]

    # -- state reads ------------------------------------------------------------------------------------------
    @read("temperature", unit="Cel", description="Temperature measured by the controller in degrees Celsius")
    def temperature(self):
        return float(self.native.temp)

    @read("setpoint", unit="Cel",
          description="Temperature setpoint stored on the controller in degrees Celsius (read only here)")
    def setpoint(self):
        return float(self.native.temp_setpoint)

    @read("tec_current", unit="A", description="TEC current in amperes as the controller reports it")
    def tec_current(self):
        return float(self.native.tec_current)

    @read("tec_voltage", unit="V", description="TEC voltage in volts as the controller reports it")
    def tec_voltage(self):
        return float(self.native.tec_voltage)

    @read("tec_current_limit", unit="A", description="TEC current limit in amperes stored on the controller")
    def tec_current_limit(self):
        return float(self.native.tec_current_limit)

    @read("errors", type="array", items="string",
          description="Texts of the error register bits that are set on the controller")
    def errors(self):
        return list(self.native.errors)

    @read("idn", type="string", description="Product name and version number reported by the controller")
    def idn(self):
        return str(self.native.idn)

    @read("uid", type="string", description="Unique device identifier reported by the controller")
    def uid(self):
        return str(self.native.uid)

    @read("is_open", type="boolean", description="True while the serial connection to the controller is open")
    def is_open(self):
        return bool(self.native.is_open)

    # -- the measurement capability ----------------------------------------------------------------------------
    @action(cap="cap.measure.temperature.v1",
            description="Measure the controller's temperature and return it with the runtime's sampling stamp",
            input={
                "probe": Field("string",
                               description="Optional probe name; the controller has one temperature sensor, so "
                                           "the name does not select a different channel"),
                "location": Field("string",
                                  description="Optional location label for the reading; the controller has one "
                                              "temperature sensor, so the label does not select another channel"),
            })
    def measure_temperature(self, probe=None, location=None):
        return {"temperature": float(self.native.temp)}

    def teardown(self):
        """Close the serial connection; this is a read-only package and closing moves no setpoint."""
        self.native.close()
