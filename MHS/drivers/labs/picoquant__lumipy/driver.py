"""OpenMHS driver for gh.picoquant/lumipy: the Luminosa Measurement interface.

The upstream `libs/pqlumi.py` exposes one concrete `Measurement` object (the module-level
`measurement` instance) over the Delphi Luminosa bridge.  This package binds that object
directly.  The card's `family-config` / `McpClientDriver` shape does not fit: the pinned MCP
server is an arbitrary-Python-code bridge over a remote execution server, not a finite set
of device tools.  The card hints themselves name the Measurement methods.

Every read/write below is a state parameter of the Measurement object or its two nested
configuration objects (`img_conf`, `point_conf`).  Measurement start/stop, analysis queries
and the measurement-name setter are extension actions.  The pinned source states units but
no numeric ranges, so every numeric write is operator_required and refuses until the site
supplies a bound.  The package is model-authored and unreviewed; only the fake backend is
exercised by the acceptance gate, and no hardware run is claimed.

Model review (2026-11-05): risk R2.  A Luminosa measurement is a laser-scanning measurement:
the instrument's laser assemblies (laser head, attenuators, shutter; libs/pqlumi.py:1093-1097)
excite the sample while it scans, and the clone states no laser class.  Every `Measurement`
call forwards to the closed Luminosa bridge `delphi_pqlumi`, so the clone does not show
whether starting or stopping a measurement switches a laser or a shutter.  The stop is
`stop_meas` (an error return raises) confirmed by `meas_status()` reading False within
0.5 s; it ends the measurement as the Luminosa software reports it, not laser emission.
NOT COVERED: `get_analysis_image` (a complete 2-D analysis image would be returned inline:
large data the standard needs an artifact path for, NEEDS_ARTIFACTS).
"""

import time

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

PIN = "dc0fe266a55219811d171ccfc99a742e4eb4fffd"
SOURCE = "libs/pqlumi.py"


def operator_limit(what):
    """No pinned line bounds `what`; the site must supply the range."""
    return Limit.operator_required(
        f"The pinned source states the unit of {what} but no numeric range; the operator supplies the site range.")


def image_size_field():
    # The source names pixels; it states no pixel-count range (libs/pqlumi.py:67-96).
    return Field("array", items=Field("integer", unit="1", limit=operator_limit("image_size")),
                 length=2, description="Image size in pixels, as [x, y] (native image_size).")


def curve_output():
    number = Field("number")
    return {
        "name": Field("string", description="Curve name."),
        "data_x": Field("array", items=number, description="X-axis samples."),
        "data_y": Field("array", items=number, description="Y-axis samples."),
        "axis_title_x": Field("string", description="X-axis title."),
        "axis_title_y": Field("string", description="Y-axis title."),
        "unit_x": Field("string", description="X-axis unit."),
        "unit_y": Field("string", description="Y-axis unit."),
        "data_delta_y": Field("array", items=number, required=False,
                              description="Optional y-axis error of an FCS analysis."),
        "fit_names": Field("array", items=Field("string"), required=False,
                           description="Optional names of the selected fits."),
        "fits_x": Field("array", items=Field("array", items=number), required=False,
                        description="Optional fit x-axis data, one array per fit."),
        "fits_y": Field("array", items=Field("array", items=number), required=False,
                        description="Optional fit y-axis data, one array per fit."),
        "irf_x": Field("array", items=Field("array", items=number), required=False,
                       description="Optional IRF x-axis data, one array per fit."),
        "irf_y": Field("array", items=Field("array", items=number), required=False,
                       description="Optional IRF y-axis data, one array per fit."),
    }


#: How long the stop waits for meas_status() to read False (inside the 1 s e-stop budget).
STOP_CONFIRM_S = 0.5


class LumipyMeasurement(Driver):
    device_id = "lumipy"
    device_kind = "instrument.microscope"
    mode, risk = "hardware", "R2"
    native = "libs.pqlumi:Measurement"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMeasurement"}
    vendor, model = "PicoQuant", "Luminosa (LumiPy)"
    display_name = "PicoQuant Luminosa through LumiPy Measurement"
    tags = ("microscope", "confocal", "lumipy", "luminosa", "measurement")
    safe_state = ("Measurement stopped through Measurement.stop_meas() and confirmed by meas_status() reading "
                  "False; the clone does not show whether that changes a laser or shutter (closed delphi_pqlumi "
                  "bridge), and the pqdc/pqscan laser, shutter and stage interfaces are not touched.")
    facts = [
        Fact("pqlumi defines the concrete Measurement class.",
             source="upstream_code", ref=f"{SOURCE}:502-517"),
        Fact("pqlumi binds one module-level measurement instance of that class.",
             source="upstream_code", ref=f"{SOURCE}:1071-1072"),
        Fact("When delphi_pqlumi cannot be imported, pqlumi sets is_fake and prints that it uses a fake module.",
             source="upstream_code", ref=f"{SOURCE}:13-18"),
        Fact("A laser assembly is made up of a laser head, attenuator, main attenuator and shutter, accessed "
             "through the pqdc module.", source="upstream_code", ref=f"{SOURCE}:1093-1097"),
        Fact("The MCP tool disclaimer warns that generated code can put connected microscope hardware, including "
             "lasers and scanners, in a hazardous operating condition.", source="vendor_doc",
             ref="MCPTool/Disclaimer.md:7"),
        Fact("start_meas accepts only the measurement types \"image\", \"line\" and \"point\" in its docstring; "
             "it forwards the string to dm.start_meas.",
             source="upstream_code", ref=f"{SOURCE}:986-1000"),
        Fact("stop_meas returns at once when is_fake; otherwise it calls dm.stop_meas, raises on an error return "
             "and returns nothing; the docstring does not promise a stop readback.", source="upstream_code",
             ref=f"{SOURCE}:1020-1033"),
        Fact("meas_status returns False while a measurement is inactive or stopped and True while it is running.",
             source="upstream_code", ref=f"{SOURCE}:1002-1018"),
        Fact("get_elapsed_meas_time returns the elapsed measurement time in seconds.",
             source="upstream_code", ref=f"{SOURCE}:1035-1052"),
        Fact("scan_range_min_x/max_x/min_y/max_y are in meters.",
             source="upstream_code", ref=f"{SOURCE}:552-614"),
        Fact("scan_range_left/top/width/height are in meters.",
             source="upstream_code", ref=f"{SOURCE}:616-738"),
        Fact("path_to_ptu is the absolute path of the last PTU file written.",
             source="upstream_code", ref=f"{SOURCE}:771-785"),
        Fact("img_conf.scan_speed is a percentage, image_size is a pixel tuple, and num_frames is a count.",
             source="upstream_code", ref=f"{SOURCE}:36-158"),
        Fact("img_conf.photons_in_brightest_px is a count and img_conf.meas_time is in seconds.",
             source="upstream_code", ref=f"{SOURCE}:160-282"),
        Fact("point_conf exposes a photon count, measurement time, stop flags, point_list in meters and "
             "selected_point in meters.", source="upstream_code", ref=f"{SOURCE}:284-483"),
        Fact("write_ptu_file enables or disables PTU output during a scan.",
             source="upstream_code", ref=f"{SOURCE}:740-770"),
        Fact("set_next_measurement_name sets the next measurement name and has no getter.",
             source="upstream_code", ref=f"{SOURCE}:805-820"),
        Fact("get_analysis_names lists the live analysis names configured in Luminosa.",
             source="upstream_code", ref=f"{SOURCE}:822-835"),
        Fact("get_analysis_curve_types lists the curve types available for one analysis.",
             source="upstream_code", ref=f"{SOURCE}:837-853"),
        Fact("get_analysis_image_types lists the image types available for one analysis.",
             source="upstream_code", ref=f"{SOURCE}:898-914"),
        Fact("get_analysis_param_types lists the parameter types available for one analysis.",
             source="upstream_code", ref=f"{SOURCE}:949-965"),
        Fact("get_analysis_curve returns the documented 1-D curve plus optional FCS fit arrays.",
             source="upstream_code", ref=f"{SOURCE}:855-896"),
        Fact("get_analysis_image returns a 2-D image and x/y/z positions in meters.",
             source="upstream_code", ref=f"{SOURCE}:916-947"),
        Fact("get_analysis_param returns a dict whose keys depend on the analysis and parameter type.",
             source="upstream_code", ref=f"{SOURCE}:967-984"),
        Fact("The upstream is_fake fallback returns a five-point curve.",
             source="upstream_code", ref=f"{SOURCE}:882-891"),
        Fact("The upstream is_fake fallback returns a 3x3 image; those values are the upstream's own test "
             "fallback, not a size or measurement of a real system.",
             source="upstream_code", ref=f"{SOURCE}:934-942"),
    ]

    # -- read-only state -------------------------------------------------------------------------------------
    @read("version", type="string", description="Luminosa software version reported by pqlumi.")
    def version(self):
        return self.native.version

    @read("analysis_names", type="array", items=Field("string"),
          description="Live analysis names configured in Luminosa.")
    def analysis_names(self):
        return list(self.native.get_analysis_names())

    @read("running", type="boolean", description="True while a measurement is running (native meas_status).")
    def running(self):
        return bool(self.native.meas_status())

    @read("elapsed_meas_time", unit="s", description="Elapsed time of the current or last measurement.")
    def elapsed_meas_time(self):
        return self.native.get_elapsed_meas_time()

    @read("scan_range_min_x", unit="m", description="Minimum reachable X scan range.")
    def scan_range_min_x(self):
        return self.native.scan_range_min_x

    @read("scan_range_max_x", unit="m", description="Maximum reachable X scan range.")
    def scan_range_max_x(self):
        return self.native.scan_range_max_x

    @read("scan_range_min_y", unit="m", description="Minimum reachable Y scan range.")
    def scan_range_min_y(self):
        return self.native.scan_range_min_y

    @read("scan_range_max_y", unit="m", description="Maximum reachable Y scan range.")
    def scan_range_max_y(self):
        return self.native.scan_range_max_y

    @read("scan_range_left", unit="m", description="Left edge of the scan range.")
    def scan_range_left(self):
        return self.native.scan_range_left

    @read("scan_range_top", unit="m", description="Top edge of the scan range.")
    def scan_range_top(self):
        return self.native.scan_range_top

    @read("scan_range_width", unit="m", description="Width of the scan range.")
    def scan_range_width(self):
        return self.native.scan_range_width

    @read("scan_range_height", unit="m", description="Height of the scan range.")
    def scan_range_height(self):
        return self.native.scan_range_height

    @read("scan_speed", type="integer", unit="%", description="Image scan speed in percent.")
    def scan_speed(self):
        return self.native.img_conf.scan_speed

    @read("image_size", type=image_size_field())
    def image_size(self):
        return list(self.native.img_conf.image_size)

    @read("stop_on_num_frames", type="boolean",
          description="Stop the image scan after num_frames frames.")
    def stop_on_num_frames(self):
        return bool(self.native.img_conf.stop_on_num_frames)

    @read("num_frames", type="integer", unit="1",
          description="Number of image frames acquired when stop_on_num_frames is enabled.")
    def num_frames(self):
        return self.native.img_conf.num_frames

    @read("stop_on_photons_in_brightest_px", type="boolean",
          description="Stop the image scan when the brightest pixel reaches the photon threshold.")
    def stop_on_photons_in_brightest_px(self):
        return bool(self.native.img_conf.stop_on_photons_in_brightest_px)

    @read("photons_in_brightest_px", type="integer", unit="1",
          description="Photon threshold in the brightest pixel for the image stop condition.")
    def photons_in_brightest_px(self):
        return self.native.img_conf.photons_in_brightest_px

    @read("img_stop_on_meas_time", type="boolean",
          description="Stop the image scan after img_meas_time seconds.")
    def img_stop_on_meas_time(self):
        return bool(self.native.img_conf.stop_on_meas_time)

    @read("img_meas_time", unit="s", description="Image measurement time used by the time stop condition.")
    def img_meas_time(self):
        return self.native.img_conf.meas_time

    @read("point_stop_on_photons", type="boolean",
          description="Stop the point scan when the photon threshold is reached.")
    def point_stop_on_photons(self):
        return bool(self.native.point_conf.stop_on_photons)

    @read("point_num_photons", type="integer", unit="1",
          description="Photon threshold for the point stop condition.")
    def point_num_photons(self):
        return self.native.point_conf.num_photons

    @read("point_stop_on_meas_time", type="boolean",
          description="Stop the point scan after point_meas_time seconds.")
    def point_stop_on_meas_time(self):
        return bool(self.native.point_conf.stop_on_meas_time)

    @read("point_meas_time", unit="s", description="Point measurement time used by the time stop condition.")
    def point_meas_time(self):
        return self.native.point_conf.meas_time

    @read("write_ptu_file", type="boolean", description="True when a PTU file is written during the scan.")
    def write_ptu_file(self):
        return bool(self.native.write_ptu_file)

    @read("path_to_ptu", type="string", description="Absolute path of the last PTU file written.")
    def path_to_ptu(self):
        return self.native.path_to_ptu

    # -- writable state (cap.device.configure.v1) -------------------------------------------------------------
    @write("scan_range_left", unit="m", limit=operator_limit("scan_range_left"),
           description="Left edge of the scan range.")
    def set_scan_range_left(self, value):
        self.native.scan_range_left = value

    @write("scan_range_top", unit="m", limit=operator_limit("scan_range_top"),
           description="Top edge of the scan range.")
    def set_scan_range_top(self, value):
        self.native.scan_range_top = value

    @write("scan_range_width", unit="m", limit=operator_limit("scan_range_width"),
           description="Width of the scan range.")
    def set_scan_range_width(self, value):
        self.native.scan_range_width = value

    @write("scan_range_height", unit="m", limit=operator_limit("scan_range_height"),
           description="Height of the scan range.")
    def set_scan_range_height(self, value):
        self.native.scan_range_height = value

    @write("scan_speed", type="integer", unit="%", limit=operator_limit("scan_speed"),
           description="Image scan speed in percent.")
    def set_scan_speed(self, value):
        self.native.img_conf.scan_speed = value

    @write("image_size", type=image_size_field())
    def set_image_size(self, value):
        self.native.img_conf.image_size = (value[0], value[1])

    # The image/point stop conditions and PTU output are configured by extension actions below:
    # keeping them out of cap.device.configure.v1 keeps each MCP tool's input schema within the
    # 2048-byte tool bound.  Their state is still readable through the @read methods above.

    # -- actions ---------------------------------------------------------------------------------------------
    @action(name="x-cap.picoquant.configure_image_stop.v1",
            description="Configure the image stop conditions (frame count, photon threshold, time).",
            input={
                "stop_on_num_frames": Field("boolean", description="Stop after num_frames frames."),
                "num_frames": Field("integer", unit="1", limit=operator_limit("num_frames"),
                                    description="Frame count for the image stop condition."),
                "stop_on_photons_in_brightest_px": Field(
                    "boolean", description="Stop when the brightest pixel reaches the photon threshold."),
                "photons_in_brightest_px": Field(
                    "integer", unit="1", limit=operator_limit("photons_in_brightest_px"),
                    description="Photon threshold in the brightest pixel."),
                "img_stop_on_meas_time": Field("boolean", description="Stop after img_meas_time seconds."),
                "img_meas_time": Field("number", unit="s", limit=operator_limit("an image measurement time"),
                                       description="Image measurement time in seconds."),
            },
            output={
                "stop_on_num_frames": Field("boolean", description="Applied frame stop flag."),
                "num_frames": Field("integer", unit="1", description="Applied frame count."),
                "stop_on_photons_in_brightest_px": Field(
                    "boolean", description="Applied photon stop flag."),
                "photons_in_brightest_px": Field(
                    "integer", unit="1", description="Applied photon threshold."),
                "img_stop_on_meas_time": Field("boolean", description="Applied time stop flag."),
                "img_meas_time": Field("number", unit="s", description="Applied image measurement time."),
            })
    def configure_image_stop(self, stop_on_num_frames, num_frames, stop_on_photons_in_brightest_px,
                             photons_in_brightest_px, img_stop_on_meas_time, img_meas_time):
        conf = self.native.img_conf
        conf.stop_on_num_frames = stop_on_num_frames
        conf.num_frames = num_frames
        conf.stop_on_photons_in_brightest_px = stop_on_photons_in_brightest_px
        conf.photons_in_brightest_px = photons_in_brightest_px
        conf.stop_on_meas_time = img_stop_on_meas_time
        conf.meas_time = img_meas_time
        return {
            "stop_on_num_frames": bool(conf.stop_on_num_frames),
            "num_frames": conf.num_frames,
            "stop_on_photons_in_brightest_px": bool(conf.stop_on_photons_in_brightest_px),
            "photons_in_brightest_px": conf.photons_in_brightest_px,
            "img_stop_on_meas_time": bool(conf.stop_on_meas_time),
            "img_meas_time": conf.meas_time,
        }

    @action(name="x-cap.picoquant.configure_point_stop.v1",
            description="Configure the point stop conditions (photon threshold and time).",
            input={
                "point_stop_on_photons": Field("boolean", description="Stop when the photon threshold is reached."),
                "point_num_photons": Field("integer", unit="1", limit=operator_limit("point_num_photons"),
                                           description="Photon threshold for the point stop condition."),
                "point_stop_on_meas_time": Field("boolean", description="Stop after point_meas_time seconds."),
                "point_meas_time": Field("number", unit="s", limit=operator_limit("a point measurement time"),
                                         description="Point measurement time in seconds."),
            },
            output={
                "point_stop_on_photons": Field("boolean", description="Applied photon stop flag."),
                "point_num_photons": Field("integer", unit="1", description="Applied photon threshold."),
                "point_stop_on_meas_time": Field("boolean", description="Applied time stop flag."),
                "point_meas_time": Field("number", unit="s", description="Applied point measurement time."),
            })
    def configure_point_stop(self, point_stop_on_photons, point_num_photons, point_stop_on_meas_time,
                             point_meas_time):
        conf = self.native.point_conf
        conf.stop_on_photons = point_stop_on_photons
        conf.num_photons = point_num_photons
        conf.stop_on_meas_time = point_stop_on_meas_time
        conf.meas_time = point_meas_time
        return {
            "point_stop_on_photons": bool(conf.stop_on_photons),
            "point_num_photons": conf.num_photons,
            "point_stop_on_meas_time": bool(conf.stop_on_meas_time),
            "point_meas_time": conf.meas_time,
        }

    @action(name="x-cap.picoquant.set_ptu_output.v1",
            description="Enable or disable PTU output during the next scan.",
            input={"write_ptu_file": Field("boolean", description="Write a PTU file during the scan.")},
            output={"write_ptu_file": Field("boolean", description="Applied PTU output flag.")})
    def set_ptu_output(self, write_ptu_file):
        self.native.write_ptu_file = write_ptu_file
        return {"write_ptu_file": bool(self.native.write_ptu_file)}

    @action(name="x-cap.picoquant.start_measurement.v1",
            description="Start an image, line or point measurement (the native start_meas).",
            input={"meas_type": Field("string", enum=["image", "line", "point"],
                                      description="Measurement type accepted by start_meas.")},
            output={"meas_type": Field("string", description="The measurement type requested."),
                    "running": Field("boolean", description="Native meas_status after the start.")})
    def start_measurement(self, meas_type):
        self.native.start_meas(meas_type)
        return {"meas_type": meas_type, "running": bool(self.native.meas_status())}

    @action(name="x-cap.picoquant.stop_measurement.v1", safe_state=True,
            description="Stop the measurement (native stop_meas) and confirm meas_status reads False; safe state.",
            output={"running": Field("boolean", description="Native meas_status after the stop (False).")})
    def stop_measurement(self):
        self._stop_confirmed()
        return {"running": False}

    @action(name="x-cap.picoquant.set_measurement_name.v1",
            description="Set the name of the next measurement (the native set_next_measurement_name).",
            input={"name": Field("string", description="Next measurement name; empty uses the default name.")},
            output={"name": Field("string", description="The name accepted by the native setter.")})
    def set_measurement_name(self, name):
        self.native.set_next_measurement_name(name)
        return {"name": name}

    @action(name="x-cap.picoquant.get_analysis_curve.v1", verb="read",
            description="Read one live analysis curve and its optional fit arrays.",
            input={"name": Field("string", description="Configured live analysis name."),
                   "curve_type": Field("string", description="Curve type identifier for that analysis.")},
            output=curve_output())
    def get_analysis_curve(self, name, curve_type):
        return self.native.get_analysis_curve(name, curve_type)

    @action(name="x-cap.picoquant.get_analysis_curve_types.v1", verb="read",
            description="List the curve types available for one live analysis.",
            input={"name": Field("string", description="Configured live analysis name.")},
            output={"types": Field("array", items=Field("string"), description="Available curve type ids.")})
    def get_analysis_curve_types(self, name):
        return {"types": list(self.native.get_analysis_curve_types(name))}

    @action(name="x-cap.picoquant.get_analysis_image_types.v1", verb="read",
            description="List the image types available for one live analysis.",
            input={"name": Field("string", description="Configured live analysis name.")},
            output={"types": Field("array", items=Field("string"), description="Available image type ids.")})
    def get_analysis_image_types(self, name):
        return {"types": list(self.native.get_analysis_image_types(name))}

    @action(name="x-cap.picoquant.get_analysis_param.v1", verb="read",
            description="Read one live analysis parameter; its keys depend on the analysis and parameter type.",
            input={"name": Field("string", description="Configured live analysis name."),
                   "param_type": Field("string", description="Parameter type identifier for that analysis.")},
            output={"param": Field("object", description="Parameter fields returned by the analysis.")})
    def get_analysis_param(self, name, param_type):
        return {"param": self.native.get_analysis_param(name, param_type)}

    @action(name="x-cap.picoquant.get_analysis_param_types.v1", verb="read",
            description="List the parameter types available for one live analysis.",
            input={"name": Field("string", description="Configured live analysis name.")},
            output={"types": Field("array", items=Field("string"), description="Available parameter type ids.")})
    def get_analysis_param_types(self, name):
        return {"types": list(self.native.get_analysis_param_types(name))}

    # -- safety ----------------------------------------------------------------------------------------------
    @estop(native="stop_meas")
    def stop(self):
        """Stop the measurement through the native stop_meas and confirm meas_status reads False."""
        self._stop_confirmed()

    def _stop_confirmed(self):
        """stop_meas, then read meas_status until it is False; a measurement still running is not a safe state."""
        self.native.stop_meas()
        deadline = time.monotonic() + STOP_CONFIRM_S
        while bool(self.native.meas_status()):
            if time.monotonic() >= deadline:
                raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                                   "stop_meas returned but meas_status still reports a running measurement")
            time.sleep(0.05)
