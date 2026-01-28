"""Tool parsing utilities for Ollama prompt-based tool calling.

Since Ollama models don't have native function calling, we use a prompt-based
approach where tools are described in the system prompt and the model outputs
structured tool calls in a specific format.
"""

import json
import re
import uuid
from typing import Any

from src.llm.base import ToolCall


def format_tools_as_prompt(tools: list[dict[str, Any]]) -> str:
    """Convert tool definitions to a prompt instruction for Ollama.

    Args:
        tools: List of tool definitions with name, description, input_schema

    Returns:
        Formatted string to append to system prompt
    """
    if not tools:
        return ""

    lines = [
        "",
        "## TOOLS",
        "",
        "You have access to tools. To use a tool, output ONLY a JSON object like this:",
        "",
        '{"name": "tool_name", "input": {}}',
        "",
        "IMPORTANT RULES:",
        "1. Output ONLY the JSON when calling a tool - no other text",
        "2. Wait for tool results before continuing",
        "3. Only use parameters that are defined for each tool",
        "",
        "Available tools:",
        "",
    ]

    for tool in tools:
        name = tool.get("name", "unknown")
        description = tool.get("description", "No description")
        schema = tool.get("input_schema", {})

        lines.append(f"### {name}")
        lines.append(f"{description}")

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if properties:
            lines.append("Parameters:")
            for prop_name, prop_def in properties.items():
                prop_type = prop_def.get("type", "any")
                prop_desc = prop_def.get("description", "")
                req_marker = " (REQUIRED)" if prop_name in required else " (optional)"
                lines.append(f"  - {prop_name} ({prop_type}){req_marker}: {prop_desc}")
        else:
            lines.append("Parameters: none")

        lines.append("")

    return "\n".join(lines)


def parse_tool_calls_from_text(
    text: str,
    tools: list[dict[str, Any]] | None = None,
) -> tuple[str, list[ToolCall]]:
    """Extract tool calls from response text.

    Looks for tool calls in various formats:
    - ```tool_call blocks
    - ```json blocks with tool-like content
    - Raw JSON with "name" and "input" fields

    Args:
        text: The response text from the LLM
        tools: Optional list of valid tools to validate against

    Returns:
        Tuple of (remaining_text, list_of_tool_calls)
    """
    tool_calls: list[ToolCall] = []
    remaining_text = text

    # Valid tool names if provided
    valid_names = {t["name"] for t in tools} if tools else None

    def try_parse_tool_call(json_str: str) -> ToolCall | None:
        """Try to parse a JSON string as a tool call."""
        try:
            data = json.loads(json_str.strip())

            name = data.get("name", "")
            if not name:
                return None

            # Validate tool name if we have a list
            if valid_names and name not in valid_names:
                return None

            tool_input = data.get("input", {})
            if not isinstance(tool_input, dict):
                tool_input = {}

            return ToolCall(
                id=f"call_{uuid.uuid4().hex[:8]}",
                name=name,
                input=tool_input,
            )
        except json.JSONDecodeError:
            return None

    # Pattern 1: ```tool_call blocks
    pattern1 = r"```tool_call\s*(.*?)\s*```"
    for match in re.findall(pattern1, text, re.DOTALL):
        tool_call = try_parse_tool_call(match)
        if tool_call:
            tool_calls.append(tool_call)
            remaining_text = re.sub(
                r"```tool_call\s*" + re.escape(match) + r"\s*```",
                "",
                remaining_text,
            )

    # Pattern 2: ```json blocks with tool-like content
    pattern2 = r"```json\s*(.*?)\s*```"
    for match in re.findall(pattern2, text, re.DOTALL):
        if '"name"' in match and '"input"' in match:
            tool_call = try_parse_tool_call(match)
            if tool_call:
                tool_calls.append(tool_call)
                remaining_text = re.sub(
                    r"```json\s*" + re.escape(match) + r"\s*```",
                    "",
                    remaining_text,
                )

    # Pattern 3: ``` blocks (no language) with tool-like content
    pattern3 = r"```\s*(.*?)\s*```"
    for match in re.findall(pattern3, text, re.DOTALL):
        if '"name"' in match and '"input"' in match:
            tool_call = try_parse_tool_call(match)
            if tool_call:
                tool_calls.append(tool_call)
                remaining_text = re.sub(
                    r"```\s*" + re.escape(match) + r"\s*```",
                    "",
                    remaining_text,
                )

    # Pattern 4: Raw JSON on its own line ({"name": "...", "input": ...})
    if not tool_calls:
        pattern4 = r'^\s*(\{"name":\s*"[^"]+",\s*"input":\s*\{[^}]*\}\s*\})\s*$'
        for match in re.findall(pattern4, text, re.MULTILINE):
            tool_call = try_parse_tool_call(match)
            if tool_call:
                tool_calls.append(tool_call)
                remaining_text = remaining_text.replace(match, "")

    return remaining_text.strip(), tool_calls


def format_tool_result(tool_call_id: str, result: str) -> dict[str, Any]:
    """Format a tool result for inclusion in the conversation.

    Args:
        tool_call_id: The ID of the tool call this is responding to
        result: The result of the tool execution (usually JSON string)

    Returns:
        Message dict to add to conversation
    """
    return {
        "role": "user",
        "content": f"Tool result for {tool_call_id}:\n```json\n{result}\n```",
    }


def format_tool_results_batch(results: list[tuple[str, str]]) -> dict[str, Any]:
    """Format multiple tool results for inclusion in the conversation.

    Args:
        results: List of (tool_call_id, result) tuples

    Returns:
        Message dict to add to conversation
    """
    parts = []
    for tool_call_id, result in results:
        parts.append(f"Result for {tool_call_id}:\n```json\n{result}\n```")

    return {
        "role": "user",
        "content": "\n\n".join(parts),
    }
