"""OpenMHS driver for gh.fibsem-os/fibsem-os: the remote fluorescence microscope API.

A direct Driver (decorated methods) over fibsem.fm.remote:RemoteFluorescenceMicroscope, the fluorescence-microscope
API over the devices that fibsem.server.devices serves from the FM's own computer (fibsem/fm/remote.py:31-33).  The
upstream class is a high-level API, not a wire-protocol object: each read asks the FM's devices through the class,
each write goes through its setter (which forwards to the camera or the session label), and live view is started and
stopped by the class's own acquisition thread.

* reads: the camera's exposure time, binning and gain; whether the FM is acquiring or interactive and why; the
  fluorescence channel's session name and colour;
* writes: exposure time, binning and gain (no text file of the clone states their ranges, so every bound is
  ``Limit.operator_required`` until the site supplies it in ``site-limits.json``; ``site-limits.example.json`` shows
  the overlay), and the channel's session name and colour;
* actions: start continuous live acquisition, and stop it as the declared safe-state action;
* the native stop is ``stop_acquisition``: it signals the acquisition thread and ends the live stream.

Every Fact cites a line of the clone at the pinned commit (8bd5dc731f523354273c38cd2cc190db9b7483e5).  This package
is model-authored and unreviewed; the acceptance gate serves it on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class RemoteFluorescenceMicroscope(Driver):
    device_id = "fibsem-remote-fm"
    device_kind = "instrument.microscope"
    mode = "hardware"
    risk = "R1"
    native = "fibsem.fm.remote:RemoteFluorescenceMicroscope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRemoteFluorescenceMicroscope"}
    vendor, model = "fibsem-os", "RemoteFluorescenceMicroscope"
    display_name = "fibsem-os remote fluorescence microscope"
    tags = ["fluorescence", "microscope", "remote", "live-view", "camera"]
    facts = [
        Fact("RemoteFluorescenceMicroscope is the FM API over devices served by fibsem.server.devices on the FM's "
             "computer, and connect(host, port) builds it from those devices", source="upstream_code",
             ref="fibsem/fm/remote.py:31-53"),
        Fact("connect raises RemoteDeviceUnreachable when the server is not running, unless offline: then the FM is "
             "built offline and comes online when the server starts", source="upstream_code",
             ref="fibsem/fm/remote.py:44-48"),
        Fact("An FM is made of the fm group and the camera, light_source, filter_set and objective devices",
             source="upstream_code", ref="fibsem/fm/microscope.py:73"),
        Fact("connect refuses an FM whose device server serves no FM devices", source="upstream_code",
             ref="fibsem/fm/remote.py:52-57"),
        Fact("is_streaming is true for the live stream, and is_acquiring is true for the live stream or a claimed "
             "operation", source="upstream_code", ref="fibsem/fm/microscope.py:650-668"),
        Fact("is_interactive is true while idle and while streaming, and false while another operation drives the FM",
             source="upstream_code", ref="fibsem/fm/microscope.py:671-683"),
        Fact("set_channel_name and set_channel_color store the session's channel label", source="upstream_code",
             ref="fibsem/fm/microscope.py:803-817"),
        Fact("set_binning, set_exposure_time and set_gain write the camera's binning, exposure time and gain "
             "parameters", source="upstream_code", ref="fibsem/fm/microscope.py:819-876"),
        Fact("The camera exposure time is in seconds", source="upstream_code",
             ref="fibsem/fm/microscope.py:832-843"),
        Fact("start_acquisition marks the FM streaming and starts a daemon thread for continuous live acquisition",
             source="upstream_code", ref="fibsem/fm/microscope.py:1155-1189"),
        Fact("stop_acquisition signals the acquisition thread, waits up to 2 seconds for it, and stops emitting "
             "new images", source="upstream_code", ref="fibsem/fm/microscope.py:1191-1207"),
    ]
    safe_state = "live acquisition stopped: the acquisition thread is signalled and no further frames are emitted"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("exposure_time", unit="s", description="Camera exposure time")
    def exposure_time(self):
        return self.native.camera.exposure_time

    @read("binning", type="integer", unit="1", description="Camera binning factor")
    def binning(self):
        return self.native.camera.binning

    @read("gain", unit="1", description="Camera gain, as a fraction of the camera's gain range")
    def gain(self):
        return self.native.camera.gain

    @read("is_acquiring", type="boolean",
          description="True while the live stream or a claimed operation drives the fluorescence microscope")
    def acquiring(self):
        return self.native.is_acquiring

    @read("is_interactive", type="boolean",
          description="True while the user may drive the hardware (idle or streaming)")
    def interactive(self):
        return self.native.is_interactive

    @read("acquiring_reason", type="string",
          description="What is driving the fluorescence microscope, or empty when it is idle")
    def acquiring_reason(self):
        return self.native.acquiring_reason

    @read("channel_name", type="string", description="Name of the current fluorescence channel")
    def channel_name(self):
        return self.native.channel_name

    @read("channel_color", type="string", description="Display colour of the current fluorescence channel")
    def channel_color(self):
        return self.native.channel_color

    # -- writes -------------------------------------------------------------------------------------------------
    @write("exposure_time", unit="s", description="Camera exposure time",
           limit=Limit.operator_required(
               "the exposure range is reported by the installed camera at runtime and no text file of the clone "
               "states a fixed range; the site sets the operating range of its camera"))
    def set_exposure_time(self, value):
        self.native.set_exposure_time(value)

    @write("binning", type="integer", unit="1", description="Camera binning factor",
           limit=Limit.operator_required(
               "the available binning factors depend on the installed camera and are read from it at runtime, so no "
               "text file of the clone fixes them; the site sets the allowed factors"))
    def set_binning(self, value):
        self.native.set_binning(value)

    @write("gain", unit="1", description="Camera gain, as a fraction of the camera's gain range",
           limit=Limit.operator_required(
               "the gain range is reported by the installed camera at runtime and no text file of the clone states "
               "a fixed range; the site sets the operating range"))
    def set_gain(self, value):
        self.native.set_gain(value)

    @write("channel_name", type="string", description="Name of the current fluorescence channel")
    def set_channel_name(self, value):
        self.native.set_channel_name(value)

    @write("channel_color", type="string", description="Display colour of the current fluorescence channel")
    def set_channel_color(self, value):
        self.native.set_channel_color(value)

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.fibsem-os.start_acquisition.v1",
            description="Start continuous live acquisition of the fluorescence microscope",
            output={"acquiring": Field("boolean", description="True once the live stream is running")})
    def start_acquisition(self):
        self.native.start_acquisition()
        return {"acquiring": self.native.is_acquiring}

    @action(name="x-cap.fibsem-os.stop_acquisition.v1", safe_state=True,
            description="Stop continuous live acquisition (the native stop and the safe state)",
            output={"acquiring": Field("boolean", description="False once the live stream is stopped")})
    def stop_acquisition(self):
        self.native.stop_acquisition()
        return {"acquiring": self.native.is_acquiring}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="stop_acquisition")
    def stop(self):
        """The native stop: signal the acquisition thread and end the live stream."""
        self.native.stop_acquisition()
