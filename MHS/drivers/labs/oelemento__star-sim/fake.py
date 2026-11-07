"""Fake backend of StarSim: a stand-in for star_sim.env:RobotEnv (star_sim/env.py:32-96) without PyLabRobot.

``RobotEnv.setup()`` builds the STARlet deck of ``star_sim/deck.py`` and a PyLabRobot ``LiquidHandler`` over the
ChatterBox backend with tip and volume tracking switched on (star_sim/lab.py:35-49), then awaits ``lh.setup()``;
``teardown()`` awaits ``lh.stop()`` (star_sim/env.py:59-69).  This fake keeps that shape: ``setup`` and ``teardown``
are the only public methods (both exist on RobotEnv, gate G7), ``lh`` is the SDK's deterministic model of the
PyLabRobot front end (``mhs.testing.pylabrobot``), and ``tips`` stands in for the upstream TipManager's
``remaining`` count (star_sim/tip_manager.py:33-42).

The deck names are the upstream's (``tip_rack``, ``source_plate``, ``dest_plate``, star_sim/deck.py:46-53).  Every
number below is test data, not a fact: the upstream deck starts with empty plates and its agent seeds tracked
volumes with ``propose_prime`` (agent.py:828-833); this fake starts with liquid in every source well so that a
stateless gate case can complete a transfer.
"""

from mhs.testing.pylabrobot import FakeDeck, FakeLiquidHandler, FakePlate, FakeTipRack, well_names

ROWS, COLUMNS = 8, 12  # placeholder: a 96-position plate and tip rack
TIP_VOLUME_UL = 1000.0  # placeholder: capacity of one fake tip
WELL_VOLUME_UL = 2000.0  # placeholder: capacity of one fake deep well
SEED_VOLUME_UL = 1500.0  # placeholder: starting tracked liquid of every source well


class _FakeTipManager:
    """``remaining``: full tip columns from the cursor on, as star_sim/tip_manager.py:33-42 counts them."""

    def __init__(self, rack):
        self._rack = rack
        self._cursor = 0

    @property
    def remaining(self):
        rows = "ABCDEFGH"[:ROWS]
        return sum(1 for column in range(self._cursor + 1, COLUMNS + 1)
                   if all(self._rack.get_item(f"{row}{column}").tracker.has_tip for row in rows))


class FakeRobotEnv:
    def __init__(self, use_hardware: bool = False, num_channels: int = 8):
        if use_hardware:
            raise ValueError("the fake models the simulated twin only; it never drives a STAR")
        self._use_hardware = False
        self._num_channels = num_channels
        self._movement_listeners = []

    async def setup(self):
        rack = FakeTipRack("tip_rack", rows=ROWS, columns=COLUMNS, tip_volume=TIP_VOLUME_UL)
        source = FakePlate("source_plate", rows=ROWS, columns=COLUMNS, max_volume=WELL_VOLUME_UL,
                           volumes={well: SEED_VOLUME_UL for well in well_names(ROWS, COLUMNS)})
        dest = FakePlate("dest_plate", rows=ROWS, columns=COLUMNS, max_volume=WELL_VOLUME_UL)
        self.lh = FakeLiquidHandler(FakeDeck([rack, source, dest]), num_channels=self._num_channels)
        self.tips = _FakeTipManager(rack)
        await self.lh.setup()

    async def teardown(self):
        await self.lh.stop()
