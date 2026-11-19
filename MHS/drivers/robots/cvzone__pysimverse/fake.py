"""Fake backend of the pysimverse drone driver: an in-memory stand-in for pysimverse.simulators.drone.drone:Drone.

Gate G7: every public member here is a method or attribute of the upstream ``Drone`` class at the pinned commit
(``simulators/drone/drone.py``), with the upstream parameter names and defaults.  The fake keeps the same state
attributes (``is_flying``, ``speed``, ``rotation_speed``, ``stream_on``) and the same command pair for each motion
method: the nonzero RC dictionary followed by a zero RC dictionary.  It records every published dictionary in
``_commands`` (a private test list) instead of sending it over ZeroMQ.

What it does not do: no ZeroMQ sockets, no state or video subscription, no flight physics, no position, battery or
video, and no wall-clock sleep.  The upstream motion methods sleep for the duration they compute and then publish a
zero command; the fake publishes the same two commands immediately.  Every number here is test data copied from the
upstream constructor or method defaults, not a fact, a limit or a safety bound.
"""


class FakeDrone:
    """The public surface of ``pysimverse.simulators.drone.drone:Drone`` that this driver uses."""

    stream_on = False

    def __init__(self, host="*", cmd_port=5550, state_port=5556, video_port=5557,
                 speed=300, rotation_speed=15):
        # placeholder: the upstream constructor defaults (drone.py:11); test data only
        self.host = host
        self.cmd_port = cmd_port
        self.state_port = state_port
        self.video_port = video_port
        self.speed = speed
        self.rotation_speed = rotation_speed
        self.is_flying = False
        self._connected = False
        self._commands = []

    def connect(self):
        """Record the native connect(); the fake opens no socket."""
        self._connected = True

    def shutdown(self):
        """Record the native shutdown(); the fake closes no socket."""
        self._connected = False

    def is_port_available(port):
        """The upstream method has no self parameter; the fake keeps that shape and reports a free port."""
        return True

    def send_rc_control(self, left_right, forward_backward, up_down, yaw, camera_angle=0, streamon=None,
                        red=None, green=None, blue=None):
        """Record the JSON object the upstream publishes (drone.py:78-91); no ZMQ traffic is sent."""
        self._commands.append({
            "left_right": left_right,
            "forward_backward": forward_backward,
            "up_down": up_down,
            "yaw": yaw,
            "cameraangle": camera_angle,
            "streamon": streamon,
            "color": {"red": red, "green": green, "blue": blue},
        })

    def streamon(self):
        self.stream_on = True
        self.send_rc_control(None, None, None, None, None, self.stream_on)

    def streamoff(self):
        self.stream_on = False
        self.send_rc_control(None, None, None, None, None, self.stream_on)

    def move_forward(self, distance):
        if self.is_flying:
            self.send_rc_control(0, self.speed, 0, 0, 0)
            self.send_rc_control(0, 0, 0, 0, 0)

    def move_backward(self, distance):
        if self.is_flying:
            self.send_rc_control(0, -self.speed, 0, 0, 0)
            self.send_rc_control(0, 0, 0, 0, 0)

    def move_right(self, distance):
        if self.is_flying:
            self.send_rc_control(self.speed, 0, 0, 0, 0)
            self.send_rc_control(0, 0, 0, 0, 0)

    def move_left(self, distance):
        if self.is_flying:
            self.send_rc_control(-self.speed, 0, 0, 0, 0)
            self.send_rc_control(0, 0, 0, 0, 0)

    def move_up(self, distance):
        if self.is_flying:
            self.send_rc_control(0, 0, self.speed, 0, 0)
            self.send_rc_control(0, 0, 0, 0, 0)

    def move_down(self, distance):
        if self.is_flying:
            self.send_rc_control(0, 0, -self.speed, 0, 0)
            self.send_rc_control(0, 0, 0, 0, 0)

    def take_off(self, takeoff_height=200, takeoff_speed=200):
        # placeholder: the upstream defaults (drone.py:220); test data only
        if not self.is_flying:
            self.is_flying = True
            self.send_rc_control(0, 0, takeoff_speed, 0, 0)
            self.send_rc_control(0, 0, 0, 0, 0)

    def land(self, landing_speed=100):
        # placeholder: the upstream default (drone.py:231); test data only
        if self.is_flying:
            self.send_rc_control(0, 0, -landing_speed, 0, 0)
            self.send_rc_control(0, 0, 0, 0, 0)
            self.is_flying = False

    def rotate(self, angle):
        if self.is_flying:
            if angle < 0:
                self.send_rc_control(0, 0, 0, -self.rotation_speed / 70, 0)
            else:
                self.send_rc_control(0, 0, 0, self.rotation_speed / 70, 0)
            self.send_rc_control(0, 0, 0, 0, 0)

    def rotate_camera(self, angle):
        if self.is_flying:
            self.send_rc_control(0, 0, 0, 0, angle)
            self.send_rc_control(0, 0, 0, 0, 0)

    def set_speed(self, speed):
        self.speed = speed

    def set_rotation_speed(self, rotation_speed):
        self.rotation_speed = rotation_speed
