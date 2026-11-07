"""OpenMHS driver for gh.karimrayttu/ece-tool-suite: the KeysightScope oscilloscope class.

A direct Driver (decorated methods) over the upstream high-level class
``ece_suite.instruments.keysight:KeysightScope``.  The class wraps a VISA transport and speaks the
InfiniiVision-compatible SCPI dialect used for Keysight, Rigol, Siglent, Rohde & Schwarz and GW
Instek scopes (docs/instruments.md:28-31).  Every channel command embeds the channel number and is
assembled at run time, so the card's PythonObjectDriver helper cannot express the interface as a
command table; this package uses a direct Driver with a native.py factory (DEVIATION FROM THE CARD,
recorded in RESULT.json).

* reads: identity and the light six-measurement set the upstream snapshot uses for streaming;
* actions: one automatic measurement from the 16-item set, peak-to-peak voltage, a scalar capture
  summary, run, single, reset and a safe-state stop;
* the e-stop sends the native stop (``:STOP``): acquisition is halted and the frozen display is the
  oscilloscope's safe state.

No setting write is served.  ``KeysightScope`` writes the channel, timebase, trigger and acquisition
settings but has no query method for any of them (keysight.py:49-108); a write without a readable
state field would not be observable, so the package does not expose one.

NOT COVERED: the waveform array.  ``capture`` transfers an IEEE 488.2 binary block (:WAV:DATA?) and
returns time and voltage arrays (keysight.py:151-161); the standard has no trace-array class yet, so
the capture action reports only the scalar summary (points, vpp, duration).  The PNG screenshot and
the FFT are not exposed.

Every Fact cites a line of the clone at the pinned commit 13f7962a674ebc998a2ad2a31eb8592df65ad022.
This package is model-authored and unreviewed: it is checked on the fake backend only, and nothing
here ran on an instrument.
"""

from mhs.driver import Driver, Fact, Field, action, estop, read

#: The 16 measurements and units of KeysightScope._MEAS_ALL (backend/ece_suite/instruments/keysight.py:175-184).
ALL_MEASUREMENTS = (
    "vpp", "vamp", "vmax", "vmin", "vtop", "vbase", "vavg", "vrms",
    "freq", "period", "duty", "pwidth", "nwidth", "rise", "fall", "over",
)

#: The light six-measurement set KeysightScope.measure returns (keysight.py:163-171).
LIGHT_MEASUREMENTS = {
    "vpp": ("V", "Peak-to-peak voltage of channel 1"),
    "vrms": ("V", "Root-mean-square voltage of channel 1"),
    "vmax": ("V", "Maximum voltage of channel 1"),
    "vmin": ("V", "Minimum voltage of channel 1"),
    "freq": ("Hz", "Frequency of channel 1"),
    "period": ("s", "Period of channel 1"),
}

#: The unit of each of the 16 measurements, copied from the upstream table (keysight.py:175-184).
MEASUREMENT_UNITS = {
    "vpp": "V", "vamp": "V", "vmax": "V", "vmin": "V",
    "vtop": "V", "vbase": "V", "vavg": "V", "vrms": "V",
    "freq": "Hz", "period": "s", "duty": "%", "pwidth": "s",
    "nwidth": "s", "rise": "s", "fall": "s", "over": "%",
}


class EceToolSuiteScope(Driver):
    device_id = "ece-scope"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "ece_suite.instruments.keysight:KeysightScope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKeysightScope"}
    vendor = "Keysight Technologies"
    model = "InfiniiVision-class oscilloscope"
    display_name = "ECE Tool Suite oscilloscope (ece_suite.instruments.keysight.KeysightScope)"
    tags = ["oscilloscope", "scpi", "visa", "keysight", "infiniivision", "measurement"]
    facts = [
        Fact("The default scope driver speaks the InfiniiVision-compatible SCPI set (:CHANx:SCAL, "
             ":TIM:SCAL, :TRIG:EDGE, :MEAS:*, :WAV:PRE? plus an IEEE-488.2 definite-length block) and "
             "covers Keysight, Rigol, Siglent, Rohde & Schwarz and GW Instek scopes",
             source="vendor_doc", ref="docs/instruments.md:28-31"),
        Fact("identify queries *IDN? and passes the reply to parse_idn", source="upstream_code",
             ref="backend/ece_suite/instruments/keysight.py:42-43"),
        Fact("parse_idn splits the *IDN? reply into vendor, model, serial and firmware", source="upstream_code",
             ref="backend/ece_suite/instruments/scpi.py:30-35"),
        Fact("reset writes *RST and then *CLS", source="upstream_code",
             ref="backend/ece_suite/instruments/keysight.py:45-47"),
        Fact("run, stop and single write :RUN, :STOP and :SINGle", source="upstream_code",
             ref="backend/ece_suite/instruments/keysight.py:110-117"),
        Fact("capture selects :WAV:SOUR, sets :WAV:FORM WORD and :WAV:BYT LSBF, reads :WAV:PRE? and "
             ":WAV:DATA?, and returns a Waveform with points and vpp metadata", source="upstream_code",
             ref="backend/ece_suite/instruments/keysight.py:151-161"),
        Fact("measure queries :MEAS:VPP?, :MEAS:VRMS?, :MEAS:VMAX?, :MEAS:VMIN?, :MEAS:FREQ? and "
             ":MEAS:PER? on the requested channel", source="upstream_code",
             ref="backend/ece_suite/instruments/keysight.py:163-171"),
        Fact("safe_float returns None instead of a value whose magnitude is above 1e30", source="upstream_code",
             ref="backend/ece_suite/instruments/scpi.py:38-42"),
        Fact("measure_all queries the 16-item InfiniiVision measurement set and tags each value with the "
             "unit V, Hz, s or %", source="upstream_code",
             ref="backend/ece_suite/instruments/keysight.py:175-190"),
        Fact("The VISA transport opens a pyvisa resource with a default timeout of 5000 ms and newline "
             "read and write terminators", source="upstream_code",
             ref="backend/ece_suite/instruments/transport.py:42-82"),
        Fact("VisaTransport serializes write, query and query_raw on a lock and closes both the instrument "
             "handle and the resource manager", source="upstream_code",
             ref="backend/ece_suite/instruments/transport.py:87-104"),
        Fact("The oscilloscope tab has four channels with V/div, offset, coupling and probe attenuation, "
             "timebase and trigger controls, Run/Stop/Single, and a measurement strip read back from the "
             "instrument", source="vendor_doc", ref="README.md:211-214"),
        Fact("The control-to-SCPI table maps set_channel, set_timebase, set_trigger, set_acquisition and "
             "run/stop/single to the Keysight dialect", source="vendor_doc",
             ref="docs/tutorial/03-instruments.md:138-152"),
        Fact("The measurement strip polls the full 16-item InfiniiVision set on demand, Keysight's ~9.9E37 "
             "invalid sentinel is filtered to null, and the 5 Hz stream carries only the light six-measurement "
             "set", source="vendor_doc", ref="docs/tutorial/03-instruments.md:178"),
        Fact("The scope front-end absolute maximum is 5 V at 50 ohm and 300 V at 1 Mohm, scaled by probe "
             "attenuation", source="vendor_doc", ref="docs/tutorial/02-architecture.md:242"),
        Fact("The runtime has scope_capture and scope_measure_vpp functions that call capture(1) and "
             "measure_vpp(1)", source="upstream_code", ref="backend/ece_suite/main.py:100-112"),
    ]
    safe_state = "acquisition stopped by the native :STOP; the frozen display is the safe state"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity (*IDN? reply)")
    def identity(self):
        return self.native.identify().raw

    @read("measurements", type="object",
          description="The light six-measurement set of channel 1, as the upstream snapshot reads it",
          properties={name: Field("number", unit=unit, description=description, nullable=True)
                      for name, (unit, description) in LIGHT_MEASUREMENTS.items()})
    def measurements(self):
        return self.native.measure()

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.karimrayttu.measure.v1",
            description="Read one scalar automatic measurement from the scope's current measurement set",
            input={"item": Field("string", description="Measurement item, for example vpp, freq or period",
                                 enum=list(ALL_MEASUREMENTS))},
            output={"item": Field("string", description="Measurement item that was read"),
                    "value": Field("number", nullable=True,
                                   description="Measured value; null when the scope reports its invalid sentinel"),
                    "unit": Field("string", description="Unit of the measurement item")})
    def measure_item(self, item):
        reading = self.native.measure_all().get(item)
        if reading is None:
            raise ValueError(f"the scope reported no measurement named {item!r}")
        return {"item": item, "value": reading["value"], "unit": reading["unit"]}

    @action(name="x-cap.karimrayttu.measure_vpp.v1",
            description="Measure peak-to-peak voltage on channel 1 (:MEAS:VPP?)",
            output={"vpp": Field("number", unit="V", description="Peak-to-peak voltage of channel 1")})
    def measure_vpp(self):
        return {"vpp": self.native.measure_vpp(1)}

    @action(name="x-cap.karimrayttu.capture.v1",
            description="Capture channel 1 and report a scalar summary of the record; the waveform array "
                        "itself is not transferred",
            output={"points": Field("integer", unit="1", description="Number of points in the captured record"),
                    "vpp": Field("number", unit="V", description="Peak-to-peak voltage of the captured record"),
                    "duration_s": Field("number", unit="s", description="Time from the first to the last point")})
    def capture(self):
        waveform = self.native.capture(1)
        duration = float(waveform.t[-1] - waveform.t[0]) if waveform.t else 0.0
        return {"points": int(waveform.meta["points"]), "vpp": float(waveform.meta["vpp"]),
                "duration_s": duration}

    @action(name="x-cap.karimrayttu.run.v1", description="Start continuous acquisition (:RUN)",
            output={"state": Field("string", description="State requested from the scope: running")})
    def run(self):
        self.native.run()
        return {"state": "running"}

    @action(name="x-cap.karimrayttu.single.v1", description="Arm one acquisition (:SINGle)",
            output={"state": Field("string", description="State requested from the scope: single")})
    def single(self):
        self.native.single()
        return {"state": "single"}

    @action(name="x-cap.karimrayttu.reset.v1", description="Reset the scope to its default setup (*RST and *CLS)",
            output={"state": Field("string", description="State requested from the scope: reset")})
    def reset_instrument(self):
        self.native.reset()
        return {"state": "reset"}

    @action(name="x-cap.karimrayttu.stop_acquisition.v1", safe_state=True,
            description="Stop acquisition (:STOP, the safe state); it takes no input",
            output={"state": Field("string", description="State requested from the scope: stopped")})
    def stop_acquisition(self):
        self.native.stop()
        return {"state": "stopped"}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends :STOP."""
        self.native.stop()

    def teardown(self):
        self.native.t.close()
