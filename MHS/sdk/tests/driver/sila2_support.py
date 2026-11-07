"""Original SDK controls; no SiLA runtime import, connection or device access."""
import copy
from importlib import import_module
from pathlib import Path
import time

from mhs.driver.loader import import_driver_module
from mhs.driver.sila2_config import compile_sila2
from mhs.bridge.sila2 import PeerLease, Sila2Bridge

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures' / 'sila2_phenix'
fixture = import_driver_module(FIXTURE)
PhenixPeer = import_module('.fake', fixture.__package__).PhenixPeer


def compiled(**changes):
    raw = copy.deepcopy(fixture.CONFIG)
    raw.update(changes)
    return compile_sila2(raw, fixture.Driver.commands, fixture.Driver.reads)


def bridge(test, peer=None, **changes):
    peer = PhenixPeer() if peer is None else peer
    result = Sila2Bridge(compiled(**changes), transport=PeerLease(peer=peer))
    test.addCleanup(result.close)
    return peer, result


def connect(result):
    return result.call(fixture.CAPS['Connect'], fixture.EXAMPLES['Connect'])


def until(test, condition, timeout=1):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition(): return
        time.sleep(.002)
    test.assertTrue(condition(), 'controlled owner did not settle within the test budget')
