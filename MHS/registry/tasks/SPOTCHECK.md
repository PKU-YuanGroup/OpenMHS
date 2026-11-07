# Task-card spot check (WP-10, 2026-10-21)

A reviewer read random task cards against their upstream clones and judged whether each card's `decision`
(the triage strategy, with its family and expected mode) is right. Target: at least 90% correct.

- Samples: `python3 MHS/registry/spotcheck.py --seed <seed> --n <n> [--pool dispatchable]`
  (`random.Random(seed).sample` over the sorted package ids of the pool). Samples over all cards draw the same
  ids from any registry build. A dispatchable-pool sample depends on the pool at drawing time, and each round's
  fixes changed the pool; `python3 MHS/registry/spotcheck.py --ids <package ids>` prints the cards a table names.
- Registry state: triage 0.9.3, source scan 9, 2,967 cards. Shipped decisions: `python3 MHS/registry/triage.py
  --out` sha256 `57ebcf7b954d187c72d377369259bc696e2ccf09efa7a9d93ee67c0a19282da6`. The tables of each round
  record the decisions at drawing time.
- Reviewer: the WP-10 implementation agent. For each card it opened the local clone at the pinned commit
  (`labs/` or `robots/`, read only): the README, the file tree and the source files the card names.
- Rubric. **correct**: the decision is what a reviewer would choose after reading the repo; an `untriaged`
  card (a 30-minute recon card) also counts as correct when the decisive code is not Python or the repo is
  ambiguous, and the reviewer's choice would not be a dispatchable driver task, because recon settles it
  without losing a device. **debatable**: two decisions are defensible and the card's is one of them; it counts
  as acceptable. **wrong**: a device driver is skipped or left in recon although its Python code shows a
  usable class, a non-device or a simulator is dispatched as something it is not (including a hardware mode
  for a simulator), the family or helper is wrong, or a duplicate or quarantine is missed. From round 5 on, a
  dispatchable card is also **wrong** when its typed content misdirects the author although the decision fits:
  a main MuJoCo model that is an asset or marked unsupported, or entries that are GUI widgets or plugin-registry
  steps.

## Result after the second verification (rounds 5 to 9)

| round | seed, pool | cards | correct | debatable | wrong | acceptable |
|---|---|---|---|---|---|---|
| 5 | 2034, dispatchable | 30 | 19 | 6 | 5 | 83.3% |
| 6 | 2035, dispatchable | 30 | 25 | 3 | 2 | 93.3% |
| 7 | 2036, all cards | 30 | 30 | 0 | 0 | 100.0% |
| 8 | 2037, dispatchable | 30 | 24 | 3 | 3 | 90.0% |
| 9 | 2038, dispatchable | 30 | 23 | 5 | 2 | 93.3% |
| 5-9 | | 150 | 121 | 17 | 12 | 92.0% |
| 5, 6, 8, 9 | dispatchable only | 120 | 91 | 17 | 12 | 90.0% |

**Each round drawn after the previous round's fixes (6, 8, 9) is at least 90% acceptable (93.3%, 90.0%,
93.3%). Over the 120 dispatchable cards, 108 are acceptable (90.0%) and 91 strictly correct
(75.8%); round 5, the first round after the verification, scored 83.3% and led to the largest
set of fixes.** Each wrong card was fixed after its round, by a rule when the cause was general and by a
curated override otherwise (see "Fixes after the second verification"). Strict correctness stays below 90%:
most debatable cards are lab applications that also contain drivers (copylot, PICA, openreactor), PyMoDAQ
plugins and research repos around a registered environment.

**Rubric caveat.** The 90% target holds only under the lenient rubric, which counts debatable cards as
acceptable. Strictly correct cards are 75.8% of the implementer's 120 dispatchable cards. The independent
third verification judged 32 dispatchable cards and found 23 strictly correct (71.9%).

**After the merge (triage 0.9.4, source scan 10).** These rounds were not re-drawn. The merge changed seven
decisions:
- the four julabo siblings (`tiagocoutinho/cryocon`, `gepace`, `vacuubrand`, `xia-pfcu`) became direct
  drivers by override;
- `pymodaq/pymodaq_plugins_teaching` (teaching mocks) is skipped;
- `ritalaezza/gym-agx` (AGX Dynamics engine) is a recon card;
- `papercodein/openopc-pymodbus-snap7-mqtt` is quarantined.

Fourteen repos whose code drives hardware are now hardware first. Rows below that name these repos show the
decision at drawing time. `python3 MHS/registry/triage.py --out` sha256 is now
`62d149a4eb0f6c5efba937c4fbf03157bdd48b07caa9a1a5d814c29dd8df1f92`.

The first verification rounds (1 to 4, triage 0.9.2) follow below with their verdicts at the time; a later
section lists the cards whose decisions 0.9.3 changed.

## The second verification's cards

The verification reviewed 36 dispatchable cards (24 correct, 5 debatable, 7 wrong) and named more cards
outside its sample. Status in triage 0.9.3:

| package | verdict then | decision now | how |
|---|---|---|---|
| `gh.alexshkarin/pylablib-cam-control` | wrong | reference (host) | override; rule 10 also no longer takes a GUI application's plugin class or a simulator class as its entry |
| `gh.kevinzakka/mujoco_scanned_objects` | wrong | skip (not a device) | object assets only: no loadable model with actuators, no source (rule) |
| `gh.naclab/self-revising-active-inference` | wrong | skip (peripheral) | `third_parties/` is vendored now (rule); its own ant-maze MJCF remained, so an override skips the agent code |
| `gh.openrl-lab/openrl` | wrong | untriaged | its only registration is in `examples/` (rule) |
| `gh.rhoban/onshape-to-robot` | wrong | untriaged | the scene is a template whose include is a placeholder (rule) |
| `gh.omnilink-tech/omnisim` | wrong | untriaged, wave 6 | Newton is an external engine (rule) |
| `gh.jpajaud/pyscope` | wrong | untriaged | a GUI application without a device class takes no protocol family (rule) |
| `gh.chanjin926/prompt2pose` | debatable | family-config (gymnasium) | the `@register_env` decorator registrations are entry symbols now (`envs.array_can:ArrayCanEnv` ...) |
| `gh.akperuht/pydaq` | debatable | family-config (scpi) | unchanged (debatable in round 5 too) |
| `gh.histedlab/scanimage-python-control` | debatable | direct-driver (python-object) | curated partner override, unchanged |
| `gh.google-deepmind/mujoco_mpc` | debatable | family-config (mujoco), wave 6 | main model `mjpc/tasks/fingers/task.xml`; unchanged |
| `gh.renforce-dynamics/genesislab` | debatable | family-config (gymnasium), wave 6 | Genesis (GPU); unchanged |
| `gh.kevinzakka/mink` | named outside the sample | skip (peripheral) | its MJCF files are copies under `examples/` (rule); it is no longer a first card of `families/mujoco.md` |
| `gh.simeon-ned/mink-warp` | named outside the sample | skip (peripheral) | same as mink |
| `gh.farama-foundation/minari` | named outside the sample | untriaged | its only registration is in `tests/conftest.py` (rule) |
| `gh.noietch/eva-client` | named outside the sample | skip (peripheral) | its MJCF files are vendored under `examples/` (rule) |
| `gh.huggingface/lerobot-libero` | pilot card | family-config (mujoco), wave 3 | curated partner decision kept; no model in the clone (robosuite composes it), so `needs_recon: model`, entries are its environment classes, and it left the pilot pool |
| `gh.robocasa/robocasa` | pilot card | untriaged | no loadable model in the clone; `needs_recon: artifacts` (the README's ~10 GB asset download) |
| `gh.ni/nidaqmx-python` | pilot card (minor) | direct-driver, pilot | module paths follow pyproject's package root: first entry `nidaqmx.task._task:Task` |
| `gh.hgomersall/pyzaber` | minor | family-config (serial) | first entry is the real `pyzaber.linear_slides:multiaxis_linear_slides`; the dummy is listed after it |
| `gh.feifanphys/instrumentdriver` | minor | family-config (scpi) | the `...Mock` class is no longer an entry; `KeysightN5182B` leads |
| `gh.dobot-arm/tcp-ip-python-v4` | pilot card (minor) | direct-driver, pilot | the facade's `motion` member feeds the hints: motion classes, risk floor R1 |
| `gh.jjshoots/crazyflyt` | minor | direct-driver, wave 2 | no motion class found: `needs_recon: motion`, out of the pilot pool |
| `gh.xarm-developer/xarm-python-sdk` | exemplar (minor) | direct-driver, wave 0 | `xarm.wrapper.xarm_api:XArmAPI` (the facade over XArm) leads |
| `gh.learnsyslab/crazyflow` | minor | family-config (gymnasium), wave 2 | `register(id=..., vector_entry_point=ReachPosEnv)` is resolved through the imports: four located entries (none before) |
| `gh.dennis-van-gils/dvg_arduino_lock-in_amp` | minor | direct-driver, wave 3 | its CUDA imports are in `timeit/` and `minimal_test/` scripts and a run-time import: `gpu: false` |

## Round 5 (seed 2034, dispatchable cards)

Drawn right after the second verification, before any of its fixes.

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.autolab-project/autolab` | family-config (scpi), wave 6 | **wrong** | an experiment-automation framework with a GUI; its drivers live in autolab-drivers. Now reference:host (override) |
| 2 | `gh.justagist/mujoco_panda` | family-config (mujoco) | correct | Panda MJCF and API on mujoco-py (archived); `install.system_deps` names the MuJoCo 2.1 binaries |
| 3 | `gh.jrafolsr/pyinstruments` | family-config (scpi) | correct | PyVISA instrument classes |
| 4 | `gh.opengalaxea/galaxeamanipsim` | family-config (gymnasium) | correct | registered Galaxea R1 simulation tasks |
| 5 | `gh.python-microscope/microscope` | direct-driver (driver pack) | correct | curated override |
| 6 | `gh.andmorifa/instrument-control-python` | direct-driver (python-object) | correct | Red Pitaya SCPI client over TCP |
| 7 | `gh.pymodaq/pymodaq_plugins_basler` | direct-driver (python-object) | correct | `hardware/basler.py` wraps pypylon |
| 8 | `gh.carlosferrazza/humanoid-bench` | family-config (gymnasium) | correct | MuJoCo humanoid benchmark with registered envs |
| 9 | `gh.hzaskywalker/plasticinelab` | family-config (gymnasium), wave 6 | correct | Taichi soft-body envs (GPU) |
| 10 | `gh.akperuht/pydaq` | family-config (scpi) | debatable | a GUI measurement framework whose `instrument_control.py` holds instrument classes; a direct driver would also fit |
| 11 | `gh.drmcnelson/linear-ccd-with-ltspice-kicad-firmware-and-python-library` | family-config (serial) | correct | TCD1304 controller over serial |
| 12 | `gh.rwb27/openflexure_microscope_software` | direct-driver (python-object) | correct | Microscope class on picamera and the stage |
| 13 | `gh.aaronslaff/tecan_sparkcontrol` | direct-driver (python-object) | correct | curated partner override |
| 14 | `gh.yannbouteiller/rtgym` | family-config (gymnasium) | **wrong** | a framework that clocks user-written envs; its registered ids need a user interface class. Now skip:tooling (override) |
| 15 | `gh.johnnycode8/gym_solutions` | family-config (gymnasium) | **wrong** | tutorial scripts for a YouTube course. Now skip:not-device (override) |
| 16 | `gh.duckietown/gym-duckietown` | family-config (gymnasium) | correct | pure Python/OpenGL simulator |
| 17 | `gh.google-research/football` | family-config (gymnasium) | correct | gym envs; `pip install .` builds the game engine (an id template is now parsed from `str.format`) |
| 18 | `gh.farama-foundation/highwayenv` | family-config (gymnasium) | correct |  |
| 19 | `gh.amacati/soulsgym` | family-config (gymnasium), wave 6 | debatable | gym envs that need Dark Souls III on Windows |
| 20 | `gh.czbiohub-sf/copylot` | family-config (serial) | debatable | a light-sheet microscope application with a hardware package (lasers, stages, cameras); a driver pack would also fit |
| 21 | `gh.nonejou072/robopal` | family-config (mujoco) | **wrong** | the main model was `vx300s(not_support_now)/scene.xml`. Unsupported paths are no main model now (rule); the card names DianaMed.xml |
| 22 | `gh.svengronauer/phoenix-drone-simulation` | family-config (gymnasium) | correct | PyBullet Crazyflie envs |
| 23 | `gh.adipandas/gym_multirotor` | family-config (gymnasium) | correct | MuJoCo multirotor envs (mujoco-py) |
| 24 | `gh.e-lab-sfsu/robocam3.1` | direct-driver (python-object) | correct | a desktop application whose camera and Marlin motion classes are reusable drivers |
| 25 | `gh.abrar2652/imitation-learning-aloha` | family-config (gymnasium) | debatable | an imitation-learning notebook with a modified gym-aloha copy |
| 26 | `gh.simpler-env/maniskill2_real2sim` | family-config (gymnasium) | correct | ManiSkill2 fork with registered real-to-sim envs |
| 27 | `gh.ni/nidaqmx-python` | direct-driver (python-object) | correct | entry `nidaqmx.task._task:Task` (package root from pyproject.toml) |
| 28 | `gh.pmezydlo/oscilloscope_lan_data_capture` | family-config (serial) | debatable | Rigol DS1000Z over LAN with telnetlib; SCPI would also fit |
| 29 | `gh.jr-robotics/robo-gym` | family-config (gymnasium) | **wrong** | its envs call robo-gym robot servers (ROS with Gazebo, or a real robot) over gRPC. Now untriaged, wave 6 (override) |
| 30 | `gh.knerlab/sim_control_software` | family-config (serial) | debatable | a structured-illumination microscope program with vendor DLLs; a driver pack would also fit |

## Round 6 (seed 2035, dispatchable cards)

Drawn after the round-5 fixes.

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.huggingface/gym-aloha` | family-config (gymnasium) | correct | partner override |
| 2 | `gh.dartsim/gym-dart` | family-config (gymnasium) | correct | gym envs on dartpy |
| 3 | `gh.asvela/keyoscacquire` | family-config (scpi) | correct |  |
| 4 | `gh.alrhub/d3il` | family-config (gymnasium) | correct | imitation-learning benchmark envs (mujoco-py system dependency) |
| 5 | `gh.openai/mujoco-worldgen` | family-config (mujoco) | debatable | a generator of randomized MuJoCo worlds (archived); tooling would also fit |
| 6 | `gh.umass-foundation-model/co-llm-agents` | family-config (gymnasium) | **wrong** | gym envs over ThreeDWorld and VirtualHome, both Unity builds. Now untriaged, wave 6 (rule: `tdw`, `unity_simulator` are external engines) |
| 7 | `gh.hyqshr/pybullet-gym-drones` | family-config (gymnasium) | correct |  |
| 8 | `gh.vadter/hantek6022be` | direct-driver (python-object) | correct | Hantek 6022BE over pyusb |
| 9 | `gh.sanket7941/pyinstrument` | family-config (scpi) | correct |  |
| 10 | `gh.scopefoundry/hw_picam` | direct-driver (python-object) | correct | PICAM ctypes wrapper with a ScopeFoundry component |
| 11 | `gh.benpruitt/tecancavro` | family-config (serial) | correct | partner override |
| 12 | `gh.kscalelabs/kbot` | family-config (mujoco) | correct | K-Bot MJCF scenes |
| 13 | `gh.veerwang/octoaxes` | family-config (serial) | **wrong** | the decision fits (Teensy motion firmware with a serial protocol), but the only entry was a GUI widget. GUI classes are never entries or hint sources now (rule); the card is a recon card |
| 14 | `gh.barisyazici/libfranka-sim` | direct-driver (twin), wave 6 | correct | curated override: a libfranka protocol simulator |
| 15 | `gh.rk-exxec/pymupump` | family-config (serial) | correct |  |
| 16 | `gh.farama-foundation/gymnasium` | family-config (gymnasium) | correct | exemplar |
| 17 | `gh.iit-dlslab/gym-quadruped` | family-config (mujoco) | correct | quadruped scenes with actuators |
| 18 | `gh.paddlepaddle/metagym` | family-config (gymnasium) | correct |  |
| 19 | `gh.omarrayyann/mjlab_manipulation` | family-config (mujoco) | debatable | mjlab (GPU) tasks; its first model was a vendored gripper (`_robotiq/`), now ranked after the robots (rule) |
| 20 | `gh.bdhammel/python_newport_controller` | direct-driver (python-object) | correct | Newport 8745 over pyusb |
| 21 | `gh.zihanwang0422/muarm` | family-config (mujoco) | correct | MuJoCo arm scenes and gym-style envs |
| 22 | `gh.l-johnston/tekinstr` | family-config (scpi) | correct |  |
| 23 | `gh.davidlutton/labtoolkit` | direct-driver (driver pack) | correct |  |
| 24 | `gh.google-research/robodesk` | family-config (mujoco) | correct | desk scene and the RoboDesk env |
| 25 | `gh.florian-lapp/nesp-lib-py` | family-config (serial) | correct |  |
| 26 | `gh.arise-initiative/robosuite_models` | family-config (mujoco) | correct | robot models (twin candidates); grippers are never the main model now |
| 27 | `gh.hello-robot/stretch_mujoco` | family-config (mujoco) | correct | curated override; `needs_recon: artifacts` |
| 28 | `gh.steiva/opentrons-ot2-http-python-wrapper` | direct-driver (python-object) | debatable | a thin client of the OT-2 HTTP API; the HTTP helper family would also fit |
| 29 | `gh.vcl-hnu/surgvla` | family-config (gymnasium) | correct | SurRoL tasks |
| 30 | `gh.openquadruped/spot_mini_mini` | family-config (gymnasium) | correct |  |

## Round 7 (seed 2036, all cards)

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.applied-ai-lab/ramp-sim` | untriaged, wave 6 | correct | Isaac Sim |
| 2 | `gh.septyawan24/epicssimulator` | untriaged | correct | EPICS servo and relay simulator |
| 3 | `gh.ros2/rmw_freertps` | bridge-runtime (ros) | correct |  |
| 4 | `gh.sasakuruppuarachchi/isaacsim_ros2_drone` | untriaged, wave 6 | correct | Isaac Sim and ROS 2 setup guide |
| 5 | `gh.mrpt/mrpt` | skip (peripheral) | correct | C++ toolkit |
| 6 | `gh.ad-sdl/madsci_examples` | skip (tooling) | correct |  |
| 7 | `gh.cuhksiriusleggedrobotteam/sirius_rl_gym` | skip (peripheral) | correct | Isaac Gym training |
| 8 | `gh.robotlocomotion/drake` | bridge-runtime (engine) | correct |  |
| 9 | `gh.adityaraghavan98/multitask-spm` | skip (not a device) | correct | one notebook |
| 10 | `gh.micro-ros/docker` | skip (tooling) | correct |  |
| 11 | `gh.mattjax16/rigol-dho-mcp` | family-config (mcp-client) | correct | an MCP server that drives the scope itself; waits for the helper |
| 12 | `gh.b4be1/rl-arch-assembly` | untriaged, wave 6 | correct | CoppeliaSim |
| 13 | `gh.sandraschi/oscilloscope-mcp` | untriaged | correct | MCP server with a built-in simulator |
| 14 | `gh.akdavanz/bioreactor-sim` | skip (not a device) | correct | JavaScript only |
| 15 | `gh.tango-controls/simulatords` | untriaged | correct | PyTango simulation suite |
| 16 | `gh.nicklashansen/puppeteer` | skip (peripheral) | correct | policy code |
| 17 | `gh.utnuclearroboticspublic/pid` | skip (peripheral) | correct | ROS 2 PID controller |
| 18 | `gh.azka-aamir/experimental-physics-automation` | skip (tooling) | correct | pyvisa-sim demo |
| 19 | `gh.ploxc/modbux` | skip (tooling) | correct | Electron Modbus tool |
| 20 | `gh.blackcoffeerobotics/bcr_arm` | family-config (ros) | correct | Gazebo arm; waits for the ROS helper |
| 21 | `gh.morse-simulator/morse` | untriaged | correct | Blender 2.79 simulator |
| 22 | `gh.dojo-sim/dojo.jl` | skip (peripheral) | correct | Julia physics engine |
| 23 | `gh.ftf1990/industrial-digital-twin-by-transformer` | skip (peripheral) | correct | forecasting models |
| 24 | `gh.di-omics/plr-mcp` | reference (host) | correct | MCP over PyLabRobot |
| 25 | `gh.dmgav/ophyd-service` | untriaged | correct | REST server for ophyd devices; recon settles host |
| 26 | `gh.robotlocomotion/spartan` | skip (tooling) | correct |  |
| 27 | `gh.dylan-losey/panda-env` | untriaged | correct | PyBullet envs without registration |
| 28 | `gh.graik/evowarepy` | skip (peripheral) | correct | Evoware script generator |
| 29 | `gh.northriv/kame` | untriaged | correct | C++ measurement program |
| 30 | `gh.mr-qb/quadcopter-simulation-with-webots` | untriaged, wave 6 | correct | Webots |

## Round 8 (seed 2037, dispatchable cards)

Drawn after the round-6 fixes.

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.google-deepmind/mujoco_menagerie` | family-config (mujoco) | correct | curated override; main model `agilex_piper/scene.xml` |
| 2 | `gh.pymodaq/pymodaq_plugins_keithley` | family-config (scpi) | correct | Keithley VISA drivers |
| 3 | `gh.zhangxp93/pyinsts` | family-config (scpi) | correct |  |
| 4 | `gh.ap/python-oceanoptics` | direct-driver (python-object) | correct | discontinued pyusb spectrometer module |
| 5 | `gh.hzaskywalker/plasticinelab` | family-config (gymnasium), wave 6 | correct |  |
| 6 | `gh.mujocolab/mjlab` | family-config (mujoco), wave 6 | **wrong** | a GPU task framework; its cartpole MJCF is an example. Now bridge-runtime:engine (override) |
| 7 | `gh.chilaslasers/pychilaslasers` | direct-driver (python-object) | correct |  |
| 8 | `gh.amsikking/asi_ms_2000_500_cp` | family-config (serial) | correct |  |
| 9 | `gh.kzhao1228/pystage_apt` | direct-driver (python-object) | correct |  |
| 10 | `gh.benelot/pybullet-gym` | family-config (gymnasium) | correct |  |
| 11 | `gh.gongxudong/fly-craft` | family-config (gymnasium) | correct |  |
| 12 | `gh.gormleylab/spectramax` | direct-driver (python-object), wave 6 | correct | SoftMax Pro automation (Windows) |
| 13 | `gh.mattchantk/gym-maze` | family-config (gymnasium) | correct |  |
| 14 | `gh.zihanwang0422/muarm` | family-config (mujoco) | correct |  |
| 15 | `gh.google-research/robodesk` | family-config (mujoco) | correct |  |
| 16 | `gh.davidlutton/labtoolkit` | direct-driver (driver pack) | correct |  |
| 17 | `gh.huggingface/gym-aloha` | family-config (gymnasium) | correct |  |
| 18 | `gh.osurobotics/kinovagrasping` | family-config (gymnasium) | debatable | RL research code around a registered Kinova gripper env |
| 19 | `gh.mabuchilab/instrumental` | direct-driver (driver pack), wave 6 | correct |  |
| 20 | `gh.myohub/myosuite` | family-config (gymnasium), wave 6 | correct |  |
| 21 | `gh.qnslab/labdaemon` | direct-driver (python-object) | **wrong** | an experiment framework; its only evidence was an HTTP client of its own server. Rule 10 now needs a hardware transport when that is the only evidence (rule; recon card) |
| 22 | `gh.uwo-fast/openreactor` | direct-driver (python-object) | debatable | a Raspberry Pi reactor application with EZO I2C drivers |
| 23 | `gh.xingyu-lin/softgym` | family-config (gymnasium) | **wrong** | envs on NVIDIA FleX through the compiled pyflex module. Now untriaged, wave 6 (rule: `pyflex` is an external engine) |
| 24 | `gh.tomwphillips/pumpy` | direct-driver (python-object) | correct |  |
| 25 | `gh.pymodaq/pymodaq_plugins_andor` | direct-driver (python-object) | debatable | entries are PyMoDAQ viewer plugins over the Andor SDK |
| 26 | `gh.arise-initiative/robosuite_models` | family-config (mujoco) | correct |  |
| 27 | `gh.vcl-hnu/surgvla` | family-config (gymnasium) | correct |  |
| 28 | `gh.simonmeersschaut/stagecontroller` | family-config (serial) | correct | Phytron stepper over serial |
| 29 | `gh.farama-foundation/gymnasium-robotics` | family-config (gymnasium) | correct | id templates are marked in the hints |
| 30 | `gh.nominal-io/instro` | direct-driver (driver pack), wave 6 | correct |  |

## Round 9 (seed 2038, dispatchable cards)

Drawn after the round-8 fixes.

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.barisyazici/libfranka-sim` | direct-driver (twin), wave 6 | correct | curated override |
| 2 | `gh.nicrusso7/rex-gym` | family-config (gymnasium) | correct |  |
| 3 | `gh.asvela/tektronix-func-gen` | family-config (scpi) | correct |  |
| 4 | `gh.boston-dynamics/spot-sdk` | direct-driver (python-object) | correct | curated override |
| 5 | `gh.prathameshnium/pica-python-instrument-control-and-automation` | direct-driver (driver pack) | debatable | a GUI suite whose instrument backends live in the GUI scripts |
| 6 | `gh.pymodaq/pymodaq_plugins_oceaninsight` | direct-driver (python-object), wave 6 | debatable | a PyMoDAQ viewer plugin over OmniDriver (.NET) |
| 7 | `gh.sail-research-lab/robust-gymnasium` | family-config (gymnasium), wave 6 | correct |  |
| 8 | `gh.abrar2652/imitation-learning-aloha` | family-config (gymnasium) | debatable | as in round 5 |
| 9 | `gh.farama-foundation/metaworld` | family-config (gymnasium) | correct |  |
| 10 | `gh.damat-le/gym-simplegrid` | family-config (gymnasium) | correct |  |
| 11 | `gh.jjshoots/crazyflyt` | direct-driver (python-object) | correct | real Crazyflie over cflib and a PyFlyt simulator |
| 12 | `gh.ap/python-seabreeze` | direct-driver (python-object) | correct |  |
| 13 | `gh.huggingface/lerobot-humanoid` | family-config (mujoco) | **wrong** | the decision fits (curated twin), but its entries were LeRobot processor steps that a plugin registry decorates. Only environment registrations count now, and twin cards take their model, not environment classes (rule) |
| 14 | `gh.beniroquai/opentrons-microscope-platereader` | family-config (serial) | correct | GRBL stage |
| 15 | `gh.ikalevatykh/mano_pybullet` | family-config (gymnasium) | correct |  |
| 16 | `gh.mba2d/test_equipment_control` | family-config (scpi) | correct |  |
| 17 | `gh.openmoss/vlabench` | family-config (mujoco) | correct | `needs_recon: artifacts` |
| 18 | `gh.aaronslaff/tecan_sparkcontrol` | direct-driver (python-object) | correct |  |
| 19 | `gh.allenneuraldynamics/runze-control` | direct-driver (python-object) | correct |  |
| 20 | `gh.openai/robogym` | family-config (mujoco) | correct | archived; mujoco-py system dependency |
| 21 | `gh.openai/multiagent-particle-envs` | family-config (gymnasium) | correct |  |
| 22 | `gh.navneet-nmk/hierarchical-meta-reinforcement-learning` | family-config (gymnasium) | debatable | paper code; its registered toy envs are real but minor |
| 23 | `gh.isri-aist/jvrc_mj_description` | family-config (mujoco) | correct | JVRC-1 model |
| 24 | `gh.pymodaq/pymodaq_plugins_demo` | family-config (serial) | **wrong** | demo plugins whose wrappers are mocks. Now skip:not-device (override) |
| 25 | `gh.kscalelabs/mujoco_playground` | family-config (mujoco) | debatable | an MJX training playground with K-Bot scenes |
| 26 | `gh.tipith/py6632b` | direct-driver (python-object) | correct |  |
| 27 | `gh.azdagkas/kinesis-piezo` | direct-driver (python-object), wave 6 | correct | Kinesis .NET |
| 28 | `gh.joshnegreanu/robo-lab` | family-config (mujoco) | correct |  |
| 29 | `gh.usnistgov/ssmdevices` | direct-driver (python-object) | correct |  |
| 30 | `gh.python-ivi/python-ivi` | family-config (scpi) | correct |  |

## Fixes after the second verification (triage 0.9.3, source scan 9)

Rules (`source_scan.py`, `triage.py`, `taskcards.py`; each with a test):

- Rule-9 markers come from the package itself: gym registrations in examples, tests, docs, `conftest.py` and
  vendored trees count only in `gym_ids_aux`; MJCF files there count as `mjcf_aux`; `third_parties/`,
  `third-party/` and `3rd_party/` are vendored trees.
- The MuJoCo marker is a loadable scene or robot model with actuators (directly, through included files, or
  through an `<include>` inside `<actuator>`), never object or fixture assets, fragments, templates, component
  libraries (grippers, objects, mounts ...) or paths marked unsupported or deprecated. Cards name the models in
  the typed `models` field (`{file, line, kind}`, main model first); a MuJoCo card without one carries
  `needs_recon: model`, and the pilot and strict-ready waves need a model.
- Simulator cards without a usable registration list the package's environment classes (robosuite and LIBERO
  styles included); twin candidates take their model instead. Class-object, vector and decorator registrations
  are resolved; id templates are marked in the hints.
- `needs_recon: artifacts` (asset, model or Git LFS downloads in the README) and `install.system_deps`
  (mujoco-py's MuJoCo 2.1 binaries) keep a card out of the pilot and strict-ready waves; `needs_recon: motion`
  marks a robot hardware card whose motion API was not found and keeps it out of the pilot.
- Simulators, mocks and dummies of the device are never rule 10's entry or device evidence, and a card lists
  them as entries only when no real class is ranked (then a dummy module's same-named real class comes first);
  `Virtual<Name>` counts as a mock only beside `<Name>`. A facade that builds another ranked class as a member ranks above it, and its members' methods feed
  the hints. GUI classes are never entry symbols or hint sources. A GUI application's plugin or widget class is
  no direct driver, and a GUI application without a device class takes no protocol family.
- Rule 10 needs a hardware transport when its only device evidence is an exported client of generic
  networking (HTTP, gRPC, ZeroMQ).
- Newton, ThreeDWorld (`tdw`), VirtualHome (`unity_simulator`) and NVIDIA FleX (`pyflex`) are external engines
  without a helper.
- Module paths follow the package roots of the packaging metadata (poetry `from`, setuptools `package_dir` and
  `where`). GPU detection reads only package imports outside `try`/`if` blocks and test or benchmark scripts.
- Pilot buckets served by two helpers take their cards from both families in turn.

Overrides (`overrides/*.json`, one-line justifications): pylablib-cam-control and autolab (hosts), rtgym
(tooling), gym_solutions and pymodaq_plugins_demo (not devices), robo-gym (external robot servers, wave 6),
mjlab (bridge-runtime engine), ac-dev-lab (recon: a collection of per-device code) and
self-revising-active-inference (skip).

## Decisions of the first rounds that 0.9.3 changed

Besides the cards the first fixes already changed (listed there): myo_sim (its loadable models are under
`legacy/`), robopianist (its models are composed at run time with dm_control) and libero-para, robocasa and
envpool (no loadable model in the clone) are untriaged recon cards; robocas-v0 is untriaged (no package
registration); mujoco_scanned_objects is skipped.

## First verification rounds (triage 0.9.2)

| round | seed, pool | cards | correct | debatable | wrong | acceptable |
|---|---|---|---|---|---|---|
| 1 | 2028, all cards | 30 | 29 | 1 | 0 | 100% |
| 1 | 2029, dispatchable | 20 | 18 | 1 | 1 | 95% |
| 2 | 2030, all cards | 30 | 30 | 0 | 0 | 100% |
| 2 | 2031, dispatchable | 20 | 18 | 0 | 2 | 90% |
| 3 | 2032, dispatchable | 20 | 16 | 2 | 2 | 90% |
| 4 | 2033, dispatchable | 20 | 18 | 1 | 1 | 95% |
| 1-4 | | 140 | 129 | 5 | 6 | 95.7% |

The second verification found that these rounds were too lenient with MuJoCo cards: lerobot-libero (round 1),
robocasa (round 3) and mujoco_scanned_objects (round 4) were judged on the decision alone, and their card
content would misdirect an author.

## Round 1 (seed 2028, all cards)

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.liorbenhorin/lerobot_so101_teleop` | untriaged, wave 6 | correct | Isaac Lab tasks for an SO-101; an external engine without a helper |
| 2 | `gh.erojasoficial-byte/fly-brain` | untriaged | correct | connectome simulation of a fly in a MuJoCo body; research code, recon settles it |
| 3 | `gh.yingyuan0414/in-hand-rotation` | skip (peripheral) | correct | Isaac Gym policy research |
| 4 | `gh.airsimdronesimulator/airsim` | skip (peripheral) | correct | a student project on AirSim, not the engine |
| 5 | `gh.manasp21/oscilloscope_mcp` | direct-driver (python-object) | debatable | an MCP server around a simulated oscilloscope with a serial ADC backend; its Ethernet and PCIe backends are stubs |
| 6 | `gh.lucasgerads/lecroy-mcp` | reference (host) | correct | MCP server over pyvisa |
| 7 | `gh.iit-dlslab/sim2real-robot-identification` | skip (peripheral) | correct | a system-identification routine |
| 8 | `gh.duburcqa/jiminy` | family-config (gymnasium) | correct | simulator with gym envs; it was wave 6 only because `msvcrt` counted as Windows-only (fixed, now wave 3) |
| 9 | `gh.tonyzhaozh/aloha` | family-config (ros) | correct | ALOHA on ROS 1, waits for the ROS helper |
| 10 | `gh.accelerationconsortium/workflow-management` | reference (host) | correct | orchestration |
| 11 | `gh.facebookresearch/pyrobot` | untriaged, wave 6 | correct | LoCoBot SDK on ROS with Habitat envs; not dispatchable either way |
| 12 | `gh.jwlodek/seabreeze` | untriaged (non-Python) | correct | the C SeaBreeze library |
| 13 | `gh.srmainwaring/ros_gz_rover` | untriaged | correct | a ROS 2 Gazebo rover simulation |
| 14 | `gh.skylark0924/rofunc` | untriaged, wave 6 | correct | robot-learning framework on Isaac Gym |
| 15 | `gh.liruiw/gensim` | untriaged | correct | LLM-generated simulation tasks; recon settles it |
| 16 | `gh.reiniscimurs/drl-robot-navigation` | skip (peripheral) | correct | a navigation policy |
| 17 | `gh.42jaylonw/shifu` | untriaged, wave 6 | correct | Isaac Gym wrapper |
| 18 | `gh.ros2/rclpy` | bridge-runtime (ros) | correct | ROS 2 client library |
| 19 | `gh.radarku/ardupilot-sitl-docker` | skip (not a device) | correct | Dockerfiles only |
| 20 | `gh.slautin/2026_domain_growth_hypothesis_learning` | skip (not a device) | correct | one notebook |
| 21 | `gh.robotology/yarp` | untriaged | correct | C++ middleware, a transport rather than a driver |
| 22 | `gh.araffin/robotics-rl-srl` | skip (peripheral) | correct | RL research |
| 23 | `gh.snhobbs/hp894xx` | direct-driver (python-object) | correct | HP89400 analyser over a Prologix GPIB-Ethernet adapter |
| 24 | `gh.florianbauer/sila-orchestrator` | reference (host) | correct | orchestrator |
| 25 | `gh.ad-sdl/madsci_examples` | skip (tooling) | correct | examples |
| 26 | `gh.a-tock/lys_em` | skip (peripheral) | correct | electron-microscope simulation and analysis |
| 27 | `gh.joshnegreanu/robo-lab` | family-config (mujoco) | correct | MuJoCo bimanual teleoperation with MJCF models |
| 28 | `gh.patilunmesh/drone_simulator` | family-config (ros) | correct | ROS drone simulation, waits for the ROS helper |
| 29 | `gh.saga0619/mujoco_ros_sim` | family-config (ros) | correct | ROS MuJoCo simulation |
| 30 | `gh.craigiedon/probrobscene` | skip (peripheral) | correct | a scene-specification language with a CoppeliaSim wrapper |

## Round 1 (seed 2029, dispatchable cards)

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.solgaardlab/apt_piezo` | family-config (scpi) | **wrong** | Thorlabs APT over pyftdi; a VISA power-supply helper picked SCPI. Now a direct driver (override) |
| 2 | `gh.myohub/myo_sim` | family-config (mujoco) | correct | MuJoCo musculoskeletal models |
| 3 | `gh.ml-lab/home-platform` | family-config (gymnasium) | debatable | HoME gym envs on Panda3D; Python 2.7 and the SUNCG data it needs are no longer available |
| 4 | `gh.dartsim/gym-dart` | family-config (gymnasium) | correct | gym envs on dartpy |
| 5 | `gh.tektronix/curvequery` | family-config (scpi) | correct | waveform download over PyVISA |
| 6 | `gh.damat-le/gym-simplegrid` | family-config (gymnasium) | correct | grid-world env |
| 7 | `gh.sfinucane/sindri` | direct-driver (python-object) | correct | Lantz-based instrument drivers |
| 8 | `gh.labpy/lantz` | direct-driver (driver pack) | correct | instrumentation toolkit with a driver pack (override) |
| 9 | `gh.nimazareian/quadruped-rl-locomotion` | family-config (mujoco) | correct | Go1 MJCF models and a gymnasium env |
| 10 | `gh.tomwphillips/pumpy` | direct-driver (python-object) | correct | Harvard Apparatus pumps |
| 11 | `gh.notfoundthisperson/robocas-v0` | family-config (gymnasium) | correct | a manipulation benchmark, wave 6 (GPU) |
| 12 | `gh.chemgymrl/chemgymrl` | family-config (gymnasium) | correct | virtual chemistry lab |
| 13 | `gh.gustavo-moura/itomori` | family-config (gymnasium) | correct | UAV risk-aware flight env |
| 14 | `gh.huggingface/lerobot-libero` | family-config (mujoco) | correct | LIBERO for LeRobot (partner override) |
| 15 | `gh.soltanilara/gym_av_aloha` | family-config (gymnasium) | correct | AV-ALOHA simulation envs |
| 16 | `gh.kscalelabs/mujoco_playground` | family-config (mujoco) | correct | MuJoCo Playground variant, wave 6 (GPU) |
| 17 | `gh.vitchyr/multiworld` | family-config (gymnasium) | correct | multitask gym envs |
| 18 | `gh.mclim9/rssd` | family-config (scpi) | correct | R&S instrument scripts over PyVISA |
| 19 | `gh.kscalelabs/kbot` | family-config (mujoco) | correct | K-Bot MJCF models, a twin of the robot |
| 20 | `gh.xylophoneengine/pycss45` | direct-driver (python-object) | correct | CSS45 spectroradiometer over USB HID |

## Round 2 (seed 2030, all cards)

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.jana-marie/temperature-logger` | untriaged (non-Python) | correct | KiCad hardware and C firmware |
| 2 | `gh.mcity/mcity-digital-twin` | skip (peripheral) | correct | CARLA and Omniverse assets |
| 3 | `gh.manas-arumalla/openarm-control` | family-config (mujoco) | correct | OpenArm v2 in MuJoCo |
| 4 | `gh.pylabrobot/slas_2026_demos` | skip (not a device) | correct | a demo notebook |
| 5 | `gh.9nate-drake/comfyui-secnodes` | skip (peripheral) | correct | ComfyUI segmentation nodes |
| 6 | `gh.osrf/gazebo_models` | untriaged (non-Python), wave 6 | correct | Gazebo model database |
| 7 | `gh.vincekurtz/drake_ddp` | skip (peripheral) | correct | trajectory optimisation research |
| 8 | `gh.openai/roboschool` | family-config (gymnasium) | correct | archived Bullet-based gym envs |
| 9 | `gh.nplan/gym-line-follower` | family-config (gymnasium) | correct | |
| 10 | `gh.mattchantk/gym-maze` | family-config (gymnasium) | correct | |
| 11 | `gh.csibug/microlink-mcp` | untriaged | correct | an MCP server for a USB microscope; its helper does not exist |
| 12 | `gh.singroup/pyvafm` | untriaged | correct | a virtual AFM |
| 13 | `gh.jm-kim-94/rl-mobile-robot-sac` | skip (peripheral) | correct | |
| 14 | `gh.bnl-atf/ophyd-basler` | family-config (ophyd) | correct | waits for the ophyd helper |
| 15 | `gh.rui-li023/labutopia` | untriaged, wave 6 | correct | Isaac Sim benchmark |
| 16 | `gh.navneet-nmk/pytorch-rl` | untriaged | correct | RL algorithms; skip would be better, recon settles it |
| 17 | `gh.ar0ne/v-rep-robotics` | skip (peripheral) | correct | |
| 18 | `gh.qnlsydney/qcodes_measurements` | skip (tooling) | correct | |
| 19 | `gh.gbionics/idyntree` | skip (peripheral) | correct | a dynamics library |
| 20 | `gh.openuc2/imswitch` | family-config (pymmcore-plus) | correct | microscope control with device managers; waits for the helper |
| 21 | `gh.qaisalramahi/holoocean-data-collection` | skip (tooling) | correct | |
| 22 | `gh.materialsproject/fireworks` | skip (peripheral) | correct | a workflow manager |
| 23 | `gh.liberomax/libero-max` | skip (peripheral) | correct | an evaluation layer |
| 24 | `gh.google/brax` | bridge-runtime (engine) | correct | |
| 25 | `gh.rainx0r/metaworld-algorithms` | skip (peripheral) | correct | |
| 26 | `gh.robot-descriptions/robot_descriptions.py` | skip (peripheral) | correct | a description loader |
| 27 | `gh.markding/gpib-pyvisa` | skip (tooling) | correct | a GPIB tutorial |
| 28 | `gh.diamondlightsource/pythonsoftioc` | untriaged | correct | an EPICS IOC framework (a transport) |
| 29 | `gh.google-research/robel` | family-config (gymnasium) | correct | ROBEL envs; the card covers the simulation side |
| 30 | `gh.micro-manager/micro-manager` | reference (host) | correct | curated override |

## Round 2 (seed 2031, dispatchable cards)

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.robotis-git/robotis_mujoco_menagerie` | family-config (mujoco) | correct | ROBOTIS MJCF models |
| 2 | `gh.davidlutton/labtoolkit` | direct-driver (driver pack) | correct | instrument classes on PyVISA |
| 3 | `gh.iherrbenza/ad9959_python` | direct-driver (python-object) | correct | AD9959 DDS over an ESP32 |
| 4 | `gh.jovanmarkov96/keysight-dsox1200-control` | family-config (scpi) | correct | |
| 5 | `gh.undalogic/usmu_py` | direct-driver (python-object) | correct | a source-measure unit |
| 6 | `gh.google-research/robopianist` | family-config (mujoco) | correct | |
| 7 | `gh.usnistgov/ssmdevices` | direct-driver (python-object) | correct | NIST instrument drivers (a pack) |
| 8 | `gh.maximecb/gym-miniworld` | family-config (gymnasium) | correct | |
| 9 | `gh.manas-arumalla/openarm-control` | family-config (mujoco) | correct | |
| 10 | `gh.personalrobotics/ssik` | family-config (mujoco) | **wrong** | an IK solver whose only MJCF files are test fixtures. Now skipped (rule) |
| 11 | `gh.drmcnelson/linear-ccd-with-ltspice-kicad-firmware-and-python-library` | family-config (serial) | correct | TCD1304 controller over serial |
| 12 | `gh.f9r/ihcpmslib-wrappers` | direct-driver (python-object), wave 6 | correct | INHECO .NET wrappers |
| 13 | `gh.microscope-cockpit/cockpit` | family-config (serial) | **wrong** | a microscope GUI over python-microscope. Now reference:host (override) |
| 14 | `gh.gregmoille/instrumentcontrol` | family-config (scpi), wave 6 | correct | |
| 15 | `gh.ksunden/zaber.serial` | direct-driver (python-object) | correct | |
| 16 | `gh.arise-initiative/robosuite_models` | family-config (mujoco) | correct | |
| 17 | `gh.openai/multiagent-particle-envs` | family-config (gymnasium) | correct | its registrations name classes the clone does not define (entry symbols `recon`) |
| 18 | `gh.cxy1997/robotiq-ur5` | family-config (mujoco) | correct | UR5 and Robotiq MJCF |
| 19 | `gh.dobot-arm/tcp-ip-python-v4` | direct-driver (python-object) | correct | |
| 20 | `gh.sail-research-lab/robust-gymnasium` | family-config (gymnasium) | correct | |

## Round 3 (seed 2032, dispatchable cards)

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.zhangxp93/pyinsts` | family-config (scpi) | correct | |
| 2 | `gh.alphatra/vacuum-instrument-monitor` | family-config (serial) | correct | vacuum gauges with a simulator |
| 3 | `gh.phuongboi/drone-control-using-reinforcement-learning` | family-config (gymnasium) | **wrong** | PPO scripts around a vendored copy of gym-pybullet-drones. Now a duplicate (override) |
| 4 | `gh.sail-sg/envpool` | family-config (mujoco), wave 6 | debatable | a batched environment engine; bridge-runtime would also fit |
| 5 | `gh.uwo-fast/openreactor` | direct-driver (python-object) | correct | Raspberry Pi reactor supervision |
| 6 | `gh.robotcontrolstack/duobench` | family-config (gymnasium) | correct | |
| 7 | `gh.maxiv-kitscontrols/sardana-albaem` | direct-driver (python-object) | correct | AlbaEM electrometer controller |
| 8 | `gh.capotosto/py_instrument_driver_package` | family-config (scpi) | correct | |
| 9 | `gh.vadter/hantek1008c` | direct-driver (python-object) | correct | |
| 10 | `gh.mba2d/test_equipment_control` | family-config (scpi) | correct | |
| 11 | `gh.farama-foundation/highwayenv` | family-config (gymnasium) | correct | |
| 12 | `gh.dartsim/gym-dart` | family-config (gymnasium) | correct | |
| 13 | `gh.roesel/elliptec` | direct-driver (python-object) | correct | |
| 14 | `gh.croningp/chemputersoftware` | direct-driver (python-object) | correct | Chemputer control with simulated calls; it was simulated only, and twins with a hardware transport are now hardware first (rule) |
| 15 | `gh.openretriever/stanford-robotics-kitchen` | family-config (mujoco) | correct | |
| 16 | `gh.pnnayyeri/gym-ur5` | family-config (gymnasium) | **wrong** | gym envs driving a CoppeliaSim scene. Now untriaged, wave 6 (rule) |
| 17 | `gh.robocasa/robocasa` | family-config (mujoco) | correct | |
| 18 | `gh.jjgoings/gym-muller_brown` | family-config (gymnasium) | correct | |
| 19 | `gh.amacati/soulsgym` | family-config (gymnasium), wave 6 | debatable | gym envs that need Dark Souls III running on Windows |
| 20 | `gh.swirl-uk/bigym2` | family-config (mujoco) | correct | |

## Round 4 (seed 2033, dispatchable cards)

| # | package | decision | verdict | note |
|---|---|---|---|---|
| 1 | `gh.lachlanhurst/so100-mujoco-rl` | family-config (gymnasium) | correct | |
| 2 | `gh.chanjin926/prompt2pose` | family-config (gymnasium) | correct | a ManiSkill 3 task |
| 3 | `gh.beniroquai/opentrons-microscope-platereader` | family-config (serial) | correct | GRBL stage and laser over serial |
| 4 | `gh.kevinzakka/mujoco_scanned_objects` | family-config (mujoco) | debatable | MJCF models of household objects, not of a device |
| 5 | `gh.osudrl/humanoid_hanoi` | family-config (mujoco) | correct | |
| 6 | `gh.openmoss/vlabench` | family-config (mujoco) | correct | |
| 7 | `gh.spencerfolk/rotorpy` | family-config (gymnasium) | correct | |
| 8 | `gh.dgretton/pyhamilton` | direct-driver (python-object), wave 6 | correct | |
| 9 | `gh.lando1784/pyagilis` | family-config (serial) | correct | Newport Agilis |
| 10 | `gh.tgojname/picocontroller_gui` | direct-driver (python-object) | correct | the Newport 8742 controller class |
| 11 | `gh.jonathanvanschenck/sr830-python` | family-config (scpi) | correct | |
| 12 | `gh.wetenschaap/pymista` | direct-driver (python-object) | correct | |
| 13 | `gh.sparks-baird/self-driving-lab-demo` | direct-driver (python-object) | correct | the decision is right; its best host class is a small serial talker |
| 14 | `gh.vcl-hnu/surgvla` | family-config (gymnasium) | correct | SurRoL tasks |
| 15 | `gh.kevinzakka/mjctrl` | family-config (mujoco) | **wrong** | teaching controllers on copied Menagerie models. Now skipped (override) |
| 16 | `gh.fdcl-gwu/gym-rotor` | family-config (gymnasium) | correct | |
| 17 | `gh.kagisokgwahla/capstone-molecule-environment` | family-config (gymnasium) | correct | |
| 18 | `gh.opengalaxea/galaxeamanipsim` | family-config (gymnasium) | correct | |
| 19 | `gh.openai/multiagent-particle-envs` | family-config (gymnasium) | correct | |
| 20 | `gh.cau-hai-lab/libero-para` | family-config (mujoco) | correct | |

## Fixes after the first verification (triage 0.9.2)

Rules (`triage.py` 0.9.2, `taskcards.py`, `build_registry.py`; each with a test):

- A repo the catalogue calls a model or a simulation (measurement model, task environment, direct simulation
  backend, digital twin) gets device evidence only together with a class that uses a hardware transport
  (serial, VISA, USB, fieldbus, a vendor SDK). This fixed the verification's simulator findings (scopesim,
  libero-plus, epics-deviceemulator) and keeps hardware off such records.
- Gym envs with Gazebo world files or plugins, CoppeliaSim scenes or Webots worlds need an external simulator
  application (gymfc, gym-ur5); their recon cards are wave 6.
- MJCF files under test fixtures are not simulator evidence (ssik).
- A strong device class on a non-VISA hardware transport is not turned into a SCPI command map by a VISA
  helper beside it (three PyMoDAQ plugins and NIST's ssmdevices became direct drivers).
- A twin candidate whose code uses a hardware transport plans a hardware device first (chemputersoftware,
  fibsem-os, oscilloscope_mcp).

Overrides (`overrides/*.json`, one-line justifications): luckyrobots and RoboDK (external engines, wave 6),
pyacq (framework, recon), labthings-fastapi and Cockpit (hosts), Open_Model_Hardware_Standard (prior art),
lantz (driver pack), apt_piezo (direct driver), drone-control-using-reinforcement-learning (duplicate) and
mjctrl (skip).

## Earlier rounds

Step 10b measured 26/30 on seed 2026 and, after two rule changes, 29/30 on seed 2027. The independent
verification then sampled 58 cards and found simulators triaged as hardware (scopesim, luckyrobots,
libero-plus, epics-deviceemulator) and a Gazebo-backed gym env in wave 2 (gymfc); it scored 17 of 20
dispatchable cards. Those findings led to the rounds above, and every card it named is fixed: scopesim is
skipped, luckyrobots and gymfc are untriaged in wave 6, and libero-plus and epics-deviceemulator are simulated
recon cards.
