"""OpenMHS driver for gh.usnistgov/ssmdevices: a Mini-Circuits RCDAT USB switch attenuator.

A direct Driver (decorated methods) over the upstream class
``ssmdevices.instruments.attenuators:MiniCircuitsRCDAT`` (attenuators.py:13).  The class is a USB HID device that
speaks a byte command protocol: an attenuation setting is read with command code 18 and written with command code 19
(attenuators.py:55-88), and the part number and serial number are read with command codes 40 and 41
(_minicircuits_usb.py:231-249).  A command is a list of up to 64 one-byte values; the reply must echo the command
code within the configured timeout (_minicircuits_usb.py:62-92).

This is a direct Driver with a native.py factory, as the card's ``decision`` says.  The card's helper hint names
PythonObjectDriver, but the family grammar has no way to express a property whose value is calibrated from a table
and whose setter is the same property, so the package is decorated explicitly.

Capabilities:

* reads: the uncalibrated attenuation setting, the part number and the serial number;
* one write: the uncalibrated attenuation setting.  The upstream property bounds it to 0 to 115 dB in 0.25 dB steps
  (attenuators.py:52-54), and the setter sends whole-decibel and quarter-decibel bytes (attenuators.py:78-86);
* the e-stop drives the attenuation to its maximum setting (115 dB), the lowest RF level the attenuator can pass.
  The device has no separate stop command.

The calibrated attenuation and the calibrated output power of the upstream class derive from a calibration table and
a frequency (attenuators.py:17-24, 90-103); this package does not expose them, because the value depends on the
calibration table selected for the installed unit and the clone states no calibration bound.  The clone ships
calibration tables under src/ssmdevices/lib/cal/; this driver does not read them.  The attenuation setting is the
value the device itself stores and reports.

Every Fact cites a line of the clone at the pinned commit 4680dde885660d6aa467dc883aec1226f401589a.  This package
is model-authored and unreviewed: it is R1, so the loader does not refuse the hardware backend on review grounds;
that backend was never executed and no hardware run is claimed.
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write

#: The upstream property's maximum (attenuators.py:52-54): the e-stop drives the attenuator to this setting.
MAX_ATTENUATION_DB = 115.0

#: The one limit of this driver, on the source line that declares it.
ATTENUATION_LIMIT = Limit(
    min=0,
    max=115,
    unit="{dB}",
    source="upstream_code",
    ref="src/ssmdevices/instruments/attenuators.py:52-54",
)


class MiniCircuitsRCDAT(Driver):
    device_id = "minicircuits-rcdat"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "ssmdevices.instruments.attenuators:MiniCircuitsRCDAT"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMiniCircuitsRCDAT"}
    vendor, model = "Mini-Circuits", "RCDAT USB switch attenuator"
    display_name = "Mini-Circuits RCDAT USB switch attenuator"
    tags = ["attenuator", "rf", "usb", "hid", "minicircuits", "rcdat"]
    facts = [
        Fact("MiniCircuitsRCDAT is the Mini-Circuits USB switch attenuator class and fixes product ID 0x23",
             source="upstream_code", ref="src/ssmdevices/instruments/attenuators.py:13-15"),
        Fact("The Mini-Circuits USB base class declares vendor ID 0x20CE for USB HID devices",
             source="upstream_code", ref="src/ssmdevices/instruments/_minicircuits_usb.py:15-18"),
        Fact("The uncalibrated attenuation_setting property is bounded to 0 to 115 dB with a 0.25 dB step",
             source="upstream_code", ref="src/ssmdevices/instruments/attenuators.py:52-54"),
        Fact("attenuation_setting reads with command code 18 and writes with command code 19",
             source="upstream_code", ref="src/ssmdevices/instruments/attenuators.py:55-88"),
        Fact("The attenuation setter sends the whole-decibel part and the quarter-decibel part, plus the channel",
             source="upstream_code", ref="src/ssmdevices/instruments/attenuators.py:78-86"),
        Fact("channel selects a port from 1 to 4, and None addresses a single attenuator",
             source="upstream_code", ref="src/ssmdevices/instruments/attenuators.py:42-49"),
        Fact("frequency selects the calibration-table row and is bounded to 10 MHz to 6 GHz",
             source="upstream_code", ref="src/ssmdevices/instruments/attenuators.py:17-24"),
        Fact("attenuation is the calibrated value from the table at calibration_path, indexed by frequency",
             source="upstream_code", ref="src/ssmdevices/instruments/attenuators.py:90-97"),
        Fact("output_power is -attenuation + output_power_offset in dBm", source="upstream_code",
             ref="src/ssmdevices/instruments/attenuators.py:99-103"),
        Fact("model and serial_number are read with command codes 40 and 41", source="upstream_code",
             ref="src/ssmdevices/instruments/_minicircuits_usb.py:231-249"),
        Fact("A command is at most 64 one-byte values and the reply must echo the command code within timeout",
             source="upstream_code", ref="src/ssmdevices/instruments/_minicircuits_usb.py:62-92"),
        Fact("open() resolves the HID path and opens it in nonblocking mode", source="upstream_code",
             ref="src/ssmdevices/instruments/_minicircuits_usb.py:35-43"),
        Fact("close() closes the HID backend", source="upstream_code",
             ref="src/ssmdevices/instruments/_minicircuits_usb.py:52-54"),
        Fact("The USB command timeout defaults to 1 s and its minimum is 0.5 s", source="upstream_code",
             ref="src/ssmdevices/instruments/_minicircuits_usb.py:33"),
        Fact("The serial number is required when more than one device is connected", source="upstream_code",
             ref="src/ssmdevices/instruments/_minicircuits_usb.py:20-24"),
    ]
    safe_state = "maximum attenuation setting (115 dB), the lowest RF level the attenuator can pass"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("attenuation_setting", unit="{dB}",
          description="Uncalibrated attenuation setting the device stores, in dB (0 to 115 dB in 0.25 dB steps)")
    def attenuation_setting(self):
        return float(self.native.attenuation_setting)

    @read("part_number", type="string",
          description="Part number the attenuator reports (command code 40)")
    def part_number(self):
        return str(self.native.model)

    @read("serial_number", type="string",
          description="Serial number the attenuator reports (command code 41)")
    def serial_number(self):
        return str(self.native.serial_number)

    # -- the one write -------------------------------------------------------------------------------------------
    @write("attenuation_setting", unit="{dB}",
           description="Uncalibrated attenuation setting in dB (0 to 115 dB in 0.25 dB steps)",
           limit=ATTENUATION_LIMIT)
    def set_attenuation_setting(self, value):
        self.native.attenuation_setting = value
        return float(self.native.attenuation_setting)      # the device keeps quarter-decibel steps

    # -- safety --------------------------------------------------------------------------------------------------
    @estop(native="attenuation_setting")
    def stop(self):
        """The native stop: drive the attenuator to its maximum 115 dB setting."""
        self.native.attenuation_setting = MAX_ATTENUATION_DB

    # -- lifecycle -----------------------------------------------------------------------------------------------
    def teardown(self):
        self.native.close()
