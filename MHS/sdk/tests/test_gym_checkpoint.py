"""Protocol checkpoints through the production family/server/client, controlled natives only."""
import copy
import threading
import unittest

from mhs import canonical
from mhs.bridge.gym_checkpoint import bounded_json, JsonCheckpoint
from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import GymnasiumDriver, DriverDefinitionError, build_manifest, build_server, close_server
from mhs.errors import MHSError
from mhs.schema import default_store
from tests.bridges import support
from tests.bridges.test_gymnasium_timing import ClockEnv, CONFIG

PROFILE = {"profile": "json_state_v1", "getter": "get_state", "setter": "set_state"}
STEP = "cap.world.step.v1"
RESET = "cap.world.reset.v1"
SEED = "cap.world.seed.v1"


class Stateful(support.FakeCartPole):
    def __init__(self):
        super().__init__(terminate_after=1000)
        self.rng = 11
        self.setters = 0
        self.fail_setters = 0
        self.get_hook = self.set_hook = None
        self.bad_state = None
        self.fail_step = False

    def reset(self, seed=None, options=None):
        self.rng = seed if seed is not None else self.rng
        return super().reset(seed=seed, options=options)

    def step(self, action):
        self.rng = (self.rng * 17 + 5) % 65521
        observation, _, terminated, truncated, info = super().step(action)
        if self.fail_step:
            raise RuntimeError("after native advancement")
        return observation, self.rng / 65521, terminated, truncated, {"rng": self.rng}

    def get_state(self):
        if self.get_hook:
            self.get_hook()
        if self.bad_state is not None:
            return self.bad_state
        return {**super().get_state(), "rng": self.rng}

    def set_state(self, state):
        self.setters += 1
        if self.set_hook:
            self.set_hook()
        super().set_state(state)
        self.rng = state["rng"]
        if self.fail_setters:
            self.fail_setters -= 1
            self.state[0] = 99.0
            raise RuntimeError("after partial mutation")


class CheckpointTests(unittest.TestCase):
    def make(self, native=None, *, profile=PROFILE, timing=None, budget=None):
        native = native or Stateful()
        class Environment(GymnasiumDriver):
            device_id = "checkpoint/world"
            backends = {"fake": lambda: native}
            checkpoint_by_backend = {"fake": copy.deepcopy(profile)} if profile else {}
            timing_by_backend = {"fake": copy.deepcopy(timing)} if timing else {}
            safe_state = "software simulation pause"
        driver = Environment(backend="fake")
        if budget is not None:
            driver.inner._max_steps = budget
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        device = next(iter(server.devices))
        client.open_session([device], mode="simulated")
        return native, driver, server, client, device

    def command(self, client, device, cap=STEP, payload=None, **kwargs):
        return client.invoke(cap, payload if payload is not None else {"ticks": 1, "action": {"index": 1}},
                              device_id=device, **kwargs)

    def rehash(self, snapshot):
        snapshot["snapshot"] = copy.deepcopy(snapshot["state"])
        snapshot["snapshot_digest"] = canonical.digest(snapshot["state"])
        snapshot["state_hash"] = canonical.state_hash(snapshot["state"]["world"])
        return snapshot

    def raw(self, client, device, method, **params):
        return client.request(method, {"session_id": client.session_id, "device_id": device,
                                       "deadline_ms": 1000, **params})

    def test_stock_roundtrip_hash_identity_rng_and_schema(self):
        native, driver, server, client, device = self.make()
        self.command(client, device, RESET, {"seed": 3})
        self.command(client, device)
        snapshot = client.snapshot(device)
        self.assertEqual(default_store().validate(snapshot, "snapshot.schema.json"), [])
        self.assertEqual(snapshot["state"]["world"], client.read("world", device_id=device)["state"])
        self.assertEqual(snapshot["state_hash"], canonical.state_hash(snapshot["state"]["world"]))
        self.assertEqual(snapshot["snapshot_digest"], canonical.digest(snapshot["state"]))
        advance = self.command(client, device)
        expected = advance["output"]
        self.assertEqual(expected["state_hash"], advance["state_hash_after"])
        self.assertEqual(expected["state_hash"], client.read("world", device_id=device)["state_hash"])
        restored = client.restore(snapshot, device)
        self.assertEqual(restored["status"], "completed", restored)
        self.assertEqual(client.read("world", device_id=device)["state"], snapshot["state"]["world"])
        self.assertEqual(self.command(client, device)["output"], expected)
        manifest = build_manifest(driver)
        self.assertIn("native_checkpoint", manifest["resources"][0]["state_schema"]["properties"])
        self.assertEqual(manifest["fidelity"]["determinism"]["kind"], "seeded")
        self.assertTrue(manifest["fidelity"]["snapshot_restore"])

    def test_pending_seed_and_normalized_observation_survive(self):
        native, driver, server, client, device = self.make()
        self.command(client, device, RESET, {"seed": 3})
        self.command(client, device, SEED, {"seed": 19})
        snapshot = client.snapshot(device)
        self.command(client, device, SEED, {"seed": 71})
        self.command(client, device, RESET, {})
        self.assertEqual(client.restore(snapshot, device)["status"], "completed")
        reset = self.command(client, device, RESET, {})
        self.assertEqual(reset["output"]["seed"], 19)
        self.assertEqual(native.seeds[-1], 19)
        self.assertEqual(driver.inner._total_steps, 0)

    def test_envelope_identity_alias_digest_and_resource_refusals_are_pre_effect(self):
        native, driver, server, client, device = self.make()
        self.command(client, device, RESET, {})
        snapshot = client.snapshot(device)
        changes = [lambda x: x.pop("snapshot_digest"),
                   lambda x: x.update(snapshot_digest="sha256:" + "0" * 64),
                   lambda x: x["snapshot"]["world"].update(tick=100),
                   lambda x: x.update(instance_id=canonical.ulid()),
                   lambda x: x.update(device_id="mhs://localhost/other"),
                   lambda x: x.update(mode="hybrid"),
                   lambda x: x.update(fidelity_digest="sha256:" + "0" * 64),
                   lambda x: x.update(revision=True),
                   lambda x: x.update(extra="undeclared"),
                   lambda x: x["state"].update(unknown={})]
        for mutate in changes:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(snapshot); mutate(changed)
                result = client.restore(changed, device)
                self.assertEqual(result["status"], "rejected", result)
                self.assertEqual(native.setters, 0)

    def test_state_fields_and_profile_are_checked_even_with_recomputed_hashes(self):
        native, driver, server, client, device = self.make()
        self.command(client, device, RESET, {})
        snapshot = client.snapshot(device)
        changes = [lambda w: w.update(tick=True), lambda w: w.update(episode=-1),
                   lambda w: w.update(seed=-1), lambda w: w.update(reward="0"),
                   lambda w: w.update(terminated=0), lambda w: w.update(observation=[]),
                   lambda w: w["native_checkpoint"].update(configuration_digest="sha256:" + "0" * 64),
                   lambda w: w["native_checkpoint"].update(pending_seed=True),
                   lambda w: w["native_checkpoint"].update(total_steps=0)]
        for mutate in changes:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(snapshot); mutate(changed["state"]["world"]);self.rehash(changed)
                self.assertEqual(client.restore(changed, device)["status"], "rejected")
                self.assertEqual(native.setters, 0)

    def test_alias_only_snapshot_is_supported_but_not_conflicting_alias(self):
        native, driver, server, client, device = self.make()
        self.command(client, device, RESET, {})
        snapshot = client.snapshot(device);snapshot.pop("state")
        self.assertEqual(client.restore(snapshot, device)["status"], "completed")

    def test_lifetime_budget_does_not_rewind_across_restore_reset_or_failed_step(self):
        native, driver, server, client, device = self.make(budget=3)
        self.command(client, device, RESET, {})
        snapshot = client.snapshot(device)
        self.command(client, device, payload={"ticks": 2, "action": {"index": 1}})
        native.fail_step = True
        self.assertNotEqual(self.command(client, device)["status"], "completed")
        native.fail_step = False
        self.assertEqual(driver.inner._total_steps, 3)
        for _ in range(2):
            self.assertEqual(client.restore(snapshot, device)["status"], "completed")
            self.command(client, device, RESET, {})
            result = self.command(client, device)
            self.assertNotEqual(result["status"], "completed")
            self.assertEqual(native.native_steps, 3)
            self.assertEqual(driver.inner._total_steps, 3)

    def test_partial_setter_failure_verified_rollback_vs_unknown(self):
        for failures, expected in [(1, "failed"), (2, "unknown")]:
            with self.subTest(failures=failures):
                native, driver, server, client, device = self.make()
                self.command(client, device, RESET, {})
                snapshot = client.snapshot(device)
                self.command(client, device)
                before = client.read("world", device_id=device)["state"]
                native.fail_setters = failures
                result = client.restore(snapshot, device)
                self.assertEqual(result["status"], expected, result)
                self.assertEqual(native.setters, 2)
                if expected == "failed":
                    self.assertEqual(client.read("world", device_id=device)["state"], before)

    def test_no_profile_refuses_and_does_not_infer_exact(self):
        native, driver, server, client, device = self.make(profile=None)
        manifest = build_manifest(driver)
        self.assertFalse(manifest["fidelity"]["snapshot_restore"])
        self.assertEqual(manifest["fidelity"]["determinism"]["kind"], "seeded")
        self.assertNotIn("native_checkpoint", client.read("world", device_id=device)["state"])
        with self.assertRaises(MHSError):client.snapshot(device)
        with self.assertRaises(MHSError):driver.inner.snapshot()
        self.assertEqual(native.setters, 0)
        class Contradiction(GymnasiumDriver):
            device_id="contradiction"
            backends={"fake":Stateful}
            fidelity={"snapshot_restore":True}
        with self.assertRaisesRegex(DriverDefinitionError, "checkpoint_by_backend"):
            Contradiction(backend="fake")

    def test_native_json_rejects_coercion_cycles_nonfinite_and_limits(self):
        native, driver, server, client, device = self.make(profile={**PROFILE, "max_bytes": 1024})
        cycle=[];cycle.append(cycle)
        values=[{1:"lost key"}, (1,2), object(), {"v":float("nan")}, cycle,
                {"v":"x"*1025}, {"v":"\ud800"}, {"v":2**53}]
        deep=[];current=deep
        for _ in range(35):current.append([]);current=current[0]
        values.append(deep)
        for value in values:
            with self.subTest(kind=type(value).__name__):
                native.bad_state=value
                with self.assertRaises(MHSError):driver.inner.snapshot()
        native.bad_state=None
        self.assertEqual(native.setters, 0)
        for value in ({**PROFILE,"max_bytes":True},{**PROFILE,"max_bytes":2**30},
                      {**PROFILE,"getter":"__dict__"},{**PROFILE,"extra":True}):
            with self.assertRaises(ValueError):JsonCheckpoint.resolve(value)

    def test_profile_is_copied_and_backend_projection_is_bound(self):
        config=copy.deepcopy(PROFILE)
        class Env(GymnasiumDriver):
            device_id="profile"
            backends={"fake":Stateful,"sim":Stateful}
            checkpoint_by_backend={"fake":config}
        driver=Env(backend="fake");self.addCleanup(driver.close)
        digest=driver.inner._checkpoint.digest
        config["getter"]="wrong"
        self.assertEqual(driver.inner._checkpoint.digest,digest)
        with self.assertRaises(DriverDefinitionError):build_manifest(driver,backend="sim")

    def test_timed_checkpoint_preserves_verified_clock_and_budget(self):
        native,driver,server,client,device=self.make(ClockEnv(),timing=CONFIG,budget=3)
        self.command(client,device,RESET,{})
        self.command(client,device,payload={"ticks":5,"action":{"index":1}})
        snapshot=client.snapshot(device)
        self.command(client,device,payload={"ticks":5,"action":{"index":1}})
        self.assertEqual(client.restore(snapshot,device)["status"],"completed")
        self.assertEqual(native.data.time,snapshot["state"]["world"]["native_checkpoint"]["physics_clock"])
        self.assertEqual(driver.inner._total_steps,2)
        changed=copy.deepcopy(snapshot);changed["state"]["world"]["native_checkpoint"]["physics_clock"]=True
        self.rehash(changed);before=native.restores
        self.assertEqual(client.restore(changed,device)["status"],"rejected")
        self.assertEqual(native.restores,before)

    def test_native_setter_cannot_rewrite_expected_document_by_mutating_argument(self):
        native,driver,server,client,device=self.make()
        self.command(client,device,RESET,{})
        snapshot=client.snapshot(device)
        def mutate(state):
            state["state"][0]=99
            native.state=list(state["state"])
        native.set_state=mutate
        result=client.restore(snapshot,device)
        self.assertNotEqual(result["status"],"completed")
        self.assertEqual(snapshot["state"]["world"]["native_checkpoint"]["native_state"]["state"][0],0)

    def test_timeout_retains_mutation_lane_until_actual_setter_finishes(self):
        native,driver,server,client,device=self.make()
        self.command(client,device,RESET,{})
        snapshot=client.snapshot(device)
        self.command(client,device)
        entered,release,finished=threading.Event(),threading.Event(),threading.Event()
        def block():
            entered.set();self.assertTrue(release.wait(3))
        native.set_hook=block
        command_id=canonical.ulid(); errors=[]
        def restore():
            try:self.raw(client,device,"mhs.restore",snapshot=snapshot,command_id=command_id,deadline_ms=25)
            except MHSError as exc:errors.append(exc)
            finally:finished.set()
        thread=threading.Thread(target=restore);thread.start()
        try:
            self.assertTrue(entered.wait(1));self.assertTrue(finished.wait(1))
            self.assertEqual(errors[0].code,"MHS.OUTCOME.TIMEOUT")
            # Before native completion, a separate command cannot acquire ownership.
            self.assertFalse(server._device_locks[device].acquire(blocking=False))
            self.assertEqual(native.native_steps,1)
        finally:release.set();thread.join(2)
        # Deterministic barrier: the native worker owns this lock through publication.
        self.assertTrue(server._device_locks[device].acquire(timeout=2));server._device_locks[device].release()
        replay=client.restore(snapshot,device,command_id=command_id)
        self.assertEqual(replay["status"],"completed",replay)
        self.assertTrue(replay["replayed"])
        self.assertEqual(native.setters,1)

    def test_estop_is_independent_and_safety_reset_cannot_release_running_restore(self):
        native, driver, server, client, device = self.make()
        self.command(client, device, RESET, {})
        snapshot = client.snapshot(device)
        entered, release, done = threading.Event(), threading.Event(), threading.Event()
        holder = {}
        def block():
            entered.set()
            self.assertTrue(release.wait(3))
        native.set_hook = block
        def restore():
            try:
                holder["result"] = client.restore(snapshot, device)
            finally:
                done.set()
        thread = threading.Thread(target=restore)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            stop = client.estop("checkpoint review", device, deadline_ms=40)
            self.assertFalse(stop["output"]["safe_state_achieved"], stop)
            self.assertTrue(server._latched[device])
            try:
                reset = self.raw(client, device, "mhs.safety.reset", deadline_ms=40)
                self.assertNotEqual(reset["status"], "completed")
            except MHSError as exc:
                self.assertEqual(exc.code, "MHS.OUTCOME.TIMEOUT")
            self.assertTrue(server._latched[device])
            self.assertFalse(done.is_set())
        finally:
            release.set()
            thread.join(2)
        self.assertTrue(done.is_set())
        self.assertEqual(holder["result"]["status"], "unknown")
        self.assertTrue(server._latched[device])
        steps = native.native_steps
        self.assertNotEqual(self.command(client, device)["status"], "completed")
        self.assertEqual(native.native_steps, steps)

    def test_capture_excludes_command_and_restore_until_worker_releases(self):
        native, driver, server, client, device = self.make()
        self.command(client, device, RESET, {})
        saved = client.snapshot(device)
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        holder = {}
        def block():
            entered.set()
            self.assertTrue(release.wait(3))
        native.get_hook = block
        def capture():
            try:
                holder["snapshot"] = client.snapshot(device)
            finally:
                finished.set()
        thread = threading.Thread(target=capture)
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            command = self.command(client, device, deadline_ms=200)
            self.assertNotEqual(command["status"], "completed", command)
            self.assertEqual(native.native_steps, 0)
            try:
                result = self.raw(client, device, "mhs.restore", snapshot=saved, deadline_ms=40)
                self.assertNotEqual(result["status"], "completed")
            except MHSError as exc:
                self.assertEqual(exc.code, "MHS.OUTCOME.TIMEOUT")
            self.assertEqual(native.setters, 0)
            self.assertFalse(finished.is_set())
        finally:
            native.get_hook = None
            release.set()
            thread.join(2)
        self.assertTrue(finished.is_set())
        self.assertEqual(holder["snapshot"]["state_hash"], client.read("world", device_id=device)["state_hash"])

    def test_mujoco_native_only_checkpoint_is_refused_at_capture_and_before_setter(self):
        from tests.driver.test_families import Pendulums
        driver = Pendulums(backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        client.hello()
        device = next(iter(server.devices))
        client.open_session([device], mode="simulated")
        client.invoke(STEP, {"ticks": 2, "action": {"ctrl": [0.5, 0.1]}}, device_id=device)
        # Preserve the invalid pre-repair wire shape as a negative fixture even
        # when the MuJoCo bridge itself supplies a conforming checkpoint.
        checkpoint = driver.snapshot()["world"]["native_checkpoint"]
        native_only = {"world": {"integration_state": checkpoint["values"],
                                  "spec": "mjSTATE_INTEGRATION", "tick": 2, "seed": 0}}
        driver.snapshot = lambda device_id=None: copy.deepcopy(native_only)
        raw = driver.snapshot()
        before = driver.native.calls.count("mj_setState")
        with self.assertRaises(MHSError) as caught:
            client.snapshot(device)
        self.assertEqual(caught.exception.code, "MHS.RESOURCE.STATE_INVALID")
        manifest = client.inspect(device)
        forged = {"device_id": device, "instance_id": manifest["instance_id"], "mode": "simulated",
                  "revision": 1, "state": raw, "snapshot": copy.deepcopy(raw),
                  "state_hash": canonical.state_hash(raw["world"]),
                  "snapshot_digest": canonical.digest(raw),
                  "fidelity_digest": canonical.digest(manifest["fidelity"])}
        receipt = client.restore(forged, device)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.RESOURCE.STATE_INVALID")
        self.assertEqual(driver.native.calls.count("mj_setState"), before)

    def test_missing_or_async_methods_refuse_and_deferred_setter_never_succeeds(self):
        import concurrent.futures
        native = Stateful()
        async def async_set(state):
            raise AssertionError("must not execute")
        native.set_state = async_set
        with self.assertRaises(MHSError):
            GymnasiumBridge(env=native, checkpoint=PROFILE)
        with self.assertRaises(MHSError):
            GymnasiumBridge(env=Stateful(), checkpoint={**PROFILE, "setter": "missing"})
        native, driver, server, client, device = self.make()
        self.command(client, device, RESET, {})
        snapshot = client.snapshot(device)
        pending = concurrent.futures.Future()
        native.set_state = lambda state: pending
        result = client.restore(snapshot, device)
        self.assertEqual(result["status"], "unknown")
        self.assertIsNotNone(driver.inner._checkpoint_fault)
        for cap, payload in [(STEP, {"ticks":1,"action":{"index":1}}), (RESET, {}), (SEED,{"seed":3})]:
            self.assertNotEqual(self.command(client, device, cap, payload)["status"], "completed")
        self.assertEqual(native.native_steps, 0)
        client.estop("unsupported async setter", device)
        self.assertNotEqual(client.reset(device)["status"], "completed")
        self.assertTrue(server._latched[device])
        pending.set_result(None)  # even eventual completion does not silently clear the fault
        self.assertNotEqual(self.command(client, device)["status"], "completed")

    def test_descriptor_resolution_and_rollback_keep_original_stop_admission(self):
        import inspect
        for phase in ("restore", "rollback", "previous_snapshot"):
            with self.subTest(phase=phase):
                entered, release = threading.Event(), threading.Event()
                class DescriptorNative(Stateful):
                    arm = False
                    @property
                    def set_state(self):
                        stack = inspect.stack()
                        in_restore = any(f.function == "restore" and f.filename.endswith("/bridge/gymnasium.py")
                                         for f in stack)
                        ready = phase == "restore" or (phase == "rollback" and self.setters == 1)
                        if self.arm and in_restore and ready:
                            self.arm = False
                            entered.set()
                            if not release.wait(3):raise RuntimeError("descriptor release timeout")
                        return super().set_state
                    def get_state(self):
                        if self.arm and phase == "previous_snapshot":
                            self.arm = False
                            entered.set()
                            if not release.wait(3):raise RuntimeError("getter release timeout")
                        return super().get_state()
                native,driver,server,client,device = self.make(DescriptorNative())
                self.command(client,device,RESET,{})
                snapshot=client.snapshot(device)
                self.command(client,device)
                if phase == "rollback":native.fail_setters=1
                native.arm=True
                result={}
                def restoring():result["receipt"]=client.restore(snapshot,device)
                thread=threading.Thread(target=restoring);thread.start()
                try:
                    self.assertTrue(entered.wait(1))
                    stop=client.estop("descriptor barrier",device,deadline_ms=50)
                    self.assertFalse(stop["output"]["safe_state_achieved"])
                    self.assertNotEqual(client.reset(device)["status"],"completed")
                    self.assertTrue(server._latched[device])
                    self.assertTrue(thread.is_alive())
                finally:
                    release.set();thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertEqual(native.setters,1 if phase == "rollback" else 0)
                self.assertNotEqual(result["receipt"]["status"],"completed")
                self.assertTrue(server._latched[device])
                steps=native.native_steps
                self.assertNotEqual(self.command(client,device)["status"],"completed")
                self.assertEqual(native.native_steps,steps)

    def test_real_pending_setter_cannot_acknowledge_safe_state_before_or_after_completion(self):
        import concurrent.futures
        release=threading.Event()
        class Pending(Stateful):
            armed=False
            worker=None
            pending=concurrent.futures.Future()
            def set_state(self,state):
                if not self.armed:return super().set_state(state)
                def later():
                    if not release.wait(3):raise RuntimeError("native completion release timeout")
                    super(Pending,self).set_state(state)
                    self.pending.set_result(None)
                self.worker=threading.Thread(target=later)
                self.worker.start()
                return self.pending
        native,driver,server,client,device=self.make(Pending())
        self.command(client,device,RESET,{})
        snapshot=client.snapshot(device)
        self.command(client,device)
        native.armed=True
        try:
            self.assertEqual(client.restore(snapshot,device)["status"],"unknown")
            self.assertFalse(native.pending.done())
            stop=client.estop("unsupported completion",device,deadline_ms=50)
            self.assertFalse(stop["output"]["safe_state_achieved"])
            self.assertNotEqual(stop["status"],"completed")
            self.assertNotEqual(client.reset(device)["status"],"completed")
            self.assertEqual(native.state[0],0.1)
        finally:
            release.set()
            if native.worker:native.worker.join(2)
        self.assertEqual(native.state[0],0.0)
        self.assertTrue(native.pending.done())
        self.assertFalse(client.estop("completion is not recovery",device)["output"]["safe_state_achieved"])
        self.assertNotEqual(client.reset(device)["status"],"completed")
        self.assertTrue(server._latched[device])

    def test_profile_native_step_in_progress_cannot_acknowledge_pause_early(self):
        native,driver,server,client,device=self.make()
        self.command(client,device,RESET,{})
        entered,release=threading.Event(),threading.Event()
        step=native.step
        def blocked(action):
            entered.set()
            if not release.wait(3):raise RuntimeError("step release timeout")
            return step(action)
        native.step=blocked
        result={}
        thread=threading.Thread(target=lambda:result.update(step=self.command(client,device)))
        thread.start()
        try:
            self.assertTrue(entered.wait(1))
            stopped=client.estop("opaque step",device,deadline_ms=50)
            self.assertFalse(stopped["output"]["safe_state_achieved"])
            self.assertTrue(server._latched[device])
        finally:
            release.set();thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(native.native_steps,1)
        self.assertTrue(client.estop("worker has completed",device)["output"]["safe_state_achieved"])


    def test_stock_close_defers_cleanup_until_synchronous_native_work_finishes(self):
        for phase in ("restore", "snapshot", "step", "reset"):
            with self.subTest(phase=phase):
                class Closing(Stateful):
                    def __init__(self):
                        super().__init__()
                        self.active = False
                        self.close_overlap = False
                        self.close_count = 0
                    def close(self):
                        self.close_count += 1
                        self.close_overlap |= self.active
                        super().close()
                native,driver,server,client,device=self.make(Closing())
                self.command(client,device,RESET,{})
                saved=client.snapshot(device)
                entered,release=threading.Event(),threading.Event()
                method={"restore":"set_state","snapshot":"get_state","step":"step","reset":"reset"}[phase]
                original=getattr(native,method)
                def blocked(*args,**kwargs):
                    native.active=True;entered.set()
                    try:
                        if not release.wait(3):raise RuntimeError("release timeout")
                        return original(*args,**kwargs)
                    finally:native.active=False
                setattr(native,method,blocked)
                result={}
                def run():
                    try:
                        if phase=="restore":result["receipt"]=client.restore(saved,device)
                        elif phase=="snapshot":result["receipt"]=client.snapshot(device)
                        elif phase=="step":result["receipt"]=self.command(client,device,payload={"ticks":3,"action":{"index":1}})
                        else:result["receipt"]=self.command(client,device,RESET,{})
                    except Exception as exc:result["error"]=repr(exc)
                thread=threading.Thread(target=run);thread.start()
                try:
                    self.assertTrue(entered.wait(1))
                    close_server(server)
                    self.assertTrue(driver.inner.closed)
                    self.assertEqual(native.close_count,0)
                    self.assertFalse(native.close_overlap)
                    self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
                    for call in (lambda:driver.inner.call(STEP,{"ticks":1,"action":{"index":1}}),
                                 driver.inner.snapshot,lambda:driver.inner.restore(saved["state"]),
                                 lambda:driver.inner.call(SEED,{"seed":9})):
                        with self.assertRaises(Exception):call()
                finally:
                    release.set();thread.join(3)
                self.assertFalse(thread.is_alive())
                self.assertTrue(driver.inner._cleanup_done.wait(2))
                self.assertEqual(native.close_count,1)
                self.assertFalse(native.close_overlap)
                driver.inner.close();close_server(server)
                self.assertEqual(native.close_count,1)
                if phase=="step":self.assertEqual(native.native_steps,1)

    def test_close_fences_a_call_admitted_before_waiting_for_native_lock(self):
        entered=threading.Event()
        class Space(Stateful):
            armed=False
            @property
            def action_space(self):
                if self.armed:entered.set()
                return self._action_space
            @action_space.setter
            def action_space(self,value):self._action_space=value
        native,driver,server,client,device=self.make(Space())
        self.command(client,device,RESET,{})
        result={}
        def run():
            try:result["value"]=driver.inner.call(STEP,{"ticks":1,"action":{"index":1}})
            except Exception as exc:result["error"]=repr(exc)
        with driver.inner._lock:
            native.armed=True
            thread=threading.Thread(target=run);thread.start()
            self.assertTrue(entered.wait(1))
            driver.inner.close()
            self.assertTrue(driver.inner.closed)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertIn("error",result)
        self.assertEqual(native.native_steps,0)
        self.assertTrue(driver.inner._cleanup_done.wait(2))

    def test_close_does_not_infer_unsupported_setter_completion_or_cleanup(self):
        import concurrent.futures
        release=threading.Event()
        class Pending(Stateful):
            def __init__(self):
                super().__init__();self.close_count=0;self.worker=None
            def set_state(self,state):
                future=concurrent.futures.Future()
                def finish():
                    if not release.wait(3):return
                    super(Pending,self).set_state(state)
                    future.set_result(None)
                self.worker=threading.Thread(target=finish);self.worker.start()
                return future
            def close(self):self.close_count+=1
        native,driver,server,client,device=self.make(Pending())
        self.command(client,device,RESET,{})
        saved=client.snapshot(device)
        try:
            self.assertEqual(client.restore(saved,device)["status"],"unknown")
            close_server(server)
            self.assertTrue(driver.inner.closed)
            self.assertEqual(native.close_count,0)
        finally:
            release.set()
            if native.worker:native.worker.join(2)
        self.assertEqual(native.setters,1)
        driver.inner.close()
        self.assertEqual(native.close_count,0)
        self.assertFalse(driver.inner._cleanup_done.is_set())
        self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])


    def test_close_fence_precedes_blocked_native_cleanup_and_is_exactly_once(self):
        entered,release=threading.Event(),threading.Event()
        class SlowClose(Stateful):
            def __init__(self):super().__init__();self.close_count=0
            def close(self):
                self.close_count+=1;entered.set()
                if not release.wait(3):raise RuntimeError("close release timeout")
                super().close()
        native,driver,server,client,device=self.make(SlowClose())
        thread=threading.Thread(target=driver.inner.close);thread.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertTrue(driver.inner.closed)
            self.assertFalse(driver.inner.safety_status()["safe_state"]["achieved"])
            with self.assertRaises(Exception):driver.inner.call(STEP,{"ticks":1,"action":{"index":1}})
            driver.inner.close()
            self.assertEqual(native.close_count,1)
            self.assertEqual(native.native_steps,0)
        finally:release.set();thread.join(2)
        self.assertTrue(driver.inner._cleanup_done.wait(1))
        self.assertEqual(native.close_count,1)


if __name__ == '__main__':unittest.main()
