"""OpenMHS driver for gh.dennis-van-gils/dvg_arduino_lock-in_amp: the DvG Arduino lock-in amplifier (Alia).

A direct Driver (decorated methods) over the card's entry class ``Alia_protocol_serial:Alia``.  The upstream class
speaks a text serial protocol whose setters are assembled from a prefix and a value (``_freq %f``, ``_offs %f``,
``_vrms %f``; Alia_protocol_serial.py:819-842), so a command table cannot reproduce the wire syntax; the driver calls
the upstream class and its ``set_ref``/``query_ref`` methods instead.

Covered here are the scalar parts of the device:

* reads: the reference waveform, frequency, offset, amplitude, RMS amplitude, the two clipping flags, the ADC
  autocalibration values, the acquisition running flag and the two constants the firmware reports (sampling rate and
  block size);
* writes: the reference waveform and the three reference voltage parameters; the frequency is
  ``Limit.operator_required`` because the firmware derives the output frequency from the sampling rate of the
  installed board (Fs / N_LUT, N_LUT clamped to 20..1000; mcu_source/v1.0.0_VSCODE/src/main.cpp:374-380);
* actions: start and stop the acquisition.  The native stop (``off``) is the @estop and, as
  ``x-cap.dennis-van-gils.stop_acquisition.v1``, the safe-state action.

The sample stream (``read_until_EOM`` / ``listen_to_lockin_amp``) is NOT COVERED: it is a binary block of arrays and
the scalar state is what this package serves.

Every Fact cites a line of the clone at the pinned commit 64c0f18f9111eef2fc4feb10466c4dd9a39fb516.  This package is
model-authored and unreviewed; it is checked on the fake backend only, and the hardware backend was never run.
"""

from enum import Enum

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class _Waveform(Enum):
    """The upstream Waveform values (Alia_protocol_serial.py:42-48); a local copy keeps the clone out of this package."""

    Sine = 0
    Square = 1
    Triangle = 2


_WAVEFORMS = ("Sine", "Square", "Triangle")


class AliaLockIn(Driver):
    device_id = "alia-lockin"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "Alia_protocol_serial:Alia"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAlia"}
    vendor = "Dennis van Gils"
    model = "DvG Arduino lock-in amplifier (Alia)"
    display_name = "DvG Arduino lock-in amplifier (Alia_protocol_serial.Alia)"
    tags = ["lock-in", "lock-in-amplifier", "signal-generation", "adc", "serial"]
    facts = [
        Fact("The device is an Arduino lock-in amplifier running at a 25 kHz sampling rate with 12-bit analog "
             "resolution", source="vendor_doc", ref="README.rst:17-19"),
        Fact("The microcontroller generates the reference signal REF_X and acquires the input signal SIG_I",
             source="vendor_doc", ref="README.rst:40-41"),
        Fact("The reference signal REF_X is a true analog-out waveform between 0 and 3.3 V", source="vendor_doc",
             ref="README.rst:51"),
        Fact("The upstream Waveform enumeration is Unknown=-1, Sine=0, Square=1 and Triangle=2",
             source="upstream_code", ref="Alia_protocol_serial.py:42-48"),
        Fact("Alia.set_ref writes the waveform, frequency, offset, amplitude and RMS amplitude as _wave, _freq, "
             "_offs, _ampl and _vrms commands, then reads the obtained values with query_ref", source="upstream_code",
             ref="Alia_protocol_serial.py:819-844"),
        Fact("Alia.query_ref sends '?' and parses the waveform, frequency, offset, amplitude, RMS amplitude and the "
             "two clipping flags from a tab-separated reply", source="upstream_code",
             ref="Alia_protocol_serial.py:685-697"),
        Fact("The firmware derives the reference frequency from the sampling rate as Fs/N_LUT and clamps N_LUT to "
             "the allowed look-up-table size", source="upstream_code",
             ref="mcu_source/v1.0.0_VSCODE/src/main.cpp:374-380"),
        Fact("The look-up-table size is clamped between MIN_N_LUT 20 and MAX_N_LUT 1000 samples", source="upstream_code",
             ref="mcu_source/v1.0.0_VSCODE/src/main.cpp:288-289"),
        Fact("The firmware clamps the reference offset, amplitude and RMS amplitude to at least 0.0 V",
             source="upstream_code", ref="mcu_source/v1.0.0_VSCODE/src/main.cpp:382-398"),
        Fact("The firmware sets a clipping flag when the scaled reference waveform falls below 0.0 or above 1.0 of "
             "the analog reference", source="upstream_code",
             ref="mcu_source/v1.0.0_VSCODE/src/main.cpp:332-340"),
        Fact("Alia.turn_on writes 'on' and Alia.turn_off writes 'off'; turn_off clears the input buffer and waits for "
             "the off acknowledgement", source="upstream_code", ref="Alia_protocol_serial.py:399-430"),
        Fact("Alia.begin turns the lock-in amplifier off at startup", source="upstream_code",
             ref="Alia_protocol_serial.py:185"),
        Fact("While the lock-in amplifier is running, the firmware switches it off on any received command, clears "
             "the transmit triggers and answers 'off'", source="upstream_code",
             ref="mcu_source/v1.0.0_VSCODE/src/main.cpp:753-779"),
        Fact("On the transition from running to off, the firmware drives the DAC output to 0 V", source="upstream_code",
             ref="mcu_source/v1.0.0_VSCODE/src/main.cpp:582-584"),
        Fact("Alia.query_ADC_autocalibration sends 'autocal?' and stores is_valid, gaincorr and offsetcorr from three "
             "tab-separated integers", source="upstream_code", ref="Alia_protocol_serial.py:548-568"),
        Fact("The firmware reports the ADC calibration as is_valid, gaincorr and offsetcorr", source="upstream_code",
             ref="mcu_source/v1.0.0_VSCODE/src/main.cpp:1075-1079"),
        Fact("The Alia constructor defaults to 1e6 baud with 1 s read and write timeouts", source="upstream_code",
             ref="Alia_protocol_serial.py:139-158"),
    ]
    safe_state = "acquisition stopped and the reference DAC driven to 0 V by the native off command"

    # -- reads ----------------------------------------------------------------------------------------------------
    def _query_ref(self):
        if not self.native.query_ref():
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.query_ref() returned False")
        return self.native.config

    def _query_autocal(self):
        if not self.native.query_ADC_autocalibration():
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.query_ADC_autocalibration() returned False")
        return self.native.config

    @read("ref_waveform", type="string",
          description="Reference waveform reported by the device (Sine, Square or Triangle)")
    def ref_waveform(self):
        return self._query_ref().ref_waveform.name

    @read("ref_freq", unit="Hz", description="Reference frequency reported by the device")
    def ref_freq(self):
        return float(self._query_ref().ref_freq)

    @read("ref_offset", unit="V", description="Reference signal DC offset reported by the device")
    def ref_offset(self):
        return float(self._query_ref().ref_V_offset)

    @read("ref_amplitude", unit="V", description="Reference signal peak amplitude reported by the device")
    def ref_amplitude(self):
        return float(self._query_ref().ref_V_ampl)

    @read("ref_amplitude_rms", unit="V",
          description="Reference signal amplitude in RMS volts reported by the device")
    def ref_amplitude_rms(self):
        return float(self._query_ref().ref_V_ampl_RMS)

    @read("ref_clipping_high", type="boolean", description="True when the reference waveform clips at the high rail")
    def ref_clipping_high(self):
        return bool(self._query_ref().ref_is_clipping_HI)

    @read("ref_clipping_low", type="boolean", description="True when the reference waveform clips at the low rail")
    def ref_clipping_low(self):
        return bool(self._query_ref().ref_is_clipping_LO)

    @read("adc_autocal_valid", type="boolean", description="True when the stored ADC autocalibration is valid")
    def adc_autocal_valid(self):
        return bool(self._query_autocal().ADC_autocal_is_valid)

    @read("adc_autocal_gaincorr", type="integer", description="ADC autocalibration gain correction (device counts)")
    def adc_autocal_gaincorr(self):
        return int(self._query_autocal().ADC_autocal_gaincorr)

    @read("adc_autocal_offsetcorr", type="integer",
          description="ADC autocalibration offset correction (device counts)")
    def adc_autocal_offsetcorr(self):
        return int(self._query_autocal().ADC_autocal_offsetcorr)

    @read("sampling_rate", unit="Hz", description="Sampling rate the firmware reported at begin()")
    def sampling_rate(self):
        return float(self.native.config.Fs)

    @read("block_size", type="integer", description="Samples per transmitted block reported at begin()")
    def block_size(self):
        return int(self.native.config.BLOCK_SIZE)

    @read("running", type="boolean", description="True while the lock-in amplifier is acquiring")
    def running(self):
        return not bool(self.native.lockin_paused)

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("ref_waveform", type="string", enum=_WAVEFORMS,
           description="Reference waveform: Sine, Square or Triangle",
           limit=Limit(allowed=_WAVEFORMS, source="upstream_code", ref="Alia_protocol_serial.py:42-48"))
    def set_ref_waveform(self, value):
        if not self.native.set_ref(waveform=_Waveform[value]):
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.set_ref(waveform=...) returned False")
        return self.native.config.ref_waveform.name

    @write("ref_freq", unit="Hz", description="Requested reference frequency",
           limit=Limit.operator_required(
               "the firmware derives the output frequency from the sampling rate of the installed board "
               "(Fs / N_LUT with N_LUT clamped to 20..1000), so the Hz range differs per board and firmware; the "
               "operator supplies the range for this unit"))
    def set_ref_freq(self, value):
        if not self.native.set_ref(freq=float(value)):
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.set_ref(freq=...) returned False")
        return float(self.native.config.ref_freq)

    @write("ref_offset", unit="V", description="Reference signal DC offset",
           limit=Limit(min=0.0, max=3.3, unit="V", source="vendor_doc", ref="README.rst:51"))
    def set_ref_offset(self, value):
        if not self.native.set_ref(V_offset=float(value)):
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.set_ref(V_offset=...) returned False")
        return float(self.native.config.ref_V_offset)

    @write("ref_amplitude", unit="V", description="Reference signal peak amplitude",
           limit=Limit(min=0.0, max=3.3, unit="V", source="vendor_doc", ref="README.rst:51"))
    def set_ref_amplitude(self, value):
        if not self.native.set_ref(V_ampl=float(value)):
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.set_ref(V_ampl=...) returned False")
        return float(self.native.config.ref_V_ampl)

    @write("ref_amplitude_rms", unit="V", description="Reference signal amplitude in RMS volts",
           limit=Limit(min=0.0, max=3.3, unit="V", source="vendor_doc", ref="README.rst:51"))
    def set_ref_amplitude_rms(self, value):
        if not self.native.set_ref(V_ampl_RMS=float(value)):
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.set_ref(V_ampl_RMS=...) returned False")
        return float(self.native.config.ref_V_ampl_RMS)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.dennis-van-gils.start_acquisition.v1",
            description="Start the lock-in acquisition (the native on command); it takes no input",
            output={"running": Field("boolean", description="True once the acquisition is running")})
    def start_acquisition(self):
        if not self.native.turn_on():
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.turn_on() returned False")
        return {"running": not bool(self.native.lockin_paused)}

    @action(name="x-cap.dennis-van-gils.stop_acquisition.v1", safe_state=True,
            description="Stop the lock-in acquisition (the native off command, the safe state); it takes no input",
            output={"running": Field("boolean", description="False once the acquisition is stopped")})
    def stop_acquisition(self):
        success, _was_off, _answer = self.native.turn_off()
        if not success:
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.turn_off() returned False")
        return {"running": not bool(self.native.lockin_paused)}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="turn_off")
    def stop(self):
        """The native stop: the runtime latches first, then sends off (Alia_protocol_serial.py:406-457)."""
        success, _was_off, _answer = self.native.turn_off()
        if not success:
            raise DriverFailed("MHS.DEVICE.FAULTED", "Alia.turn_off() returned False")
