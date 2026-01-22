"""Kite MCP client using FastMCP with session persistence."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError

KITE_MCP_URL = "https://mcp.kite.trade/mcp"

# Session file for persisting cookies
SESSION_DIR = Path.home() / ".portfolio-copilot"
SESSION_FILE = SESSION_DIR / "kite_session.pkl"


def extract_text(result: Any) -> str:
    """Extract text from CallToolResult."""
    try:
        if result and hasattr(result, "content") and result.content:
            content = result.content
            if hasattr(content, "__getitem__") and len(content) > 0:
                first = content[0]
                return first.text if hasattr(first, "text") else str(first)
    except (TypeError, IndexError, AttributeError):
        pass
    return ""


def parse_json_response(text: str, default: Any = None) -> Any:
    """Parse JSON from MCP response text."""
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


@dataclass
class LoginResult:
    """Result from login tool."""

    url: str
    message: str


class AuthenticationError(Exception):
    """Raised when authentication is required."""


class KiteClient:
    """Persistent Kite MCP client that maintains session state."""

    def __init__(self):
        self._client: Client | None = None
        self._connected: bool = False
        self._logged_in: bool = False

    async def connect(self) -> None:
        """Establish connection to Kite MCP."""
        if self._client is None or not self._connected:
            if self._client is not None:
                await self.disconnect()
            self._client = Client(KITE_MCP_URL)
            await self._client.__aenter__()
            self._connected = True

    async def disconnect(self) -> None:
        """Close the connection."""
        if self._client and self._connected:
            await self._client.__aexit__(None, None, None)
            self._connected = False
        self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()

    async def _call_tool(self, tool_name: str, args: dict | None = None) -> str:
        """Call an MCP tool and return the text result."""
        await self.connect()
        try:
            result = await self._client.call_tool(tool_name, args or {})
            return extract_text(result)
        except ToolError as e:
            if "log in first" in str(e).lower() or "session" in str(e).lower():
                self._logged_in = False
                raise AuthenticationError("Not logged in. Run 'login' first.") from e
            raise

    async def is_logged_in(self) -> bool:
        """Check if the user is currently logged in.

        Attempts a lightweight API call to verify session validity.
        """
        if self._logged_in:
            return True

        try:
            # Try to get profile - this is a lightweight call
            text = await self._call_tool("get_profile")
            data = parse_json_response(text, {})
            if data and isinstance(data, dict) and data.get("user_id"):
                self._logged_in = True
                return True
        except (AuthenticationError, ToolError):
            pass

        self._logged_in = False
        return False

    async def get_profile(self) -> dict:
        """Get user profile information.

        Returns:
            Dict with user_id, user_name, email, etc.
        """
        text = await self._call_tool("get_profile")
        data = parse_json_response(text, {})
        return data if isinstance(data, dict) else {}

    async def login(self) -> LoginResult:
        """Get login URL for Kite OAuth."""
        text = await self._call_tool("login")

        # Extract URL from the response
        url_match = re.search(r"https://kite\.zerodha\.com/connect/login[^\s\)]+", text)
        url = url_match.group(0) if url_match else ""

        return LoginResult(url=url, message=text)

    def mark_logged_in(self) -> None:
        """Mark the client as logged in (called after successful login)."""
        self._logged_in = True

    async def list_tools(self) -> list[str]:
        """List available MCP tools."""
        await self.connect()
        tools = await self._client.list_tools()
        return [tool.name for tool in tools]

    # Portfolio Tools

    async def get_holdings(self) -> list[dict]:
        """Fetch portfolio holdings (long-term DEMAT holdings)."""
        text = await self._call_tool("get_holdings")
        data = parse_json_response(text, [])
        return data if isinstance(data, list) else []

    async def get_positions(self) -> dict:
        """Fetch current trading positions (net and day).

        Returns dict with 'net' and 'day' position arrays.
        """
        text = await self._call_tool("get_positions")
        data = parse_json_response(text, {"net": [], "day": []})
        return data if isinstance(data, dict) else {"net": [], "day": []}

    async def get_margins(self, segment: str | None = None) -> dict:
        """Fetch account margins and buying power.

        Args:
            segment: Optional segment filter (e.g., 'equity', 'commodity')
        """
        args = {"segment": segment} if segment else {}
        text = await self._call_tool("get_margins", args)
        data = parse_json_response(text, {})
        return data if isinstance(data, dict) else {}

    # Market Data Tools

    async def get_quotes(self, instruments: list[str]) -> dict:
        """Get real-time quotes for instruments.

        Args:
            instruments: List of instrument identifiers (e.g., ['NSE:RELIANCE', 'NSE:TCS'])
        """
        text = await self._call_tool("get_quotes", {"instruments": instruments})
        data = parse_json_response(text, {})
        return data if isinstance(data, dict) else {}

    async def get_ltp(self, instruments: list[str]) -> dict:
        """Get last traded price for instruments.

        Args:
            instruments: List of instrument identifiers (e.g., ['NSE:RELIANCE', 'NSE:TCS'])
        """
        text = await self._call_tool("get_ltp", {"instruments": instruments})
        data = parse_json_response(text, {})
        return data if isinstance(data, dict) else {}

    async def search_instruments(self, query: str) -> list[dict]:
        """Search for instruments by name or symbol.

        Args:
            query: Search query (e.g., 'reliance', 'TCS')
        """
        text = await self._call_tool("search_instruments", {"search_q": query})
        data = parse_json_response(text, [])
        return data if isinstance(data, list) else []
