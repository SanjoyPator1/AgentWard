"""Convert MCP tool definitions into OpenAI's function-calling tool schema.

Every feature that talks to an MCP server needs this same conversion and it
carries no task-specific content, so it lives here rather than being
reimplemented per feature.
"""

from __future__ import annotations

from typing import Any

from mcp.types import Tool


def to_openai_tool(tool: Tool) -> dict[str, Any]:
    """One MCP Tool -> one OpenAI-shaped tool definition.

    MCP's `input_schema` (the wire's `inputSchema`) is already JSON Schema,
    which is exactly what OpenAI's `parameters` field expects, so this is a
    rename, not a translation.
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema,
        },
    }


def to_openai_tools(tools: list[Tool]) -> list[dict[str, Any]]:
    """Convert a whole `tools/list` result, preserving registration order.

    Order matters for prompt caching: both the MCP server's own `tools/list`
    cache hint and a model provider's prompt cache key off a stable prefix,
    so this never re-sorts what the server returned.
    """
    return [to_openai_tool(tool) for tool in tools]


__all__ = ["to_openai_tool", "to_openai_tools"]
