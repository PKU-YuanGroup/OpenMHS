"""OpenMHS driver for gh.alba-synchrotron/sls-detector: the SLS Mythen II detector client.

A direct Driver (decorated methods) over the upstream client class ``sls.client:Detector``.  The clone implements a
binary request/reply protocol over two TCP sockets (control and stop; ``sls/client.py:32-75`` and
``sls/protocol.py:328-334``), so this package drives the upstream Python client object rather than a text command
table.

The interface is the upstream object's own scalar state and acquisition control:

* reads: detector type, run status, detector settings, module count and module 0 serial number, energy threshold,
  exposure time, number of frames and cycles, frame period, delay after trigger and the exposure time left;
* writes: energy threshold, exposure time, number of frames, number of cycles, frame period and delay after trigger.
  The client functions that encode them check no numeric range (``sls/protocol.py:474-518``), so every write is
  ``Limit.operator_required``: it is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site overlay supplies the range of
  this detector (``site-limits.example.json`` shows the overlay);
* actions: ``acquire`` runs one configured acquisition through the upstream ``Detector.acquire()`` generator and
  returns the last frame's counts; ``start_acquisition`` and ``stop_acquisition`` expose the native start/stop.  The
  stop is also the e-stop and, as ``stop_acquisition``, the safe-state action.

Thread safety.  The upstream ``Detector`` keeps one ``Connection`` object per port and every call connects and closes
it (``sls/client.py:94-115``, ``:149-150``), so two calls on the same port at once replace each other's socket.  The
runtime serialises actions and writes under the driver lock, but reads do not take it.  While ``acquire`` holds the
control connection open for its frames, the reads that use the control port (every read except ``run_status`` and
``exposure_time_left``) return no value and are left out of the state instead of reconnecting that socket.  A read on
the stop port can still overlap the e-stop's ``stop_acquisition``; that can only make the e-stop report its stop as
not reached (and retry), never invent a stop.  The upstream sockets have no timeout (``sls/client.py:43-48``), so a
detector that does not answer leaves the stop unacknowledged and the runtime reports ``SAFE_STATE_UNREACHED``.

Frames are returned as a JSON array of integer counts.  The frame size is the ``data_bytes`` the detector reports in
``update_client`` (``sls/protocol.py:337-356``): the Mythen drawing shows 6 modules of 10 chips of 128 channels
(``sls/client.py:2-11``), 1280 counts per module; the fake returns a 16-count placeholder array so the receipt stays
small.  The array is named in the RESULT.json notes.

Every Fact cites a line of the clone at the pinned commit 961d33152af298eb4cbd311d9d185683ba992199.  This package is
model-authored and unreviewed: the gate checks the fake backend only; no hardware run is claimed.
"""

from mhs.driver import Cancelled, Driver, Fact, Field, Limit, action, estop, read, write

_ENERGY_REASON = (
    "no line of the clone states the valid energy threshold range of the detector; the operator supplies the range "
    "of this Mythen II in site-limits.json")
_EXPOSURE_REASON = (
    "no line of the clone states the valid exposure time range of the detector; the operator supplies the range of "
    "this Mythen II in site-limits.json")
_FRAMES_REASON = (
    "no line of the clone states a valid number of frames; the operator supplies the range of this Mythen II in "
    "site-limits.json")
_CYCLES_REASON = (
    "no line of the clone states a valid number of cycles; the operator supplies the range of this Mythen II in "
    "site-limits.json")
_PERIOD_REASON = (
    "no line of the clone states the valid frame period range of the detector; the operator supplies the range of "
    "this Mythen II in site-limits.json")
_DELAY_REASON = (
    "no line of the clone states the valid delay after trigger range of the detector; the operator supplies the "
    "range of this Mythen II in site-limits.json")


class SlsDetector(Driver):
    device_id = "mythen"
    device_kind = "sensor"
    mode = "hardware"
    risk = "R1"
    native = "sls.client:Detector"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDetector"}
    vendor, model = "ALBA Synchrotron / SLS", "Mythen II"
    display_name = "SLS Mythen II detector (sls.client.Detector)"
    tags = ["detector", "mythen", "sls", "photon-counting", "tcp", "acquisition"]
    facts = [
        Fact("Detector is the upstream client class for one SLS detector; its constructor takes the host, the control "
             "port and the stop port and keeps one Connection object for each", source="upstream_code",
             ref="sls/client.py:142-151"),
        Fact("DEFAULT_CTRL_PORT is 1952 and DEFAULT_STOP_PORT is 1953", source="upstream_code",
             ref="sls/protocol.py:14-15"),
        Fact("The Mythen layout comment draws 6 modules, 10 chips per module and 128 channels per chip",
             source="upstream_code", ref="sls/client.py:2-11"),
        Fact("Connection.connect creates a socket, sets TCP_NODELAY and connects without setting a timeout; "
             "Connection.close closes the socket", source="upstream_code", ref="sls/client.py:43-53"),
        Fact("Each control-port call runs inside 'with self.conn_ctrl' and each stop-port call inside "
             "'with self.conn_stop', so every call connects and closes the detector's shared Connection object",
             source="upstream_code", ref="sls/client.py:94-115"),
        Fact("request_reply writes the request, reads a ResultType and raises SLSError on ResultType.FAIL",
             source="upstream_code", ref="sls/protocol.py:328-334"),
        Fact("run_status is a stop_property that calls protocol.get_run_status on the stop connection",
             source="upstream_code", ref="sls/client.py:378-380"),
        Fact("RunStatus names are IDLE, ERROR, WAITING, FINISHED, TRANSMITTING and RUNNING",
             source="upstream_code", ref="sls/protocol.py:190-196"),
        Fact("start_acquisition sends START_AND_READ_ALL when keep_connection is true and otherwise sends "
             "START_ACQUISITION through request_reply", source="upstream_code", ref="sls/protocol.py:696-707"),
        Fact("stop_acquisition sends STOP_ACQUISITION through request_reply on the stop connection",
             source="upstream_code", ref="sls/protocol.py:720-722"),
        Fact("Detector.stop_acquisition uses the stop connection and Detector.start_acquisition the control "
             "connection with keep_connection=False", source="upstream_code", ref="sls/client.py:382-388"),
        Fact("Detector.acquire() runs an Acquisition context with progress_interval=None and yields each frame",
             source="upstream_code", ref="sls/client.py:390-393"),
        Fact("The raw acquisition generator keeps the control connection open while it starts the acquisition and "
             "fetches frames; an SLSError is re-raised unless the Acquisition's own stop() set _stopped, and any "
             "other exception stops the acquisition before the control socket is closed because the comment says "
             "otherwise the detector hangs", source="upstream_code", ref="sls/client.py:551-573"),
        Fact("Acquisition.stop sets _stopped and calls the detector's stop_acquisition", source="upstream_code",
             ref="sls/client.py:610-612"),
        Fact("fetch_frames yields frames while fetch_frame returns OK and ends on FINISHED; a FAIL raises SLSError, "
             "which the comment says may come from an acquisition error or a stop", source="upstream_code",
             ref="sls/protocol.py:668-687"),
        Fact("update_client returns data_bytes and dynamic_range among the client information",
             source="upstream_code", ref="sls/protocol.py:337-356"),
        Fact("_to_numpy_meta decodes 24 and 32-bit frames as '<i4', 16-bit frames as '<i2' and 8-bit frames as '<i'",
             source="upstream_code", ref="sls/protocol.py:305-313"),
        Fact("The timer wire value is an integer and acquisition time, frame period and delay after trigger are "
             "converted from seconds to nanoseconds on write and back to seconds on read",
             source="upstream_code", ref="sls/protocol.py:500-512"),
        Fact("get_time_left converts acquisition time, frame period, delay after trigger, actual time and measurement "
             "time from nanoseconds to seconds", source="upstream_code", ref="sls/protocol.py:488-497"),
        Fact("The client exposes exposure_time, nb_frames, nb_cycles, delay_after_trigger and frame_period as "
             "properties over the timer types", source="upstream_code", ref="sls/client.py:288-333"),
        Fact("The detector threshold is held in eV", source="upstream_code", ref="sls/shm.py:177-178"),
        Fact("The energy threshold client property reads and writes module -1", source="upstream_code",
             ref="sls/client.py:198-211"),
        Fact("The protocol comment says mod_nb -1 means ALL for the energy threshold", source="upstream_code",
             ref="sls/protocol.py:474-476"),
        Fact("DetectorSettings names include STANDARD, FAST and HIGHGAIN; DetectorType names include MYTHEN",
             source="upstream_code", ref="sls/protocol.py:139-163"),
        Fact("get_nb_modules queries the module count by dimension and get_module_serial_number queries a module's "
             "serial number through get_id", source="upstream_code", ref="sls/client.py:159-171"),
        Fact("set_energy_threshold and the timer encoder pass the value into the request struct without checking a "
             "numeric range", source="upstream_code", ref="sls/protocol.py:474-518"),
    ]
    safe_state = (
        "acquisition stop requested with the native stop_acquisition command (STOP_ACQUISITION on the stop port, "
        "acknowledged by the detector's reply; a FAIL reply raises); the run status read after the command is "
        "reported, not an independently sensed quiescence")

    #: True while ``acquire`` holds the upstream control connection open (see the module docstring).
    _acquiring = False

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("detector_type", type="string",
          description="Detector type name reported by the detector (for example MYTHEN)")
    def detector_type(self):
        if self._acquiring:
            return None   # control port held by acquire
        return self.native.detector_type.name

    @read("run_status", type="string",
          description="Run status name: IDLE, ERROR, WAITING, FINISHED, TRANSMITTING or RUNNING")
    def run_status(self):
        return self.native.run_status.name

    @read("settings", type="string",
          description="Detector settings name reported for module 0 (for example STANDARD)")
    def settings(self):
        if self._acquiring:
            return None   # control port held by acquire
        return self.native.settings.name

    @read("nb_modules", type="integer", unit="1",
          description="Number of installed detector modules in the X dimension")
    def nb_modules(self):
        if self._acquiring:
            return None   # control port held by acquire
        return int(self.native.get_nb_modules())

    @read("module_serial_number", type="integer", unit="1",
          description="Serial number of detector module 0")
    def module_serial_number(self):
        if self._acquiring:
            return None   # control port held by acquire
        return int(self.native.get_module_serial_number(0))

    @read("energy_threshold", type="integer", unit="{eV}",
          description="Energy threshold applied to all modules, in electronvolts")
    def energy_threshold(self):
        if self._acquiring:
            return None   # control port held by acquire
        return int(self.native.energy_threshold)

    @read("exposure_time", unit="s", description="Acquisition exposure time")
    def exposure_time(self):
        if self._acquiring:
            return None   # control port held by acquire
        return float(self.native.exposure_time)

    @read("nb_frames", type="integer", unit="1", description="Number of frames per acquisition cycle")
    def nb_frames(self):
        if self._acquiring:
            return None   # control port held by acquire
        return int(self.native.nb_frames)

    @read("nb_cycles", type="integer", unit="1", description="Number of acquisition cycles")
    def nb_cycles(self):
        if self._acquiring:
            return None   # control port held by acquire
        return int(self.native.nb_cycles)

    @read("frame_period", unit="s", description="Period between exposures")
    def frame_period(self):
        if self._acquiring:
            return None   # control port held by acquire
        return float(self.native.frame_period)

    @read("delay_after_trigger", unit="s",
          description="Delay between an external trigger and the start of exposure or readout")
    def delay_after_trigger(self):
        if self._acquiring:
            return None   # control port held by acquire
        return float(self.native.delay_after_trigger)

    @read("exposure_time_left", unit="s",
          description="Exposure time left in the current acquisition")
    def exposure_time_left(self):
        return float(self.native.exposure_time_left)

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("energy_threshold", type="integer", unit="{eV}",
           description="Energy threshold applied to all modules, in electronvolts",
           limit=Limit.operator_required(_ENERGY_REASON))
    def set_energy_threshold(self, value):
        self.native.energy_threshold = value

    @write("exposure_time", unit="s", description="Acquisition exposure time",
           limit=Limit.operator_required(_EXPOSURE_REASON))
    def set_exposure_time(self, value):
        self.native.exposure_time = value

    @write("nb_frames", type="integer", unit="1", description="Number of frames per acquisition cycle",
           limit=Limit.operator_required(_FRAMES_REASON))
    def set_nb_frames(self, value):
        self.native.nb_frames = value

    @write("nb_cycles", type="integer", unit="1", description="Number of acquisition cycles",
           limit=Limit.operator_required(_CYCLES_REASON))
    def set_nb_cycles(self, value):
        self.native.nb_cycles = value

    @write("frame_period", unit="s", description="Period between exposures",
           limit=Limit.operator_required(_PERIOD_REASON))
    def set_frame_period(self, value):
        self.native.frame_period = value

    @write("delay_after_trigger", unit="s",
           description="Delay between an external trigger and the start of exposure or readout",
           limit=Limit.operator_required(_DELAY_REASON))
    def set_delay_after_trigger(self, value):
        self.native.delay_after_trigger = value

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.alba-synchrotron.acquire.v1", cancellable=True,
            description="Run one configured acquisition through Detector.acquire() and return the last frame",
            output={
                "counts": Field("array", items=Field("integer", unit="1"),
                                description="Detector counts of the last acquired frame"),
                "nb_frames": Field("integer", unit="1",
                                   description="Number of frames the acquisition yielded"),
                "run_status": Field("string",
                                    description="Run status name after the acquisition returned"),
            })
    def acquire(self):
        counts = []
        frames = 0
        self._acquiring = True
        generator = None
        try:
            generator = self.native.acquire()
            for frame in generator:
                self.check_cancelled()
                counts = [int(value) for value in frame]
                frames += 1
        except Exception:
            if self.cancelled():
                raise Cancelled("acquisition stopped because the e-stop was requested")
            raise
        finally:
            try:
                if generator is not None:
                    generator.close()   # runs the upstream cleanup (it stops an unfinished acquisition) now
            finally:
                self._acquiring = False
        self.check_cancelled()
        return {"counts": counts, "nb_frames": frames, "run_status": self.native.run_status.name}

    @action(name="x-cap.alba-synchrotron.start_acquisition.v1",
            description="Start acquisition with the configured timers (the native start_acquisition command)",
            output={"run_status": Field("string", description="Run status name read after the start command")})
    def start_acquisition(self):
        self.native.start_acquisition()
        return {"run_status": self.native.run_status.name}

    @action(name="x-cap.alba-synchrotron.stop_acquisition.v1", safe_state=True,
            description="Stop acquisition with the native stop_acquisition command (the safe state); it takes no "
                        "input",
            output={"run_status": Field("string", description="Run status name read after the stop command")})
    def stop_acquisition(self):
        self.native.stop_acquisition()
        return {"run_status": self.native.run_status.name}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends STOP_ACQUISITION on the stop port."""
        self.native.stop_acquisition()
