"""BSE India corporate announcements scraper."""

import csv
import io
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import structlog

log = structlog.get_logger()

BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
BSE_ANN_BASE = "https://www.bseindia.com/xml-data/corpfiling/AttachLive"
BSE_BHAV_URL = "https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{date}_F_0000.CSV"

_CACHE_DIR = Path(__file__).resolve().parents[3] / "data"
_SCRIP_CACHE_FILE = _CACHE_DIR / "bse_scrip_codes.json"
_CACHE_MAX_AGE_SECS = 7 * 24 * 60 * 60  # 1 week

# ── Dynamic scrip code mapping ───────────────────────────────────────────────

_symbol_to_scrip: dict[str, str] = {}
_scrip_loaded = False


def _load_scrip_codes() -> None:
    """Load BSE scrip code mapping from cache or fetch from BSE bhav copy."""
    global _symbol_to_scrip, _scrip_loaded
    if _scrip_loaded:
        return

    data = _read_scrip_cache()
    if data is None:
        data = _fetch_bse_scrip_codes()
        if data:
            _write_scrip_cache(data)

    if data:
        _symbol_to_scrip = data
        log.debug("scrip_codes_loaded", count=len(_symbol_to_scrip))
    else:
        log.warning("scrip_codes_unavailable")

    _scrip_loaded = True


def _read_scrip_cache() -> dict[str, str] | None:
    """Read cached scrip code mapping if fresh enough."""
    try:
        if not _SCRIP_CACHE_FILE.exists():
            return None
        age = time.time() - _SCRIP_CACHE_FILE.stat().st_mtime
        if age > _CACHE_MAX_AGE_SECS:
            return None
        return json.loads(_SCRIP_CACHE_FILE.read_text())
    except Exception:
        log.debug("scrip_cache_read_failed", exc_info=True)
        return None


def _write_scrip_cache(data: dict[str, str]) -> None:
    """Write scrip code mapping to cache."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _SCRIP_CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        log.debug("scrip_cache_write_failed", exc_info=True)


def _fetch_bse_scrip_codes() -> dict[str, str]:
    """Fetch BSE bhav copy CSV to build ticker symbol -> scrip code mapping.

    The bhav copy CSV has columns including:
    - FinInstrmId: BSE scrip code (e.g. "500325")
    - TckrSymb: Ticker symbol (e.g. "RELIANCE")
    """
    client = httpx.Client(
        timeout=30.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        },
    )

    # Try today and a few previous days (weekends/holidays may not have data)
    for days_back in range(7):
        dt = datetime.now() - timedelta(days=days_back)
        date_str = dt.strftime("%Y%m%d")
        url = BSE_BHAV_URL.format(date=date_str)

        try:
            resp = client.get(url)
            if resp.status_code != 200:
                continue

            # Check it's actually CSV, not an error page
            if resp.text.strip().startswith("<!DOCTYPE") or resp.text.strip().startswith("<html"):
                continue

            reader = csv.DictReader(io.StringIO(resp.text))
            result: dict[str, str] = {}
            for row in reader:
                ticker = (row.get("TckrSymb") or "").strip().upper()
                scrip = (row.get("FinInstrmId") or "").strip()
                if ticker and scrip and scrip.isdigit():
                    result[ticker] = scrip

            if result:
                log.info("bhav_copy_fetched", count=len(result), date=date_str)
                return result

        except Exception:
            log.debug("bhav_copy_fetch_failed", date=date_str, exc_info=True)
            continue

    log.warning("bhav_copy_unavailable")
    return {}


def get_scrip_code(symbol: str) -> str:
    """Resolve an NSE/BSE ticker symbol to a BSE scrip code.

    Falls back to returning the symbol itself if not found.
    """
    _load_scrip_codes()
    return _symbol_to_scrip.get(symbol.upper(), symbol)


# ── Data model & classification ──────────────────────────────────────────────


@dataclass
class CorporateEvent:
    """A corporate event/announcement from BSE."""

    title: str
    category: str
    description: str
    url: str
    date: datetime | None
    symbol: str
    source: str = "bse"


# Category classification keywords
_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "board_meeting": ["board meeting", "board of directors"],
    "dividend": ["dividend", "interim dividend", "final dividend"],
    "acquisition": ["acquisition", "acquired", "takeover"],
    "merger": ["merger", "amalgamation", "demerger"],
    "earnings": [
        "financial results", "quarterly results", "earnings",
        "annual results", "result",
    ],
    "govt_policy": ["regulation", "government", "sebi", "rbi", "policy"],
}

# Category display colors for Rich
CATEGORY_COLORS: dict[str, str] = {
    "board_meeting": "yellow",
    "dividend": "green",
    "acquisition": "magenta",
    "merger": "blue",
    "earnings": "cyan",
    "govt_policy": "red",
    "other": "dim",
}


def categorize_event(title: str) -> str:
    """Classify event into a category using keyword matching."""
    title_lower = title.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return category
    return "other"


# ── Scraper ──────────────────────────────────────────────────────────────────


class BSEScraper:
    """Scraper for BSE India corporate announcements."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://www.bseindia.com/",
                "Accept": "application/json",
            },
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def get_corporate_events(
        self, symbol: str, limit: int = 20
    ) -> list[CorporateEvent]:
        """Fetch corporate events for a specific stock from BSE.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE") or BSE scrip code
            limit: Maximum number of events to return

        Returns:
            List of CorporateEvent objects
        """
        # Resolve symbol to BSE scrip code
        scrip = get_scrip_code(symbol)

        try:
            params = {
                "pageno": "1",
                "strCat": "-1",
                "strPrevDate": "",
                "strScrip": scrip,
                "strSearch": "P",
                "strToDate": "",
                "strType": "C",
            }
            resp = await self._client.get(BSE_API_URL, params=params)
            resp.raise_for_status()

            data = resp.json()
            table = data.get("Table", [])

            events: list[CorporateEvent] = []
            for row in table[:limit]:
                news_sub = row.get("NEWSSUB", "") or ""
                headline = row.get("HEADLINE", "") or ""
                att_name = row.get("ATTACHMENTNAME", "") or ""
                dt_str = row.get("NEWS_DT", "") or row.get("DT_TM", "") or ""

                # Parse date
                event_date = self._parse_date(dt_str)

                # Build URL to attachment if available
                url = ""
                if att_name:
                    url = f"{BSE_ANN_BASE}/{att_name}"

                title = news_sub or headline
                if not title:
                    continue

                events.append(
                    CorporateEvent(
                        title=title.strip(),
                        category=categorize_event(title),
                        description=headline.strip(),
                        url=url,
                        date=event_date,
                        symbol=symbol.upper(),
                    )
                )

            return events

        except httpx.HTTPStatusError as e:
            log.error("bse_api_http_error", symbol=symbol, status_code=e.response.status_code)
            return []
        except Exception:
            log.error("bse_api_error", symbol=symbol, exc_info=True)
            return []

    @staticmethod
    def _parse_date(dt_str: str) -> datetime | None:
        """Parse date string from BSE API response."""
        if not dt_str:
            return None
        # BSE returns dates like "2026-01-29T19:46:42.323"
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%d-%b-%Y %H:%M:%S",
            "%d/%m/%Y",
            "%d-%b-%Y",
        ):
            try:
                return datetime.strptime(dt_str.strip(), fmt)
            except ValueError:
                continue
        return None
