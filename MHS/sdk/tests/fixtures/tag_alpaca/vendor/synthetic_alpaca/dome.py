"""Synthetic Alpaca responder text for the OpenMHS tag-bridge SDK tests (original, never executed)."""


def init_routes(app, devname, module):
    """Route /api/v1/<devname>/<devnum>/<member> to the responder classes (text only)."""


class azimuth:
    def on_get(self, req, resp, devnum):
        resp.text = "azimuth"


class slewing:
    def on_get(self, req, resp, devnum):
        resp.text = "slewing"


class slewtoazimuth:
    def on_put(self, req, resp, devnum):
        resp.text = "slewtoazimuth Azimuth"


class abortslew:
    def on_put(self, req, resp, devnum):
        resp.text = "abortslew"


class Dome:
    """The device class behind the responders."""

    def __init__(self):
        self.slewing = False

    def abort_slew(self):
        self.slewing = False
