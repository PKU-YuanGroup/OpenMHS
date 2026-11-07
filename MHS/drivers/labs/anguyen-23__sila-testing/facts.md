OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and scope for gh.anguyen-23/sila-testing (PhenixImager feature)

Every fact cites the pinned clone `labs/anguyen-23/sila-testing` at commit `0b572380e06977c1920510773b4bfee7bcd0eec5`.
Gate G7 reads the three primary files at their exact SHA-256 (`declarations.py`): the FDL
`servers/phenix_imager/PhenixImager.sila.xml`, the generated proto and the implementation
`servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The PhenixImager feature controls a PerkinElmer Opera Phenix high-content screening imager through its RCI (Remote Control Interface) protocol. | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:12-18 |
| Stop is an unobservable command that stops the currently running acquisition protocol. | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:103-114 |
| GoStandby takes DurationSeconds, an Integer with MinimalInclusive 60. | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:136-147 |
| RunAcquisitionProtocol is observable; TimeoutMinutes is an Integer from 1 to 1440 (default 600 in its description) and ProgressInfo is its intermediate response. | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:159-212 |
| DeviceState is a String property: Operate, Idle, Standby, Offline or Service. | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:226-232 |
| StagePosition is a String property: Transfer, Operate, Service or Home. | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:234-240 |
| StageMotionTimeout means that stage movement did not complete within 2 minutes. | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:309-315 |
| PhenixImagerImpl starts with _simulation_mode set to True. | upstream_code | servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py:66 |
| In real mode, get_DeviceState returns the device_state name of the transport status, or Offline when there is no status. | upstream_code | servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py:158-162 |
| The RCI receive callback stores the status of every PROGRESS and STATUS reply in _status. | upstream_code | servers/phenix_imager/phenix_imager/rci_transport.py:287-301 |
| _require_connected raises NotConnected when the instrument is not connected. | upstream_code | servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py:78-85 |
| Disconnect requires only a connection; in simulation mode it clears the connection, sets Offline and empties the protocol list. | upstream_code | servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py:207-215 |
| Stop first requires a connection; in real mode it then calls the transport send_stop without an argument and returns. | upstream_code | servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py:263-273 |
| send_stop sends the RCI STOP command with a barcode that defaults to an empty string. | upstream_code | servers/phenix_imager/phenix_imager/rci_transport.py:241-243 |
| _send_command waits up to COMMAND_RESPONSE_TIMEOUT_S for a response and raises TimeoutError when none arrives. | upstream_code | servers/phenix_imager/phenix_imager/rci_transport.py:261-276 |
| _send_command_expect_ack checks only whether the reply is a REJECT; any other reply passes. | upstream_code | servers/phenix_imager/phenix_imager/rci_transport.py:278-285 |
| A real acquisition waits for a completion event that only a progress of 100 or more sets, for up to TimeoutMinutes, and sends EJECT only afterwards. | upstream_code | servers/phenix_imager/phenix_imager/feature_implementations/pheniximager_impl.py:401-435 |
| The transport reaches the instrument on port 8213 and listens for callbacks on port 8300. | upstream_code | servers/phenix_imager/phenix_imager/rci_transport.py:26-27 |
| COMMAND_RESPONSE_TIMEOUT_S is 20.0 and STAGE_MOTION_TIMEOUT_S is 120.0. | upstream_code | servers/phenix_imager/phenix_imager/rci_transport.py:32-33 |
| connect creates the COM object RCI_DEVICELib.RCIDeviceClass through comtypes.client. | upstream_code | servers/phenix_imager/phenix_imager/rci_transport.py:175-178 |
| The phenix_imager server is the PerkinElmer Opera Phenix RCI wrapper (comtypes) on port 50058. | vendor_doc | README.md:48 |
| All servers start in simulation mode by default; the SimulationController feature switches to real mode. | vendor_doc | README.md:72 |

## Limits

| input | bound | source | ref |
|---|---|---|---|
| `PhenixHost` (Connect), `PlateBarcode` (StageIn, StageOut, RunAcquisitionProtocol), `ProtocolName`, `DurationSeconds`, `TimeoutMinutes` | `Limit.operator_required` on every input of every effectful command | none | Sila2Driver requires an operator envelope on each effect input; no source states a deployable host, plate, protocol or duration |
| `DurationSeconds` | at least 60 s (FDL protocol constraint, checked by the declaration) | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:144 |
| `TimeoutMinutes` | 1 to 1440 min (FDL protocol constraint, checked by the declaration) | upstream_code | servers/phenix_imager/PhenixImager.sila.xml:189-190 |

The two FDL constraints are protocol bounds of the feature, not optical, stage, thermal or deployment limits; the
operator overlay must narrow them. String inputs carry the SDK's finite allocation bound (4,096 bytes), which is not a
source fact. `site-limits.example.json` is an example overlay that allows the fake's placeholder host, plate, protocol
and durations; it is not a deployable Phenix configuration.

## Risk

R2, the minimum Sila2Driver accepts and the level the hazard table (MHS/spec/04-safety.md, section 2.1) gives an
automated imager with a motorized plate stage that a robot loads (FDL lines 65-66 and 86-87). The Opera Phenix is a
confocal fluorescence instrument (pheniximager_impl.py:111); the clone does not state its laser class. A human
reviewer must confirm the class of the installed light sources and raise the package to R3 if any is 3B or higher
outside a class 1 enclosure.

## Scope

Served: the complete PhenixImager feature, eight commands and seven properties, as nine extension capabilities
(`x-cap.anguyen-23.<member>.v1`, eight commands plus the DisplayIcon artifact), six property reads and four local
diagnostic reads of the last known acquisition execution (whether a confirmation is known, its UUID, its progress and
the last intermediate text). The e-stop is the feature's Stop command.

NOT COVERED: the eight other servers of the repository (temperature, pump, plate reader, Multidrop Combi, VENUS,
barcode scanner, Micronic tube scanner, xArm 6), the Phenix server's other features (SimulationController,
ScreenStreamer, MessagingClient and the shared features `BaseInstrumentServer` registers), the switch between
simulation and real mode, and any acquired image: the feature returns status text and progress, not image data.

## Fake

`fake.py` is the SDK's controlled peer re-targeted at this card. Its device behaviour follows the simulation branch of
`PhenixImagerImpl` where the tests touch it; its differences are stated in its docstring and in `RESULT.json` notes.
One of them matters for safety: the fake refuses every command except Stop while an acquisition runs, but the upstream
accepts them, Disconnect included (pheniximager_impl.py:207-215 checks only the connection), and Stop then raises
NotConnected (pheniximager_impl.py:78-85, 263-265). A run that another client of the server disconnected can therefore
not be stopped through the feature; `foreign_disconnect()` models that path, and a repository case shows that the e-stop
then stays unachieved and the latch holds. Through this package's own endpoint a Disconnect cannot interleave with a
running acquisition: the helper's single ordinary lane is busy, and an unconfirmed acquisition fences new effects.
Every number and string in it is a placeholder: the host `phenix-controlled.invalid`, the plate `PLATE-0001`, two
protocol names copied from the simulation list (pheniximager_impl.py:45-51) as test data, the 2 x 1 PNG icon, the
progress values and an acquisition that completes on the second progress poll. The upstream simulation images 96 wells
at 0.1 s each (pheniximager_impl.py:349-369).
