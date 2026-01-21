"""Indian stock market news scrapers."""

from src.data.scrapers.economictimes import EconomicTimesScraper, fetch_et_news
from src.data.scrapers.moneycontrol import MoneyControlScraper, fetch_moneycontrol_news

__all__ = [
    "MoneyControlScraper",
    "EconomicTimesScraper",
    "fetch_moneycontrol_news",
    "fetch_et_news",
]
