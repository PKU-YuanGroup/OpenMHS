"""OpenMHS driver for gh.diamondlightsource/dodal: the DECTRIS Eiger area detector (classic ophyd ``EigerDetector``).

The selected entry symbol is ``dodal.devices.eiger:EigerDetector`` (src/dodal/devices/eiger.py:48), the classic Ophyd
Device that drives the Eiger camera, its Odin file writer and the fan through EPICS; the i03 beamline module builds it
with ``devices.v1_init`` (src/dodal/beamlines/i03.py:185-190).  The FastCS Eiger of ophyd-async in the same module is
built with ``skip=True`` (i03.py:193-200) and is another repository's class, so it is not this package's native.  The
detector is R1: it has no beam, laser, heater or mechanism of its own.

Shape and deviation from the card
---------------------------------
The card names the config-only ``OphydDriver`` family, which proves direct ``Component(EpicsSignal...)`` declarations
only.  ``EigerDetector``'s controls are its own methods over nested Devices, so this is a direct
:class:`mhs.driver.Driver` over the same entry symbol.

Re-authored stop route (model review, 2026-11-05)
-------------------------------------------------
The upstream stop and ROI calls need a ``DetectorParams`` (``change_roi_mode`` asserts it, eiger.py:221-223).  The
hardware backend (``native.py``) builds the device as i03 does, applies the operator's ``DetectorParams`` with the
upstream ``set_detector_parameters`` (eiger.py:101-120) and refuses parameters without a fixed ``run_number``.  With
them the native ``stop()`` (eiger.py:186-211) completes: Odin stopped, file writer start timeout set, camera acquire
cleared, ROI mode disabled with the detector's full size, dev/shm streaming off.  The package then arms and ends a
collection only through the upstream ``stage``/``unstage`` (eiger.py:142-147, 161-184); the earlier ``armed`` write,
which called ``set_cam_acquire`` outside the arming chain, is removed.

Files
-----
Odin writes the frames to files: ``set_odin_pvs`` sets the file path to ``DetectorParams.directory`` and the file name
to ``full_filename`` and waits for ``AcquisitionID_RBV`` to report it (eiger.py:286-306, eiger_odin.py:39).  The file
action publishes, through the SDK's native-file artifacts (``mhs.file_artifacts``), the regular ``.h5`` files directly
in that directory whose names start with the acquisition id Odin reports followed by ``_``, once the collection ended:
no arming chain runs and the detector is not armed (``is_armed``, eiger.py:134-135; integrator v4, 2026-11-05), and the
meta listener and every file-writer node report ``Writing_RBV`` 0 (``create_finished_status``, eiger_odin.py:125-129).
Files an earlier collection of the same connection wrote carry the same acquisition id and cannot be told apart.  The clone does
not state the names Odin gives its files: if they differ, the action finds none and fails rather than publishing
anything else.  Files above the artifact bound (16 MiB at most, 2 MiB by default) are refused and stay on the beamline's
file system; an EIGER2 X 16M frame has 4148 x 4362 pixels (src/dodal/devices/detector/det_dim_constants.py:80-82), so
only small or reduced collections and the meta file can fit.

Every Fact cites the pinned commit f96fef4e72a734de6bb523b4229410254e7e8eab.  The package is model-authored and
unreviewed (``reviewed_by`` is null); it has been checked on the fake backend only and has never connected to a detector,
an EPICS IOC, Odin or a config server.
"""

import os
import re

from mhs.driver import Driver, DriverFailed, Fact, Field, OutcomeUnknown, action, estop, read
from mhs.file_artifacts import NativeFileDirectory

#: Modules of the clone the facts cite.
SOURCE = "src/dodal/devices/eiger.py"
ODIN = "src/dodal/devices/eiger_odin.py"
PARAMS = "src/dodal/devices/detector/detector.py"
CONVERTER = "src/dodal/devices/detector/det_dist_to_beam_converter.py"
UTILS = "src/dodal/utils.py"
I03 = "src/dodal/beamlines/i03.py"
#: Extension capabilities (no catalogue class arms, ends or stops an area-detector acquisition).
STAGE = "x-cap.diamondlightsource.eiger-stage.v1"
UNSTAGE = "x-cap.diamondlightsource.eiger-unstage.v1"
DISARM = "x-cap.diamondlightsource.eiger-disarm.v1"
FILES = "x-cap.diamondlightsource.eiger-files.v1"
#: Media type published for the Odin writer's HDF5 files.
HDF5 = "application/x-hdf5"
#: Bound of one published file: the artifact store's absolute bound (the endpoint's store may allow less).
MAX_FILE_BYTES = 16 * 1024 * 1024
#: Most files of one acquisition the package publishes; more refuse instead of truncating.
MAX_FILES = 8
#: An acquisition id usable as a file-name prefix (one path component).
_ACQUISITION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}")


class EigerDetectorDriver(Driver):
    device_id = "eiger-detector"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "dodal.devices.eiger:EigerDetector"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeEigerDetector"}
    model = "EigerDetector (dodal)"
    display_name = "DECTRIS Eiger area detector (dodal)"
    tags = ["ophyd", "epics", "eiger", "odin", "area-detector", "acquisition", "hdf5"]

    safe_state = ("Camera acquire cleared (disarm_detector runs after every e-stop); when the native stop() ran its "
                  "cleanup with the operator's DetectorParams, Odin is also stopped, ROI mode disabled at full size "
                  "and dev/shm streaming off (a stop() after an earlier stop or unstage only logs Already disarmed); "
                  "a stop() or disarm that fails or exceeds the 1 s e-stop budget, or a stop() returning while an "
                  "arming chain runs, reports SAFE_STATE_UNREACHED, latched and retried")

    facts = [
        Fact("EigerDetector is a classic ophyd Device that implements Stageable", source="upstream_code",
             ref=f"{SOURCE}:48"),
        Fact("cam is an EigerDetectorCam Component with the CAM: suffix and odin is an EigerOdin Component",
             source="upstream_code", ref=f"{SOURCE}:55-56"),
        Fact("stale_params and bit_depth are EpicsSignalRO Components on CAM:StaleParameters_RBV and "
             "CAM:BitDepthImage_RBV", source="upstream_code", ref=f"{SOURCE}:58-59"),
        Fact("detector_params is a class attribute that defaults to None", source="upstream_code",
             ref=f"{SOURCE}:62"),
        Fact("EigerTimeouts defaults to a 10 s general status timeout and a 60 s arming timeout; the i03 entry uses "
             "20 s and 60 s", source="upstream_code", ref=f"{SOURCE}:20-45"),
        Fact("The constructor takes the beamline (default i03), uses that beamline's timeouts or the i03 ones, and "
             "sets disarming_status to None", source="upstream_code", ref=f"{SOURCE}:67-87"),
        Fact("set_detector_parameters stores the DetectorParams and raises when they are None or lack the detector "
             "size constants or the beam centre converter", source="upstream_code", ref=f"{SOURCE}:101-120"),
        Fact("async_stage sets disarming_status to None, clears Odin errors, raises when Odin is not initialised and "
             "starts the arming chain", source="upstream_code", ref=f"{SOURCE}:122-132"),
        Fact("is_armed returns true only when odin.fan.ready is 1 and cam.acquire is 1", source="upstream_code",
             ref=f"{SOURCE}:134-135"),
        Fact("stage waits for a started arming and, when the detector is not armed, waits up to the arming timeout "
             "for async_stage", source="upstream_code", ref=f"{SOURCE}:137-147"),
        Fact("unstage sets a new disarming_status, waits for arming, stops Odin after all frames in free-run mode, "
             "sets the file writer start timeout and waits 30 s for filewriters_finished; in a finally block it "
             "disarms, checks Odin's state and disables ROI mode; it finishes disarming_status and returns the Odin "
             "state only when no exception was raised", source="upstream_code", ref=f"{SOURCE}:161-184"),
        Fact("stop runs its cleanup only when disarming_status is None: it waits for any arming, stops Odin, sets the "
             "file writer start timeout, disarms the detector, disables ROI mode, waits for the combined status and "
             "turns off dev/shm streaming, and finishes disarming_status in a finally block",
             source="upstream_code", ref=f"{SOURCE}:186-211"),
        Fact("When disarming_status is set and not done, stop only waits for it up to the arming timeout and runs no "
             "cleanup", source="upstream_code", ref=f"{SOURCE}:189-191"),
        Fact("When disarming_status is set and done, stop only logs Already disarmed, doing nothing",
             source="upstream_code", ref=f"{SOURCE}:212-213"),
        Fact("change_roi_mode asserts detector_params is not None and, for a disable, sets roi_mode 0 and the image "
             "size and chunks of the file writer to the detector's full size", source="upstream_code",
             ref=f"{SOURCE}:221-249"),
        Fact("set_odin_pvs sets the Odin file path to DetectorParams.directory and the file name to full_filename, "
             "and returns a status that also waits for the meta listener file name and the acquisition id to "
             "report that name", source="upstream_code", ref=f"{SOURCE}:286-306"),
        Fact("_wait_fan_ready stores Odin's writers-finished status as filewriters_finished and returns a status "
             "that waits for the fan ready flag", source="upstream_code", ref=f"{SOURCE}:404-407"),
        Fact("disarm_detector clears cam.acquire and waits for the general status timeout", source="upstream_code",
             ref=f"{SOURCE}:425-426"),
        Fact("The arming chain asserts detector_params and runs Odin stop, dev/shm, threshold, camera, Odin, MX "
             "settings, trigger counts, stale parameters, Odin status, set_cam_acquire and the fan-ready wait "
             "without blocking", source="upstream_code", ref=f"{SOURCE}:436-469"),
        Fact("set_cam_pvs sets the camera trigger mode to EXTERNAL_SERIES", source="upstream_code",
             ref=f"{SOURCE}:272-276"),
        Fact("The meta listener's ready signal reads Writing_RBV and the file writer's id reads AcquisitionID_RBV",
             source="upstream_code", ref=f"{ODIN}:27-39"),
        Fact("Each of the four Odin file-writer nodes has a writing signal on Writing_RBV", source="upstream_code",
             ref=f"{ODIN}:45-65"),
        Fact("create_finished_status is done when the meta listener's ready and every node's writing equal 0",
             source="upstream_code", ref=f"{ODIN}:125-129"),
        Fact("Odin stop sets the file writer capture to 0 and the meta listener stop_writing to 1",
             source="upstream_code", ref=f"{ODIN}:169-174"),
        Fact("DetectorParams validates that directory is an existing directory and stores it with a trailing slash",
             source="upstream_code", ref=f"{PARAMS}:83-88"),
        Fact("run_number is a property: override_run_number when it is set, else get_run_number of the directory "
             "and prefix", source="upstream_code", ref=f"{PARAMS}:62-68"),
        Fact("get_run_number lists the directory's .nxs files that start with the prefix and returns 1 or the "
             "highest run number found plus 1", source="upstream_code", ref=f"{UTILS}:128-142"),
        Fact("full_filename is the prefix and the run number joined by an underscore", source="upstream_code",
             ref=f"{PARAMS}:135-137"),
        Fact("beam_xy_converter builds a DetectorDistanceToBeamXYConverter from det_dist_to_beam_converter_path and "
             "the global config client", source="upstream_code", ref=f"{PARAMS}:56-60"),
        Fact("The converter reads its lookup table through the config client when it is built",
             source="upstream_code", ref=f"{CONVERTER}:17-22"),
        Fact("The i03 module builds the classic EigerDetector with the EA-EIGER-01 prefix and builds the FastCS Eiger "
             "only with skip=True", source="upstream_code", ref=f"{I03}:185-200"),
        Fact("The i03 config client is built from the URL in the CONFIG_SERVER_URL_ENV_VAR environment variable "
             "(or a default endpoint) and set as the global config client", source="upstream_code",
             ref=f"{I03}:102-110"),
    ]

    _staged = False
    _files = None
    _files_problem = "the file directory was not declared"

    def setup(self):
        params = self.native.detector_params
        if params is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", "the Eiger has no DetectorParams: its stop and ROI calls need "
                               "them (eiger.py:221-223); native.connect applies the operator's")
        # The operator's DetectorParams.directory is resolved once here; after that no link is followed.  A directory
        # the helper refuses (for example one every user may write) disables only the file action, never the stop.
        try:
            self._files = NativeFileDirectory(os.path.realpath(str(params.directory)), media_types={".h5": HDF5},
                                              max_file_bytes=MAX_FILE_BYTES, max_files=MAX_FILES, cleanup="keep")
        except ValueError as exc:
            self._files, self._files_problem = None, str(exc)

    @read("armed", type="boolean",
          description="True when the Odin fan is ready and the camera acquire is on (is_armed)")
    def get_armed(self):
        return bool(self.native.is_armed())

    @read("bit_depth", type="integer", description="Image bit depth from CAM:BitDepthImage_RBV")
    def get_bit_depth(self):
        return int(self.native.bit_depth.get())

    @read("stale_params", type="integer", description="Stale-parameter count from CAM:StaleParameters_RBV")
    def get_stale_params(self):
        return int(self.native.stale_params.get())

    @read("acquisition_id", type="string",
          description="Odin's acquisition id (OD:AcquisitionID_RBV): the file-name prefix of the last armed collection")
    def get_acquisition_id(self):
        return str(self.native.odin.file_writer.id.get())

    @action(name=STAGE,
            description="Arm the Eiger for one externally triggered collection with the operator's DetectorParams: "
                        "stage() runs the upstream arming chain unless the detector is armed",
            output={"armed": Field("boolean", description="is_armed after stage returned"),
                    "armed_here": Field("boolean", description="True when this call ran the arming chain; false when "
                                                               "the detector was already armed and stage() did "
                                                               "nothing")})
    def stage(self):
        armed_before = bool(self.native.is_armed())
        self.native.stage()
        if not armed_before:
            # Only an arming chain run by this connection creates filewriters_finished, which unstage waits on.
            self._staged = True
        return {"armed": bool(self.native.is_armed()), "armed_here": not armed_before}

    @action(name=UNSTAGE,
            description="End the collection this connection staged: unstage() waits for the Odin writers, disarms the "
                        "camera, checks Odin and disables ROI mode; without a staged collection only disarm_detector "
                        "runs (staged false)",
            output={"armed": Field("boolean", description="is_armed afterwards"),
                    "staged": Field("boolean", description="True when a collection this connection staged was "
                                                           "unstaged; false when only the camera acquire was cleared"),
                    "odin_ok": Field("boolean", description="unstage's result: Odin initialised and no frame dropped "
                                                            "or timed out; false without a staged collection")})
    def unstage(self):
        if not self._staged:
            # Upstream unstage waits on filewriters_finished, which only the arming chain creates (eiger.py:174, 405),
            # and would raise after disarming, leaving disarming_status unfinished for every later stop().
            self.native.disarm_detector()
            return {"armed": bool(self.native.is_armed()), "staged": False, "odin_ok": False}
        try:
            odin_ok = self.native.unstage()
        finally:
            self._staged = False
        return {"armed": bool(self.native.is_armed()), "staged": True, "odin_ok": bool(odin_ok)}

    @action(name=DISARM, safe_state=True,
            description="Clear the Eiger camera acquire (disarm_detector) and report the resulting armed state",
            output={"armed": Field("boolean", description="False once the camera acquire is cleared")})
    def disarm(self):
        self.native.disarm_detector()
        return {"armed": bool(self.native.is_armed())}

    @action(name=FILES,
            description="Publish, as one bounded ZIP artifact, the .h5 files Odin wrote for the acquisition id it "
                        "reports: the regular files directly in DetectorParams.directory whose names start with the id "
                        "and an underscore, once the detector is neither arming nor armed (is_armed) and every Odin "
                        "writer reports Writing_RBV 0",
            output={"artifact_ref": Field("string", description="ZIP of the acquisition's files (manifest.json and "
                                                                "files/<name>)"),
                    "acquisition_id": Field("string", description="The acquisition id the files belong to"),
                    "files": Field("integer", description="Number of files in the artifact")})
    def files(self):
        if self._files is None:
            raise DriverFailed("MHS.DEVICE.NOT_READY", f"the DetectorParams directory cannot publish files: "
                               f"{self._files_problem}")
        # integrator v4 (2026-11-05; Claude Sonnet safety lens D1): while an arming chain runs or the detector is armed
        # (is_armed, eiger.py:134-135) the collection has not ended and Writing_RBV may still be 0 before capture starts,
        # so the files under this id may be an earlier collection's or incomplete.
        if not self.native.arming_status.done or self.native.is_armed():
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "the detector is arming or armed (is_armed): the "
                               "collection has not ended")
        odin = self.native.odin
        acquisition = odin.file_writer.id.get()
        if not isinstance(acquisition, str) or not _ACQUISITION.fullmatch(acquisition):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "Odin reports no acquisition id usable as a file-name prefix")
        if odin.meta.ready.get() != 0 or any(node.writing.get() != 0 for node in odin.nodes.nodes):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "Odin is still writing this acquisition")
        names = self._files.matching(re.escape(acquisition) + r"_[A-Za-z0-9._-]+\.h5")
        if not names:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", "no .h5 file of this acquisition in the directory")
        published = self._files.publish(self.ctx, names)
        return {"artifact_ref": published["artifact_ref"], "acquisition_id": acquisition,
                "files": len(published["files"])}

    @estop
    def stop(self):
        self._staged = False
        self.native.stop()
        # stop() waits for a started arming (eiger.py:195), but after that wait timed out its finally block marks the
        # disarm finished, so every later stop() is a no-op (eiger.py:210-213) while the arming chain, which ends with
        # set_cam_acquire (eiger.py:462), may still run and re-arm the camera after the safe-state disarm.
        if not self.native.arming_status.done:
            raise OutcomeUnknown("an arming chain is still running and may set the camera acquire again; the stop is "
                                 "not confirmed until it has finished")
