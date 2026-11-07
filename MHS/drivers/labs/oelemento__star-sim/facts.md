# Facts and tags for gh.oelemento/star-sim

Every fact cites its source at commit `5b5211a4c5414e5a9752b286515fbe87e769842d`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| star-sim is a simulated Hamilton STARlet built on PyLabRobot; the same protocol runs against a simulated robot (ChatterBox backend) or the physical Hamilton STAR | vendor_doc | README.md:3-5 |
| make_liquid_handler switches PyLabRobot tip tracking and volume tracking on before the deck is built | upstream_code | star_sim/lab.py:34-36 |
| use_hardware=False selects LiquidHandlerChatterboxBackend(num_channels=num_channels); True selects the STAR backend | upstream_code | star_sim/lab.py:40-47 |
| The deck is a STARLetDeck with one Hamilton 1000 uL filtered tip rack named tip_rack on a tip carrier | upstream_code | star_sim/deck.py:43-48 |
| Two 96-well plates named source_plate and dest_plate sit on a plate carrier | upstream_code | star_sim/deck.py:51-55 |
| RobotEnv defaults to the simulation (use_hardware False) with 8 channels | upstream_code | star_sim/env.py:33 |
| RobotEnv.setup builds the liquid handler and deck, a TipManager and a PlateMap, then awaits lh.setup() | upstream_code | star_sim/env.py:59-66 |
| RobotEnv.teardown awaits lh.stop() | upstream_code | star_sim/env.py:68-69 |
| Each primitive acquires fresh tips, performs one liquid-handling action and drops the tips before it returns | upstream_code | star_sim/primitives.py:3-5 |
| column_transfer picks up tips, aspirates, dispenses and discards the tips in a finally block | upstream_code | star_sim/primitives.py:55-67 |
| _plate_state maps each non-empty well id to its tracked used volume in microlitres | upstream_code | star_sim/env.py:101-116 |
| TipManager.remaining counts the tip columns from the cursor on that still hold every tip | upstream_code | star_sim/tip_manager.py:33-42 |
| The column_transfer agent tool takes a volume of 1 to 1000 uL per channel | upstream_code | agent.py:53 |
| The mix_column agent tool takes a volume of 1 to 1000 uL | upstream_code | agent.py:96 |
| mix_column takes 1 to 10 repetitions | upstream_code | agent.py:97 |
| propose_prime seeds the plate volume trackers with the declared volumes | upstream_code | agent.py:825-833 |
| The project was tested with pylabrobot 0.2.1 and requires pylabrobot>=0.2.1 | vendor_doc | requirements.txt:2-3 |

Profile references (checked by gate G7 against the clone): the handler `lh` (`star_sim/env.py:60`), `setup`
(`star_sim/env.py:59`), `teardown` (`star_sim/env.py:68`), 8 channels (`star_sim/env.py:33`), tip tracking
(`star_sim/lab.py:35`), volume tracking (`star_sim/lab.py:36`), the labware names (`star_sim/deck.py:47`, `:52`,
`:53`), the PyLabRobot calls of `transfer` (`star_sim/primitives.py:55-66`) and `mix`
(`star_sim/primitives.py:128-140`), and the volume-tracker read (`star_sim/env.py:113`).

Limits: the volume per channel is 1 to 1000 uL, cited per operation at the tool that performs it (`transfer`:
`column_transfer`, `agent.py:53`; `mix`: `mix_column`, `agent.py:96`), and the mix cycles 1 to 10 (`mix_column`,
`agent.py:97`). They bound the simulated twin's tool inputs; they are not a statement about a
physical STAR.

Safety: simulated only. There is no native stop: PyLabRobot `stop()` (RobotEnv.teardown) is teardown. An e-stop
latches the runtime; a running operation sends no further PyLabRobot step after it, but the step in progress is not
interrupted, so an e-stop during an operation is reported `SAFE_STATE_UNREACHED`. A step that fails with an error
other than a PyLabRobot bookkeeping error is an unknown outcome and fences the device; with no native stop only a
restart of the endpoint recovers it. After a failure or an e-stop the tips stay mounted (the upstream primitives
discard them in a `finally` block, `star_sim/primitives.py:65-66`; this package does not move after a failure), so
the next operation fails `channel_free` until the endpoint is restarted. The upstream can drive a
physical STAR (`use_hardware=True`, `star_sim/lab.py:40-43`); this package never exposes that path.

Tags: liquid-handler, pylabrobot, hamilton, starlet, digital-twin, simulation
