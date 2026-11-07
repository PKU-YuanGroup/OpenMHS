# Facts and tags for gh.ut-amrl/socialgym2

Every fact cites its source at commit `09a84865b8e22c86dd16658f403b18c3bbc67572`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RosSocialEnv is a PettingZoo ParallelEnv for multi-agent social navigation, not a ROS transport class | upstream_code | src/environment/ros_social_gym.py:46-51 |
| The constructor's num_agents default is (3, 5); possible_agents is player_<index> for the maximum of that range | upstream_code | src/environment/ros_social_gym.py:80-81 |
| The constructor builds possible_agents and curr_num_agents from num_agents | upstream_code | src/environment/ros_social_gym.py:144-157 |
| Every possible agent's action space is spaces.Discrete(2) | upstream_code | src/environment/ros_social_gym.py:168 |
| Every possible agent's observation space is Box(low=-9999, high=9999, shape=(len(observer),)) | upstream_code | src/environment/ros_social_gym.py:169-171 |
| observation_space(agent) and action_space(agent) return the entries of those per-agent maps | upstream_code | src/environment/ros_social_gym.py:223-227 |
| The constructor starts a ROS node and a roslaunch parent for launch_config, then creates the UTMRS service client and the SocialPips service proxy | upstream_code | src/environment/ros_social_gym.py:194-207 |
| UTMRS waits for and proxies the utmrsStepper and utmrsReset services | upstream_code | src/environment/services/utmrs.py:62-66 |
| reset(seed=None, return_info=True, options=None) resets the scenario, observer and rewarder, calls the simulator reset and a default step, and returns a dict of per-agent observations and a dict of infos | upstream_code | src/environment/ros_social_gym.py:272-346 |
| step(action_dict) copies each agent's discrete action into the action array sent to the UTMRS step together with x/y/angle velocity arrays and max speeds | upstream_code | src/environment/ros_social_gym.py:348-396 |
| step returns per-agent observation, reward, termination, truncation and info dicts | upstream_code | src/environment/ros_social_gym.py:447 |
| RosSocialEnv.seed(seed=None) is a no-op and close() is a no-op | upstream_code | src/environment/ros_social_gym.py:269-270 |
| RosSocialEnv.close does not shut down the launched simulator | upstream_code | src/environment/ros_social_gym.py:220-221 |
| ManualZoneEnv is a RosSocialEnv subclass and overrides sim_step to use the manual-zone response type | upstream_code | src/environment/environment_types/manual_zone.py:110 |
| ManualZoneEnv.sim_step calls the UTMRS step and converts it with its own response type | upstream_code | src/environment/environment_types/manual_zone.py:180-183 |
| The config runner wraps the environment with SuperSuit's pettingzoo_env_to_vec_env_v1 and concat_vec_envs_v1 before training | upstream_code | src/config_run.py:436-442 |
| The README describes the project as a multi-agent simulator for real world social navigation | vendor_doc | README.md:7 |

Limits: the driver declares no manual bound. The only action bound is the per-agent ``Discrete(2)`` space the
Gymnasium bridge derives from the fake's action space, cited as ``src/environment/ros_social_gym.py:168`` (0 .. 1 for
each ``player_<index>``). The observation bounds ``-9999 .. 9999`` are the upstream observation-space bounds
(``src/environment/ros_social_gym.py:169-171``); they do not bound an actuation. The device is simulated (R0), so no
limit is ``operator_required`` and no ``site-limits.example.json`` is needed.

Shape note (DEVIATION FROM THE CARD): the card names the ros family and RosDriver, but the runtime is a PettingZoo
``ParallelEnv`` (``src/environment/ros_social_gym.py:46``) whose primary control is the multi-agent ``step`` at line
348, not a rosbridge transport. The package uses ``GymnasiumDriver``; its shared production adapter exposes the upstream's per-agent
``Discrete(2)`` spaces as one joint ``Dict`` so the step input is a dict of agent actions. The action bounds are still
the sourced per-agent ones.

Fidelity contract (`driver.py`, ``fidelity = {...}``): engine ``analytic:package fake (no physics)``, level F0,
determinism ``seeded`` with ``seed_control`` ``parameter``, timestep 0 ms (the clone declares no fixed simulator
timestep; the UTMRS clock is external), ``realtime_factor`` 0, clock ``lockstep``, reset ``full``, no snapshot and
restore. The gaps say that the fake runs no ROS, roslaunch, UTMRS/pedsim simulator, physics, human agents, observer or
rewarder; that the real observation width is ``len(observer)`` and the fake returns a shorter placeholder vector; that
the bridge's scalar reward/flags are a joint projection while the per-agent maps stay in ``info``; that the agent
count is a placeholder five; and that upstream ``seed()`` and ``close()`` are no-ops.

Safety: simulated R0 device. There is no hardware transport and no native stop in the upstream environment. The e-stop
is the runtime's software latch; after it no step or reset is accepted until ``mhs.safety.reset`` clears the latch, and
the last world state stays readable. This is not a physical emergency stop.

Tags: ros, simulation, multi-agent, social-navigation, pettingzoo, reinforcement-learning

## Reviewed production boundary

The raw fake preserves method spaces and per-agent dictionary results. `adapter.py` is the common projection for
fake and explicitly attached native peers: it derives each agent space, sums finite rewards, retains all maps and
original metadata, and tracks terminal agents across shrinking active sets. An unfinished empty/missing map is a
failure, not success. Once all episode agents finish, terminated means all terminated; truncated means any truncated.
The pinned upstream uses success_observation for both flags, so this ambiguity remains visible.

The `sim` factory deliberately refuses before ROS imports or process creation: an independently acknowledged stop
and owned launcher lifecycle remain unavailable. The adapter cannot turn a local software fence into a confirmed
external simulator stop, and safety reset remains refused for that unconfirmed external scope. Upstream seed is a
no-op; real attached peers have no canonical seed/reset capability. `x-cap.ut-amrl.reset_unseeded.v1` performs the
native reset and reports observation without inventing a seed. The fake retains its separate deterministic test RNG.
This extension is effectful and subject to the normal command lock, e-stop latch and active-call guard.

Only controlled raw peers were tested. No real ROS, UTMRS or production deployment ran. Physics tick receipt
accounting and actual elapsed simulation time are unverified; no private L14 SDK patch is required by this package.

## Model review lifecycle correction

The shared adapter enters an irreversible closing state before cleanup. No safety recovery or new native control is admitted afterward. Cleanup waits for the last in-flight call and executes once; failures are retained without reopening. This is local lifecycle bookkeeping, not an independently confirmed external stop.

Step rewards, observations and terminal maps contain exactly the unfinished agents for that call. Retired agents cannot contribute additional rewards. The activity report applies the current terminal results.
