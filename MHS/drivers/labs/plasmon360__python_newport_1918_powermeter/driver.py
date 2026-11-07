"""OpenMHS driver for gh.plasmon360/python_newport_1918_powermeter: a Newport 1918-C optical power meter.

A direct Driver (decorated methods) over the upstream class newport_1918c:Newport_1918c (newport_1918c.py:21), the
Python 2.7 ctypes wrapper around Newport's usbdll.dll (README.md:8, README.md:12).  The class opens the instrument by
USB product id (newport_1918c.py:45-66) and sends and receives ASCII with newp_usb_send_ascii and
newp_usb_get_ascii (newport_1918c.py:99-148).

* reads: the wavelength the meter is set to (PM:Lambda?), the serial number and the model number the instrument
  reports through GetInstrumentList (newport_1918c.py:33-35, 81-95);
* ``cap.measure.intensity.v1`` (the class verb is read): one PM:Power? reading at the wavelength already set, or
  after setting the requested wavelength with read_instant_power (newport_1918c.py:210-219).  The class returns the
  PM:Power? reply as text and the clone states no unit for it, so the value is reported as the class returns it, in
  the dimensionless unit of the catalogue output field.  The wavelength range is not stated in any text file of the
  clone: set_wavelength reads it from the instrument with PM:MIN:Lambda? and PM:MAX:Lambda? (newport_1918c.py:159),
  so the wavelength input is ``Limit.operator_required``: a call that carries it is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range of its instrument (site-limits.example.json shows
  the overlay).

The configured wavelength is also a writable state parameter.  The configure class floor is R1, so the device is
declared R1 above the card's R0 floor; the only native stop the class has is close_device, exposed as the e-stop with
the USB session closed as the safe state.  The device observes optical power and actuates no external output; the
upstream class is Python 2.7 source and the pinned clone is not imported by the gate.  The package is model-authored
and unreviewed, so it runs on the fake backend only and no hardware was attached.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

WAVELENGTH_REASON = (
    "no text file of the clone states the wavelength range of the instrument: set_wavelength reads it from the "
    "device with PM:MIN:Lambda? and PM:MAX:Lambda? at run time (newport_1918c.py:159), and the 500 to 550 nm values "
    "in the example are calls, not bounds (newport_1918c.py:315-322); the site states the range of its instrument")


class Newport1918c(Driver):
    device_id = "newport-1918c"
    device_kind = "sensor.optical"
    mode = "hardware"
    risk = "R1"
    native = "newport_1918c:Newport_1918c"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeNewport1918c"}
    vendor = "Newport"
    model = "1918-C optical power meter"
    display_name = "Newport 1918-C optical power meter (newport_1918c.Newport_1918c)"
    tags = ["optical-power", "power-meter", "newport", "usb", "ctypes", "measurement"]
    facts = [
        Fact("The README describes a Python module that communicates with a Newport 1918 power meter on a Windows "
             "computer through ctypes and Newport's usbdll.dll", source="vendor_doc", ref="README.md:8"),
        Fact("The module is written for Python 2.7 and the README says it would need minor modifications for "
             "Python 3+", source="vendor_doc", ref="README.md:12"),
        Fact("The user-facing device class is Newport_1918c", source="upstream_code", ref="newport_1918c.py:21"),
        Fact("The constructor loads usbdll.dll with windll.LoadLibrary, defaulting to the 32-bit Newport install "
             "path and product id 0xCEC7", source="upstream_code", ref="newport_1918c.py:24-27"),
        Fact("The constructor opens the device by product id and reads the device id, model number and serial "
             "number from get_instrument_list", source="upstream_code", ref="newport_1918c.py:32-35"),
        Fact("open_device_with_product_id opens the instrument with newp_usb_open_devices and stores the "
             "connection state", source="upstream_code", ref="newport_1918c.py:45-66"),
        Fact("get_instrument_list returns the device id, model number and serial number", source="upstream_code",
             ref="newport_1918c.py:81-95"),
        Fact("ask sends a query with newp_usb_send_ascii and reads the reply with newp_usb_get_ascii",
             source="upstream_code", ref="newport_1918c.py:99-127"),
        Fact("write sends a command string with newp_usb_send_ascii", source="upstream_code",
             ref="newport_1918c.py:129-148"),
        Fact("set_wavelength converts a float wavelength to an integer, reads PM:MIN:Lambda? and PM:MAX:Lambda?, and "
             "writes PM:Lambda only when the value is inside that range", source="upstream_code",
             ref="newport_1918c.py:150-162"),
        Fact("read_buffer writes the PM:DS:* datastore commands, polls PM:DS:COUNT?, and reads PM:Lambda?, "
             "PM:STAT:MEAN? and PM:STAT:SDEV?", source="upstream_code", ref="newport_1918c.py:187-208"),
        Fact("read_instant_power sets the wavelength and returns the replies to PM:Lambda? and PM:Power?",
             source="upstream_code", ref="newport_1918c.py:210-219"),
        Fact("close_device closes the instrument with newp_usb_uninit_system", source="upstream_code",
             ref="newport_1918c.py:68-79"),
        Fact("The example measures at a 500 nm wavelength and sweeps 500 to 550 nm with an interval of 10 nm",
             source="upstream_code", ref="newport_1918c.py:315-322"),
    ]

    safe_state = "USB session closed with newp_usb_uninit_system; the instrument keeps its last wavelength"

    # -- state ----------------------------------------------------------------------------------------------------
    @read("wavelength_nm", unit="nm", description="Wavelength the power meter is set to, read with PM:Lambda?")
    def wavelength_nm(self):
        return float(self.native.ask("PM:Lambda?"))

    @write("wavelength_nm", unit="nm",
           description="Wavelength the power meter measures at, written with PM:Lambda in whole nanometres",
           limit=Limit.operator_required(WAVELENGTH_REASON))
    def set_wavelength_nm(self, value):
        self.native.set_wavelength(int(float(value)))
        applied = float(self.native.ask("PM:Lambda?"))
        if int(applied) != int(float(value)):
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"the instrument reports {applied} nm instead of the requested {int(float(value))} nm; "
                "set_wavelength keeps the current wavelength when the request is outside the instrument's "
                "PM:MIN:Lambda? to PM:MAX:Lambda? range")
        return applied

    @read("serial_number", type="string",
          description="Serial number the instrument reports through GetInstrumentList")
    def serial_number(self):
        return str(self.native.serial_number)

    @read("model_number", type="string",
          description="Model number the instrument reports through GetInstrumentList")
    def model_number(self):
        return str(self.native.model_number)

    # -- measurement ----------------------------------------------------------------------------------------------
    @action(cap="cap.measure.intensity.v1",
            description="Read the optical power the detector sees: at the wavelength already set when no wavelength "
                        "is given, otherwise after setting the requested whole nanometres with the native "
                        "read_instant_power. The intensity is the PM:Power? value as the class returns it; the "
                        "clone states no unit for that reading",
            input={"wavelength_nm": Field(
                "number", unit="nm",
                description="Wavelength to set before the reading, in whole nanometres; leave it out to read at "
                            "the wavelength the instrument already holds",
                limit=Limit.operator_required(WAVELENGTH_REASON))})
    def measure_intensity(self, wavelength_nm=None):
        if wavelength_nm is None:
            return {"intensity": float(self.native.ask("PM:Power?"))}
        requested = int(float(wavelength_nm))
        actual, power = self.native.read_instant_power(requested)
        if int(float(actual)) != requested:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"the instrument reports {actual} nm instead of the requested {requested} nm; set_wavelength keeps "
                "the current wavelength when the request is outside the instrument's PM:MIN:Lambda? to "
                "PM:MAX:Lambda? range")
        return {"intensity": float(power)}

    @estop(native="close_device")
    def stop(self):
        """The native stop: the runtime latches first, then closes the USB session with close_device."""
        self.native.close_device()

    def teardown(self):
        self.native.close_device()
