"""Fake backend of the OT-2 driver: an in-memory stand-in for ot2_api:OpentronsAPI.

Gate G7: every public method defined here exists on ``ot2_api:OpentronsAPI`` (ot2_api.py), and the public attributes
the driver reaches (``run_id``, ``pipette_id``, ``labware_dct``) are assigned by the upstream __init__
(ot2_api.py:88-91).  The starting positions and canned replies are test data only; each is marked ``# placeholder``
and none is a Fact or a Limit.  The fake keeps no HTTP connection and never talks to a robot.
"""


class FakeOpentronsAPI:
    def __init__(self, **_options):
        self.run_id = None
        self.pipette_id = None
        self.labware_dct = {str(i): None for i in range(1, 12)}
        self._runs = []
        self._run_status = "idle"          # placeholder
        self._run_action = None
        self._aspirated = 0.0
        self._dispensed = 0.0
        self._homed = False

    def health(self, timeout: float = 5.0) -> dict:
        return {"name": "fake OT-2",           # placeholder
                "api_version": "0.0.0-fake",   # placeholder
                "robot_model": "OT-2 fake"}    # placeholder

    def create_run(self, protocol_id: str = None, verbose: bool = True) -> dict:
        self.run_id = f"run-{len(self._runs) + 1}"    # placeholder
        self._run_status = "created"                  # placeholder
        self._runs.append({"id": self.run_id, "current": True, "status": self._run_status,
                           "pipettes": [], "labware": []})
        return {"data": {"id": self.run_id}}

    def get_run_info(self) -> list:
        return list(self._runs)

    def home_robot(self, verbose: bool = True) -> dict:
        self._homed = True
        return {"data": {"status": "succeeded"}}      # placeholder

    def load_pipette(self, mount: str = "left", verbose: bool = True) -> dict:
        self.pipette_id = f"pipette-{mount}"          # placeholder
        return {"data": {"status": "succeeded", "result": {"pipetteId": self.pipette_id}}}

    def load_labware(self, labware_api_name: str, slot_name: int,
                     namespace: str = "opentrons", verbose: bool = True) -> dict:
        labware_id = f"labware-{slot_name}"           # placeholder
        self.labware_dct[str(slot_name)] = labware_id
        return {"data": {"status": "succeeded", "result": {"labwareId": labware_id}}}

    def aspirate(self, labware_id: str, well_name: str, well_location: str = "top",
                 offset: tuple = (0, 0, 0), volume_offset: int = 0, volume: int = 25,
                 flow_rate: int = 25, verbose: bool = False) -> dict:
        self._aspirated += float(volume)
        return {"data": {"status": "succeeded"}}      # placeholder

    def dispense(self, labware_id: str, well_name: str, well_location: str = "top",
                 offset: tuple = (0, 0, 0), volume_offset: int = 0, volume: int = 25,
                 flow_rate: int = 25, pushout: int = 0, verbose: bool = False) -> dict:
        self._dispensed += float(volume)
        return {"data": {"status": "succeeded"}}      # placeholder

    def control_run(self, action: str) -> dict:
        if action not in ("play", "pause", "stop", "resume-from-recovery"):
            raise ValueError(f"Invalid action argument: {action}")
        self._run_action = action
        if action == "stop":
            self._run_status = "stopped"              # placeholder
        return {"data": {"actionType": action}}
