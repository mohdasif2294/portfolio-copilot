"""Indian stock market news scrapers."""

from src.data.scrapers.economictimes import EconomicTimesScraper
from src.data.scrapers.moneycontrol import MoneyControlScraper

__all__ = [
    "MoneyControlScraper",
    "EconomicTimesScraper",
]
