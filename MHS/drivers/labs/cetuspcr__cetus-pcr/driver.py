"""OpenMHS driver for gh.cetuspcr/cetus-pcr: the Cetus PCR low-cost thermocycler.

A direct Driver over the card's entry class ``functions:ArduinoPCR`` (functions.py:72), the host-side controller of
the Cetus PCR.  The controller is a GUI program: it scans the serial ports, checks the ``Cetus is ready.`` startup
line (functions.py:234-262), then starts ``serial_monitor`` to parse ``tempSample`` and ``tempLid`` lines
(functions.py:184-232).  The Arduino firmware accepts framed text commands between ``<`` and ``>`` with
space-separated integer arguments (arduino/cetuspcr/serialtools.h:13-15): ``<peltier state pwm_signal>``, where
state 0 is heating and state 1 is cooling (serialtools.h:81-102), and ``<printTemps argument>``
(serialtools.h:104-107).

A SerialDriver command table cannot express this device: the host reads unsolicited multi-line replies, and the
experiment loop is a method of the upstream class, not a request/response command.  The driver therefore uses the
upstream object directly (a direct Driver, a deviation from the card's helper; see RESULT.json notes).

* reads: the block (sample) and lid temperatures, the running flag and the current experiment step and cycle;
* one action: run one temperature hold step for a number of cycles through the upstream PID experiment loop
  (``ArduinoPCR.run_experiment``, functions.py:115-182); when the loop returns, the driver clears ``is_running`` and
  writes ``<peltier 0 0>`` so a finished or failed run does not leave a PWM drive set;
* the safe state and the e-stop clear ``is_running``, set ``is_waiting`` so the upstream loop takes its cancellation
  branch, and write ``<peltier 0 0>`` through the open serial device (functions.py:135-144); the cooling button of
  the upstream application writes the same zero command (interface.py:349).

The temperature, duration and cycle inputs are ``Limit.operator_required``: no text file of the clone states a safe
temperature range, a maximum hold time or a maximum cycle count for the machine.  The PCR phase temperatures in the
report are protocol examples, not device limits.  Until an operator supplies the ranges in site-limits.json, every
call is refused ``MHS.SAFETY.LIMITS_UNSET``.  This is R2 because the Peltier heats the sample block; the safe-state
action satisfies SAFE-045 for a model-written package.  The hardware path was never run, and the package is
model-authored and unreviewed.
"""

from types import SimpleNamespace

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

_TEMPERATURE_REASON = (
    "no text file of the clone states a safe sample temperature range for the machine: the firmware drives the "
    "Peltier directly by PWM and has no temperature setpoint command (arduino/cetuspcr/serialtools.h:81-107); the "
    "PCR phase temperatures in the report are protocol examples, not limits of this device. The site supplies the "
    "range of its machine"
)
_DURATION_REASON = (
    "no text file of the clone states a maximum hold time: the upstream loop runs until the step duration the "
    "operator entered (functions.py:131-170). The site supplies the longest hold it allows"
)
_CYCLES_REASON = (
    "no text file of the clone states a maximum cycle count: the upstream loop is range(int(n_cycles)) with no "
    "bound (functions.py:123). The site supplies the number of cycles it allows"
)


class CetusPcr(Driver):
    device_id = "cetus-pcr"
    device_kind = "lab.thermal_block"
    mode = "hardware"
    risk = "R2"
    native = "functions:ArduinoPCR"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCetusPcr"}
    vendor, model = "CetusPCR", "Cetus PCR thermocycler"
    display_name = "Cetus PCR low-cost thermocycler (functions.ArduinoPCR)"
    tags = ["thermocycler", "pcr", "peltier", "serial", "temperature", "thermal block"]
    facts = [
        Fact("ArduinoPCR is the host-side serial controller class of the Cetus PCR",
             source="upstream_code", ref="functions.py:72"),
        Fact("The application constructs the controller with baudrate 9600 and timeout 1",
             source="upstream_code", ref="interface.py:872"),
        Fact("The Arduino firmware opens the serial port at 9600 baud",
             source="upstream_code", ref="arduino/cetuspcr/cetuspcr.ino:4"),
        Fact("The firmware announces 'Cetus is ready.' after its setup",
             source="upstream_code", ref="arduino/cetuspcr/serialtools.h:31"),
        Fact("The firmware frames a command between '<' and '>' and splits its arguments on spaces",
             source="upstream_code", ref="arduino/cetuspcr/serialtools.h:13-15"),
        Fact("The command <peltier state pwm_signal> uses state 0 to heat and state 1 to cool",
             source="upstream_code", ref="arduino/cetuspcr/serialtools.h:81-102"),
        Fact("A heating command writes the heat PWM, clears the cool PWM and prints tempSample and tempLid",
             source="upstream_code", ref="arduino/cetuspcr/serialtools.h:84-94"),
        Fact("A cooling command writes the cool PWM and clears the heat PWM",
             source="upstream_code", ref="arduino/cetuspcr/serialtools.h:96-101"),
        Fact("The firmware ends every processed command with the line nextpls",
             source="upstream_code", ref="arduino/cetuspcr/serialtools.h:108"),
        Fact("The firmware handles only the peltier and printTemps commands; it has no temperature setpoint command",
             source="upstream_code", ref="arduino/cetuspcr/serialtools.h:81-107"),
        Fact("The controller sends <peltier 0 N> for heating and <peltier 1 N> for cooling, with N the integer PID "
             "output or its absolute value", source="upstream_code", ref="functions.py:149-153"),
        Fact("The PID output is limited to -255 to 255", source="upstream_code", ref="functions.py:86"),
        Fact("On cancellation the upstream loop writes <peltier 0 0> and returns",
             source="upstream_code", ref="functions.py:137-144"),
        Fact("The experiment loop checks is_running only inside the is_waiting branch",
             source="upstream_code", ref="functions.py:135-137"),
        Fact("serial_monitor sets is_waiting True when a nextpls line arrives", source="upstream_code",
             ref="functions.py:211-212"),
        Fact("serial_monitor parses tempSample and tempLid lines into current_sample_temperature and "
             "current_lid_temperature", source="upstream_code", ref="functions.py:200-206"),
        Fact("run_experiment repeats the experiment steps n_cycles times", source="upstream_code",
             ref="functions.py:123-125"),
        Fact("initialize_connection scans the serial ports, opens the matching port and checks the startup line "
             "before starting serial_monitor", source="upstream_code", ref="functions.py:234-262"),
        Fact("The upstream close path clears is_running, clears is_connected and closes the serial device",
             source="upstream_code", ref="interface.py:324-327"),
    ]
    safe_state = ("Peltier drives at zero PWM (is_running cleared and <peltier 0 0> written; the firmware also "
                  "clears the cooling PWM)")

    # -- reads -------------------------------------------------------------------------------------------------
    @read("sample_temperature", unit="Cel",
          description="Sample-block temperature the serial monitor last read from a tempSample line")
    def sample_temperature(self):
        return float(self.native.current_sample_temperature)

    @read("lid_temperature", unit="Cel",
          description="Lid temperature the serial monitor last read from a tempLid line")
    def lid_temperature(self):
        return float(self.native.current_lid_temperature)

    @read("is_running", type="boolean",
          description="True while an experiment loop is running; the e-stop and the safe state clear it")
    def is_running(self):
        return bool(self.native.is_running)

    @read("current_step", type="string",
          description="Name of the experiment step the upstream loop is running, empty before the first step")
    def current_step(self):
        return str(self.native.current_step)

    @read("current_cycle", type="integer",
          description="Number of the experiment cycle the upstream loop is running, 0 before the first cycle")
    def current_cycle(self):
        return int(self.native.current_cycle)

    # -- the experiment action ---------------------------------------------------------------------------------
    # The 24 h max_duration_ms is the runtime bound of one long-running call, not a device limit; the operator's
    # duration_s and cycles limits bound what the protocol may ask the machine to do.
    @action(name="x-cap.cetuspcr.run_protocol.v1", long_running=True, max_duration_ms=86400000,
            cancellable=True,
            description="Run one temperature hold step for a number of cycles through the upstream PID experiment "
                        "loop; the Peltier is driven by that loop, not by a temperature setpoint of the firmware",
            input={
                "temperature": Field("number", unit="Cel",
                                     description="Target sample-block temperature of the hold step",
                                     limit=Limit.operator_required(_TEMPERATURE_REASON)),
                "duration_s": Field("number", unit="s",
                                    description="Duration of one hold step, in seconds",
                                    limit=Limit.operator_required(_DURATION_REASON)),
                "cycles": Field("integer", unit="1",
                                description="Number of times the hold step is repeated",
                                limit=Limit.operator_required(_CYCLES_REASON)),
                "name": Field("string", description="Experiment name, used in the upstream log file name"),
            },
            output={
                "completed": Field("boolean", description="True when the upstream loop returned after the last cycle"),
                "cycles_completed": Field("integer", description="Cycle number the upstream loop reached last"),
                "actual_temperature": Field("number", unit="Cel",
                                            description="Sample-block temperature after the loop returned"),
                "actual_duration_s": Field("number", unit="s",
                                           description="Elapsed experiment time the upstream loop last reported"),
            })
    def run_protocol(self, temperature, duration_s, cycles, name="cetus hold"):
        steps = [SimpleNamespace(name="hold", temperature=float(temperature), duration=float(duration_s))]
        self.native.experiment = SimpleNamespace(name=str(name), n_cycles=int(cycles), final_hold=0, steps=steps)
        self.native.is_running = True
        try:
            self.native.run_experiment()
        finally:
            if self.native.is_running:
                self.native.is_running = False
            self._write_peltier_off()
        self.check_cancelled()
        return {
            "completed": True,
            "cycles_completed": int(self.native.current_cycle),
            "actual_temperature": float(self.native.current_sample_temperature),
            "actual_duration_s": float(self.native.elapsed_time),
        }

    # -- safety ------------------------------------------------------------------------------------------------
    @action(name="x-cap.cetuspcr.stop_peltier.v1", safe_state=True,
            description="Clear the experiment flag and write <peltier 0 0>, setting both Peltier PWMs to zero; it "
                        "takes no input",
            output={"stopped": Field("boolean", description="True once the zero-PWM command was written")})
    def stop_peltier(self):
        self.native.is_running = False
        self.native.is_waiting = True
        self._write_peltier_off()
        return {"stopped": True}

    @estop(native="serial_device")
    def stop(self):
        """Clear is_running, let the loop take its cancellation branch, and write <peltier 0 0>."""
        self.native.is_running = False
        self.native.is_waiting = True
        self._write_peltier_off()

    def _write_peltier_off(self) -> None:
        device = self.native.serial_device
        if device is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               "the Cetus PCR serial device is not open, so the Peltier cannot be set to zero")
        device.write(b"<peltier 0 0>")

    # -- lifecycle ---------------------------------------------------------------------------------------------
    def setup(self):
        if not self.native.is_connected:
            self.native.initialize_connection()
        if not self.native.is_connected:
            raise DriverFailed("MHS.DEVICE.NOT_READY",
                               "the Cetus PCR serial port did not report 'Cetus is ready.'")

    def teardown(self):
        self.native.is_running = False
        if self.native.is_connected:
            self.native.is_connected = False
            device = self.native.serial_device
            if device is not None:
                device.close()
