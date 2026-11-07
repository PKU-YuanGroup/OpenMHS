"""Fake backend of the PICam driver: an in-memory stand-in for picam:PiCAM.

Gate G7: every public method defined here exists on the upstream ``PiCAM`` class (picam.py:20-301).  The fake keeps
the camera parameters in a dictionary and the ROI list as named tuples, like the upstream wrapper keeps them in the
PICam library; reads never move by themselves, so reading the state twice gives the same state.  Every number below
is test data of the fake, not a device fact or a device limit: the frame is an 8 x 8 placeholder while a real
readout has the configured ROI size, and the parameter values are canned replies.  Nothing here loads the PICam DLL
or talks to a camera.
"""

import collections

# placeholder: the six fields of the upstream ROI_tuple (picam.py:18); values below are test data.
_ROI = collections.namedtuple("_ROI", "x width x_binning y height y_binning")

# placeholder: 8 x 8 frame of test values, not the device's array and not a sensor size.
_SIDE = 8
_PIXELS = [((row * _SIDE + column) * 257) % 65536          # placeholder
           for row in range(_SIDE) for column in range(_SIDE)]


class FakePiCAM:
    """The fake camera object; its method surface is the upstream PiCAM surface."""

    def __init__(self, **_options):
        # placeholder: canned parameter values, not device defaults.
        self._params = {
            "ExposureTime": 10.0,                              # placeholder
            "AdcSpeed": 2.0,                                   # placeholder
            "ReadoutStride": 16,                               # placeholder
            "SensorTemperatureStatus": "Unlocked",             # placeholder
        }
        self._rois = [_ROI(0, _SIDE, 1, 0, _SIDE, 1)]          # placeholder
        self.roi_array = list(self._rois)                      # set by read_rois upstream (picam.py:199-201)
        self.closed = False                                    # placeholder: call flag of the fake
        self.commits = 0                                       # placeholder: call counter of the fake
        self.acquisitions = 0                                  # placeholder: call counter of the fake

    def get_param_names(self):
        return [name for name in self._params] + ["Rois"]

    def get_param_readwrite(self, pname):
        if pname in ("ExposureTime", "Rois"):
            return "ReadWrite"
        if pname in self._params:
            return "ReadOnly"
        raise ValueError("PICAM fake does not know the parameter {}".format(pname))

    def read_param(self, pname):
        if pname == "Rois":
            return list(self._rois)
        if pname in self._params:
            return self._params[pname]
        raise ValueError("PICAM fake does not know the parameter {}".format(pname))

    def write_param(self, pname, newval):
        if pname == "ExposureTime":
            self._params[pname] = float(newval)
            return
        if pname == "AdcSpeed":
            self._params[pname] = float(newval)
            return
        raise ValueError("PICAM fake does not write the parameter {}".format(pname))

    def commit_parameters(self):
        self.commits += 1                                     # placeholder: the fake only records the commit
        return []

    def read_rois(self):
        self.roi_array = list(self._rois)
        return list(self.roi_array)

    def write_rois(self, rois_list):
        self._rois = [_ROI(*(int(item[index]) for index in range(6))) for item in rois_list]
        self.roi_array = list(self._rois)

    def write_single_roi(self, x, width, x_binning, y, height, y_binning):
        return self.write_rois([_ROI(int(x), int(width), int(x_binning), int(y), int(height), int(y_binning))])

    def acquire(self, readout_count=1, readout_timeout=-1):
        self.acquisitions += 1                                # placeholder: the fake only records the call
        return list(_PIXELS)                                  # placeholder: always the 8 x 8 test frame

    def reshape_frame_data(self, dat):
        # placeholder: the fake returns its 8 x 8 test frame whatever ROI was configured; the real size is the
        # configured ROI width/binning by height/binning (picam.py:290-301).
        values = list(dat) if dat is not None else []
        if len(values) < len(_PIXELS):
            values = list(_PIXELS)
        return [[values[row * _SIDE + column] for column in range(_SIDE)] for row in range(_SIDE)]

    def close(self):
        self.closed = True                                     # placeholder: the fake only records the call
