"""Fake backend of the SynQS Andor Solis camera: an in-memory stand-in for AndorSolis.blacs_workers:AndorCamera.

Gate G7: every public method here exists on the upstream ``AndorCamera`` class (AndorSolis/blacs_workers.py:16-113).
The acquisition attributes are a plain dictionary, as in the upstream class; writes change it, and ``snap`` returns
a frame.  All numbers here are test data of the fake, not device facts: the frame is 8 x 8 placeholders, while the
upstream default acquisition attributes name a 2560 x 2160 frame.  Nothing here talks to a camera or loads the Andor
SDK.
"""

# placeholder: 8 x 8 frame of test values, not the device's 2560 x 2160 sensor.
_FRAME_SIDE = 8  # placeholder
_FRAME = [[(row * _FRAME_SIDE + column) % 256 for column in range(_FRAME_SIDE)]  # placeholder
          for row in range(_FRAME_SIDE)]  # placeholder

# placeholder: starting acquisition attributes of the fake, not device limits or defaults of a real camera.
_START_ATTRIBUTES = {
    "acquisition": "single",              # placeholder
    "emccd": False,                       # placeholder
    "preamp": False,                      # placeholder
    "exposure_time": 0.02,                # placeholder
    "readout": "full_image",              # placeholder
    "trigger": "internal",                # placeholder
    "trigger_edge": "rising",             # placeholder
    "number_accumulations": 1,            # placeholder
    "number_kinetics": 1,                 # placeholder
    "xbin": 1,                            # placeholder
    "ybin": 1,                            # placeholder
    "height": _FRAME_SIDE,                # placeholder
    "width": _FRAME_SIDE,                 # placeholder
    "cooldown": True,                     # placeholder
    "temperature": 0.0,                   # placeholder
}


class FakeAndorCamera:
    def __init__(self, **_options):
        self.attributes = dict(_START_ATTRIBUTES)
        self.captures = 0                 # placeholder: call counter of the fake, not a device value
        self.configured = False           # placeholder: call flag of the fake
        self.closed = False               # placeholder: call flag of the fake
        self.armed = False                # placeholder: fake arming flag
        self._abort_acquisition = False   # placeholder: fake abort flag

    def set_attributes(self, attr_dict):
        self.attributes.update(attr_dict)

    def set_attribute(self, name, value):
        self.attributes[name] = value

    def get_attribute_names(self, visibility_level, writeable_only=True):
        return list(self.attributes.keys())

    def get_attribute(self, name):
        return self.attributes[name]

    def configure_acquisition(self, continuous=False, bufferCount=None):
        self.configured = True            # placeholder: the fake only records that setup ran
        self.armed = True                 # placeholder: the fake only records that setup ran

    def snap(self):
        self.captures += 1                # placeholder: the fake only records that it was called
        self.armed = False                # placeholder: the fake only records the end of a capture
        # placeholder: the fake caps every frame at its 8 x 8 test frame, whatever ROI was configured.
        width = max(1, min(int(self.attributes.get("width", _FRAME_SIDE)), _FRAME_SIDE))
        height = max(1, min(int(self.attributes.get("height", _FRAME_SIDE)), _FRAME_SIDE))
        return [[_FRAME[row % _FRAME_SIDE][column % _FRAME_SIDE] for column in range(width)]
                for row in range(height)]

    def grab(self):
        return self.snap()

    def grab_multiple(self, n_images, images, waitForNextBuffer=True):
        for _index in range(n_images):
            images.append(self.snap())

    def stop_acquisition(self):
        pass

    def abort_acquisition(self):
        self._abort_acquisition = True    # placeholder: the fake only records that it was called
        self.armed = False                # placeholder: the fake only records that it was called

    def close(self):
        self.closed = True                # placeholder: the fake only records that it was called
