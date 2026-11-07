"""Hardware backend factory for the LI-COR Odyssey Classic driver.

This module is imported only when the hardware backend is opened.  It imports the pinned upstream transport
(``plr_v4.odyssey.connection:OdysseyDriver``) and adapts the plain configuration mapping the driver sends to the
upstream ``ScanParameters`` dataclass.  The adapter keeps the upstream method names the driver calls and bounds the
status-page Stop request to two seconds, so an unreachable instrument cannot make an e-stop wait for the transport's
default sixty-second timeout.  The gate never imports this module and no hardware was attached while it was written.

Deployment requirements: the upstream package (and its ``pylabrobot`` dependency) must be installed, the instrument
must be reachable at ``host`` or ``ODYSSEY_HOST``, and ``ODYSSEY_USER`` / ``ODYSSEY_PASS`` must hold the Basic Auth
credentials.  These are deployment facts, not device facts.
"""

from __future__ import annotations

import asyncio

from plr_v4.odyssey.connection import OdysseyDriver, ScanParameters

#: Bound of the status-page Stop POST used by the e-stop and safe-state action.
STOP_TIMEOUT_S = 2.0


class _HardwareOdyssey:
    """Adapt the plain driver surface to the pinned upstream ``OdysseyDriver``."""

    def __init__(self, driver: OdysseyDriver) -> None:
        self._driver = driver

    async def setup(self) -> None:
        await self._driver.setup()

    async def stop(self) -> None:
        await self._driver.stop()

    async def configure_scan(self, params: dict) -> str:
        return await self._driver.configure_scan(ScanParameters(**params))

    async def wait_initialization(self, scan_name: str, group: str) -> None:
        await self._driver.wait_initialization(scan_name, group)

    async def start_scan(self) -> str:
        return await self._driver.start_scan()

    async def pause_scan(self) -> str:
        return await self._driver.pause_scan()

    async def stop_scan(self) -> str:
        return await self._driver.stop_scan()

    async def cancel_scan(self) -> str:
        return await self._driver.cancel_scan()

    async def get_status(self) -> dict:
        return await self._driver.get_status()

    async def stop_from_status(self) -> str:
        return await asyncio.wait_for(self._driver.stop_from_status(), timeout=STOP_TIMEOUT_S)

    async def get_jpeg_preview(self, group: str, scan_name: str, contrast_700: int = 5, contrast_800: int = 5,
                               channels: str = "700 800", background: str = "black") -> bytes:
        return await self._driver.get_jpeg_preview(
            group, scan_name,
            contrast_700=contrast_700,
            contrast_800=contrast_800,
            channels=channels,
            background=background,
        )

    async def get_instrument_info(self) -> str:
        return await self._driver.get_instrument_info()


def connect(**options) -> _HardwareOdyssey:
    """Open the pinned upstream transport from deployment options and environment credentials."""
    host = options.get("host")
    port = int(options.get("port", 80))
    timeout = float(options.get("timeout", 60.0))
    group = str(options.get("group", "odyssey"))
    driver = OdysseyDriver.from_env(host=host, port=port, timeout=timeout, group=group)
    return _HardwareOdyssey(driver)
