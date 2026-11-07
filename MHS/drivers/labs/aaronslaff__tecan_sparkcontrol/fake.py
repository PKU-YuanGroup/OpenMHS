"""Fake backend of the SparkControl driver: an in-memory stand-in for SparkControlClient.

Gate G7: every public method defined here exists on
``spark_control_automation:SparkControlClient`` (spark_control_automation.py:186-462).  The fake does no HTTP and
imports nothing from the clone.  All values below are test data, not device facts: the status, apps, settings and
plate-geometry documents, the method status words and the calibration response are placeholders written only so the
driver can be exercised.  Nothing here talks to a device.
"""

from copy import deepcopy


class FakeSparkControlClient:
    """An in-memory client with the public surface of SparkControlClient."""

    def __init__(self, **_options):
        self._status = {"state": "idle"}                                  # placeholder canned reply
        self._apps = {"apps": []}                                         # placeholder canned reply
        self._settings = {"settings": {}}                                 # placeholder canned reply
        self._plate_geometry = {"plate_type": "96-well microplate",
                                "rows": 8, "columns": 12}                 # placeholder canned reply
        self._methods = {}
        self._calibrations = 0                                            # placeholder counter

    def get_instrument_status(self):
        return deepcopy(self._status)

    def get_available_apps(self):
        return deepcopy(self._apps)

    def get_instrument_settings(self):
        return deepcopy(self._settings)

    def get_plate_geometry(self):
        return deepcopy(self._plate_geometry)

    def calibrate_instrument(self, calibration_type):
        self._calibrations += 1                                           # placeholder counter
        return {"calibration_type": calibration_type,
                "status": "completed"}                                    # placeholder canned reply

    def start_method(self, method_id, plate_config=None):
        self._methods[method_id] = {"method_id": method_id,
                                    "status": "running"}                  # placeholder method state
        return {"method_id": method_id,
                "status": "running"}                                      # placeholder canned reply

    def get_method_status(self, method_id):
        method = self._methods.get(method_id)
        if method is None:
            return {"method_id": method_id,
                    "status": "unknown"}                                  # placeholder canned reply
        return deepcopy(method)

    def stop_method(self, method_id):
        method = self._methods.setdefault(method_id, {"method_id": method_id})
        method["status"] = "stopped"                                      # placeholder method state
        return {"method_id": method_id,
                "status": "stopped"}                                      # placeholder canned reply

    def get_measurement_results(self, method_id):
        return {"method_id": method_id,
                "results": []}                                            # placeholder canned reply
