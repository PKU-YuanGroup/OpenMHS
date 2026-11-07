"""OpenMHS driver for gh.moler-group/scanning-squid: the scanning SQUID microscope's Attocube coarse positioner.

Authored by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 (the user's decision of 2026-11-05:
Claude authors, Claude Sonnet reviews).  The earlier DeepSeek package served the BlueFors warm-up heater supply, a
peripheral of the repository, through an invented native (blocked, G7.NATIVE_NOT_FOUND).

The repository's device.  scanning-squid controls a scanning SQUID microscope: "A physical scanning SQUID microscope is
represented by an instance of the Microscope class (or likely one of its subclasses, like SusceptometerMicroscope)"
(docs/pages/microscope.rst:4).  The microscope is a QCoDeS Station that builds an Attocube ANC300 controller, two
Lakeshore temperature controllers, the x/y/z piezo scanner driven by NI-DAQ analog outputs, the SQUID record and the
SR830 lock-ins (microscope/microscope.py:75-121); the documentation's examples construct a
``SusceptometerMicroscope`` (susceptometer.py:51; docs/examples/ApproachGetSurfaceExample.ipynb), imported, as the
documentation says, with the repository's scanning-squid directory on the path (``microscope.susceptometer``;
docs/pages/workflow.rst:15).  That class is this package's native, and the card's override names it.

What is served, and why only that.  The microscope moves the SQUID relative to the sample in two ways: the piezo
scanner, whose ``goto`` writes a ramp to a DAQ output task created and awaited inside the call (scanner.py:159-168)
and so cannot be stopped from outside, and the Attocube stick-slip positioners on the ANC300, which have a stop:
``stop(axis)`` sends ``stop <n>`` and then sets the axis mode to ``gnd`` (instruments/atto.py:143-152).  Under the
e-stop rule only the Attocube stepping can be served.  It is R2: the documentation names the approach as "the most
dangerous" part of a measurement, where a missed touchdown crashes the SQUID into the sample with the Attocubes
(workflow.rst:34-38), and warns about crashing when moving the Attocubes (workflow.rst:54).

* ``x-cap.moler-group.atto_step.v1``: ``atto.step(axis, steps)`` (atto.py:154-177): mode ``stp``, one ``stepu`` or
  ``stepd`` command with the axis and the count, ``stepw``, a wait of abs(steps)/frequency*1.25 s, mode ``gnd``; the
  output reports the mode read back after it.  ``steps`` is ``Limit.operator_required`` (no source bounds a step
  count; the site decides how far a model may step each axis, and the sign of a z step towards the sample is a
  property of the mounting).  The step count is a request, not a measured move: ``step`` sends the step command with
  ``ask`` (atto.py:169), and the class's ``ask_raw``, which QCoDeS's ``ask`` calls, writes every command twice
  (atto.py:109-124).  The source does not show what the ANC300 does with the second copy (possibly more steps, up to
  about twice the count; a restarted count; or an ERROR reply, after which ``step`` raises with the first copy under
  way), so an operator measures the steps one command makes before setting the limit.  If ``atto.step`` raises, this
  driver stops and grounds that axis (``atto.stop``) and reports an unknown outcome;
* ``x-cap.moler-group.atto_ground.v1`` (the safe-state action) and the e-stop: ``atto.stop(axis)`` for z, x and y, then
  the mode of each axis read back through its QCoDeS parameter (``getm <n>``, atto.py:71-79); the stop fails unless
  every axis reads ``gnd``.  A grounded axis gets no drive voltage, so it cannot step;
* reads: the scanner position (``scanner.get_pos``, an NI-DAQ analog-input read clamped by the upstream to the
  configured voltage limits, scanner.py:109-131) and the three Attocube axis modes.

Not served: scanner motion (``goto``, ``retract``, scans), touchdowns, approach, surfaces, lock-ins, temperature
controllers and the heater.  ``stop`` cannot stop a scanner ramp, and the upstream holds no lock on the ANC300's VISA
session: an e-stop that lands while ``step`` is still exchanging its first commands (before its wait) may interleave
with them; the read-back then fails and the runtime keeps the latch and retries.  The driver's own reads of the axis
modes take a lock the e-stop also takes and are refused while a step is in progress.  A step checks for cancellation
under that lock before it starts, and a stop that runs while a step is in flight reports itself unconfirmed (the step
may set its axis to ``stp`` after it): the runtime keeps the latch and re-runs the stop, which confirms once the step
has returned.
"""

from __future__ import annotations

import threading

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, OutcomeUnknown, action, estop, read

ATTO = "scanning-squid/instruments/atto.py"
SCANNER = "scanning-squid/scanner.py"
MICROSCOPE = "scanning-squid/microscope/microscope.py"
SUSCEPTOMETER = "scanning-squid/microscope/susceptometer.py"

#: The Attocube axes the microscope code and its example configuration name (microscope.py:329 steps 'z';
#: docs/examples/config_susceptometer.json:49 maps x, y, z to controller axes 1, 2, 3).
AXES = ("x", "y", "z")
#: The stop grounds z first: z is the axis that approaches the sample (microscope.py:314-339).
STOP_ORDER = ("z", "x", "y")
GROUNDED = "gnd"

STEPS = Limit.operator_required(
    "no source bounds a number of Attocube steps, and the upstream writes each step command twice "
    "(atto.py:109-124, 169), so the steps one command makes are not known from the source: measure them on "
    "the bench first. How far a model may step each axis, and in which direction z approaches the sample, "
    "depend on the mounting and the sample (the documentation warns of crashing the SQUID into the sample "
    "with the Attocubes, docs/pages/workflow.rst:34-38, 54)")

_LOCK_GUARD = threading.Lock()


class ScanningSquidAttocube(Driver):
    device_id = "scanning-squid-microscope"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R2"
    native = "microscope.susceptometer:SusceptometerMicroscope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSusceptometerMicroscope"}
    vendor, model = "Moler group (Stanford)", "scanning SQUID susceptometer microscope (Attocube ANC300 positioner)"
    display_name = "Scanning SQUID microscope: Attocube coarse positioning (scanning-squid)"
    tags = ["scanning squid", "microscope", "attocube", "anc300", "qcodes", "cryogenic", "positioner"]
    safe_state = ("every Attocube axis stopped and grounded: stop(axis) sends 'stop n' and sets mode gnd "
                  "(atto.py:143-152) for z, x and y, and the e-stop succeeds only when each axis mode reads back gnd "
                  "(getm, atto.py:71-79); the piezo scanner is not stopped (its ramps cannot be) and keeps its voltage")
    facts = [
        Fact("A physical scanning SQUID microscope is represented by a Microscope or a subclass such as "
             "SusceptometerMicroscope, a QCoDeS Station of instrument components", source="vendor_doc",
             ref="docs/pages/microscope.rst:4"),
        Fact("SusceptometerMicroscope is the Microscope subclass for a scanning SQUID susceptometer and takes the "
             "configuration file and the temperature mode", source="upstream_code", ref=f"{SUSCEPTOMETER}:51-67"),
        Fact("The Microscope constructor closes every QCoDeS instrument, loads the configuration, starts file "
             "logging and adds the Attocube controller, the Lakeshore 372 and 331, the scanner, the SQUID and the "
             "lock-ins", source="upstream_code", ref=f"{MICROSCOPE}:78-121"),
        Fact("The Attocube component is an ANC300 built from the configuration's atto entry", source="upstream_code",
             ref=f"{MICROSCOPE}:123-134"),
        Fact("Importing the microscope module writes squid_units.txt into the current directory", source="upstream_code",
             ref=f"{MICROSCOPE}:62-69"),
        Fact("approach steps the z Attocube by attosteps between capacitive touchdowns until a touchdown or a safety "
             "check breaks the loop", source="upstream_code", ref=f"{MICROSCOPE}:314-339"),
        Fact("The ANC300 axis mode parameter reads with getm n and writes with setm n; its values are gnd, inp, cap, "
             "stp, off, stp+ and stp-", source="upstream_code", ref=f"{ATTO}:71-79"),
        Fact("The axis voltage parameter is limited to the configured voltage limit of the temperature mode",
             source="upstream_code", ref=f"{ATTO}:81-89"),
        Fact("ask_raw clears the device, sends the command twice, raises if the second reply contains ERROR and "
             "sleeps 0.2 s", source="upstream_code", ref=f"{ATTO}:109-124"),
        Fact("stop(axis) writes 'stop n' and then sets the axis mode to gnd", source="upstream_code",
             ref=f"{ATTO}:143-152"),
        Fact("step(axis, steps) refuses a non-integer, sets mode stp, sends stepu or stepd with the axis and the step "
             "count, writes stepw, sleeps abs(steps)/frequency*1.25 s, sets mode gnd and records the move in its "
             "metadata", source="upstream_code", ref=f"{ATTO}:154-177"),
        Fact("step sends its stepu or stepd command with ask, not write", source="upstream_code",
             ref=f"{ATTO}:168-169"),
        Fact("_parse_axis accepts an axis label or controller index of the configured axes", source="upstream_code",
             ref=f"{ATTO}:185-209"),
        Fact("Initialising the ANC300 sets each axis frequency and voltage to the configured values, grounds each "
             "axis and prints the controller version", source="upstream_code", ref=f"{ATTO}:305-319"),
        Fact("The Scanner constructor moves the scanner to [0, 0, 0]", source="upstream_code", ref=f"{SCANNER}:51-61"),
        Fact("get_pos reads the x, y and z scanner voltages with an NI-DAQ analog-input task and clamps each to the "
             "configured voltage limits", source="upstream_code", ref=f"{SCANNER}:109-131"),
        Fact("goto writes a ramp to an analog-output task created inside the call and waits until it is done",
             source="upstream_code", ref=f"{SCANNER}:133-180"),
        Fact("The documentation calls the approach the most dangerous part of a measurement: a missed touchdown "
             "crashes the SQUID into the sample using the Attocubes", source="vendor_doc",
             ref="docs/pages/workflow.rst:34-38"),
        Fact("The example configuration maps the Attocube axes x, y and z to controller axes 1, 2 and 3",
             source="vendor_doc", ref="docs/examples/config_susceptometer.json:49"),
    ]

    # -- the ANC300 session -------------------------------------------------------------------------------------------
    def _session(self) -> dict:
        """A lock for the exchanges this driver makes itself, and the number of steps in progress (lazily made)."""
        session = getattr(self, "_anc300_session", None)
        if session is None:
            with _LOCK_GUARD:
                session = getattr(self, "_anc300_session", None)
                if session is None:
                    session = {"lock": threading.RLock(), "stepping": 0}
                    self._anc300_session = session
        return session

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _axis_index(self, axis: str) -> int:
        axes = self.native.atto.axes
        if axis not in axes:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", f"the microscope configuration has no Attocube axis "
                               f"{axis!r} (configured: {sorted(axes)})")
        return int(axes[axis])

    def _mode(self, axis: str) -> str:
        index = self._axis_index(axis)
        try:
            return str(self.native.atto.parameters[f"mode_ax{index}"].get())
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            raise DriverFailed("MHS.DEVICE.FAULTED", f"reading the mode of Attocube axis {axis} failed "
                               f"({type(exc).__name__})") from exc

    def _ground_all(self) -> dict:
        """stop(axis) for z, x, y (every axis is tried), then read every mode back; gnd on all or a failure.

        It takes the session lock against this driver's own reads, never against a step in progress (atto.step holds
        no lock and sleeps between its commands, atto.py:165-173).
        """
        with self._session()["lock"]:
            return self._ground_all_locked()

    def _ground_all_locked(self) -> dict:
        failures = []
        for axis in STOP_ORDER:
            try:
                self.native.atto.stop(axis)
            except Exception as exc:  # noqa: BLE001 - stop the other axes too, then fail
                failures.append(f"stop({axis}) raised {type(exc).__name__}")
        modes = {}
        for axis in STOP_ORDER:
            try:
                modes[axis] = self._mode(axis)
            except DriverFailed as exc:
                failures.append(str(exc))
        wrong = {axis: mode for axis, mode in modes.items() if mode != GROUNDED}
        if self._session()["stepping"]:
            # atto.step sets its axis to stp and sends stepu/stepd (atto.py:167-169) at a moment this driver cannot
            # see; a stop that ran before those commands would be undone by them.  The stop is reported unconfirmed
            # while a step is in flight; the runtime keeps the latch and runs it again until none is.
            failures.append("a step command was in flight during this stop and may set its axis to stp after it "
                            "(atto.py:167-169); the stop is confirmed only by a run after the step returned")
        if failures or wrong:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the Attocube axes were not all confirmed grounded: "
                               + "; ".join(failures + [f"axis {a} reads {m!r}" for a, m in wrong.items()]))
        return {axis: modes[axis] for axis in AXES}

    def _ground_after_failure(self, axis: str) -> str:
        """atto.stop(axis) after a step that raised (atto.py:143-152), then its mode read back; says what happened."""
        with self._session()["lock"]:
            try:
                self.native.atto.stop(axis)
            except Exception as exc:  # noqa: BLE001 - reported in the unknown outcome, never swallowed
                return (f"Stopping and grounding it then raised {type(exc).__name__}: run the ground action or the "
                        "e-stop.")
            try:
                mode = self._mode(axis)
            except DriverFailed as exc:
                return f"It was stopped and grounded (atto.stop), but its mode was not read back ({exc})."
        return f"It was stopped and grounded (atto.stop); its mode reads {mode!r}."

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("scanner_position", type="array", items="number", unit="V", length=3,
          description="Scanner x, y, z DAQ voltages (NI-DAQ analog inputs; the upstream clamps each to the configured "
                      "voltage limits)")
    def scanner_position(self):
        return [float(value) for value in self.native.scanner.get_pos()]

    @read("attocube_modes", type="object",
          properties={axis: Field("string", description=f"Mode of the {axis} Attocube axis (gnd, stp, ...)")
                      for axis in AXES},
          description="Mode of each Attocube axis read with getm (atto.py:71-79)")
    def attocube_modes(self):
        session = self._session()
        with session["lock"]:
            if session["stepping"]:
                raise DriverFailed("MHS.DEVICE.BUSY", "an Attocube step is in progress; the modes are read after it "
                                   "(the ANC300 session has no lock of its own)")
            return {axis: self._mode(axis) for axis in AXES}

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.moler-group.atto_step.v1", risk="R2",
            description="Step one Attocube axis with atto.step: mode stp, stepu or stepd with the count (the upstream "
                        "writes it twice, atto.py:109-124, 169, so the steps made are not known from the source), "
                        "stepw, a wait, mode gnd",
            input={"axis": Field("string", enum=list(AXES), description="Attocube axis to step"),
                   "steps": Field("integer", unit="1", description="Number of steps requested: positive steps up, "
                                                                    "negative down (atto.py:155-156)", limit=STEPS)},
            output={"axis": Field("string", description="Axis stepped"),
                    "steps": Field("integer", description="Steps requested (the steps made are not read back)"),
                    "mode": Field("string", description="The axis mode read back after the step (gnd expected, "
                                                        "atto.py:173)")})
    def step(self, axis, steps):
        self._axis_index(axis)
        session = self._session()
        with session["lock"]:
            # Under the lock the e-stop takes: an e-stop that ran first cancelled this operation (the server cancels
            # before it stops), so no step starts after it; one that runs later sees the step in flight.
            self.check_cancelled()
            session["stepping"] += 1
        try:
            try:
                self.native.atto.step(axis, int(steps))
            except Exception as exc:  # noqa: BLE001 - the step may have run part way: ground the axis, then unknown
                raise OutcomeUnknown(f"atto.step({axis!r}, {int(steps)}) raised {type(exc).__name__}; the axis may "
                                     f"have stepped and been left in mode stp. {self._ground_after_failure(axis)}"
                                     ) from exc
        finally:
            with session["lock"]:
                session["stepping"] -= 1
        self.check_cancelled()
        with session["lock"]:
            mode = self._mode(axis)
        return {"axis": axis, "steps": int(steps), "mode": mode}

    @action(name="x-cap.moler-group.atto_ground.v1", safe_state=True, risk="R2",
            description="Stop and ground every Attocube axis (atto.stop) and read each mode back",
            output={"modes": Field("object",
                                   properties={axis: Field("string", description=f"Mode of the {axis} axis")
                                               for axis in AXES},
                                   description="Each axis mode read back after the stop (gnd)")})
    def ground(self):
        return {"modes": self._ground_all()}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="atto.stop", latency_ms=5000)
    def stop(self):
        """The runtime latches first; then every Attocube axis is stopped, grounded and read back."""
        self._ground_all()
