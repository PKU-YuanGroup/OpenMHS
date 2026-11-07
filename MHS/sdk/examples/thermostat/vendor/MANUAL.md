# TH-1 tutorial thermostat: operator manual (synthetic)

This manual belongs to the OpenMHS tutorial driver. The TH-1 is not a real
product; the manual exists so that the acceptance gate can check the
provenance references of the tutorial (gate G4) against it.

## Ratings

- Setpoint range: 5 to 80 Cel. The controller rejects other values.
- Zone trim: see the SDK (thermo/controller.py), front and back zones.
- Fan: the speed range depends on the installed fan; the operator sets it.

## Emergency stop

The red EMERGENCY OFF switch on the front panel cuts heater power in
hardware, independently of the controller (latching; turn to release).
The SDK call emergency_off() does the same in software.

## Safe state

Heater off, fan at idle. heater_off() reaches it.
