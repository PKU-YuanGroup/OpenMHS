# Facts and tags for gh.chauby/coppeliasimrl

Every fact cites its source at commit `8eb98b8a42b515b61eae5ffebcc9f228e2f5fdd1`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository describes itself as a reinforcement learning workspace for CoppeliaSim (VREP) simulation environments | vendor_doc | README.md:3 |
| The environment setup lists CoppeliaSim 4.2 and the legacy Gym package as required software | vendor_doc | README.md:16-18 |
| The cart-pole demo is started after CoppeliaSim is running and cart_pole.ttt has been imported | vendor_doc | README.md:27 |
| CartPoleEnv is a gym.Env subclass | upstream_code | CartPole/CartPoleEnv.py:13 |
| The constructor builds a Discrete(3) action space when action_type is 'discrete' and a Box(-1.0, 1.0) action space when it is 'continuous' | upstream_code | CartPole/CartPoleEnv.py:17-40 |
| The cart-pole demo instantiates CartPoleEnv with action_type='discrete' | upstream_code | examples/demo_cart_pole_learning.py:19 |
| In the discrete action mapping action 0 applies zero force, action 1 applies +1.0 and action 2 applies -1.0 | upstream_code | CartPole/CartPoleEnv.py:84-90 |
| For a continuous action the push force is action*2.0, so the action range -1.0 to 1.0 maps to -2.0 to 2.0 | upstream_code | CartPole/CartPoleEnv.py:91-92 |
| The failure thresholds are a cart position of 0.8 and a pole angle of 40*pi/360 rad | upstream_code | CartPole/CartPoleEnv.py:24-25 |
| The episode ends when the cart position reaches +-0.8 or the pole angle leaves +-40*pi/360 rad | upstream_code | CartPole/CartPoleEnv.py:99 |
| The observation is [cart position, pole angle, cart linear velocity, pole angular velocity] | upstream_code | CartPole/CartPoleEnv.py:119-121 |
| Joint velocities are computed by dividing the position change by a 0.005 s interval | upstream_code | CartPole/CartPoleEnv.py:119-120 |
| A reset draws the four state values uniformly from -0.05 to 0.05 | upstream_code | CartPole/CartPoleEnv.py:133 |
| Every step that is not done pays reward 1.0; the first step after done pays 1.0 and later steps pay 0.0 | upstream_code | CartPole/CartPoleEnv.py:102-117 |
| The reset stops and restarts the CoppeliaSim simulation and sets the joint torque to zero | upstream_code | CartPole/CartPoleEnv.py:136-141 |
| The environment connects to the remote API server at 127.0.0.1 on port 19997 and runs it in synchronous mode | upstream_code | CartPole/CartPoleEnv.py:52-64 |
| Each step triggers one synchronous simulation advance and waits for its ping time | upstream_code | CartPole/CartPoleEnv.py:124-125 |
| The joint driver sets the prismatic joint target velocity to +-1000 and its maximum force to abs(torque) | upstream_code | CartPole/CartPoleSimModel.py:57-63 |
| Joint positions are read from the prismatic and revolute joints through the remote API buffer mode | upstream_code | CartPole/CartPoleSimModel.py:43-51 |
| The remote API wrapper loads a platform-specific remoteApi library (remoteApi.so, .dll or .dylib) next to sim.py | upstream_code | VREP_RemoteAPIs/sim.py:14-20 |
| CartPoleEnv.close stops the simulation and finishes all remote API connections | upstream_code | CartPole/CartPoleEnv.py:149-152 |

Limits: the driver declares none. The only bound is the discrete action space, which the gymnasium bridge derives
from the fake environment's `action_space` (`Discrete(3)`: `action.index` from 0 to 2, source `upstream_code`, ref
`CartPole/CartPoleEnv.py:38`) and the `ticks` bound (1 to `max_ticks`, 10000 by default). The device is
simulated (R0), so no limit is `operator_required` and there is no hardware stop.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `coppeliasim`, level F1 (rigid-body dynamics in the
CoppeliaSim engine; the binary scene's contact, friction and actuator parameters are not stated in the clone),
determinism `seeded` with `seed_control` `parameter`, timestep 5 ms (the interval the upstream velocity computation
uses, `CartPoleEnv.py:119-120`; the scene setting itself was not read), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled, that the fake's dynamics are placeholders and
that the fake was never compared with a running CoppeliaSim.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the upstream has no stop command beyond
stopping the simulation); after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the
state stays readable.

Tags: cartpole, coppeliasim, reinforcement-learning, simulation, gym
