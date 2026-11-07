# Facts and tags for gh.scopefoundry/hw_picam

Every fact cites its source at commit `fab5d61440b38e04e176e66ff880d16061f23997`: `upstream_code` is a code or
comment line of the clone. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PiCAM loads the PICam shared library named by the PICAM_DLL environment variable with ctypes when the module is imported | upstream_code | picam.py:13-14 |
| read_param dispatches on the PICam parameter type and returns the value; an enumeration is returned as its short name and Rois as a list of ROI tuples | upstream_code | picam.py:57-106 |
| write_param sets integer, floating-point and enumeration parameters through the PICam C API | upstream_code | picam.py:115-142 |
| commit_parameters commits the parameter set and returns the names of the parameters that failed | upstream_code | picam.py:164-173 |
| The upstream exposure value is in milliseconds | upstream_code | picam.py:334 |
| The ScopeFoundry plug-in labels ExposureTime in ms and AdcSpeed in MHz | upstream_code | picam_hw.py:43-44 |
| read_rois stores the returned ROI list on self.roi_array and returns it | upstream_code | picam.py:199-201 |
| write_single_roi writes one ROI_tuple through write_rois | upstream_code | picam.py:231-238 |
| acquire takes readout_count readouts and returns a flat uint16 array; ReadoutStride is treated as a byte count | upstream_code | picam.py:240-263 |
| reshape_frame_data reshapes the flat readout per ROI, dividing the ROI width and height by the binning | upstream_code | picam.py:290-301 |
| The readout measurement reads the ROIs, commits the parameters, acquires one readout and reshapes it per ROI | upstream_code | picam_readout.py:34-44 |
| close closes the camera and uninitializes the PICam library | upstream_code | picam.py:52-54 |
| The cooling status enumeration values are Unlocked, Locked and Faulted | upstream_code | picam_ctypes.py:2906-2911 |

Limits: exposure time and the six ROI fields are `Limit.operator_required`. The clone declares the PICam constraint
types (`Range` for ExposureTime, `Rois` for the ROI parameter, picam_ctypes.py:1802 and 1896) but the numeric ends
are queried from the camera at run time; no text file of the clone states a fixed exposure, pixel or binning range.
The ScopeFoundry setting initials in picam_hw.py:20-25 are constructor defaults of the GUI, not device bounds, so
they are not used as limits. `site-limits.example.json` is an example operator overlay that fills these bounds.

Action and fake: the capture action follows the upstream readout path (picam_readout.py:34-44) and writes a 16-bit
PGM file; the receipt carries the path and size, not the pixel array. The fake returns an 8 x 8 placeholder frame
while the real frame size is the configured ROI width divided by its binning by the height divided by its binning
(picam.py:295-299); the real size is not a fixed fact of the clone.

Safety: the native stop is `close()` (picam.py:52-54), which closes the camera and uninitializes the PICam library;
the e-stop calls it and the safe state is the closed camera. The upstream text documents no independent hardware
e-stop, so `estop_physical_ref` is not set; the device is an R1 camera and the card's floor is R1. This package is
model-authored and unreviewed, and nothing here ran on hardware.

Tags: camera, ccd, picam, princeton-instruments, imaging, scopefoundry
