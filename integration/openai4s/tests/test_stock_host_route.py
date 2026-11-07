"""LEAD-HOST-PATH: the governed MHS path through the real OpenAI4S host route.

No mocked dispatcher, gate, journal or ledger: the production ``HostDispatcher``
and ``MCPService`` resolve a real connector row and ``MCPManager`` spawns the
real ``mhs.mcp`` stdio server against a loopback reference endpoint.  The only
substitutions are the local simulator (there is no hardware) and the permission
broker, which is the exact input of the denied-approval scenario.

The route exists only on an OpenAI4S tree with ``openai4s-core.patch``
applied; on an unpatched tree the class is skipped with that reason.
Permits and resets go through the host operator route, never the agent row.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from mhs import canonical
from mhs.mcp import projection_tool_name
from openai4s.config import get_config
from openai4s.host_dispatch import HostDispatcher
from openai4s.mcp_client import manager as global_mcp_manager
from openai4s.tools.mcp import CallMCPTool

from openai4s_mhs.config import MHSConfig
from openai4s_mhs.host_evidence import HostLedger, verify_package
from openai4s_mhs.hostroute import export_host_package
from openai4s_mhs.mcp_invoke import MCPConnector, MCPInvokeError, invoke, reconcile
from openai4s_mhs.mcpconfig import connector_entries
from openai4s_mhs.operator_route import OperatorRoute
from openai4s_mhs.operator_route import reset as operator_reset

from .hardware_endpoint import start_endpoint
from .host_remediation_support import connector_env, write_settings
from .support import sdk_projection_available

CAPABILITY = "cap.world.step.v1"
PROXY = Path(__file__).with_name("lost_reply_proxy.py")


def core_patch_applied() -> bool:
    """Whether the importable OpenAI4S carries openai4s-core.patch."""
    try:
        from openai4s.host.mcp import MCPService
    except Exception:  # noqa: BLE001 - no OpenAI4S at all
        return False
    return all(hasattr(MCPService, name) for name in ("is_trusted_estop", "emergency_stop"))


class Broker:
    """A deterministic stand-in for the human/policy approval channel."""

    def __init__(self, allow: bool) -> None:
        self.allow = allow
        self.calls: list[dict] = []

    def approvals_reviewer_for(self, **_kwargs):
        return "user"

    def gate(self, **kwargs):
        self.calls.append(
            {
                key: kwargs.get(key)
                for key in ("method", "target", "side_effect_class")
            }
        )
        return {
            "allow": self.allow,
            "message": "test broker: ordinary approval unavailable"
            if not self.allow
            else "test broker: approved",
        }


@unittest.skipUnless(sdk_projection_available(), "mhs.mcp / OpenAI4S MCP client not available")
@unittest.skipUnless(
    core_patch_applied(),
    "OpenAI4S without openai4s-core.patch: the governed host route is not wired in "
    "(python3 -m openai4s_mhs core-patch check)",
)
class StockHostRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="mhs-host-route-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.addCleanup(self._shutdown_connections)

    def _shutdown_connections(self) -> None:
        try:
            global_mcp_manager().shutdown()
        except Exception:  # noqa: BLE001 - teardown must not mask the test
            pass

    def _route(
        self,
        *,
        mode: str = "simulated",
        allow_hardware: bool = False,
        estop_devices: list[str] | None = None,
        enable: bool = True,
    ) -> dict:
        endpoint = start_endpoint("conveyor", mode=mode)
        self.addCleanup(endpoint.close)
        device_id = str(endpoint.devices[0]["device_id"])
        endpoint_id = "route-" + uuid.uuid4().hex[:8]
        settings_path = write_settings(
            self.directory / endpoint_id,
            endpoint.url,
            endpoint_id=endpoint_id,
            allow_hardware=allow_hardware,
            estop_devices=estop_devices,
        )
        config = MHSConfig.load(settings_path)
        row = connector_entries(config)[0]
        self.assertNotIn("--operator-tools", row["command"])
        row["env"] = connector_env()
        host = HostDispatcher(
            cfg=get_config(),
            workspace=self.directory / endpoint_id / "workspace",
        )
        host.store.upsert_connector(
            connector_id=row["id"],
            name=row["name"],
            command=row["command"],
            enabled=enable,
            env=row["env"],
        )
        return {
            "endpoint": endpoint,
            "device_id": device_id,
            "endpoint_id": endpoint_id,
            "config": config,
            "row": row,
            "host": host,
        }

    def _call(self, route: dict, tool: str, arguments: dict) -> dict:
        return route["host"](
            "mcp_call",
            [{"server": route["row"]["id"], "tool": tool, "args": dict(arguments)}],
        )

    def _capability_tool(self, route: dict) -> str:
        return projection_tool_name(route["device_id"], CAPABILITY)

    def _safety(self, route: dict) -> dict:
        with MCPConnector(route["endpoint_id"], route["config"]) as connector:
            response = connector.call("mhs__safety", {"device_id": route["device_id"]})
            self.assertFalse(response["is_error"], response)
            return dict(response["raw"]["structuredContent"]["safety"])

    # -- positive path -----------------------------------------------------
    def test_discovery_read_command_and_verified_evidence_on_the_real_route(self) -> None:
        route = self._route()
        broker = Broker(True)
        with mock.patch("openai4s.permissions.broker", return_value=broker):
            tools = route["host"]("mcp_tools", [route["row"]["id"]])
            self.assertFalse(tools.get("error"), tools)
            names = {item["name"] for item in tools["tools"]}
            self.assertIn("mhs__inspect", names)
            self.assertIn("mhs__read", names)
            self.assertIn(self._capability_tool(route), names)

            read = self._call(
                route,
                "mhs__read",
                {"device_id": route["device_id"], "resource_id": "workcell"},
            )
            self.assertFalse(read["is_error"], read)
            self.assertEqual(read["raw"]["structuredContent"]["read"]["revision"], 0)

            result = self._call(route, self._capability_tool(route), {"ticks": 2})
            self.assertFalse(result["is_error"], result)
            receipt = result["raw"]["structuredContent"]["receipt"]
            self.assertEqual(receipt["status"], "completed")
            self.assertTrue(receipt["command_id"])

            # The agent row never issues a permit, even with an allowing broker:
            # the host route refuses the operator tool before any endpoint call.
            refused = self._call(
                route,
                "mhs__permit",
                {
                    "device_id": route["device_id"],
                    "capability_id": CAPABILITY,
                    "input": {"ticks": 5},
                },
            )
            self.assertTrue(refused["is_error"], refused)
            error = refused["raw"]["structuredContent"]["mhs_error"]
            self.assertEqual(error["mhs_code"], "MHS.AUTH.FORBIDDEN")
            self.assertEqual(error["policy"], "operator_route_only")

        # The operator issues it on the host operator route, and the permitted
        # command runs in the same operator session (a permit is bound to the
        # session and principal that requested it).  The governed wrapper must
        # not fold ``permit_id`` into the physical input digest.
        with OperatorRoute(route["endpoint_id"], route["config"], operator="human:test") as op:
            permit = op.permit(route["device_id"], CAPABILITY, {"ticks": 5})
            self.assertIsNone(permit["audit_error"])
            permitted_receipt = op.invoke(
                route["device_id"], CAPABILITY, {"ticks": 5},
                permit_id=permit["permit"]["permit_id"],
            )
        self.assertEqual(permitted_receipt["status"], "completed", permitted_receipt)
        self.assertEqual(permitted_receipt["input_digest"], permit["permit"]["input_digest"])

        with mock.patch("openai4s.permissions.broker", return_value=broker):
            evidence = self._call(route, "mhs__evidence", {})
            self.assertFalse(evidence["is_error"], evidence)
            self.assertTrue(evidence["raw"]["structuredContent"]["evidence"]["verify"]["valid"])

            # The allowed case reaches the same trusted route; the ordinary
            # gate being permissive does not change the stop's audit/policy.
            stopped = self._call(
                route,
                "mhs__estop",
                {"device_id": route["device_id"], "reason": "allowed stop"},
            )
            self.assertFalse(stopped.get("is_error"), stopped)
            self.assertTrue(
                stopped["raw"]["structuredContent"]["estop"]["output"]["latched"]
            )

        self.assertEqual(route["endpoint"].spec.bridges[route["device_id"]].sim.tick, 7)
        # The ordinary command went through the approval gate...
        self.assertTrue(any(call["method"] == "mcp_call" for call in broker.calls))

        # ...and the real host route persisted intent, receipt and endpoint
        # evidence in the durable ledger, and nothing in the journal for the
        # read-only discovery calls.
        ledger = HostLedger(route["config"].host_ledger_path)
        records = ledger.records()
        kinds = [item.get("kind") for item in records]
        self.assertEqual(kinds[0], "genesis")
        self.assertIn("invoke_intent", kinds)
        self.assertIn("invoke_outcome", kinds)
        self.assertIn("endpoint_evidence", kinds)
        self.assertIn("operator_permit_request", kinds)
        self.assertIn("operator_permit_result", kinds)
        self.assertTrue(ledger.verify()["valid"])
        evidence_records = [item for item in records if item.get("kind") == "endpoint_evidence"]
        self.assertTrue(evidence_records)
        self.assertTrue(evidence_records[-1]["valid"])
        self.assertTrue(str(evidence_records[-1]["head_digest"]).startswith("sha256:"))

        journal = [
            json.loads(line)
            for line in Path(route["config"].command_journal_path)
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        dispatched_tools = {
            item.get("tool") for item in journal if item.get("tool") is not None
        }
        self.assertEqual(dispatched_tools, {self._capability_tool(route)})
        self.assertEqual(
            {item.get("phase") for item in journal},
            {"allocated", "prepared", "dispatching", "completed"},
        )

        package = export_host_package(route["config"], route["endpoint_id"])
        self.assertTrue(package["package_verify"]["valid"], package["package_verify"])
        self.assertTrue(package["endpoint_verify"]["valid"])
        self.assertTrue(verify_package(package["package"])["valid"])

    # -- approval denials and the narrow stop exception --------------------
    def test_denied_approval_blocks_commands_but_not_the_trusted_stop(self) -> None:
        route = self._route()
        deny = Broker(False)
        with mock.patch("openai4s.permissions.broker", return_value=deny):
            denied = self._call(route, self._capability_tool(route), {"ticks": 1})
            self.assertIn("Permission denied", denied["error"])
            self.assertTrue(deny.calls)

            # The model-facing CallMCPTool path is still approval-gated for an
            # ordinary MCP call...
            self.assertTrue(CallMCPTool.requires_approval)

            # ...but the named, device-bound stop reaches the endpoint.
            stopped = self._call(
                route,
                "mhs__estop",
                {"device_id": route["device_id"], "reason": "operator stop"},
            )
            self.assertFalse(stopped.get("is_error"), stopped)
            self.assertEqual(
                stopped["raw"]["structuredContent"]["estop"]["status"], "completed"
            )
            self.assertTrue(stopped["raw"]["structuredContent"]["estop"]["output"]["latched"])
            self.assertTrue(stopped["raw"]["structuredContent"]["trusted_stop"])
            # The ordinary approval broker was consulted only for the denied
            # command, never for the trusted stop.
            self.assertEqual(
                [call["target"] for call in deny.calls],
                [f"{route['row']['id']}/{self._capability_tool(route)}"],
            )
            self.assertTrue(self._safety(route)["estop_engaged"])

        ledger = HostLedger(route["config"].host_ledger_path)
        kinds = [item.get("kind") for item in ledger.records()]
        self.assertIn("emergency_stop_request", kinds)
        self.assertIn("emergency_stop_result", kinds)
        self.assertTrue(ledger.verify()["valid"])

        # The agent cannot release the latch through the host route, even when
        # the ordinary approval allows the call...
        with mock.patch("openai4s.permissions.broker", return_value=Broker(True)):
            agent_reset = self._call(route, "mhs__reset", {"device_id": route["device_id"]})
        self.assertTrue(agent_reset["is_error"], agent_reset)
        self.assertEqual(
            agent_reset["raw"]["structuredContent"]["mhs_error"]["mhs_code"], "MHS.AUTH.FORBIDDEN"
        )
        self.assertTrue(self._safety(route)["estop_engaged"])
        # ...the reset is the operator's, on the host operator route.
        reset = operator_reset(
            route["endpoint_id"], route["device_id"], operator="human:test",
            reason="area checked", config=route["config"],
        )
        self.assertEqual(reset["receipt"]["status"], "completed", reset)
        self.assertFalse(self._safety(route)["estop_engaged"])
        deny_again = Broker(False)
        with mock.patch("openai4s.permissions.broker", return_value=deny_again):
            named = route["host"](
                "mhs_emergency_stop",
                [
                    {
                        "server": route["row"]["id"],
                        "device_id": route["device_id"],
                        "reason": "named action stop",
                    }
                ],
            )
        self.assertFalse(named.get("is_error"), named)
        self.assertEqual(named["raw"]["structuredContent"]["estop"]["status"], "completed")
        self.assertEqual(deny_again.calls, [])
        self.assertTrue(self._safety(route)["estop_engaged"])
        self.assertEqual(
            route["endpoint"].spec.bridges[route["device_id"]].sim.tick,
            0,
            "no denied command may have reached the simulator",
        )

    def test_unavailable_approval_channel_does_not_block_the_trusted_stop(self) -> None:
        route = self._route()

        class ExplodingBroker:
            def approvals_reviewer_for(self, **_kwargs):
                return "user"

            def gate(self, **_kwargs):
                raise RuntimeError("approval channel unavailable")

        with mock.patch("openai4s.permissions.broker", return_value=ExplodingBroker()):
            stopped = self._call(
                route,
                "mhs__estop",
                {"device_id": route["device_id"], "reason": "channel down"},
            )
        self.assertFalse(stopped.get("is_error"), stopped)
        self.assertTrue(stopped["raw"]["structuredContent"]["estop"]["output"]["latched"])
        self.assertTrue(self._safety(route)["estop_engaged"])

    def test_unauthorized_target_is_refused_without_an_endpoint_effect(self) -> None:
        route = self._route(estop_devices=["mhs://some-other-endpoint/lab/other"])
        deny = Broker(False)
        with mock.patch("openai4s.permissions.broker", return_value=deny):
            stopped = self._call(
                route,
                "mhs__estop",
                {"device_id": route["device_id"], "reason": "must refuse"},
            )
        self.assertIn("error", stopped)
        self.assertIn("MHS.HOST.DEVICE_NOT_ALLOWED", stopped["error"])
        self.assertFalse(self._safety(route)["estop_engaged"])
        # A refused stop is not an ordinary approval request either.
        self.assertEqual(deny.calls, [])

    def test_disabled_connector_refuses_the_named_stop(self) -> None:
        route = self._route(enable=False)
        deny = Broker(False)
        with mock.patch("openai4s.permissions.broker", return_value=deny):
            named = route["host"](
                "mhs_emergency_stop",
                [
                    {
                        "server": route["row"]["id"],
                        "device_id": route["device_id"],
                        "reason": "disabled",
                    }
                ],
            )
        self.assertIn("error", named)
        self.assertIn("disabled", named["error"])
        self.assertFalse(self._safety(route)["estop_engaged"])

    def test_unmapped_mhs_connector_is_refused_by_the_endpoint_mapping(self) -> None:
        route = self._route()
        rogue_id = "mhs-rogue-" + uuid.uuid4().hex[:8]
        route["host"].store.upsert_connector(
            connector_id=rogue_id,
            name=rogue_id,
            command=[
                sys.executable,
                "-m",
                "mhs.mcp",
                "--endpoint",
                route["endpoint"].url,
                "--config",
                str(route["config"].config_path),
            ],
            enabled=True,
            env=route["row"]["env"],
        )
        deny = Broker(False)
        with mock.patch("openai4s.permissions.broker", return_value=deny):
            named = route["host"](
                "mhs_emergency_stop",
                [
                    {
                        "server": rogue_id,
                        "device_id": route["device_id"],
                        "reason": "not a configured connector",
                    }
                ],
            )
        self.assertIn("error", named)
        self.assertIn("MHS.HOST.CONFIG_REQUIRED", named["error"])
        self.assertFalse(self._safety(route)["estop_engaged"])
        self.assertEqual(deny.calls, [])

    def test_non_mhs_connector_is_not_granted_the_trusted_exception(self) -> None:
        route = self._route()
        plain_id = "plain-" + uuid.uuid4().hex[:8]
        route["host"].store.upsert_connector(
            connector_id=plain_id,
            name=plain_id,
            command=["python3", "-m", "not_mhs"],
            enabled=True,
        )
        deny = Broker(False)
        with mock.patch("openai4s.permissions.broker", return_value=deny):
            response = route["host"](
                "mcp_call",
                [
                    {
                        "server": plain_id,
                        "tool": "mhs__estop",
                        "args": {"device_id": route["device_id"]},
                    }
                ],
            )
        self.assertIn("Permission denied", response["error"])
        self.assertFalse(
            route["host"]._mcp_service.is_trusted_estop(
                {"server": plain_id, "tool": "mhs__estop"}
            )
        )
        self.assertFalse(self._safety(route)["estop_engaged"])

    # -- MCP error propagation --------------------------------------------
    def test_hardware_disabled_is_error_is_propagated_by_the_governed_route(self) -> None:
        route = self._route(mode="hardware", allow_hardware=False)
        allow = Broker(True)
        with mock.patch("openai4s.permissions.broker", return_value=allow):
            result = self._call(route, self._capability_tool(route), {"ticks": 1})
        self.assertTrue(result["is_error"], result)
        self.assertEqual(
            result["raw"]["structuredContent"]["mhs_error"]["mhs_code"],
            "MHS.AUTH.HARDWARE_DISABLED",
        )
        self.assertEqual(route["endpoint"].spec.bridges[route["device_id"]].sim.tick, 0)
        journal = Path(route["config"].command_journal_path)
        phases = [
            json.loads(line).get("phase")
            for line in journal.read_text(encoding="utf-8").splitlines()
        ]
        self.assertIn("tool_error", phases)
        self.assertNotIn("completed", phases)

    def test_host_route_lost_reply_is_unknown_and_blocks_the_next_command(self) -> None:
        route = self._route()
        proxy_command = [
            sys.executable,
            str(PROXY),
            "--",
            sys.executable,
            "-m",
            "mhs.mcp",
            "--endpoint",
            route["endpoint"].url,
            "--config",
            str(route["config"].config_path),
        ]
        route["host"].store.upsert_connector(
            connector_id=route["row"]["id"],
            name=route["row"]["name"],
            command=proxy_command,
            enabled=True,
            env=route["row"]["env"],
        )
        allow = Broker(True)
        with mock.patch("openai4s.permissions.broker", return_value=allow), mock.patch.dict(
            os.environ, {"OPENAI4S_MCP_DEADLINE_S": "1.5"}
        ):
            result = self._call(route, self._capability_tool(route), {"ticks": 3})
            self.assertTrue(result["is_error"], result)
            error = result["raw"]["structuredContent"]["mhs_error"]
            self.assertEqual(error["mhs_code"], "MHS.OUTCOME.UNKNOWN")
            self.assertTrue(error["reconcile_required"])
            command_id = error["command_id"]
            self.assertTrue(command_id)
            self.assertEqual(route["endpoint"].spec.bridges[route["device_id"]].sim.tick, 3)

            records = [
                json.loads(line)
                for line in Path(route["config"].command_journal_path)
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            phases = [item.get("phase") for item in records if item.get("command_id") == command_id]
            self.assertIn("dispatching", phases)
            self.assertIn("unknown", phases)
            ledger = HostLedger(route["config"].host_ledger_path)
            outcomes = [
                item
                for item in ledger.records()
                if item.get("command_id") == command_id and item.get("outcome") == "unknown"
            ]
            self.assertTrue(outcomes)
            self.assertTrue(ledger.verify()["valid"])
            self.assertIn(
                "endpoint_evidence",
                [item.get("kind") for item in ledger.records()],
            )

            blocked = self._call(route, self._capability_tool(route), {"ticks": 1})
            self.assertTrue(blocked["is_error"], blocked)
            self.assertEqual(
                blocked["raw"]["structuredContent"]["mhs_error"]["mhs_code"],
                "MHS.HOST.RECONCILE_REQUIRED",
            )

        observed = reconcile(
            route["endpoint_id"],
            route["device_id"],
            config=route["config"],
            settle_s=0.0,
        )
        self.assertEqual(observed["reconcile"]["outcome"], "reconciled")
        self.assertEqual(observed["reconcile"]["resolved_command_ids"], [command_id])
        # Restore the direct connector row (the proxy's one-swallow fault is
        # spent) and drop the cached proxy connection before the next command.
        route["host"].store.upsert_connector(
            connector_id=route["row"]["id"],
            name=route["row"]["name"],
            command=route["row"]["command"],
            enabled=True,
            env=route["row"]["env"],
        )
        global_mcp_manager().disconnect(route["row"]["id"])
        with mock.patch("openai4s.permissions.broker", return_value=Broker(True)):
            after = self._call(route, self._capability_tool(route), {"ticks": 1})
        self.assertFalse(after["is_error"], after)
        self.assertEqual(route["endpoint"].spec.bridges[route["device_id"]].sim.tick, 4)

    # -- journal gate through the real route -------------------------------
    def test_new_host_route_command_is_blocked_after_a_lost_reply(self) -> None:
        route = self._route()
        # Put the route's journal into a durable UNKNOWN state, as a crash or
        # lost reply would have, then ask the real dispatcher for a new effect.
        journal_path = Path(route["config"].command_journal_path)
        unknown_id = canonical.ulid()
        record = {
            "kind": "command_dispatch",
            "phase": "dispatching",
            "command_id": unknown_id,
            "endpoint_id": route["endpoint_id"],
            "device_id": route["device_id"],
            "capability_id": CAPABILITY,
            "arguments_digest": canonical.digest({"ticks": 9}),
        }
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        allow = Broker(True)
        with mock.patch("openai4s.permissions.broker", return_value=allow):
            blocked = self._call(route, self._capability_tool(route), {"ticks": 1})
        self.assertTrue(blocked["is_error"], blocked)
        error = blocked["raw"]["structuredContent"]["mhs_error"]
        self.assertEqual(error["mhs_code"], "MHS.HOST.RECONCILE_REQUIRED")
        self.assertIn(unknown_id, error["message"] + json.dumps(error.get("pending_command_ids", [])))
        self.assertEqual(route["endpoint"].spec.bridges[route["device_id"]].sim.tick, 0)


if __name__ == "__main__":
    unittest.main()
