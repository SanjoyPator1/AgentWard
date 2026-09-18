"""SimpleToolLoop tested entirely offline: an in-process MCPServer (no
Docker, no network - the SDK connects a Client directly to a Server/MCPServer
instance) plus a scripted call_model() standing in for a real LLM. This is
the cheapest way to verify the loop's termination logic without Ollama,
Gemini, or fhir-mcp running - see substrate/fhir-mcp's own test_wire_protocol
for the same "no live model needed" philosophy applied to the tool layer.
"""

from __future__ import annotations

import json

from agentward_harness.mcp_tools import to_openai_tools
from agentward_harness.model import ModelConfig, ModelReply, ToolCallRequest
from agentward_harness.trajectory import TrajectoryLogger
from mcp import Client
from mcp.server import MCPServer

from f1_care_gap_hunter.harness.v1 import loop as loop_module
from f1_care_gap_hunter.harness.v1.loop import LocalTool, SimpleToolLoop, _cap_tool_result

_CONFIG = ModelConfig(provider="ollama", model="test-model", base_url="http://x", api_key="x")


def _make_in_process_server() -> MCPServer:
    server = MCPServer("test-server")

    @server.tool()
    def echo(text: str) -> str:
        return f"echo: {text}"

    return server


class _ScriptedModel:
    """Replays a fixed sequence of ModelReply objects, one per call_model(),
    and records the messages it was called with so a test can inspect what
    the loop actually sent on a later call."""

    def __init__(self, replies: list[ModelReply]) -> None:
        self._replies = list(replies)
        self.calls: list[list[dict]] = []

    async def __call__(self, messages, tools, config, **kwargs) -> ModelReply:
        self.calls.append(messages)
        return self._replies.pop(0)


def _tool_call_reply(
    name: str, arguments_json: str = "{}", extra: dict | None = None
) -> ModelReply:
    return ModelReply(
        content=None,
        reasoning=None,
        tool_calls=[
            ToolCallRequest(id="call_1", name=name, arguments_json=arguments_json, extra=extra)
        ],
        finish_reason="tool_calls",
        prompt_tokens=10,
        completion_tokens=5,
    )


def _final_reply(content: str = "final answer") -> ModelReply:
    return ModelReply(
        content=content,
        reasoning=None,
        tool_calls=[],
        finish_reason="stop",
        prompt_tokens=10,
        completion_tokens=5,
    )


def _trajectory() -> TrajectoryLogger:
    return TrajectoryLogger("test-run")


class TestSimpleToolLoop:
    async def test_stops_when_model_asks_for_no_more_tools(self, monkeypatch) -> None:
        monkeypatch.setattr(loop_module, "call_model", _ScriptedModel([_final_reply("done")]))

        async with Client(_make_in_process_server()) as client:
            sim_loop = SimpleToolLoop(
                mcp_client=client,
                mcp_tool_defs=[],
                local_tools=[],
                config=_CONFIG,
                max_steps=5,
                stop_tool_names=set(),
                trajectory=_trajectory(),
            )
            result = await sim_loop.run([{"role": "system", "content": "sys"}])

        assert result.terminated_by == "no_tool_calls"
        assert result.total_steps == 1
        assert result.messages[-1] == {"role": "assistant", "content": "done"}

    async def test_stops_on_designated_stop_tool(self, monkeypatch) -> None:
        monkeypatch.setattr(
            loop_module,
            "call_model",
            _ScriptedModel([_tool_call_reply("submit_findings", '{"findings": []}')]),
        )
        received: dict = {}

        def handle_submit(arguments: dict) -> dict:
            received.update(arguments)
            return {"ok": True}

        submit_tool = LocalTool(
            schema={
                "type": "function",
                "function": {"name": "submit_findings", "parameters": {}},
            },
            handler=handle_submit,
        )

        async with Client(_make_in_process_server()) as client:
            sim_loop = SimpleToolLoop(
                mcp_client=client,
                mcp_tool_defs=[],
                local_tools=[submit_tool],
                config=_CONFIG,
                max_steps=5,
                stop_tool_names={"submit_findings"},
                trajectory=_trajectory(),
            )
            result = await sim_loop.run([{"role": "system", "content": "sys"}])

        assert result.terminated_by == "stop_tool_called"
        assert result.total_steps == 1
        assert received == {"findings": []}

    async def test_exhausts_step_budget_when_model_never_stops(self, monkeypatch) -> None:
        monkeypatch.setattr(
            loop_module,
            "call_model",
            _ScriptedModel([_tool_call_reply("echo", '{"text": "hi"}') for _ in range(3)]),
        )

        async with Client(_make_in_process_server()) as client:
            tools = await client.list_tools()
            sim_loop = SimpleToolLoop(
                mcp_client=client,
                mcp_tool_defs=to_openai_tools(tools.tools),
                local_tools=[],
                config=_CONFIG,
                max_steps=3,
                stop_tool_names=set(),
                trajectory=_trajectory(),
            )
            result = await sim_loop.run([{"role": "system", "content": "sys"}])

        assert result.terminated_by == "budget"
        assert result.total_steps == 3

    async def test_real_mcp_tool_call_round_trips_through_the_loop(self, monkeypatch) -> None:
        monkeypatch.setattr(
            loop_module,
            "call_model",
            _ScriptedModel([_tool_call_reply("echo", '{"text": "hello"}'), _final_reply("got it")]),
        )

        async with Client(_make_in_process_server()) as client:
            tools = await client.list_tools()
            sim_loop = SimpleToolLoop(
                mcp_client=client,
                mcp_tool_defs=to_openai_tools(tools.tools),
                local_tools=[],
                config=_CONFIG,
                max_steps=5,
                stop_tool_names=set(),
                trajectory=_trajectory(),
            )
            result = await sim_loop.run([{"role": "system", "content": "sys"}])

        tool_messages = [m for m in result.messages if m.get("role") == "tool"]
        assert len(tool_messages) == 1
        assert "echo: hello" in tool_messages[0]["content"]
        assert result.terminated_by == "no_tool_calls"

    async def test_round_trips_provider_specific_extra_on_tool_calls(self, monkeypatch) -> None:
        """Gemini's "thinking" models attach an opaque `extra_content` (a
        `thought_signature`) to each tool call and reject the *next* request
        if it isn't echoed back verbatim on the outbound assistant message -
        confirmed against the real API. The loop must round-trip `extra` for
        any provider that sends one, without knowing what's in it, and do
        nothing for a provider (Ollama/qwen3) that sends none."""
        # Matches the real shape captured live from Gemini's response:
        # `extra_content` is itself the field pydantic captured as "extra".
        captured_extra = {"extra_content": {"google": {"thought_signature": "opaque-blob"}}}
        scripted = _ScriptedModel(
            [
                _tool_call_reply("echo", '{"text": "hi"}', extra=captured_extra),
                _final_reply("done"),
            ]
        )
        monkeypatch.setattr(loop_module, "call_model", scripted)

        async with Client(_make_in_process_server()) as client:
            tools = await client.list_tools()
            sim_loop = SimpleToolLoop(
                mcp_client=client,
                mcp_tool_defs=to_openai_tools(tools.tools),
                local_tools=[],
                config=_CONFIG,
                max_steps=5,
                stop_tool_names=set(),
                trajectory=_trajectory(),
            )
            await sim_loop.run([{"role": "system", "content": "sys"}])

        # The second call_model() invocation is the one that would be
        # rejected by a real "thinking" provider if extra_content were lost.
        second_call_messages = scripted.calls[1]
        assistant_message = next(m for m in second_call_messages if m["role"] == "assistant")
        assert assistant_message["tool_calls"][0]["extra_content"] == {
            "google": {"thought_signature": "opaque-blob"}
        }

    async def test_caps_an_oversized_tool_result_before_it_reaches_the_model(
        self, monkeypatch
    ) -> None:
        """Regression test: a single oversized tool result (measured live -
        a 14-resource, ~14.5KB raw search_resources dump) can by itself push
        the *next* model call over a provider's per-minute token budget (a
        real 413 on Groq's free tier). The loop must cap what actually
        enters the conversation, not just what the trajectory log records."""
        monkeypatch.setattr(
            loop_module,
            "call_model",
            _ScriptedModel([_tool_call_reply("huge_tool"), _final_reply("done")]),
        )

        huge_result = "x" * 20_000

        def handle_huge_tool(_arguments: dict) -> str:
            return huge_result

        huge_tool = LocalTool(
            schema={"type": "function", "function": {"name": "huge_tool", "parameters": {}}},
            handler=handle_huge_tool,
        )

        async with Client(_make_in_process_server()) as client:
            sim_loop = SimpleToolLoop(
                mcp_client=client,
                mcp_tool_defs=[],
                local_tools=[huge_tool],
                config=_CONFIG,
                max_steps=5,
                stop_tool_names=set(),
                trajectory=_trajectory(),
            )
            result = await sim_loop.run([{"role": "system", "content": "sys"}])

        tool_message = next(m for m in result.messages if m["role"] == "tool")
        assert len(tool_message["content"]) < len(huge_result)
        assert "truncated" in tool_message["content"]
        assert "chars total" in tool_message["content"]

    async def test_does_not_mutate_the_input_messages_list(self, monkeypatch) -> None:
        monkeypatch.setattr(loop_module, "call_model", _ScriptedModel([_final_reply("done")]))
        original = [{"role": "system", "content": "sys"}]

        async with Client(_make_in_process_server()) as client:
            sim_loop = SimpleToolLoop(
                mcp_client=client,
                mcp_tool_defs=[],
                local_tools=[],
                config=_CONFIG,
                max_steps=5,
                stop_tool_names=set(),
                trajectory=_trajectory(),
            )
            await sim_loop.run(original)

        assert original == [{"role": "system", "content": "sys"}]


class TestCapToolResult:
    """`_cap_tool_result` tested directly: it must never sever an individual
    item's fields to fit the budget, only drop whole items - see its own
    docstring for the real failure (a lost `performedPeriod`) this replaces.
    """

    def test_short_result_untouched(self) -> None:
        text = json.dumps({"resources": [{"id": "1"}]})
        assert _cap_tool_result(text) == text

    def test_keeps_complete_items_and_drops_the_rest(self) -> None:
        # Each item is large enough that only a few fit under the budget.
        big_field = "y" * 500
        resources = [{"id": str(i), "padding": big_field} for i in range(30)]
        text = json.dumps({"resource_type": "Procedure", "resources": resources})

        result = _cap_tool_result(text)
        parsed = json.loads(result)

        assert len(parsed["resources"]) < len(resources)
        # Every kept item is the exact, complete original object - never a
        # partial/cut-off dict with fields missing.
        for i, item in enumerate(parsed["resources"]):
            assert item == resources[i]
        assert "_truncated_note" in parsed
        assert "older ones were omitted" in parsed["_truncated_note"]
        assert len(result) <= 4200  # some slack for the note itself

    def test_keeps_the_most_recent_items_not_the_first_ones(self) -> None:
        """Regression test for a real bug: search_resources requests no sort,
        so items arrive in whatever order the FHIR server stores them (here,
        oldest-id-first, matching what was observed live). Keeping "whatever
        fits first" silently kept 5 of 11 procedures - the 5 *oldest* - and
        dropped the most recent one, which was the one that actually cleared
        the gap being checked for. The model reported a gap that the oracle's
        own ground truth says does not exist."""
        big_field = "y" * 500
        # Oldest first, as an unsorted FHIR response would arrive.
        resources = [
            {"id": str(i), "performedPeriod": {"start": f"20{10 + i:02d}-01-01"}, "pad": big_field}
            for i in range(30)
        ]
        text = json.dumps({"resource_type": "Procedure", "resources": resources})

        result = _cap_tool_result(text)
        parsed = json.loads(result)

        kept_ids = {item["id"] for item in parsed["resources"]}
        newest_ids = {item["id"] for item in resources[-len(parsed["resources"]) :]}
        assert kept_ids == newest_ids, "must keep the newest items, not the first ones seen"

    def test_falls_back_to_raw_truncation_when_no_list_field(self) -> None:
        text = json.dumps({"note": "x" * 20_000})
        result = _cap_tool_result(text)
        assert len(result) < len(text)
        assert "truncated" in result
        assert "chars total" in result

    def test_non_json_text_falls_back_to_raw_truncation(self) -> None:
        text = "not json at all, just a huge blob " * 500
        result = _cap_tool_result(text)
        assert len(result) < len(text)
        assert "truncated" in result
