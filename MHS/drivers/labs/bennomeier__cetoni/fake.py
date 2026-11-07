"""In-memory fake backend of the Cetoni syringe-pump driver.

There is no usable upstream simulator: ``cetoniSerial.FakeSyringe`` (cetoniSerial.py:472) only prints and overrides
``read``/``write`` with unrelated signatures, so this fake models the small part of ``cetoniSerial:Syringe`` the
driver touches.  Every public method here exists on the upstream class (G7).  The calibration and start values are
test data, marked ``# placeholder``; they are not facts and none is written into the driver's Facts, Limits or
references.  The motion is immediate and deterministic: reading the state twice gives the same state unless a write
or action changed it.  Nothing here talks to a device.
"""


class FakeCetoni:
    def __init__(self, **_options):
        self.volume = 1000.0                 # placeholder: uL of the modelled syringe
        self.crossSection = self.volume / 60  # placeholder: uL per mm, as the upstream constructor computes it
        self.gearFactor = 1.0                # placeholder
        self.positionConversionFactor = 6000.0  # placeholder: increments per mm
        self.maxProfileVelocity = 6000000    # placeholder: 0x607F value of the modelled drive
        self.maxVolperS = self.maxProfileVelocity * 0.001 / 60 / self.gearFactor * self.crossSection  # placeholder
        self.currentPosition = 0             # placeholder: increments
        self.targetPosition = 0              # placeholder: increments
        self.velocity = 0                    # placeholder: 0x6081 value
        self.status = 1079                   # placeholder: the ready state the upstream waitUntilReady expects
        self.physicalOutputs = 0             # placeholder: cached 0x60fe outputs
        self.enabled = True                  # placeholder
        self.closed = False                  # placeholder

    def readCurrentPosition(self):
        return self.currentPosition

    def readTargetPosition(self):
        return self.targetPosition

    def readVelocity(self):
        return self.velocity

    def readStatus(self):
        return self.status

    def writeTargetPosition(self, pos):
        self.targetPosition = int(pos)

    def setVelocity(self, velocity):
        if not 0 < velocity <= self.maxProfileVelocity:
            raise ValueError(f"velocity {velocity!r} is outside 0 < v <= {self.maxProfileVelocity}")
        self.velocity = int(velocity)

    def setFlowRate(self, flowRate):
        if not 0 <= flowRate <= self.maxVolperS:
            raise ValueError(f"flow rate {flowRate!r} is outside 0 <= q <= {self.maxVolperS}")
        mm_per_s = flowRate / self.crossSection
        rpm = mm_per_s * 60 * self.gearFactor
        self.setVelocity(int(rpm * 1000))

    def vol2increments(self, vol):
        return round((vol / self.crossSection) * self.positionConversionFactor)

    def write(self, index, subindex, numberOfWords, value, dtype="L", read=True):
        """Record the writes the driver makes; the return value is not used by this package."""
        if index == 0x6040:
            if (value & 0x0F) == 0x06:
                self.enabled = False
                self.status = 64          # placeholder: switch on disabled
            elif (value & 0x0F) == 0x0F:
                self.enabled = True
                self.status = 1079        # placeholder: operation enabled / ready
            else:
                self.status = 1079        # placeholder: any other control word leaves the drive ready
        elif index == 0x60FE:
            self.physicalOutputs = int(value)
        elif index == 0x6081:
            self.velocity = int(value)
        elif index == 0x607A:
            self.targetPosition = int(value)
        return b""

    def switchValves(self, v1, v2):
        self.physicalOutputs = self.physicalOutputs & ~((1 << 16) + (1 << 17))
        self.physicalOutputs = self.physicalOutputs | ((v1 << 16) + (v2 << 17))

    def toInput(self):
        self.switchValves(1, 0)

    def toOutput(self):
        self.switchValves(0, 1)

    def aspirate(self, volume):
        self.currentPosition -= self.vol2increments(volume)
        self.targetPosition = self.currentPosition
        self.status = 1079                # placeholder: ready after the move

    def dispense(self, volume):
        self.currentPosition += self.vol2increments(volume)
        self.targetPosition = self.currentPosition
        self.status = 1079                # placeholder: ready after the move

    def close(self):
        self.closed = True
