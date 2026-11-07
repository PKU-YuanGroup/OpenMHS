"""OpenMHS driver for gh.naqslab/naqslab_devices: the SR865 lock-in amplifier over SCPI (a family driver).

The upstream repository is a collection of labscript device classes.  This package covers one of its entry
symbols, ``SR865.labscript_device:SR865``: the three static settings the upstream class exposes (time constant,
sensitivity and phase reference) and the worker commands that program and read them.  The other entry symbols
(SignalGenerator Models and NovaTech DDS) are compile-time labscript devices with a different command map and are
not exposed by this package.

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The commands are the raw commands of the upstream
worker (``OFLT``, ``SCAL`` and ``PHAS`` in SR865/blacs_worker.py); the bridge opens the instrument itself
(``host``/``port`` or a VISA resource, options of the hardware backend), so only the commands and the allowed
setting values are shared.

* reads: the instrument index of the time constant (OFLT?), the instrument index of the sensitivity (SCAL?) and
  the phase reference in degrees (PHAS?);
* writes: time constant in seconds, sensitivity in volts and phase in degrees, each limited by the values the
  upstream code states; the two index-valued settings are translated to the same 0-based index the upstream
  ``numpy.digitize`` calls compute;
* the e-stop writes ``*CLS``, the status-clear command of the upstream worker; this driver controls no output,
  so the clear leaves the measurement settings alone.

Every Limit and Fact cites a line of the clone at the pinned commit (2c0ac4fb715ec7ad71c6f0061cd3c7e3d6583b69).
This package is model-authored and unreviewed, and its wire syntax has not been tried on an instrument.
"""

from mhs.driver import Fact, Field, Limit, ScpiDriver

DEVICE = "SR865/labscript_device.py"
WORKER = "SR865/blacs_worker.py"

#: The 28 sensitivities in the order of their SCAL index, transcribed from the upstream ``sens`` array
#: (SR865/labscript_device.py:20-22): 1 V down to 1 nV.
SENSITIVITIES = [
    1, 500e-3, 200e-3, 100e-3, 50e-3, 20e-3, 10e-3, 5e-3, 2e-3, 1e-3,
    500e-6, 200e-6, 100e-6, 50e-6, 20e-6, 10e-6, 5e-6, 2e-6, 1e-6,
    500e-9, 200e-9, 100e-9, 50e-9, 20e-9, 10e-9, 5e-9, 2e-9, 1e-9,
]

#: The 22 time constants in the order of their OFLT index, transcribed from the upstream ``tau`` array
#: (SR865/labscript_device.py:24-26): 1 us up to 30 ks.
TIME_CONSTANTS = [
    1e-6, 3e-6, 10e-6, 30e-6, 100e-6, 300e-6,
    1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3,
    1, 3, 10, 30, 100, 300, 1e3, 3e3, 10e3, 30e3,
]


class Sr865(ScpiDriver):
    device_id = "sr865"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "SR865.labscript_device:SR865"
    backends = {"fake": ".fake:FakeSr865"}
    vendor, model = "Stanford Research Systems", "SR865 lock-in amplifier"
    display_name = "SRS SR865 lock-in amplifier"
    tags = ["lock-in amplifier", "sr865", "scpi", "labscript"]
    #: The upstream worker does not identify the instrument; it starts with '*ESE 122;*CLS;'
    #: (SR865/blacs_worker.py:53), so there is no identity probe on connect.
    idn = False
    facts = [
        Fact("The SR865 is a lock-in amplifier; the upstream class is described as 'SR865 Lock-In Amplifier'",
             source="upstream_code", ref=f"{DEVICE}:28-29"),
        Fact("The valid sensitivities are the 28 values of the sens array, from 1 V down to 1 nV",
             source="upstream_code", ref=f"{DEVICE}:20-22"),
        Fact("The valid time constants are the 22 values of the tau array, from 1 us up to 30 ks",
             source="upstream_code", ref=f"{DEVICE}:24-26"),
        Fact("set_tau rejects a value that is not exactly one of the tau array values",
             source="upstream_code", ref=f"{DEVICE}:50-53"),
        Fact("set_tau converts a valid time constant to its OFLT index with "
             "np.digitize(tau_constant, tau, right=True), so 1 us is index 0",
             source="upstream_code", ref=f"{DEVICE}:50-51"),
        Fact("set_sens rejects a value that is not exactly one of the sens array values",
             source="upstream_code", ref=f"{DEVICE}:62-65"),
        Fact("set_sens converts a valid sensitivity to its SCAL index with np.digitize(sensitivity, sens), "
             "so 1 V is index 0",
             source="upstream_code", ref=f"{DEVICE}:62-63"),
        Fact("The phase reference is in degrees; the device auto-converts it to the -180,180 range",
             source="upstream_code", ref=f"{DEVICE}:67-69"),
        Fact("The worker programs the three settings with 'OFLT {:d};SCAL {:d};PHAS {:.6f}'",
             source="upstream_code", ref=f"{WORKER}:22"),
        Fact("The worker reads the three settings with 'OFLT?;SCAL?;PHAS?'",
             source="upstream_code", ref=f"{WORKER}:23"),
        Fact("The worker sends '*ESE 122;*CLS;' during initialization", source="upstream_code",
             ref=f"{WORKER}:53"),
    ]
    parameters = {
        "time_constant": Field(
            "number", unit="s", writable=True,
            description="Time constant of the low-pass filter (OFLT index selected from seconds)",
            limit=Limit(allowed=TIME_CONSTANTS, source="upstream_code", ref=f"{DEVICE}:24-26")),
        "sensitivity": Field(
            "number", unit="V", writable=True,
            description="Signal input sensitivity (SCAL index selected from volts)",
            limit=Limit(allowed=SENSITIVITIES, source="upstream_code", ref=f"{DEVICE}:20-22")),
        "phase": Field(
            "number", unit="deg", writable=True,
            description="Phase reference in degrees (PHAS)",
            limit=Limit(min=-180, max=180, source="upstream_code", ref=f"{DEVICE}:67-69",
                        reason="the docstring states the device converts phase into the -180,180 range")),
        "tau_index": Field(
            "integer", description="Index the instrument reports for the time constant (OFLT?)"),
        "sens_index": Field(
            "integer", description="Index the instrument reports for the sensitivity (SCAL?)"),
    }
    reads = {
        "tau_index": {"query": "OFLT?", "parse": {"kind": "int"}},
        "sens_index": {"query": "SCAL?", "parse": {"kind": "int"}},
        "phase": {"query": "PHAS?", "parse": {"kind": "float"}},
    }
    writes = {
        "time_constant": {"write": "OFLT {value:d}", "type": "integer",
                          "enum_map": {seconds: index for index, seconds in enumerate(TIME_CONSTANTS)}},
        "sensitivity": {"write": "SCAL {value:d}", "type": "integer",
                        "enum_map": {volts: index for index, volts in enumerate(SENSITIVITIES)}},
        "phase": {"write": "PHAS {value:.6f}", "type": "number"},
    }
    safe_state = ("status registers cleared (*CLS); this driver controls no output and leaves the measurement "
                  "settings unchanged")
    safety_bindings = {"estop": {"write": "*CLS"}}
