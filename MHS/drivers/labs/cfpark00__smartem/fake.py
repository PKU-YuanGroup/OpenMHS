"""Fake backend of the SmartEM Verios driver: an in-memory stand-in for ThermoFisherVerios.

Gate G7: every public method defined here exists on ``smartem.online.microscope:ThermoFisherVerios``
(smartem/online/microscope.py:217-399).  The class is synchronous, so the fake is synchronous too.  The
upstream class imports the proprietary ``autoscript_sdb_microscope_client`` in its constructor and talks to a
real instrument; this object never imports it and never talks to a device.

The image is a small synthetic frame (test data, marked ``# placeholder``); the real device returns the frame
at the resolution the caller requested.  The fixed placeholder size keeps the receipts small.  No value here
is a fact, a limit or a statement about an instrument.
"""


class FakeThermoFisherVerios:
    def __init__(self, **_options):
        self.initialized = False
        self.closed = False
        self.prepared = False
        self.focus_calls = 0
        self.last_image_request = None
        self.last_move = None

    def initialize(self):
        self.initialized = True

    def close(self):
        self.closed = True

    def connect(self):
        self.initialized = True

    def disconnect(self):
        self.closed = True

    def prepare_acquisition(self):
        self.prepared = True

    def auto_focus(self, baseline=False):
        self.focus_calls += 1

    def auto_contrast_brightness(self, baseline=False):
        pass

    def auto_stig(self):
        pass

    def get_image(self, params):
        self.last_image_request = dict(params)
        resolution = params["resolution"]
        # placeholder: at most 16 x 16, not the instrument's real frame size
        width = max(1, min(16, int(resolution[0])))
        height = max(1, min(16, int(resolution[1])))
        # placeholder: synthetic ramp pixels, not the instrument's data
        image = [[(row * width + column) % 256 for column in range(width)] for row in range(height)]
        if params.get("invert"):
            # placeholder: the 16-bit full scale matches get_image's bit_depth 16 (microscope.py:327)
            image = [[65535 - value for value in row] for row in image]
        return image

    def move(self, x, y, z=None, r=None, t=None):
        self.last_move = (x, y, z, r, t)
