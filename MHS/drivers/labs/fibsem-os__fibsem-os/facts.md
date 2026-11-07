# Facts and tags for gh.fibsem-os/fibsem-os

Every fact cites its source at commit `8bd5dc731f523354273c38cd2cc190db9b7483e5`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RemoteFluorescenceMicroscope is the FM API over devices served by fibsem.server.devices on the FM's computer, and connect(host, port) builds it from those devices | upstream_code | fibsem/fm/remote.py:31-53 |
| connect raises RemoteDeviceUnreachable when the server is not running, unless offline: then the FM is built offline and comes online when the server starts | upstream_code | fibsem/fm/remote.py:44-48 |
| An FM is made of the fm group and the camera, light_source, filter_set and objective devices | upstream_code | fibsem/fm/microscope.py:73 |
| connect refuses an FM whose device server serves no FM devices | upstream_code | fibsem/fm/remote.py:52-57 |
| is_streaming is true for the live stream, and is_acquiring is true for the live stream or a claimed operation | upstream_code | fibsem/fm/microscope.py:650-668 |
| is_interactive is true while idle and while streaming, and false while another operation drives the FM | upstream_code | fibsem/fm/microscope.py:671-683 |
| set_channel_name and set_channel_color store the session's channel label | upstream_code | fibsem/fm/microscope.py:803-817 |
| set_binning, set_exposure_time and set_gain write the camera's binning, exposure time and gain parameters | upstream_code | fibsem/fm/microscope.py:819-876 |
| The camera exposure time is in seconds | upstream_code | fibsem/fm/microscope.py:832-843 |
| start_acquisition marks the FM streaming and starts a daemon thread for continuous live acquisition | upstream_code | fibsem/fm/microscope.py:1155-1189 |
| stop_acquisition signals the acquisition thread, waits up to 2 seconds for it, and stops emitting new images | upstream_code | fibsem/fm/microscope.py:1191-1207 |

Limits: exposure time, binning and gain are `Limit.operator_required`. The ranges belong to the installed camera and
are reported by it at runtime (`autoscript.devices:AutoscriptFMCamera._exposure_time_limits`,
fibsem/drivers/autoscript/devices.py:1426-1431, for the Thermo FM camera), so no text file of the clone fixes them;
the site supplies the operating range in `site-limits.json` (`site-limits.example.json` shows the overlay). The
channel name and colour are session labels, not numeric hardware settings, so they carry no numeric limit.

Safety: the e-stop and the safe-state action `x-cap.fibsem-os.stop_acquisition.v1` both call the native
`stop_acquisition()`, which signals the acquisition thread and ends the live stream (fibsem/fm/microscope.py:1191-1199).
No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set. The driver is R1
(illumination and live-view acquisition), below the R2/R3 range where the loader refuses an unreviewed model-written
hardware backend.

Tags: fluorescence, microscope, remote, live-view, camera
