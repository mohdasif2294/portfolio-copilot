"""Portfolio tools for agent workflows."""

from typing import Any

from src.mcp.kite_client import AuthenticationError, KiteClient


async def fetch_holdings(client: KiteClient) -> dict[str, Any]:
    """Fetch portfolio holdings and calculate summary metrics.

    Returns:
        Dict with 'holdings', 'total_value', 'total_pnl', 'error'
    """
    try:
        holdings = await client.get_holdings()

        if not holdings:
            return {
                "holdings": [],
                "total_value": 0,
                "total_pnl": 0,
                "error": None,
            }

        total_value = 0.0
        total_pnl = 0.0

        for h in holdings:
            qty = h.get("quantity", 0)
            last_price = h.get("last_price", 0)
            pnl = h.get("pnl", 0)

            total_value += qty * last_price
            total_pnl += pnl

        return {
            "holdings": holdings,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "error": None,
        }

    except AuthenticationError:
        return {
            "holdings": [],
            "total_value": 0,
            "total_pnl": 0,
            "error": "Not logged in. Please run 'login' first.",
        }
    except Exception as e:
        return {
            "holdings": [],
            "total_value": 0,
            "total_pnl": 0,
            "error": str(e),
        }


def analyze_performers(
    holdings: list[dict[str, Any]],
    analysis_type: str = "worst",
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Identify best or worst performing stocks.

    Args:
        holdings: List of holdings from Kite
        analysis_type: "worst", "best", or "all"
        top_n: Number of stocks to return

    Returns:
        List of stocks with calculated metrics
    """
    if not holdings:
        return []

    analyzed = []

    for h in holdings:
        symbol = h.get("tradingsymbol", "")
        qty = h.get("quantity", 0)
        avg_price = h.get("average_price", 0)
        last_price = h.get("last_price", 0)
        pnl = h.get("pnl", 0)

        # Calculate return percentage
        if avg_price > 0:
            return_pct = ((last_price - avg_price) / avg_price) * 100
        else:
            return_pct = 0

        analyzed.append({
            "symbol": symbol,
            "quantity": qty,
            "average_price": avg_price,
            "last_price": last_price,
            "pnl": pnl,
            "return_pct": return_pct,
            "day_change_pct": h.get("day_change_percentage", 0),
        })

    # Sort based on analysis type
    if analysis_type == "worst":
        analyzed.sort(key=lambda x: x["return_pct"])
    elif analysis_type == "best":
        analyzed.sort(key=lambda x: x["return_pct"], reverse=True)
    # "all" keeps original order

    return analyzed[:top_n]


async def get_stock_quotes(
    client: KiteClient,
    symbols: list[str],
) -> dict[str, Any]:
    """Get current quotes for stocks.

    Args:
        client: Kite MCP client
        symbols: List of stock symbols

    Returns:
        Dict mapping symbol to quote data
    """
    try:
        # Format symbols for Kite API
        instruments = [f"NSE:{sym}" for sym in symbols]
        quotes = await client.get_quotes(instruments)
        return {"quotes": quotes, "error": None}
    except Exception as e:
        return {"quotes": {}, "error": str(e)}
