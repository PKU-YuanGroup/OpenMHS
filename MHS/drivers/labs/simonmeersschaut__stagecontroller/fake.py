"""Fake backend of the StageController driver: a transcript-like recorder of the commands the driver sends.

The upstream class ``stage.Serial`` has one public method, ``send`` (stage.py:73-76); the fake implements that
method only.  ``send`` records the command in ``sent`` (test data, marked ``# placeholder``) and returns an empty
reply, as if the controller answered with an empty frame.  The fake does not open a serial port and never imports
the upstream clone.
"""


class FakeStage:
    def __init__(self, **_options):
        self.sent = []  # placeholder: commands recorded during the gate, not device facts

    def send(self, msg):
        self.sent.append(msg)  # placeholder: the fake keeps the command for the package tests
        return b""  # placeholder: the fake's empty reply, not a device fact
