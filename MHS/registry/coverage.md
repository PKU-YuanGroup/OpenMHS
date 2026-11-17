# OpenMHS registry coverage

Generated 2026-10-20T00:00:00Z by `MHS/registry/build_registry.py`; every number is computed from the records and cards.

## Decisions

| strategy / role | repos |
|---|---|
| bridge-runtime/framework | 154 |
| bridge-runtime/sim-env | 24 |
| bridge-runtime/transport | 91 |
| bridge-runtime/twin-candidate | 4 |
| direct-driver/device-driver | 243 |
| direct-driver/driver-pack | 34 |
| direct-driver/sim-env | 29 |
| direct-driver/twin-candidate | 6 |
| family-config/device-driver | 86 |
| family-config/driver-pack | 3 |
| family-config/sim-env | 455 |
| family-config/twin-candidate | 37 |
| reference/driver-pack | 1 |
| reference/framework | 4 |
| reference/host | 244 |
| reference/prior-art | 51 |
| reference/twin-candidate | 5 |
| skip/device-driver | 2 |
| skip/docs | 126 |
| skip/driver-pack | 2 |
| skip/framework | 24 |
| skip/host | 1 |
| skip/not-device | 705 |
| skip/prior-art | 19 |
| skip/sim-env | 214 |
| skip/tooling | 402 |
| skip/transport | 1 |

Deciding rule: 1 6, 2 119, 3 1, 4 11, 5 8, 6 78, 7 402, 8 619, 9 285, 10 93, override 1345

## Waves

| wave | cards | meaning |
|---|---|---|
| 0 | 4 | exemplars, done before the handoff (curated overrides) |
| 1 | 54 | pilot pool: the non-exemplar cards of tasks/pilot-candidates.json (MHS/handoff/pilot-20.json dispatches 20 of them) |
| 2 | 153 | strict-ready: Python, pip install backed by a root file with no system dependency, no GPU, licence known, AST entry symbol (or, for MuJoCo, a main scene or robot model), candidate classes, no artifact download |
| 3 | 456 | other dispatchable cards with an available helper |
| 4 | 0 | recon-only cards (decision untriaged, or a dispatchable card blocked on recon:entry_symbol): confirm an entry symbol and a decision |
| 5 | 92 | family members waiting for a post-pilot helper (blocked_on helper:<name>) |
| 6 | 134 | cards that need a GPU, Windows or an external engine without a helper (Isaac, Unity, Unreal, Habitat, AirSim, CARLA, Gazebo) |
| 9 | 2074 | never dispatched as a repo task: skip, reference and bridge-runtime cards |

## Families

| family | repos | bridge_status | helper | dispatchable now | untriaged |
|---|---|---|---|---|---|
| python-object | 494 | available | PythonObjectDriver | 0 | 0 |
| gymnasium | 408 | available | GymnasiumDriver | 0 | 0 |
| other | 388 | none | - | 0 | 0 |
| ros2 | 260 | available | RosDriver | 0 | 0 |
| mujoco | 197 | available | MujocoDriver | 0 | 0 |
| ros1 | 140 | available | RosDriver | 0 | 0 |
| gazebo | 134 | available | RosDriver | 0 | 0 |
| cli-process | 120 | none | - | 0 | 0 |
| scpi-visa | 118 | available | ScpiDriver | 0 | 0 |
| mcp-proxy | 85 | available | McpClientDriver | 0 | 0 |
| serial | 58 | available | SerialDriver | 0 | 0 |
| isaac-gym | 57 | none | - | 0 | 0 |
| micromanager | 47 | planned (helper:pymmcore-plus) | - | 0 | 0 |
| pybullet | 46 | none | - | 0 | 0 |
| isaac-sim | 41 | none | - | 0 | 0 |
| http-api | 40 | planned (helper:http) | - | 0 | 0 |
| opentrons | 40 | planned (helper:http) | - | 0 | 0 |
| docker | 35 | none | - | 0 | 0 |
| bluesky-ophyd | 28 | available | OphydDriver | 0 | 0 |
| tag-bridge | 27 | available | TagDriver | 0 | 0 |
| pylabrobot | 24 | available | PyLabRobotDriver | 0 | 0 |
| qcodes | 24 | available | QcodesDriver | 0 | 0 |
| isaac-lab | 23 | none | - | 0 | 0 |
| unity | 20 | none | - | 0 | 0 |
| airsim | 17 | none | - | 0 | 0 |
| sila2 | 16 | available | Sila2Driver | 0 | 0 |
| webots | 15 | none | - | 0 | 0 |
| habitat | 13 | none | - | 0 | 0 |
| replay | 11 | none | - | 0 | 0 |
| sapien | 11 | none | - | 0 | 0 |
| lerobot-real | 7 | planned (helper:lerobot) | - | 0 | 0 |
| dm-env | 6 | none | - | 0 | 0 |
| drake | 6 | none | - | 0 | 0 |
| madsci | 4 | planned (helper:http) | - | 0 | 0 |
| mavlink | 4 | planned (helper:mavlink) | - | 0 | 0 |
| flowchem | 2 | planned (helper:http) | - | 0 | 0 |
| brax-mjx | 1 | none | - | 0 | 0 |

## Waiting for a helper

| prerequisite | cards |
|---|---|
| helper:mavlink | 2 |
| helper:lerobot | 1 |

## Licences

| licence class | repos |
|---|---|
| copyleft | 205 |
| network-copyleft | 28 |
| permissive | 1910 |
| proprietary | 17 |
| source-available | 43 |
| unknown | 708 |
| weak-copyleft | 56 |

| licence source | repos |
|---|---|
| catalog | 1658 |
| license-file | 569 |
| none | 705 |
| package-metadata | 35 |

## Modes and evidence

| mode | repos |
|---|---|
| hardware | 515 |
| replay | 3 |
| simulated | 861 |

| evidence | repos |
|---|---|
| agent_read | 45 |
| contract_checked | 799 |
| declared | 6 |
| static_scan | 2117 |

| ring | repos |
|---|---|
| 1 | 799 |
| 3 | 2168 |

## Card quality

- with entry symbols: 830 (an `ast` class located in the clone: 488); blocked on `recon:entry_symbol`: 0
- with install commands backed by a root file: 1477
- mock strategy: fake 1634, transcript 75, upstream-sim 1258
- risk floors: R0 2706, R1 218, R2 43

## First 50 dispatchable cards

| wave | rank | package | decision | helper | risk floor |
|---|---|---|---|---|---|

## Catalogue rows without a local clone

| catalogue row | repo | category | source status |
|---|---|---|---|
| 320 | `baotruyenthach/dvrk_grasp_pipeline_isaacgym` | complete environment | unavailable |
| 321 | `baotruyenthach/dvrk_issacgym` | complete environment | unavailable |
| 1457 | `linorobot2/lino2_upper` | device backend | unavailable |

## Clones without a catalogue row

| package | track | family | tier |
|---|---|---|---|
| `gh.sickag/sick_scan_xd` | robots | ros2 | A |
