"""OpenMHS driver for gh.aaronslaff/tecan_sparkcontrol: a Tecan SparkControl microplate reader over its HTTP API.

A direct Driver over the upstream HTTP client ``spark_control_automation:SparkControlClient``.  The client sends
JSON over HTTP to the instrument (spark_control_automation.py:113-177) and returns the decoded response documents;
it has no text line protocol, so a SerialDriver or ScpiDriver command table cannot express it.  The card names the
python-object family; this is a direct Driver because the client methods return raw JSON documents and the stop path
needs the method id this driver keeps.

* reads: the instrument status, the available apps, the instrument settings, the plate geometry, and the status and
  results of the method this driver last started or stopped (empty before any method is tracked);
* actions: calibration, start a method, stop a named method, and stop the tracked method as the safe-state action;
* no write parameter: the only client write is ``update_instrument_settings(settings)``, whose request document is
  not described by any text file of the clone, so a writable state field cannot be given a bounded schema;
* no method creation: ``create_method`` and the strip builders take upstream dataclasses and their parameter
  ranges are not stated by any text file of the clone, so they are not exposed;
* the only stop path is ``stop_method(method_id)`` (spark_control_automation.py:402-405).  The e-stop and the
  safe-state action stop the tracked method; without a tracked method there is nothing the client can address, so
  they query the instrument status instead and say so in the output.

The clone exposes reagent injection with a volume and a speed (spark_control_automation.py:307-329), a shaking strip
(350-372) and a measurement temperature field (81), so the declared risk is R2 even though the card's floor is R1.
No text file of the clone documents an independent hardware e-stop; the safe-state action satisfies SAFE-045 and the
driver does not claim a safety-rated stop.  This package is model-authored and unreviewed: it is checked on the fake
backend only, and its hardware backend is refused until a human signs ``reviewed_by`` (R2).
"""

from mhs.driver import Driver, Fact, Field, action, estop, read


class SparkControl(Driver):
    device_id = "tecan-sparkcontrol"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R2"
    native = "spark_control_automation:SparkControlClient"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSparkControlClient"}
    vendor, model = "Tecan", "SparkControl V2.4"
    display_name = "Tecan SparkControl microplate reader (spark_control_automation.SparkControlClient)"
    tags = ["microplate-reader", "plate-reader", "luminescence", "absorbance", "fluorescence", "tecan", "http"]
    facts = [
        Fact("The client sends JSON over HTTP to a base URL and authenticates with a bearer API key or HTTP basic "
             "credentials", source="upstream_code", ref="spark_control_automation.py:113-177"),
        Fact("get_instrument_status reads GET /api/v1/status and get_available_apps reads GET /api/v1/apps",
             source="upstream_code", ref="spark_control_automation.py:186-194"),
        Fact("start_method posts /api/v1/methods/start with a method_id and an optional plate_config",
             source="upstream_code", ref="spark_control_automation.py:374-395"),
        Fact("get_method_status reads GET /api/v1/methods/{method_id}/status and stop_method posts to "
             "/api/v1/methods/{method_id}/stop", source="upstream_code",
             ref="spark_control_automation.py:397-405"),
        Fact("get_measurement_results reads GET /api/v1/methods/{method_id}/results", source="upstream_code",
             ref="spark_control_automation.py:407-410"),
        Fact("get_instrument_settings reads GET /api/v1/settings and get_plate_geometry reads "
             "GET /api/v1/plate-geometry", source="upstream_code", ref="spark_control_automation.py:431-444"),
        Fact("calibrate_instrument posts /api/v1/calibrate with a calibration type", source="upstream_code",
             ref="spark_control_automation.py:446-462"),
        Fact("A method strip can be an injection with a volume in microliters and a speed in microliters per second",
             source="upstream_code", ref="spark_control_automation.py:307-329"),
        Fact("A shaking strip takes a duration in seconds, a frequency in rpm and an amplitude in mm",
             source="upstream_code", ref="spark_control_automation.py:350-372"),
        Fact("The measurement parameters carry an optional temperature", source="upstream_code",
             ref="spark_control_automation.py:69-86"),
        Fact("The supported plate types are 96-well, 384-well and 1536-well microplates and a cell chip",
             source="upstream_code", ref="spark_control_automation.py:61-67"),
        Fact("The scripts target SparkControl V2.4 (Document Part No. 30245640)", source="upstream_code",
             ref="spark_control_automation.py:13"),
    ]
    safe_state = ("the tracked method is stopped with the native stop_method; without a tracked method the driver "
                  "only queries the instrument status, because the client has no global stop request")

    #: The method this driver last started or stopped.  It is driver bookkeeping, not a device fact.
    _method_id = ""

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("instrument_status", type="object",
          description="Status document returned by the instrument")
    def instrument_status(self):
        return self.native.get_instrument_status()

    @read("available_apps", type="object",
          description="Applications document returned by the instrument")
    def available_apps(self):
        return self.native.get_available_apps()

    @read("instrument_settings", type="object",
          description="Instrument settings document returned by the instrument")
    def instrument_settings(self):
        return self.native.get_instrument_settings()

    @read("plate_geometry", type="object",
          description="Plate geometry document returned by the instrument")
    def plate_geometry(self):
        return self.native.get_plate_geometry()

    @read("method_status", type="object",
          description="Status of the method this driver last started or stopped; empty before the first method")
    def method_status(self):
        if not self._method_id:
            return {}
        return self.native.get_method_status(self._method_id)

    @read("measurement_results", type="object",
          description="Measurement results of the method this driver last started or stopped; empty before the "
                      "first method")
    def measurement_results(self):
        if not self._method_id:
            return {}
        return self.native.get_measurement_results(self._method_id)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.aaronslaff.calibrate_instrument.v1",
            description="Run the native calibration procedure for a calibration type",
            input={"calibration_type": Field("string",
                                             description="Calibration type passed to the native procedure")},
            output={"response": Field("object",
                                      description="Calibration response document returned by the instrument")})
    def calibrate(self, calibration_type):
        response = self.native.calibrate_instrument(calibration_type)
        return {"response": response}

    @action(name="x-cap.aaronslaff.start_method.v1",
            description="Start a method and remember its id for the stop path",
            input={"method_id": Field("string", description="Method id to start")},
            output={"response": Field("object",
                                      description="Start response document returned by the instrument")})
    def start_method(self, method_id):
        self._method_id = method_id
        try:
            response = self.native.start_method(method_id)
        except Exception:
            self._method_id = ""
            raise
        return {"response": response}

    @action(name="x-cap.aaronslaff.stop_method.v1",
            description="Stop the method with the given id and remember it for the safe-state action",
            input={"method_id": Field("string", description="Method id to stop")},
            output={"response": Field("object",
                                      description="Stop response document returned by the instrument")})
    def stop_method(self, method_id):
        response = self.native.stop_method(method_id)
        self._method_id = method_id
        return {"response": response}

    @action(name="x-cap.aaronslaff.stop_active_method.v1", safe_state=True,
            description="Stop the tracked method (the safe state); it takes no input",
            output={"stopped": Field("boolean",
                                     description="True when a tracked method was stopped"),
                    "method_id": Field("string",
                                       description="Method id that was stopped; empty without a tracked method")})
    def stop_active_method(self):
        if not self._method_id:
            self.native.get_instrument_status()
            return {"stopped": False, "method_id": ""}
        method_id = self._method_id
        self.native.stop_method(method_id)
        return {"stopped": True, "method_id": method_id}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def emergency_stop(self):
        """Stop the tracked method; without one, query the instrument status (the client has no global stop)."""
        if self._method_id:
            self.native.stop_method(self._method_id)
        else:
            self.native.get_instrument_status()
