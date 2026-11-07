"""Hardware backend: opens an HP 89400-series analyzer through the upstream HP894xx class.

Used only with backend="hardware" and allow_hardware=True (an operator decision).  This package is
model-authored and unreviewed; the acceptance gate runs the fake backend and never imports this module or the
upstream package.  Nothing in this file ran: the hardware path was never exercised.

The upstream class HP89400Device forwards its constructor arguments to PrologixGPIBEthernetDevice
(python/HP894xx/HP89400Device.py:56-57), and its __enter__ and reset methods connect through the upstream
transport (python/HP894xx/HP89400Device.py:63-72, 78-81).  The factory therefore forwards every option to
that constructor and connects once.  The option names are those of the installed upstream transport: the
clone calls PrologixGPIBEthernet(ip, timeout) in its command-line example
(python/bin/hp_spectrum_analyzer.py:91) but does not define the device constructor's signature, so this
package does not guess a host or GPIB-address parameter here.  The upstream package and its dependencies
(plx_gpib_ethernet, numpy, timeout_decorator) must be installed by the operator; the card's install block
declares no command.
"""


def connect(**options):
    from HP894xx.HP89400Device import HP89400Device

    device = HP89400Device(**options)
    device.connect()
    return device
