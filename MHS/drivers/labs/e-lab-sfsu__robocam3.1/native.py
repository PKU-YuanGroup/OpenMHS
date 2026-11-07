"""Hardware backend: opens the RoboCam 3.1 camera through the upstream ``robocam.camera:Camera`` class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed, and it is R1: the loader refuses the hardware backend of an
unreviewed model-written package only at R2 and R3, so this package does not claim that refusal.
The acceptance gate runs the fake backend and never imports this module or the upstream package.

Options of the backend are the constructor options of the upstream class (robocam/camera.py:113):
``resolution`` is a ``(width, height)`` pair, ``backend`` selects "playerone", "picamera2" or "cv2",
and ``device_index`` selects the device.  With no ``backend`` the upstream constructor auto-detects
PlayerOne, then Picamera2, then OpenCV (robocam/camera.py:146-153).  The upstream class opens the
camera in its constructor; no other connection step exists.
"""


def connect(resolution=(1920, 1080), backend=None, device_index=0):
    from robocam.camera import Camera

    return Camera(resolution=resolution, backend=backend, device_index=device_index)
