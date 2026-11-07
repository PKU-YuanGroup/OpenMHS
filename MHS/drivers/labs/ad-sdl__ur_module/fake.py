"""Analytic in-memory fake of ``ur_interface.ur:UR`` for the OpenMHS acceptance gate.

This is not a recording and not the upstream simulator (the clone ships no simulator).  It keeps the native object
shape the driver uses: ``get_movement_state()`` returns the ``(state, joints)`` tuple of
src/ur_interface/ur.py:189-210, ``home(home_location, linear_motion=False)`` is the blocking move of
src/ur_interface/ur.py:212-230 and raises ``URMovementError`` when the move fails, and ``ur_dashboard`` is a child
object with the dashboard getters and commands the driver reaches.  ``get_robot_mode`` and ``get_safety_status``
return the parsed second word, as upstream (src/ur_interface/ur_dashboard.py:136-149, 222-237); the other getters
return the raw answer.

Dashboard answers.  Upstream, ``send_command`` returns None after any socket error (ur_dashboard.py:58-87); the fake
answers None to every command named in ``silent``, and the two parsing getters then raise AttributeError as the
upstream's ``split`` of None does.  ``answers`` replaces the answer to a command (for example the manual's failure
text 'Failed to execute: stop').  The default answers ('Powering off', 'Stopped', 'Pausing program', 'Brake
releasing') are the success texts of the vendor manual in the clone (resources/DashboardServer_e-Series.pdf, pages
6 and 8), which G4 cannot read; what the dashboard answers to 'pause' or 'stop' when no program plays is not stated
in the clone, and the fake answers the success text.  ``ignore_power_off`` keeps the robot mode RUNNING after
'power off' (the manual lists 'power off' as a remote-control command, so a robot in local control would not obey).

Not modelled: the upstream's sleeps (3 s in the constructor, 20 s after 'brake release'), the socket protocol, the
controller's mode transitions (the mode changes at once), what 'power off' does to a playing program, and URX: the
fake refuses a move unless the robot mode is RUNNING, where upstream URX would fail the movej and ``UR.home`` would
raise URMovementError.  The joint check is exact equality, which stands in for the upstream's norm threshold because
the fake's joints change only by a move.

Every number below is test data, marked ``# placeholder``; no value here is copied into a Fact, a Limit or the
reference.  The fake never talks to a device and completes instantly, so its timing is F0 and its evidence is
contract-checked only.  The real URX/dashboard path was never run.
"""


class URMovementError(Exception):
    """Stand-in for ``ur_interface.ur_error_types.URMovementError`` (src/ur_interface/ur_error_types.py:10-13)."""


class _FakeDashboard:
    """The ``UR.ur_dashboard`` child, limited to the methods this driver calls."""

    def __init__(self):
        self.robot_mode = "RUNNING"                # fake initial state, not a device fact
        self.safety_status = "NORMAL"              # fake initial state, not a device fact
        self.operational_mode = "AUTOMATIC"        # fake initial state, not a device fact
        self.program_state = "STOPPED"             # fake initial state, not a device fact
        self.loaded_program = "No program loaded"  # fake initial state, not a device fact
        self.program_run_status = "Program running: false"  # fake initial state, not a device fact
        self.remote_control = "true"               # fake initial state, not a device fact
        self.silent = set()                        # commands answered None, as send_command after a socket error
        self.answers = {}                          # command -> replacement answer
        self.ignore_power_off = False              # keep RUNNING after 'power off'
        self.sent = []                             # every dashboard command, in order

    def _answer(self, command, text):
        self.sent.append(command)
        if command in self.silent:
            return None
        return self.answers.get(command, text)

    def _word(self, command, value):
        answer = self._answer(command, value)
        if answer is None:
            raise AttributeError("'NoneType' object has no attribute 'split'")
        return answer

    def get_robot_mode(self):
        return self._word("robotmode", self.robot_mode)

    def get_safety_status(self):
        return self._word("safetystatus", self.safety_status)

    def get_operational_mode(self):
        return self._answer("get operational mode", self.operational_mode)

    def get_program_state(self):
        return self._answer("programState", self.program_state)

    def get_loaded_program(self):
        return self._answer("get loaded program", self.loaded_program)

    def get_program_run_status(self):
        return self._answer("running", self.program_run_status)

    def is_in_remote_control(self):
        return self._answer("is in remote control", self.remote_control)

    def pause_program(self):
        answer = self._answer("pause", "Pausing program")
        if answer == "Pausing program" and self.program_state == "PLAYING":
            self.program_state = "PAUSED"
            self.program_run_status = "Program running: false"
        return answer

    def stop_program(self):
        answer = self._answer("stop", "Stopped")
        if answer == "Stopped":
            self.program_state = "STOPPED"
            self.program_run_status = "Program running: false"
        return answer

    def power_off(self):
        answer = self._answer("power off", "Powering off")
        if answer is not None and not self.ignore_power_off:
            self.robot_mode = "POWER_OFF"
        return answer

    def brake_release(self):
        answer = self._answer("brake release", "Brake releasing")
        if (answer == "Brake releasing" and self.safety_status == "NORMAL"
                and self.robot_mode in ("POWER_OFF", "BOOTING", "POWER_ON", "IDLE")):
            self.robot_mode = "RUNNING"
        return answer


class FakeUrModule:
    """Stand-in for ``ur_interface.ur:UR``; only the public members the driver resolves are defined here."""

    def __init__(self, **_options):
        self.ur_dashboard = _FakeDashboard()
        # placeholder: six zero joint values for the test arm
        self._joints = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self._last_joints = None
        self.fail_moves = False                    # makes a move fail as a failed URX movej would

    def get_movement_state(self):
        current = list(self._joints)
        if self._last_joints is None or current == self._last_joints:
            state = "READY"
        else:
            state = "BUSY"
        self._last_joints = current
        return state, current

    def home(self, home_location, linear_motion=False):
        values = [float(item) for item in home_location]
        if self.fail_moves or self.ur_dashboard.robot_mode != "RUNNING" or len(values) != len(self._joints):
            raise URMovementError("Failed to home the robot")
        self._joints = values
        return None
