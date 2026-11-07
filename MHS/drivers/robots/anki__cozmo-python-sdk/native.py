"""Hardware backend: connects to the Cozmo engine and returns its Robot.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is model-authored
and unreviewed: the loader refuses the hardware backend of an unreviewed model-written package at R2 and R3
only, so an operator can still open this R1 package with allow_hardware.  The acceptance gate runs the fake
backend and never imports this module or the cozmo package.  Nothing here was ever run.

The SDK is asyncio: ``cozmo.run.connect_on_loop`` opens the connection on a loop the caller provides
(cozmo/run.py:526-560) and ``CozmoConnection.wait_for_robot`` returns the ready Robot (cozmo/conn.py:469-488).
The connection has to keep running, so this factory runs the loop forever on a daemon thread and returns a
small proxy: the five reads are forwarded as plain property reads (the Robot updates them from messages), and
the three commands run on the SDK loop thread through ``call_soon_threadsafe``, because the SDK's transport is
not safe to write from another thread.

Options: ``serial`` picks an iOS device by serial number (cozmo/run.py:126-129), or ``ip_addr`` (with
``tcp_port``, default from the SDK) connects to a Cozmo engine over TCP (cozmo/run.py:303-311); with neither,
the SDK's own FirstAvailableConnector is used (cozmo/run.py:348-400).
"""

import asyncio
import threading


class _RobotOnLoop:
    """The Robot with its commands dispatched on the SDK's event loop thread; reads are plain properties."""

    def __init__(self, robot, loop):
        self._robot = robot
        self._loop = loop

    def _dispatch(self, name, *args, **kwargs):
        done = threading.Event()
        outcome = {}

        def call():
            try:
                outcome["value"] = getattr(self._robot, name)(*args, **kwargs)
            except BaseException as exc:  # noqa: BLE001 - re-raised on the caller's thread
                outcome["error"] = exc
            finally:
                done.set()

        self._loop.call_soon_threadsafe(call)
        if not done.wait(10.0):
            raise TimeoutError(f"the Cozmo SDK loop did not run {name} within 10 s")
        if "error" in outcome:
            raise outcome["error"]
        return outcome["value"]

    # -- commands the driver sends (the native methods of Robot) ------------------------------------------------
    def set_head_angle(self, angle, **kwargs):
        return self._dispatch("set_head_angle", angle, **kwargs)

    def set_lift_height(self, height, **kwargs):
        return self._dispatch("set_lift_height", height, **kwargs)

    def stop_all_motors(self):
        return self._dispatch("stop_all_motors")

    # -- state the driver reads (Robot properties) --------------------------------------------------------------
    @property
    def head_angle(self):
        return self._robot.head_angle

    @property
    def lift_height(self):
        return self._robot.lift_height

    @property
    def lift_ratio(self):
        return self._robot.lift_ratio

    @property
    def is_charging(self):
        return self._robot.is_charging

    @property
    def is_cliff_detected(self):
        return self._robot.is_cliff_detected


def connect(serial=None, ip_addr=None, tcp_port=None, **options):
    import cozmo.run

    connector = None
    if ip_addr is not None:
        connector = cozmo.run.TCPConnector(ip_addr=ip_addr) if tcp_port is None \
            else cozmo.run.TCPConnector(ip_addr=ip_addr, tcp_port=tcp_port)
    elif serial is not None:
        connector = cozmo.run.IOSConnector(serial=serial)

    loop = asyncio.new_event_loop()
    cozmo_connection = cozmo.run.connect_on_loop(loop, connector=connector)
    robot = loop.run_until_complete(cozmo_connection.wait_for_robot())
    threading.Thread(target=loop.run_forever, name="cozmo-sdk-loop", daemon=True).start()
    return _RobotOnLoop(robot, loop)
