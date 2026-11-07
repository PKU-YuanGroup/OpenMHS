"""OpenMHS driver for gh.pymodaq/pymodaq_plugins_daqmx: a National Instruments DAQmx analog output.

A direct Driver (decorated methods) over the upstream PyMoDAQ actuator plugin
``pymodaq_plugins_daqmx.hardware.national_instruments.daq_NIDAQmx:DAQ_NIDAQmx_Actuator``.  The card's
PythonObjectDriver shape cannot express ``writeAnalog(Nsamples, Nchannels, values, autostart)``; the write needs
the upstream method with its array argument, so this package uses a direct Driver and ``native.py``.

* reads: the first device name, the analog output and analog input maximum rates, the analog trigger support, the
  number of triggering sources, the last analog value written to the task buffer and the write position;
* one write: the analog output voltage.  The upstream reads the card's output window from the device at run time
  (daqmx.py:723-730), so no text file states a fixed range: the limit is ``Limit.operator_required`` and every write
  is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the window of its installed card
  (``site-limits.example.json`` shows the overlay);
* the native stop is the e-stop.  It stops the NI task; the driver does not claim that the analog output level is
  reset, and the clone documents that the applied output voltage cannot be read back (scanner_details.rst:28).

Every Fact cites a line of the clone at the pinned commit f2129a920a64338b2ca3b0e06614680b30385072.  This package
is model-authored and unreviewed; it is checked on the fake backend only.  At R1 the loader does not refuse the
hardware backend of an unreviewed model-written package, so this module makes no human-review claim.
"""

import numpy as np

from mhs.driver import Driver, DriverFailed, Fact, Limit, estop, read, write


class DaqmxActuator(Driver):
    device_id = "nidaqmx"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = ("pymodaq_plugins_daqmx.hardware.national_instruments.daq_NIDAQmx:"
              "DAQ_NIDAQmx_Actuator")
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDaqmxActuator"}
    vendor, model = "National Instruments", "NI-DAQmx analog output task"
    display_name = "NI-DAQmx analog output (PyMoDAQ DAQ_NIDAQmx_Actuator)"
    tags = ["ni-daqmx", "daq", "analog-output", "pymodaq"]
    facts = [
        Fact("The actuator plugin declares Volts as its controller units", source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daq_NIDAQmx.py:633"),
        Fact("get_NIDAQ_devices returns the system device names reported by DAQmxGetSysDevNames",
             source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:297-311"),
        Fact("getAOMaxRate reads the maximum analog output rate from the device",
             source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:364-368"),
        Fact("getAIMaxRate reads the maximum single-channel analog input rate from the device",
             source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:370-374"),
        Fact("getTriggeringSources lists PFI terminals of digital-triggering devices and analog input channels of "
             "analog-triggering devices", source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:388-403"),
        Fact("writeAnalog stores the written array in write_buffer and writes a single sample with "
             "WriteAnalogScalarF64 when the array holds one value", source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:642-647"),
        Fact("get_last_write returns the last element of write_buffer for a scalar write",
             source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:613-615"),
        Fact("get_last_write_index returns the task's current write position, or -1 when no task exists",
             source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:602-611"),
        Fact("getAOVoltageRange reads the device's analog output voltage ranges and uses a constant only when the "
             "query fails", source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:723-730"),
        Fact("stop stops the NI task and start starts it", source="upstream_code",
             ref="src/pymodaq_plugins_daqmx/hardware/national_instruments/daqmx.py:732-738"),
        Fact("The scanner documentation states that one cannot read the current voltage applied at an analog "
             "output", source="vendor_doc",
             ref="docs/source/user_guide/scanner_details.rst:28"),
        Fact("The upstream documentation describes an analog output driving a piezoelectric scanner through an "
             "amplifier", source="vendor_doc",
             ref="docs/source/user_guide/scanner_use.rst:4"),
    ]
    safe_state = "the native stop stops the NI task; the driver does not change the last output value"

    def _device_name(self):
        devices = list(self.native.devices)
        if not devices:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the upstream wrapper reports no NI-DAQmx device")
        return str(devices[0])

    # -- reads ------------------------------------------------------------------------------------------------
    @read("device", type="string", description="First NI-DAQmx device name reported by the upstream wrapper")
    def device(self):
        return self._device_name()

    @read("analog_output_max_rate", unit="Hz",
          description="Maximum analog output rate reported by the device")
    def analog_output_max_rate(self):
        return float(self.native.getAOMaxRate(self._device_name()))

    @read("analog_input_max_rate", unit="Hz",
          description="Maximum single-channel analog input rate reported by the device")
    def analog_input_max_rate(self):
        return float(self.native.getAIMaxRate(self._device_name()))

    @read("analog_triggering_supported", type="boolean",
          description="True when the device reports support for an analog start trigger")
    def analog_triggering_supported(self):
        return bool(self.native.isAnalogTriggeringSupported(self._device_name()))

    @read("trigger_source_count", type="integer",
          description="Number of triggering sources the upstream wrapper reports for this device")
    def trigger_source_count(self):
        return len(self.native.getTriggeringSources([self._device_name()]))

    @read("analog_output", unit="V",
          description="Last value the driver wrote to the analog output buffer; not a measured output voltage")
    def analog_output(self):
        return float(self.native.get_last_write())

    @read("last_write_index", type="integer",
          description="Write position reported by the NI task, or -1 when no task exists")
    def last_write_index(self):
        return int(self.native.get_last_write_index())

    # -- the one write ------------------------------------------------------------------------------------------
    @write("analog_output", unit="V", description="Voltage written to the first analog output channel",
           limit=Limit.operator_required(
               "the clone reads the output voltage range from the device at run time and uses a constant only when "
               "that query fails, so no text file states the window of the installed card; the site supplies the "
               "output window of its hardware"))
    def set_analog_output(self, value):
        values = np.asarray([float(value)], dtype=np.float64)
        self.native.writeAnalog(1, 1, values, autostart=True)
        return float(self.native.get_last_write())

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then stops the NI task."""
        self.native.stop()
