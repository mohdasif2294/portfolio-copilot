"""Shared utilities for stock symbol extraction and validation."""

import csv
import io
import json
import logging
import re
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_NSE_EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
_CACHE_DIR = Path(__file__).resolve().parents[3] / "data"
_CACHE_FILE = _CACHE_DIR / "nse_symbols.json"
_CACHE_MAX_AGE_SECS = 7 * 24 * 60 * 60  # 1 week

# ── Handcrafted aliases (short names, abbreviations, common misspellings) ──
# These take priority over the auto-generated mapping from NSE.
_MANUAL_ALIASES: dict[str, str] = {
    # Nifty 50 short names / common aliases
    "reliance": "RELIANCE",
    "reliance industries": "RELIANCE",
    "tcs": "TCS",
    "tata consultancy": "TCS",
    "tata consultancy services": "TCS",
    "infosys": "INFY",
    "infy": "INFY",
    "hdfc bank": "HDFCBANK",
    "hdfc": "HDFCBANK",
    "icici bank": "ICICIBANK",
    "icici": "ICICIBANK",
    "sbi": "SBIN",
    "state bank": "SBIN",
    "state bank of india": "SBIN",
    "wipro": "WIPRO",
    "bharti airtel": "BHARTIARTL",
    "airtel": "BHARTIARTL",
    "bharti": "BHARTIARTL",
    "kotak": "KOTAKBANK",
    "kotak bank": "KOTAKBANK",
    "kotak mahindra": "KOTAKBANK",
    "axis bank": "AXISBANK",
    "axis": "AXISBANK",
    "itc": "ITC",
    "larsen": "LT",
    "larsen & toubro": "LT",
    "l&t": "LT",
    "asian paints": "ASIANPAINT",
    "asianpaint": "ASIANPAINT",
    "maruti": "MARUTI",
    "maruti suzuki": "MARUTI",
    "bajaj finance": "BAJFINANCE",
    "bajaj finserv": "BAJAJFINSV",
    "bajaj auto": "BAJAJ-AUTO",
    "hul": "HINDUNILVR",
    "hindustan unilever": "HINDUNILVR",
    "sun pharma": "SUNPHARMA",
    "sun pharmaceutical": "SUNPHARMA",
    "tech mahindra": "TECHM",
    "techmahindra": "TECHM",
    "titan": "TITAN",
    "titan company": "TITAN",
    "adani ports": "ADANIPORTS",
    "adani green": "ADANIGREEN",
    "adani enterprises": "ADANIENT",
    "adani": "ADANIENT",
    "power grid": "POWERGRID",
    "powergrid": "POWERGRID",
    "ntpc": "NTPC",
    "nestle": "NESTLEIND",
    "nestle india": "NESTLEIND",
    "ultratech": "ULTRACEMCO",
    "ultratech cement": "ULTRACEMCO",
    "tata motors": "TATAMOTORS",
    "tata steel": "TATASTEEL",
    "jio": "JIOFIN",
    "jio financial": "JIOFIN",
    "hcl": "HCLTECH",
    "hcl tech": "HCLTECH",
    "hcl technologies": "HCLTECH",
    "ongc": "ONGC",
    "oil and natural gas": "ONGC",
    "coal india": "COALINDIA",
    "jsw steel": "JSWSTEEL",
    "jsw": "JSWSTEEL",
    "m&m": "M&M",
    "mahindra": "M&M",
    "mahindra & mahindra": "M&M",
    "hero motocorp": "HEROMOTOCO",
    "hero": "HEROMOTOCO",
    "eicher motors": "EICHERMOT",
    "eicher": "EICHERMOT",
    "grasim": "GRASIM",
    "grasim industries": "GRASIM",
    "hindalco": "HINDALCO",
    "hindalco industries": "HINDALCO",
    "cipla": "CIPLA",
    "dr reddy": "DRREDDY",
    "dr reddys": "DRREDDY",
    "dr reddy's": "DRREDDY",
    "divis": "DIVISLAB",
    "divis lab": "DIVISLAB",
    "divi's": "DIVISLAB",
    "britannia": "BRITANNIA",
    "apollo hospitals": "APOLLOHOSP",
    "apollo": "APOLLOHOSP",
    "indusind bank": "INDUSINDBK",
    "indusind": "INDUSINDBK",
    "sbi life": "SBILIFE",
    "hdfc life": "HDFCLIFE",
    "tata consumer": "TATACONSUM",
    "tata consumer products": "TATACONSUM",
    "upl": "UPL",
    "bpcl": "BPCL",
    "bharat petroleum": "BPCL",
    # Popular non-Nifty 50
    "zomato": "ZOMATO",
    "paytm": "PAYTM",
    "one97": "PAYTM",
    "nykaa": "NYKAA",
    "fsn e-commerce": "NYKAA",
    "policybazaar": "POLICYBZR",
    "pb fintech": "POLICYBZR",
    "delhivery": "DELHIVERY",
    "vedanta": "VEDL",
    "vedl": "VEDL",
    "tata power": "TATAPOWER",
    "tata elxsi": "TATAELXSI",
    "irctc": "IRCTC",
    "indian railway": "IRCTC",
    "pidilite": "PIDILITIND",
    "pidilite industries": "PIDILITIND",
    "havells": "HAVELLS",
    "havells india": "HAVELLS",
    "dabur": "DABUR",
    "dabur india": "DABUR",
    "marico": "MARICO",
    "godrej consumer": "GODREJCP",
    "godrej": "GODREJCP",
    "berger paints": "BERGEPAINT",
    "berger": "BERGEPAINT",
    "siemens": "SIEMENS",
    "abb": "ABB",
    "abb india": "ABB",
    "page industries": "PAGEIND",
    "page": "PAGEIND",
    "avenue supermarts": "DMART",
    "dmart": "DMART",
    "srf": "SRF",
    "muthoot finance": "MUTHOOTFIN",
    "muthoot": "MUTHOOTFIN",
    "bajaj holdings": "BAJAJHLDNG",
    "icici prudential": "ICICIPRULI",
    "icici pru": "ICICIPRULI",
    "bandhan bank": "BANDHANBNK",
    "bandhan": "BANDHANBNK",
    "idfc first": "IDFCFIRSTB",
    "idfc first bank": "IDFCFIRSTB",
    "yes bank": "YESBANK",
    "federal bank": "FEDERALBNK",
    "iex": "IEX",
    "indian energy exchange": "IEX",
    "cdsl": "CDSL",
    "hal": "HAL",
    "hindustan aeronautics": "HAL",
    "bhel": "BHEL",
    "bharat heavy": "BHEL",
    "sail": "SAIL",
    "steel authority": "SAIL",
    "indian oil": "IOC",
    "ioc": "IOC",
    "gail": "GAIL",
    "gail india": "GAIL",
    "gabriel": "GABRIEL",
    "gabriel india": "GABRIEL",
    "lupin": "LUPIN",
    "biocon": "BIOCON",
    "torrent pharma": "TORNTPHARM",
    "torrent": "TORNTPHARM",
    "aurobindo": "AUROPHARMA",
    "aurobindo pharma": "AUROPHARMA",
    "colgate": "COLPAL",
    "colgate palmolive": "COLPAL",
    "indigo": "INDIGO",
    "interglobe": "INDIGO",
    "interglobe aviation": "INDIGO",
    "spicejet": "SPICEJET",
}

# ── Dynamic NSE symbol registry ──────────────────────────────────────────────

# Populated lazily: company_name_lower -> SYMBOL
_nse_name_to_symbol: dict[str, str] = {}
# Set of all valid NSE symbols (uppercase)
_nse_symbols: set[str] = set()
_nse_loaded = False


def _load_nse_symbols() -> None:
    """Load NSE equity list from cache or fetch from NSE website.

    Builds two lookups:
      _nse_name_to_symbol: "3m india limited" -> "3MINDIA"
      _nse_symbols: {"3MINDIA", "RELIANCE", ...}
    """
    global _nse_name_to_symbol, _nse_symbols, _nse_loaded
    if _nse_loaded:
        return

    data = _read_cache()
    if data is None:
        data = _fetch_nse_equity_list()
        if data:
            _write_cache(data)

    if not data:
        logger.warning("Could not load NSE symbol list; falling back to manual aliases only")
        _nse_loaded = True
        return

    for symbol, company_name in data.items():
        _nse_symbols.add(symbol)
        name_lower = company_name.lower()
        # Map full company name -> symbol
        _nse_name_to_symbol[name_lower] = symbol
        # Also map symbol lowercase -> symbol  (e.g. "tatamotors" -> "TATAMOTORS")
        _nse_name_to_symbol[symbol.lower()] = symbol

        # Generate useful sub-names:
        # Strip common suffixes like "Limited", "Ltd", "Ltd.", "Industries Limited" etc.
        short = re.sub(
            r"\s+(limited|ltd\.?|industries limited|india limited|corporation limited)$",
            "",
            name_lower,
        )
        if short != name_lower and short not in _nse_name_to_symbol:
            _nse_name_to_symbol[short] = symbol

    _nse_loaded = True
    logger.debug("Loaded %d NSE symbols", len(_nse_symbols))


def _read_cache() -> dict[str, str] | None:
    """Read cached symbol list if fresh enough."""
    try:
        if not _CACHE_FILE.exists():
            return None
        age = time.time() - _CACHE_FILE.stat().st_mtime
        if age > _CACHE_MAX_AGE_SECS:
            return None
        return json.loads(_CACHE_FILE.read_text())
    except Exception:
        logger.debug("Cache read failed", exc_info=True)
        return None


def _write_cache(data: dict[str, str]) -> None:
    """Write symbol list to cache."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        logger.debug("Cache write failed", exc_info=True)


def _fetch_nse_equity_list() -> dict[str, str]:
    """Fetch full NSE equity list CSV and return {SYMBOL: company_name}."""
    try:
        client = httpx.Client(
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            },
        )
        resp = client.get(_NSE_EQUITY_URL)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        result: dict[str, str] = {}
        for row in reader:
            symbol = (row.get("SYMBOL") or "").strip()
            name = (row.get("NAME OF COMPANY") or "").strip()
            if symbol and name:
                result[symbol] = name

        logger.info("Fetched %d symbols from NSE", len(result))
        return result
    except Exception:
        logger.warning("Failed to fetch NSE equity list", exc_info=True)
        return {}


def refresh_nse_symbols() -> int:
    """Force refresh the NSE symbol list. Returns count of symbols loaded."""
    global _nse_loaded
    _nse_loaded = False
    _nse_name_to_symbol.clear()
    _nse_symbols.clear()
    # Delete cache to force re-fetch
    try:
        _CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    _load_nse_symbols()
    return len(_nse_symbols)


# Merged lookup: manual aliases take priority, then NSE auto-generated names
def _get_name_to_symbol() -> dict[str, str]:
    """Get the combined name -> symbol mapping (manual aliases override NSE)."""
    _load_nse_symbols()
    # NSE names first, then manual overrides on top
    merged = dict(_nse_name_to_symbol)
    merged.update(_MANUAL_ALIASES)
    return merged


def is_valid_symbol(symbol: str) -> bool:
    """Check if a symbol exists in the NSE equity list."""
    _load_nse_symbols()
    return symbol.upper() in _nse_symbols


# ── Public API (NAME_TO_SYMBOL kept for backward compat) ─────────────────────

# Lazy property — first access triggers NSE load
class _NameToSymbolProxy(dict):
    """Dict proxy that lazy-loads NSE symbols on first access."""

    _loaded = False

    def _ensure_loaded(self):
        if not self._loaded:
            self._loaded = True
            self.update(_get_name_to_symbol())

    def __contains__(self, key):
        self._ensure_loaded()
        return super().__contains__(key)

    def __getitem__(self, key):
        self._ensure_loaded()
        return super().__getitem__(key)

    def get(self, key, default=None):
        self._ensure_loaded()
        return super().get(key, default)

    def keys(self):
        self._ensure_loaded()
        return super().keys()

    def values(self):
        self._ensure_loaded()
        return super().values()

    def items(self):
        self._ensure_loaded()
        return super().items()

    def __iter__(self):
        self._ensure_loaded()
        return super().__iter__()

    def __len__(self):
        self._ensure_loaded()
        return super().__len__()


NAME_TO_SYMBOL: dict[str, str] = _NameToSymbolProxy()

# Words to ignore when extracting symbols
STOPWORDS = {
    # Articles and determiners
    "a", "an", "the", "all", "any", "each", "every", "few", "more", "most",
    "no", "other", "some", "such", "this", "that", "these", "those",
    # Auxiliary verbs
    "am", "are", "be", "been", "being", "can", "could", "dare", "did",
    "do", "does", "had", "has", "have", "may", "might", "must", "need",
    "ought", "shall", "should", "used", "was", "were", "will", "would",
    # Prepositions
    "about", "above", "after", "at", "beneath", "by", "for", "from", "in",
    "into", "of", "on", "over", "regarding", "to", "under", "up", "with",
    # Conjunctions
    "and", "but", "either", "neither", "nor", "or", "so", "yet",
    # Adverbs and modifiers
    "also", "how", "just", "now", "only", "same", "than", "too", "very",
    "when", "where", "why",
    # Pronouns
    "he", "her", "hers", "herself", "him", "himself", "his", "i", "it",
    "its", "itself", "me", "my", "myself", "our", "ours", "ourselves",
    "she", "their", "theirs", "themselves", "them", "they", "us", "we",
    "you", "your", "yours", "yourself", "yourselves",
    # Interrogatives
    "what", "which", "who", "whom",
    # Common verbs
    "ask", "call", "come", "feel", "find", "get", "give", "go", "know",
    "leave", "look", "make", "seem", "see", "show", "take", "tell",
    "think", "try", "use", "want", "work",
    # Adjectives
    "bad", "good",
    # Financial/stock-related words
    "analysis", "analyze", "fundamental", "fundamentals",
    "growth", "hold", "invest", "investing", "investment", "market",
    "opinion", "portfolio", "price", "recommend", "recommendation",
    "research", "sell", "share", "shares", "stock", "stocks", "suggest",
    "thoughts", "value", "view",
    # Events-related words
    "event", "events", "announcement", "announcements", "corporate",
    "action", "actions", "meeting", "meetings", "dividend", "dividends",
    "merger", "mergers", "acquisition", "acquisitions", "earning",
    # Time-related words
    "here", "there", "today", "tomorrow", "yesterday",
    # Exchange-related words
    "bse", "exchange", "nifty", "nse", "sensex",
    # Politeness and common phrases
    "help", "please", "thank", "thanks",
}


def extract_symbol(query: str) -> str | None:
    """Extract stock symbol from natural language query.

    This function tries multiple strategies in order:
    Strategy 0: Exchange pattern matching (e.g., "NSE:INFY", "BSE:TCS")
    Strategy 1: Known company name mappings — manual aliases + all NSE-listed companies
    Strategy 2: Exact NSE symbol match (validates against full NSE list)
    Strategy 3: Uppercase word detection (matches uppercase words that look like symbols)
    Strategy 4: Non-stopword fallback (any word that's not a stopword and looks like a symbol)

    Args:
        query: Natural language query like "Is Reliance a good buy?"

    Returns:
        Stock symbol like "RELIANCE" or None if not found

    Examples:
        >>> extract_symbol("Is Reliance a good buy?")
        'RELIANCE'
        >>> extract_symbol("analyze ZOMATO")
        'ZOMATO'
        >>> extract_symbol("what about paytm stock")
        'PAYTM'
        >>> extract_symbol("is gabriel good")
        'GABRIEL'
        >>> extract_symbol("check NSE:INFY")
        'INFY'
        >>> extract_symbol("events for 3M India")
        '3MINDIA'
    """
    if not query:
        return None

    # Strategy 0: Check for exchange:symbol patterns (NSE:INFY, BSE:TCS)
    exchange_match = re.search(r"\b(?:NSE|BSE):([A-Z][A-Z0-9&-]{1,14})\b", query, re.IGNORECASE)
    if exchange_match:
        return exchange_match.group(1).upper()

    query_lower = query.lower()

    # Strategy 1: Check known company name mappings (longest match first)
    # This now includes all NSE-listed company names + manual aliases
    name_map = _get_name_to_symbol()
    for name in sorted(name_map.keys(), key=len, reverse=True):
        if name in query_lower:
            return name_map[name]

    # Strategy 2: Check if any word is an exact valid NSE symbol
    _load_nse_symbols()
    words_upper = re.findall(r"\b([A-Z][A-Z0-9&-]{1,14})\b", query)
    for word in words_upper:
        if word in _nse_symbols and word.lower() not in STOPWORDS:
            return word

    # Strategy 3: Look for uppercase words (likely symbols)
    for match in words_upper:
        if match.lower() not in STOPWORDS:
            return match

    # Strategy 4: Look for any word that could be a symbol
    words = re.findall(r"\b([a-zA-Z][a-zA-Z0-9&-]{1,14})\b", query)
    for word in words:
        word_lower = word.lower()
        if word_lower not in STOPWORDS and len(word) >= 2:
            if word[0].isupper() or word_lower not in _COMMON_WORDS:
                return word.upper()

    return None


# Common English words that are unlikely to be stock symbols
_COMMON_WORDS = {
    "after", "again", "against", "because", "before", "being", "between",
    "during", "each", "further", "having", "once", "only", "other",
    "over", "same", "should", "such", "through", "under", "until",
    "very", "while", "company", "companies", "business", "industry",
    "sector", "earnings", "profit", "loss", "revenue", "quarter",
    "year", "month", "week", "day", "time", "money", "percent",
    "percentage", "increase", "decrease", "rise", "fall", "drop",
    "gain", "down", "high", "low", "best", "worst", "top", "bottom",
    "first", "last", "next", "previous", "current", "recent", "latest",
    "new", "old", "big", "small", "large", "long", "short", "term",
}


def normalize_symbol(symbol: str) -> str:
    """Normalize a stock symbol to standard format.

    Args:
        symbol: Raw symbol input

    Returns:
        Normalized uppercase symbol
    """
    if not symbol:
        return ""

    # Remove common prefixes/suffixes
    symbol = symbol.strip().upper()
    symbol = re.sub(r"^(NSE:|BSE:)", "", symbol)
    symbol = re.sub(r"\.NS$|\.BO$", "", symbol)

    return symbol
