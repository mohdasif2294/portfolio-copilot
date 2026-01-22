"""Screener.in scraper for fundamental analysis of Indian stocks."""

import re
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.screener.in"
COMPANY_URL = f"{BASE_URL}/company"


@dataclass
class FundamentalData:
    """Fundamental data for a stock."""

    symbol: str
    name: str = ""

    # Valuation
    market_cap: float = 0  # in Cr
    current_price: float = 0
    pe_ratio: float = 0
    pb_ratio: float = 0
    dividend_yield: float = 0

    # Profitability
    roe: float = 0  # Return on Equity %
    roce: float = 0  # Return on Capital Employed %
    profit_margin: float = 0

    # Growth
    revenue_growth_3yr: float = 0
    profit_growth_3yr: float = 0

    # Financial Health
    debt_to_equity: float = 0
    current_ratio: float = 0
    interest_coverage: float = 0

    # Shareholding
    promoter_holding: float = 0
    promoter_holding_change: float = 0  # Change in last quarter

    # Screener's analysis
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)

    # Additional info
    sector: str = ""
    industry: str = ""
    book_value: float = 0
    face_value: float = 0
    high_52w: float = 0
    low_52w: float = 0

    error: str | None = None


class ScreenerScraper:
    """Scraper for Screener.in fundamental data."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def get_fundamentals(self, symbol: str) -> FundamentalData:
        """Fetch fundamental data for a stock.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS")

        Returns:
            FundamentalData with all available metrics
        """
        url = f"{COMPANY_URL}/{symbol.upper()}/"

        try:
            response = await self._client.get(url)

            if response.status_code == 404:
                return FundamentalData(
                    symbol=symbol,
                    error=f"Stock {symbol} not found on Screener.in",
                )

            response.raise_for_status()

        except httpx.HTTPError as e:
            return FundamentalData(symbol=symbol, error=str(e))

        soup = BeautifulSoup(response.text, "lxml")

        data = FundamentalData(symbol=symbol.upper())

        # Extract company name
        name_elem = soup.select_one("h1.margin-0")
        if name_elem:
            data.name = name_elem.get_text(strip=True)

        # Extract key ratios from the top section
        self._extract_key_ratios(soup, data)

        # Extract pros and cons
        self._extract_pros_cons(soup, data)

        # Extract shareholding
        self._extract_shareholding(soup, data)

        # Extract sector/industry
        self._extract_sector(soup, data)

        return data

    def _extract_key_ratios(self, soup: BeautifulSoup, data: FundamentalData) -> None:
        """Extract key ratios from the top ratios section."""
        # Find all ratio items in the top section
        ratio_items = soup.select("li.flex.flex-space-between span")

        # Also check the main ratios section
        ratios_section = soup.select_one("#top-ratios")
        if ratios_section:
            ratio_items.extend(ratios_section.select("li span"))

        # Map ratio names to attributes
        ratio_map = {
            "market cap": ("market_cap", self._parse_cr_value),
            "current price": ("current_price", self._parse_number),
            "stock p/e": ("pe_ratio", self._parse_number),
            "price to earning": ("pe_ratio", self._parse_number),
            "book value": ("book_value", self._parse_number),
            "price to book": ("pb_ratio", self._parse_number),
            "dividend yield": ("dividend_yield", self._parse_percent),
            "roce": ("roce", self._parse_percent),
            "roe": ("roe", self._parse_percent),
            "debt to equity": ("debt_to_equity", self._parse_number),
            "face value": ("face_value", self._parse_number),
            "high / low": ("high_52w", self._parse_high_low),
            "52 week high": ("high_52w", self._parse_number),
            "52 week low": ("low_52w", self._parse_number),
        }

        # Process ratio list items
        for i in range(0, len(ratio_items) - 1, 2):
            name_elem = ratio_items[i]
            value_elem = ratio_items[i + 1] if i + 1 < len(ratio_items) else None

            if not value_elem:
                continue

            name = name_elem.get_text(strip=True).lower()
            value_text = value_elem.get_text(strip=True)

            for key, (attr, parser) in ratio_map.items():
                if key in name:
                    try:
                        if attr == "high_52w" and "/" in value_text:
                            high, low = self._parse_high_low(value_text)
                            data.high_52w = high
                            data.low_52w = low
                        else:
                            setattr(data, attr, parser(value_text))
                    except (ValueError, AttributeError):
                        pass
                    break

        # Also try the warehouse data section for more ratios
        warehouse = soup.select_one("#warehouse-data")
        if warehouse:
            self._extract_warehouse_data(warehouse, data)

    def _extract_warehouse_data(self, warehouse: BeautifulSoup, data: FundamentalData) -> None:
        """Extract data from warehouse section."""
        # Look for specific data points
        text = warehouse.get_text()

        # Revenue growth
        growth_match = re.search(r"Sales growth.*?([+-]?\s*\d+\.?\d*)\s*%", text)
        if growth_match:
            data.revenue_growth_3yr = float(growth_match.group(1))

        # Profit growth
        profit_match = re.search(r"Profit growth.*?([+-]?\s*\d+\.?\d*)\s*%", text)
        if profit_match:
            data.profit_growth_3yr = float(profit_match.group(1))

    def _extract_pros_cons(self, soup: BeautifulSoup, data: FundamentalData) -> None:
        """Extract pros and cons sections."""
        # Find pros
        pros_section = soup.select_one(".pros")
        if pros_section:
            pros_items = pros_section.select("li")
            data.pros = [li.get_text(strip=True) for li in pros_items[:5]]

        # Find cons
        cons_section = soup.select_one(".cons")
        if cons_section:
            cons_items = cons_section.select("li")
            data.cons = [li.get_text(strip=True) for li in cons_items[:5]]

    def _extract_shareholding(self, soup: BeautifulSoup, data: FundamentalData) -> None:
        """Extract shareholding pattern."""
        # Look for shareholding section
        shareholding = soup.select_one("#shareholding")
        if not shareholding:
            return

        # Find promoter holding row
        rows = shareholding.select("tr")
        for row in rows:
            cells = row.select("td")
            if cells and "promoter" in cells[0].get_text().lower():
                # Get the latest quarter value
                values = [c.get_text(strip=True) for c in cells[1:]]
                if values:
                    try:
                        data.promoter_holding = self._parse_percent(values[-1])
                        if len(values) > 1:
                            prev = self._parse_percent(values[-2])
                            data.promoter_holding_change = data.promoter_holding - prev
                    except (ValueError, IndexError):
                        pass
                break

    def _extract_sector(self, soup: BeautifulSoup, data: FundamentalData) -> None:
        """Extract sector and industry."""
        # Look for sector info in company details
        details = soup.select_one(".company-info") or soup.select_one(".about")
        if details:
            text = details.get_text()
            sector_match = re.search(r"Sector:\s*([^\n]+)", text)
            if sector_match:
                data.sector = sector_match.group(1).strip()

            industry_match = re.search(r"Industry:\s*([^\n]+)", text)
            if industry_match:
                data.industry = industry_match.group(1).strip()

    def _parse_number(self, text: str) -> float:
        """Parse a number from text."""
        # Remove commas and currency symbols
        cleaned = re.sub(r"[₹,\s]", "", text)
        # Extract number
        match = re.search(r"-?[\d.]+", cleaned)
        if match:
            return float(match.group())
        return 0.0

    def _parse_cr_value(self, text: str) -> float:
        """Parse a value in Crores."""
        text = text.lower()
        multiplier = 1

        if "cr" in text:
            multiplier = 1
        elif "lakh" in text or "lac" in text:
            multiplier = 0.01

        return self._parse_number(text) * multiplier

    def _parse_percent(self, text: str) -> float:
        """Parse a percentage value."""
        return self._parse_number(text.replace("%", ""))

    def _parse_high_low(self, text: str) -> tuple[float, float]:
        """Parse high/low range like '2,500 / 1,800'."""
        parts = text.split("/")
        if len(parts) == 2:
            return self._parse_number(parts[0]), self._parse_number(parts[1])
        return 0.0, 0.0


async def get_stock_fundamentals(symbol: str) -> FundamentalData:
    """Convenience function to fetch fundamentals for a stock.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE", "TCS")

    Returns:
        FundamentalData with metrics
    """
    async with ScreenerScraper() as scraper:
        return await scraper.get_fundamentals(symbol)
