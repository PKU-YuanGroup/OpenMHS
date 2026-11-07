"""OpenMHS driver for gh.aaronslaff/tecan_fluentcontrol: a Tecan FluentControl liquid handler.

A direct Driver (decorated methods) over the upstream HTTP client
``fluent_control_automation:FluentControlClient``.  The client sends JSON over HTTP and has no text line protocol,
so a SerialDriver or ScpiDriver command table cannot express it; the driver calls the upstream methods and keeps the
session id the client does not keep.  The card names the python-object family; this is a direct driver because the
transfer method takes a list of upstream ``TransferParameters`` dataclasses and the runtime needs a driver-held
session id for the stop path.

* reads: the instrument status, the deck layout, and the status of the session this driver last created or started;
* actions: post a transfer session, start it, read its status, cancel it, and cancel the active session as the
  safe-state action;
* no write parameter: the upstream client has no set-point-like state, only session and deck operations.  The deck
  layout is read; posting a deck layout is not exposed because the clone does not document the GET deck schema and a
  writable state field cannot carry the upstream ``LabwarePosition`` list without inventing that schema;
* the only stop path in the client is ``cancel_transfer_session(session_id)``; there is no global stop request.  The
  e-stop cancels the tracked session, or queries the instrument status when no session is tracked, and the
  ``cancel_active_transfer`` safe-state action does the same.

The transfer volume is ``Limit.operator_required``: no text file of the clone states a volume range or the capacity
of the tips on a unit, so every transfer is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site overlay supplies the
range (``site-limits.example.json`` shows the overlay).  The package is model-authored and unreviewed; it is checked
on the fake backend only and the hardware backend is refused until a human signs ``reviewed_by`` (R2).
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

#: No text file of the clone states a transfer volume range; the site sets it for its deck and its tips.
_VOLUME_LIMIT = Limit.operator_required(
    "no text file of the clone states a transfer volume range, and the tip capacity of a unit depends on the tips "
    "installed; the site supplies the volume range for its deck and tips")


class FluentControl(Driver):
    device_id = "fluentcontrol"
    device_kind = "lab.liquid_handler"
    mode = "hardware"
    risk = "R2"
    native = "fluent_control_automation:FluentControlClient"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeFluentControlClient"}
    vendor, model = "Tecan", "FluentControl"
    display_name = "Tecan FluentControl liquid handler (fluent_control_automation.FluentControlClient)"
    tags = ["liquid-handler", "pipetting", "tecan", "http"]
    facts = [
        Fact("The scripts control FluentControl instruments programmatically for deck layouts and liquid transfer "
             "operations", source="vendor_doc", ref="FLUENT_CONTROL_README.md:3"),
        Fact("The client takes a base URL and authenticates with a bearer API key or HTTP basic credentials",
             source="upstream_code", ref="fluent_control_automation.py:86-113"),
        Fact("get_instrument_status reads GET /api/v1/status and get_deck_layout reads GET /api/v1/deck/layout",
             source="upstream_code", ref="fluent_control_automation.py:159-167"),
        Fact("post_transfer_session posts the transfers to /api/v1/transfers/session with a generated session_id and "
             "status pending", source="upstream_code", ref="fluent_control_automation.py:190-210"),
        Fact("start_transfer_session posts to /api/v1/transfers/session/{session_id}/start",
             source="upstream_code", ref="fluent_control_automation.py:212-215"),
        Fact("get_transfer_status reads GET /api/v1/transfers/session/{session_id}/status",
             source="upstream_code", ref="fluent_control_automation.py:217-220"),
        Fact("cancel_transfer_session posts to /api/v1/transfers/session/{session_id}/cancel and takes the session id",
             source="upstream_code", ref="fluent_control_automation.py:222-225"),
        Fact("A transfer finishes with status completed, failed or cancelled",
             source="upstream_code", ref="fluent_control_automation.py:344"),
        Fact("Source and destination are position IDs, liquid class and tip type are names, and the volume is in "
             "microliters", source="vendor_doc", ref="FLUENT_CONTROL_README.md:245-249"),
        Fact("Aspiration and dispense speeds are in microliters per second, the air gap and mix volume in "
             "microliters, and the retract distance in millimetres",
             source="vendor_doc", ref="FLUENT_CONTROL_README.md:250-257"),
    ]
    safe_state = ("the active transfer session is cancelled; when no session is tracked the driver only queries the "
                  "instrument status, because the client has no global stop request")

    #: The session this driver last created or started.  It is driver bookkeeping, not a device fact.
    _session_id = ""

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("instrument_status", type="object", description="Status document returned by the instrument")
    def instrument_status(self):
        return self.native.get_instrument_status()

    @read("deck_layout", type="object", description="Deck layout document returned by the instrument")
    def deck_layout(self):
        return self.native.get_deck_layout()

    @read("transfer_status", type="object",
          description="Status of the transfer session this driver last created or started; empty before the first "
                      "session")
    def transfer_status(self):
        if not self._session_id:
            return {}
        return self.native.get_transfer_status(self._session_id)

    # -- actions ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.aaronslaff.post_transfer_session.v1",
            description="Post one source-to-destination transfer and create a transfer session",
            input={
                "source_position": Field("string", description="Source deck position ID"),
                "destination_position": Field("string", description="Destination deck position ID"),
                "volume_ul": Field("number", unit="uL", description="Transfer volume",
                                   limit=_VOLUME_LIMIT),
                "liquid_class": Field("string", description="Liquid class name"),
                "tip_type": Field("string", description="Tip type name"),
            },
            output={"session_id": Field("string", description="Session id returned by the instrument"),
                    "status": Field("string", description="Session status returned by the instrument")})
    def post_transfer_session(self, source_position, destination_position, volume_ul, liquid_class, tip_type):
        transfer = {
            "source_position": source_position,
            "destination_position": destination_position,
            "volume_ul": volume_ul,
            "liquid_class": liquid_class,
            "tip_type": tip_type,
        }
        response = self.native.post_transfer_session([transfer])
        if not isinstance(response, dict):
            raise DriverFailed("MHS.DEVICE.FAULTED", "post_transfer_session returned no object")
        session_id = response.get("session_id")
        status = response.get("status")
        if not isinstance(session_id, str) or not session_id:
            raise DriverFailed("MHS.DEVICE.FAULTED", "post_transfer_session returned no session_id")
        if not isinstance(status, str) or not status:
            raise DriverFailed("MHS.DEVICE.FAULTED", "post_transfer_session returned no status")
        self._session_id = session_id
        return {"session_id": session_id, "status": status}

    @action(name="x-cap.aaronslaff.start_transfer_session.v1",
            description="Start the transfer session with the given id",
            input={"session_id": Field("string", description="Session id to start")},
            output={"session_id": Field("string", description="Session id that was started")})
    def start_transfer_session(self, session_id):
        self.native.start_transfer_session(session_id)
        self._session_id = session_id
        return {"session_id": session_id}

    @action(name="x-cap.aaronslaff.transfer_status.v1", verb="read",
            description="Read the status of the transfer session with the given id",
            input={"session_id": Field("string", description="Session id to read")},
            output={"session_id": Field("string", description="Session id that was read"),
                    "status": Field("string", description="Session status returned by the instrument")})
    def get_transfer_status(self, session_id):
        response = self.native.get_transfer_status(session_id)
        if not isinstance(response, dict):
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_transfer_status returned no object")
        status = response.get("status")
        if not isinstance(status, str) or not status:
            raise DriverFailed("MHS.DEVICE.FAULTED", "get_transfer_status returned no status")
        return {"session_id": session_id, "status": status}

    @action(name="x-cap.aaronslaff.cancel_transfer_session.v1",
            description="Cancel the transfer session with the given id",
            input={"session_id": Field("string", description="Session id to cancel")},
            output={"session_id": Field("string", description="Session id that was cancelled")})
    def cancel_transfer_session(self, session_id):
        self.native.cancel_transfer_session(session_id)
        self._session_id = session_id
        return {"session_id": session_id}

    @action(name="x-cap.aaronslaff.cancel_active_transfer.v1", safe_state=True,
            description="Cancel the active transfer session (the safe state); it takes no input",
            output={"cancelled": Field("boolean", description="True when a tracked session was cancelled"),
                    "session_id": Field("string", description="Session that was cancelled; empty without a session")})
    def cancel_active_transfer(self):
        if not self._session_id:
            self.native.get_instrument_status()
            return {"cancelled": False, "session_id": ""}
        session_id = self._session_id
        self.native.cancel_transfer_session(session_id)
        return {"cancelled": True, "session_id": session_id}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="cancel_transfer_session")
    def stop(self):
        """Cancel the tracked session; without one, query the instrument status (the client has no global stop)."""
        if self._session_id:
            self.native.cancel_transfer_session(self._session_id)
        else:
            self.native.get_instrument_status()
