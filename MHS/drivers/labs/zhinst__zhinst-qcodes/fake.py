"""Fake backend of the PQSC driver: a source-shaped stand-in for the QCoDeS PQSC class.

Gate G7: every public method and property here exists on the upstream
``zhinst.qcodes.driver.devices.pqsc:PQSC`` class or on its in-clone base
``ZIBaseInstrument``.  State lives in private attributes.  The values are canned
test data chosen for the gate, not facts about a PQSC; each is marked ``# placeholder``.

The firmware placeholder is an integer because get_idn() returns the system/fwrevision node value
(base.py:48-55), whose type the clone does not show for a device (its test node documentation types
/zi/about/fwrevision as Integer (64 bit), tests/data/nodedoc_zi.json:41-47); the driver reads it as text (model review).

Fidelity gaps: this is an analytic stand-in, not a recording.  It does not open a
LabOne session, does not read the node tree, does not model ZSync ports, trigger
counts, hold-off timing, feedback processing or the real reference-clock lock, and
``wait_done`` returns immediately instead of waiting for a trigger sequence.  A first
supervised hardware run must verify the identity, the streaming-node list, the
reference-clock state and the arm/run/stop sequence against the instrument.
"""


class FakePQSC:
    def __init__(self, **_options):
        self._idn = {                                          # placeholder identity
            "vendor": "Zurich Instruments",                    # placeholder
            "model": "PQSC",                                   # placeholder
            "serial": "dev0000",                               # placeholder
            "firmware": 0,                                     # placeholder: an integer node value
        }
        self._serial = "dev0000"                               # placeholder
        self._device_type = "PQSC"                             # placeholder
        self._streaming_nodes = ["/dev0000/demods/0/sample"]   # placeholder node path
        self._ref_clock_locked = True                          # placeholder state
        self._armed = False
        self._running = False
        self._reset_count = 0
        self._stops = 0
        self._calls = []

    @property
    def serial(self):
        return self._serial

    @property
    def device_type(self):
        return self._device_type

    def get_idn(self):
        return dict(self._idn)

    def get_streamingnodes(self):
        return list(self._streaming_nodes)

    def check_ref_clock(self, *, timeout=30.0, sleep_time=1.0):
        return self._ref_clock_locked

    def arm(self, *, deep=True, repetitions=None, holdoff=None):
        self._armed = True
        self._running = False
        self._calls.append(("arm", deep, repetitions, holdoff))

    def arm_and_run(self, *, repetitions=None, holdoff=None):
        self._armed = True
        self._running = True
        self._calls.append(("arm_and_run", repetitions, holdoff))

    def run(self, *, deep=True):
        self._running = True
        self._calls.append(("run", deep))

    def stop(self, *, deep=True):
        self._running = False
        self._armed = False
        self._stops += 1
        self._calls.append(("stop", deep))

    def wait_done(self, *, timeout=10.0, sleep_time=0.005):
        # placeholder: the fake has no trigger sequence to wait for
        self._calls.append(("wait_done", timeout, sleep_time))

    def factory_reset(self, deep=True):
        self._armed = False
        self._running = False
        self._reset_count += 1
        self._calls.append(("factory_reset", deep))
