# Facts and tags for gh.attolab/pymodaq_plugins_pylablib_camera

Every fact cites its source at commit `ff1e71510bc1a4b07a700034d37f74a5e916abf8`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a generic PyMoDAQ camera plugin meant to be subclassed for a camera through the pylablib library, and the plugin does not work on its own | vendor_doc | README.rst:16-19 |
| The generic viewer handles hardware ROI, hardware binning and frames through a callback | vendor_doc | README.rst:35 |
| DAQ_2DViewer_ThorlabsPLL enumerates the Thorlabs serial numbers at import with Thorlabs.list_cameras_tlcam() | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_ThorlabsPLL.py:17 |
| DAQ_2DViewer_ThorlabsPLL.init_controller opens Thorlabs.ThorlabsTLCamera with the serial number selected in settings['camera_list'] | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_ThorlabsPLL.py:24-29 |
| The viewer keeps the pylablib camera controller in self.controller and reads the camera information string from controller.get_device_info()[1] | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:140-144 |
| A change of the exposure setting is written to the controller as param.value()/1000, milliseconds to seconds | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:61-63 |
| exposure reads controller.get_exposure() and writes controller.set_exposure(value) | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:114-122 |
| get_roi returns hstart, hend, vstart, vend, hbin and vbin; the viewer derives the image width and height from the first four values | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:153-158 |
| Some pylablib get_roi calls return only four values instead of six and the viewer then assumes a binning of 1 | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:186-190 |
| update_rois calls controller.set_roi with hstart, hend=hstart+width, vstart, vend=vstart+height and the two binning factors | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:229-244 |
| The viewer reads the detector size with controller.get_detector_size() when it clears the ROI | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:97-108 |
| stop calls controller.stop_acquisition() and then controller.clear_acquisition() | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:326-330 |
| close closes the pylablib controller with controller.close() | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:315-321 |
| The viewer's exposure-time setting starts at 1 ms and its binning setting admits [1, 2]; these are UI defaults of the parameter tree, not bounds reported by a camera | upstream_code | src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_GenericPylablibCamera.py:26-30 |

Limits: the exposure and the six ROI/binning writes are `Limit.operator_required`. No text file of the clone states a
usable range of an installed camera: the viewer's settings (1 ms, `limits: [1, 2]`) are UI defaults
(daq_2Dviewer_GenericPylablibCamera.py:26-30), and the sensor geometry differs by model. The site supplies the range of
its camera (`site-limits.example.json` shows the overlay; its values are examples only, not measurements of any
camera).

Safety: the e-stop is the viewer's native `stop` (`controller.stop_acquisition` then `controller.clear_acquisition`,
daq_2Dviewer_GenericPylablibCamera.py:326-330); the safe state is the stopped acquisition. No line of the clone
documents an independent hardware e-stop, and at R1 SAFE-045 does not ask for one, so `estop_physical_ref` is not set.

Not covered: the image arrays the viewer emits from its Qt callback thread. The standard's image form is an artifact
reference and this package has no artifact store, so no image capability is bound.

Tags: camera, thorlabs, pylablib, imaging, roi, binning
