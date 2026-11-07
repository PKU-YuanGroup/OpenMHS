# Facts and tags for gh.pku-alignment/safety-gymnasium

Every fact cites its source at commit `ae966e511b9927f06b39c727ca5c650136a4e696`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README runs the Point Goal1 task as SafetyPointGoal1-v0 and states that its step returns (observation, reward, cost, terminated, truncated, info) | vendor_doc | README.md:483-494 |
| The README also documents the standard Gymnasium id SafetyPointGoal1Gymnasium-v0, whose step returns five items without the separate cost | vendor_doc | README.md:547-554 |
| Each task is also registered in the Gymnasium registry under a Gymnasium suffix, served by the conversion wrapper make_gymnasium_environment | upstream_code | safety_gymnasium/__init__.py:61-66 |
| The conversion wrapper calls the Safety-Gymnasium environment and returns (observation, reward, terminated, truncated, info), putting cost into info | upstream_code | safety_gymnasium/wrappers/gymnasium_conversion.py:26-34 |
| The Goal task family registers Goal0, Goal1 and Goal2 for all robots with max_episode_steps 1000 | upstream_code | safety_gymnasium/__init__.py:136-137 |
| A registered task uses the entry point safety_gymnasium.builder:Builder | upstream_code | safety_gymnasium/__init__.py:80 |
| Builder is the gymnasium.Env subclass that the registered task instantiates | upstream_code | safety_gymnasium/builder.py:55 |
| Builder builds the task and seeds it during setup | upstream_code | safety_gymnasium/builder.py:141-144 |
| Builder.reset resets the task and returns (observation, info) | upstream_code | safety_gymnasium/builder.py:180-191 |
| Builder.step applies one action, computes reward and cost, increments the step count and returns the six Safety-Gymnasium items | upstream_code | safety_gymnasium/builder.py:193-251 |
| BaseTask defaults the episode length to 1000 environment steps | upstream_code | safety_gymnasium/bases/base_task.py:181 |
| Builder truncates when the step count reaches task.num_steps | upstream_code | safety_gymnasium/builder.py:244-247 |
| Observation flattening is enabled by default | upstream_code | safety_gymnasium/bases/underlying.py:224 |
| The flattened observation space is built with flatten_space when observation_flatten is true | upstream_code | safety_gymnasium/bases/base_task.py:270-275 |
| The agent sensors are accelerometer, velocimeter, gyro and magnetometer | upstream_code | safety_gymnasium/bases/base_agent.py:49 |
| Lidar uses 16 bins | upstream_code | safety_gymnasium/bases/base_task.py:47 |
| A lidar-observed obstacle adds a Box(0.0, 1.0, (num_bins,)) to the observation space | upstream_code | safety_gymnasium/bases/base_task.py:239-247 |
| The Point action space is a Box built from the model's actuator_ctrlrange | upstream_code | safety_gymnasium/bases/base_agent.py:227-234 |
| The point model has two actuators, a motor named x and a velocity actuator named z | upstream_code | safety_gymnasium/assets/xmls/point.xml:54-56 |
| The point model default ctrlrange for both the motor and velocity actuators is -1 to 1 | upstream_code | safety_gymnasium/assets/xmls/point.xml:24-25 |
| The point model physics timestep is 0.002 s | upstream_code | safety_gymnasium/assets/xmls/point.xml:19 |
| The default frameskip is a binomial draw of 10 trials at probability 1.0 | upstream_code | safety_gymnasium/bases/underlying.py:95-96 |
| simulation_forward steps MuJoCo once per drawn frameskip | upstream_code | safety_gymnasium/bases/underlying.py:345-355 |
| Goal level 0 places the goal in the [-1, -1, 1, 1] extent with keepout 0.305 | upstream_code | safety_gymnasium/tasks/safe_navigation/goal/goal_level0.py:27-29 |
| Goal level 1 widens the placement extent to [-1.5, -1.5, 1.5, 1.5] and adds 8 hazards and one vase | upstream_code | safety_gymnasium/tasks/safe_navigation/goal/goal_level1.py:31-34 |
| The goal radius is 0.3, the sparse goal reward is 1.0 and the dense distance reward is 1.0 | upstream_code | safety_gymnasium/assets/geoms/goal.py:31-40 |
| An episode terminates when the distance to the goal is at most the goal size | upstream_code | safety_gymnasium/tasks/safe_navigation/goal/goal_level0.py:57-61 |
| A hazard has radius 0.2 and a cost coefficient of 1.0 | upstream_code | safety_gymnasium/assets/geoms/hazards.py:32-37 |

## Limits

The driver declares no limit of its own. The only bound is the step action, and the bridge derives it from the
environment's action space: the point model gives its two actuators the default ctrlrange -1 to 1
(`safety_gymnasium/assets/xmls/point.xml:24-25`), so `action.values` is two values each in [-1, 1]. The model file
states the bound, so no limit is `operator_required` and no `site-limits.json` is needed.

## Fidelity contract

`driver.py` declares engine `gymnasium:SafetyPointGoal1Gymnasium-v0`, level F0 (the fake is a kinematic point model,
not MuJoCo), determinism `seeded` with `seed_control` `parameter`, `timestep_ms` 20.0 (one environment step), 
`realtime_factor` 0, clock `lockstep`, reset `full` and no snapshot/restore. The gaps say what is not modelled: the
MuJoCo rigid-body dynamics and contacts, the analytic stand-in for the sensor and lidar values, the 10 physics
substeps of 2 ms per upstream environment step, the layout RNG, rendering, vision, vase costs and validation.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch (the environment has no native stop); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and
the world state stays readable.

Tags: goal, gymnasium, mujoco, point, reinforcement-learning, safety-gymnasium, simulation
