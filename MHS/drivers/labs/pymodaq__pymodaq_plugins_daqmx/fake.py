"""Fake backend of the DAQmx driver: an in-memory stand-in for the upstream actuator plugin.

Gate G7: every public method defined here is an attribute of
``pymodaq_plugins_daqmx.hardware.national_instruments.daq_NIDAQmx:DAQ_NIDAQmx_Actuator`` in the clone (directly or
through DAQ_NIDAQmx_base and DAQmx).  The driver reaches only those methods and the ``devices`` list that the
upstream ``DAQmx.__init__`` sets.  Every starting value in this file is test data (``# placeholder``), not a fact
about any card, and nothing here talks to a device.

The write path mirrors ``DAQmx.writeAnalog``: the value array is kept in ``write_buffer``, a scalar write sets
``is_scalar``, and the write position advances by the number of samples.  ``stop`` marks the fake task stopped and
counts the call so the e-stop path is observable.
"""

import numpy as np


class FakeDaqmxActuator:
    def __init__(self, **_options):
        self.devices = ["Dev1"]                      # placeholder
        self.channels = ["Dev1/ao0", "Dev1/ai0"]     # placeholder
        self.write_buffer = np.array([0.0])          # placeholder
        self.is_scalar = True
        self._write_index = 0                        # placeholder
        self._stopped = False
        self._stop_calls = 0

    def get_NIDAQ_devices(self):
        return list(self.devices)

    def getAOMaxRate(self, device):
        return 1000000.0                             # placeholder, Hz

    def getAIMaxRate(self, device):
        return 500000.0                              # placeholder, Hz

    def isAnalogTriggeringSupported(self, device):
        return True                                  # placeholder

    def getTriggeringSources(self, devices=None):
        return ["Dev1/PFI0", "Dev1/ai0"]             # placeholder

    def writeAnalog(self, Nsamples, Nchannels, values, autostart=False):
        array = np.asarray(values, dtype=np.float64)
        if int(np.prod(array.shape)) != int(Nsamples) * int(Nchannels):
            raise ValueError("the shape of analog outputs values is incorrect")
        self.write_buffer = array.reshape(-1)
        self.is_scalar = self.write_buffer.size == 1
        self._write_index += int(Nsamples)
        self._stopped = False

    def get_last_write(self):
        if self.is_scalar:
            return float(self.write_buffer[-1])
        return 0.0

    def get_last_write_index(self):
        return int(self._write_index)

    def start(self):
        self._stopped = False

    def stop(self):
        self._stopped = True
        self._stop_calls += 1
