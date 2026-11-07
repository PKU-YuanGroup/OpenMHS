"""Fake backend for the LI-COR Odyssey Classic driver.

The upstream transport is ``plr_v4.odyssey.connection:OdysseyDriver`` (connection.py:223); this fake implements the
same public method names with in-memory state, so gate G7 can compare it with the pinned class.  It never imports or
runs the clone and never opens a socket.

Every number and byte below is test data, not a device fact: the placeholder JPEG is 8 x 6 pixels, the progress is a
canned value, and the fake accepts start, pause, stop and cancel without enforcing the instrument's
configure-before-start rule.  The real instrument reports 16-bit TIFF channels and the upstream status page reports
the live progress; neither is modelled here.
"""

import base64

# placeholder: an 8 x 6 JPEG generated for this fake, not a scan and not a measured image
_PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywt"
    "QFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09P"
    "T09PT09PT09PT09PT09PT09PT09PT0//wAARCAAGAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQF"
    "BgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkK"
    "FhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZ"
    "mqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEB"
    "AQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEI"
    "FEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3"
    "eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq"
    "8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDg6KKK6TA//9k="
)

_PLACEHOLDER_INFO = "<html><body>Odyssey Classic 9120 (fake placeholder)</body></html>"  # placeholder


class FakeOdyssey:
    """In-memory stand-in for ``OdysseyDriver``; public methods mirror the pinned class."""

    def __init__(self, *, stop_ignored=False, **_options):
        self._stop_ignored = bool(stop_ignored)  # placeholder negative path: the instrument keeps its state
        self._open = False
        self._closed = False
        self._params = {}
        self._state = "Idle"
        self._progress = 0.0
        self._time_remaining = ""
        self._current_user = ""
        self._lid_status = "closed"
        self._stop_from_status_calls = 0

    async def setup(self):
        self._open = True
        self._closed = False

    async def stop(self):
        self._closed = True
        self._open = False

    async def configure_scan(self, params):
        self._params = dict(params)
        self._state = "Configured"
        self._progress = 0.0
        self._time_remaining = ""
        return ""

    async def wait_initialization(self, scan_name, group, timeout_steps=7):
        self._params["name"] = str(scan_name)
        self._params["group"] = str(group)
        return None

    async def start_scan(self):
        self._state = "Scanning"
        self._progress = 42.0  # placeholder progress
        self._time_remaining = "00:00:00"  # placeholder
        return ""

    async def pause_scan(self):
        self._state = "Paused"
        return ""

    async def stop_scan(self):
        self._state = "Stopped"
        return ""

    async def cancel_scan(self):
        self._state = "Idle"
        self._progress = 0.0
        return ""

    async def get_status(self):
        return {
            "state": self._state,
            "current_user": self._current_user,
            "progress": str(self._progress),
            "time_remaining": self._time_remaining,
            "lid_status": self._lid_status,
        }

    async def stop_from_status(self):
        self._stop_from_status_calls += 1
        if not self._stop_ignored:
            self._state = "Stopped"
        return ""  # the upstream returns the response text unchecked

    async def get_jpeg_preview(self, group, scan_name, contrast_700=5, contrast_800=5,
                               channels="700 800", background="black"):
        return _PLACEHOLDER_JPEG

    async def get_instrument_info(self):
        return _PLACEHOLDER_INFO
