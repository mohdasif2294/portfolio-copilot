"""Shared utilities for stock symbol extraction and validation."""

import re

# Common Indian stock name to NSE symbol mapping
# This covers Nifty 50 and other popular stocks
NAME_TO_SYMBOL: dict[str, str] = {
    # Nifty 50 constituents
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
    # Popular non-Nifty 50 stocks
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
    Strategy 1: Known company name mappings (case-insensitive)
    Strategy 2: Uppercase word detection (matches uppercase words that look like symbols)
    Strategy 3: Non-stopword fallback (any word that's not a stopword and looks like a symbol)

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
    """
    if not query:
        return None

    # Strategy 0: Check for exchange:symbol patterns (NSE:INFY, BSE:TCS)
    exchange_match = re.search(r"\b(?:NSE|BSE):([A-Z][A-Z0-9&-]{1,14})\b", query, re.IGNORECASE)
    if exchange_match:
        return exchange_match.group(1).upper()

    query_lower = query.lower()

    # Strategy 1: Check known company name mappings (longest match first)
    # Sort by length descending to match "tata consultancy services" before "tcs"
    for name in sorted(NAME_TO_SYMBOL.keys(), key=len, reverse=True):
        if name in query_lower:
            return NAME_TO_SYMBOL[name]

    # Strategy 2: Look for uppercase words (likely symbols)
    # Match 2-15 character uppercase words, including those with & or -
    uppercase_matches = re.findall(r"\b([A-Z][A-Z0-9&-]{1,14})\b", query)
    for match in uppercase_matches:
        # Skip common uppercase words
        if match.lower() not in STOPWORDS:
            return match

    # Strategy 3: Look for any word that could be a symbol
    # This handles lowercase unknown symbols like "zomato" not in mapping
    words = re.findall(r"\b([a-zA-Z][a-zA-Z0-9&-]{1,14})\b", query)
    for word in words:
        word_lower = word.lower()
        # Skip stopwords and common words
        if word_lower not in STOPWORDS and len(word) >= 2:
            # Check if it looks like a potential symbol
            # (not a common English word, or starts with capital)
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
