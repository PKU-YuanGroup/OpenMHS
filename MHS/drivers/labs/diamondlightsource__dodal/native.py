"""Hardware backend of the Eiger detector package: the pinned dodal classic-Ophyd EigerDetector with DetectorParams.

The gate never imports this module.  ``connect`` runs only when an operator loads the hardware backend
(``mhs.adapter.load_driver(..., backend="hardware", allow_hardware=True, ...)``); it is then the only code that imports
dodal and, through it, ophyd, the EPICS client and the config-server client.  The model has never run it against an IOC,
Odin or a config server.

What it does, in the order the pinned upstream needs (commit f96fef4e):

1. ``config_server_url`` becomes dodal's global config client, as the i03 module's ``config_client`` fixture does
   (``ConfigClient.from_url`` and ``set_config_client``, src/dodal/beamlines/i03.py:102-110).  ``DetectorParams`` reads
   its beam-centre lookup table through it (src/dodal/devices/detector/detector.py:56-60).
2. ``detector_params`` (a mapping of ``DetectorParams`` fields, the operator's deployment parameters) is validated by
   the upstream model.  Its ``directory`` must already exist (detector.py:83-88) and it must carry ``run_number``:
   without it ``run_number`` is derived again from the directory's nexus files on every access (detector.py:62-68,
   src/dodal/utils.py:128-142), so the acquisition id Odin writes under (``full_filename``, detector.py:135-137) could
   change between arming and the package's file publication.  ``connect`` refuses parameters without it.
3. ``EigerDetector(prefix=..., name=..., beamline=...)`` is built as i03 builds it (src/dodal/beamlines/i03.py:185-190;
   constructor src/dodal/devices/eiger.py:67-87); ``wait_for_connection`` waits for every Signal of the Device graph,
   so a missing PV raises before an MHS command is served.
4. ``set_detector_parameters`` (eiger.py:101-120) stores the parameters and checks the size constants and the beam
   centre converter.  The native ``stop()`` and the ROI calls need them (``change_roi_mode`` asserts them,
   eiger.py:221-223).

The parameters are fixed for the connection: each collection arms with them, so a new run number (a new file-name
prefix) needs a new connection.  ``connection_timeout_s`` is a deployment choice, not a device bound.  The driver has
no hardware backend review (``reviewed_by`` is null); at R1 the loader does not require one for a model-authored
backend, and no hardware run is claimed.
"""

from collections.abc import Mapping


def connect(*, prefix, detector_params, config_server_url, name="eiger", beamline="i03", connection_timeout_s=10.0):
    if not isinstance(prefix, str) or not prefix:
        raise ValueError("prefix must be the non-empty EPICS prefix of the Eiger")
    if not isinstance(name, str) or not name.isidentifier():
        raise ValueError("name must be a Python identifier (it names the ophyd Device and its Signals)")
    if not isinstance(beamline, str) or not beamline.isidentifier():
        raise ValueError("beamline must be a beamline name such as 'i03' (it selects the upstream timeouts)")
    if (isinstance(connection_timeout_s, bool) or not isinstance(connection_timeout_s, (int, float))
            or not 0 < connection_timeout_s <= 60):
        raise ValueError("connection_timeout_s must be a number of seconds in (0, 60]")
    if not isinstance(config_server_url, str) or not config_server_url:
        raise ValueError("config_server_url must name the deployment's config server (beam-centre lookup table)")
    if not isinstance(detector_params, Mapping):
        raise ValueError("detector_params must be a mapping of DetectorParams fields")
    if detector_params.get("run_number") is None:
        raise ValueError("detector_params must set run_number: without it the acquisition id is derived again from "
                         "the directory's nexus files on every access (detector.py:62-68, utils.py:128-142)")
    from daq_config_server.client import ConfigClient
    from dodal.common.beamlines.beamline_utils import set_config_client
    from dodal.devices.detector import DetectorParams
    from dodal.devices.eiger import EigerDetector

    set_config_client(ConfigClient.from_url(config_server_url))
    params = DetectorParams.model_validate(dict(detector_params))
    if params.override_run_number is None:
        raise ValueError("detector_params did not set run_number")
    device = EigerDetector(prefix=prefix, name=name, beamline=beamline)
    device.wait_for_connection(timeout=connection_timeout_s)
    device.set_detector_parameters(params)
    return device
