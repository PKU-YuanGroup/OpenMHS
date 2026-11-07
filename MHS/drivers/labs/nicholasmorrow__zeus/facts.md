# Facts and tags for gh.nicholasmorrow/zeus

Every fact cites its source at commit `d2f5dbc1bc4fa80e930af49b3701ba5a1e0ed5fc`: `vendor_doc` (a text file of the
clone such as `README`) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| ZeusModule is the user-facing driver class for one ZEUS module | upstream_code | zeus.py:287 |
| The constructor accepts a module id in the range 1 to 31 and opens the CAN bus before initializing the Z-drive and the dosing drive | upstream_code | zeus.py:334-356 |
| initCANBus selects the socketcan_ctypes interface on channel can0 | upstream_code | zeus.py:506-511 |
| The README initializes can_bus through an 8-devices USB2CAN interface with ./init_can.sh | vendor_doc | README:1 |
| sendCommand splits a command into 7-byte chunks and sends each chunk with sendDataObject | upstream_code | zeus.py:481-495 |
| The constructor sets pos to 0, minZPosition to 0 and maxZPosition to 1800 | upstream_code | zeus.py:347-349 |
| initZDrive sets pos to maxZPosition before sending the ZI command | upstream_code | zeus.py:521-526 |
| moveZDrive builds a GZ command with the four-digit gy position and the gw speed code, and accepts only slow or fast | upstream_code | zeus.py:528-549 |
| pickUpTip builds a GT command with tt and go, and discardTip builds a GU command with go | upstream_code | zeus.py:551-561 |
| aspiration builds a GA command with the five-digit ai volume, ge, go and lq table indices and the optional mixing fields | upstream_code | zeus.py:567-583 |
| dispensing builds a GD command with the four-digit di volume, ge, go, lq and zm fields and the optional mixing fields | upstream_code | zeus.py:585-602 |
| switchOff sends the AV command | upstream_code | zeus.py:604-606 |
| setEmergencyStop builds the AB command for an on state; the off branch references the undefined name seld, so this driver never sends the off command | upstream_code | zeus.py:682-687 |
| Error code 36 means "Emergency stop is active or was sent during action" | upstream_code | zeus.py:297 |
| Error codes 53, 54 and 55 report a maximum tip volume, a maximum pipetting-drive volume and a failed volume check | upstream_code | zeus.py:304-306 |
| The clone's demo constructs ZeusModule(1) | upstream_code | tests/demo.py:5 |

Limits:

- `position` on `x-cap.nicholasmorrow.move_z.v1` is `Limit.operator_required`: the clone validates against the
  constructor attributes `minZPosition`/`maxZPosition` (`zeus.py:348-349`), which are defaults, not a stated device
  bound.
- `volume` on the aspirate and dispense actions is `Limit.operator_required`: the clone states no volume range or
  unit, and the fixed-width `ai`/`di` fields (`zeus.py:572`, `zeus.py:590`) are a command-format width, not a safety
  bound.
- `container_geometry`, `deck_geometry`, `liquid_class` and `tip_type` are `Limit.operator_required`: the clone
  states no range for a geometry, liquid-class or tip-type table index; the operator supplies the indices configured
  on the unit.
- The z-drive `speed` is the enum `slow`/`fast`, the only values `moveZDrive` accepts (`zeus.py:535-543`).

Safety: the native stop is the AB emergency-stop command (`setEmergencyStop(1)`, `zeus.py:682-687`). It is both the
`@estop` method and the safe-state action `x-cap.nicholasmorrow.emergency_stop.v1`. The clone does not document an
independent physical e-stop, so `estop_physical_ref` is not set. The off branch of `setEmergencyStop` is broken
upstream (it references `seld` at `zeus.py:686`), so this driver never sends AW.

`native.py` notes that the upstream `setup.py` and `requirements.txt` are empty and that python-can and a configured
SocketCAN interface are operator prerequisites.

Tags: liquid-handling, pipetting, can, socketcan, zeus
