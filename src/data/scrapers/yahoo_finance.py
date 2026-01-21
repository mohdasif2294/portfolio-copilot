"""Yahoo Finance news scraper using RSS feeds."""

import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx
from bs4 import BeautifulSoup

# Yahoo Finance RSS feeds - India focused
RSS_FEEDS = {
    "india": "https://finance.yahoo.com/rss/topfinstories",
    "india_news": "https://in.finance.yahoo.com/news/rss",
}

STOCK_NEWS_URL = "https://finance.yahoo.com/quote/{symbol}/news"


@dataclass
class NewsArticle:
    """A scraped news article."""

    title: str
    content: str
    url: str
    published_at: datetime | None
    source: str = "yahoo_finance"
    symbol: str | None = None


class YahooFinanceScraper:
    """Scraper for Yahoo Finance news via RSS and web."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def get_rss_news(
        self, feed: str = "india", limit: int = 10
    ) -> list[NewsArticle]:
        """Fetch news from RSS feed.

        Args:
            feed: Feed name ("india" or "india_news")
            limit: Maximum articles to fetch
        """
        feed_url = RSS_FEEDS.get(feed, RSS_FEEDS["india"])

        try:
            response = await self._client.get(feed_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        parsed = feedparser.parse(response.text)
        articles = []

        for entry in parsed.entries[:limit]:
            # Parse publish date
            published_at = None
            if hasattr(entry, "published"):
                try:
                    published_at = parsedate_to_datetime(entry.published)
                except (ValueError, TypeError):
                    pass

            # Get content from description or fetch full article
            content = ""
            if hasattr(entry, "summary"):
                # Clean HTML from summary
                soup = BeautifulSoup(entry.summary, "lxml")
                content = soup.get_text(strip=True)

            # If content is too short, try to fetch full article
            if len(content) < 200 and hasattr(entry, "link"):
                full_content = await self._fetch_article_content(entry.link)
                if full_content:
                    content = full_content

            articles.append(
                NewsArticle(
                    title=entry.title if hasattr(entry, "title") else "",
                    content=content,
                    url=entry.link if hasattr(entry, "link") else "",
                    published_at=published_at,
                )
            )

        return articles

    async def search_stock_news(
        self, symbol: str, limit: int = 10
    ) -> list[NewsArticle]:
        """Search for news about a specific stock.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE.NS" for NSE stocks)
            limit: Maximum articles to fetch
        """
        # Try multiple symbol formats for Indian stocks
        symbols_to_try = [symbol]
        if not any(symbol.endswith(suffix) for suffix in [".NS", ".BO", ".L", ".TO"]):
            symbols_to_try = [f"{symbol}.NS", f"{symbol}.BO", symbol]

        for yahoo_symbol in symbols_to_try:
            url = STOCK_NEWS_URL.format(symbol=yahoo_symbol)

            try:
                response = await self._client.get(url)
                if response.status_code == 404:
                    continue  # Try next symbol format
                response.raise_for_status()
            except httpx.HTTPError:
                continue  # Try next symbol format

            soup = BeautifulSoup(response.text, "lxml")
            articles = []

            # Find news items - Yahoo uses various class names
            news_items = soup.select("li[class*='stream-item']")[:limit]

            if not news_items:
                # Try alternate selectors
                news_items = soup.select("div[class*='Ov(h)'] a[href*='/news/']")[:limit]

            if not news_items:
                news_items = soup.select("a[href*='/news/']")[:limit]

            for item in news_items:
                link = item.select_one("a") if item.name != "a" else item
                if not link:
                    continue

                title_elem = link.select_one("h3") or link
                title = title_elem.get_text(strip=True)
                article_url = link.get("href", "")

                if not title or len(title) < 10:
                    continue

                if not article_url.startswith("http"):
                    article_url = "https://finance.yahoo.com" + article_url

                # Fetch full article content
                content = await self._fetch_article_content(article_url)

                articles.append(
                    NewsArticle(
                        title=title,
                        content=content or title,
                        url=article_url,
                        published_at=None,
                        symbol=symbol.upper(),
                    )
                )

            if articles:
                return articles

        # No articles found with any symbol format
        return []

    async def _fetch_article_content(self, url: str) -> str | None:
        """Fetch and extract content from a news article."""
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        # Try various content selectors
        content_selectors = [
            "div.caas-body",
            "article",
            "div[class*='article-body']",
            "div[class*='story-body']",
        ]

        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Remove unwanted elements
                for tag in content_div.select("script, style, aside, nav, footer"):
                    tag.decompose()

                content = content_div.get_text(separator="\n", strip=True)
                content = re.sub(r"\n{3,}", "\n\n", content)
                content = re.sub(r" {2,}", " ", content)

                if len(content) > 100:
                    return content[:5000]

        return None


async def fetch_yahoo_news(
    symbol: str | None = None, limit: int = 10
) -> list[NewsArticle]:
    """Convenience function to fetch Yahoo Finance news.

    Args:
        symbol: Optional stock symbol to search for
        limit: Maximum articles to fetch
    """
    async with YahooFinanceScraper() as scraper:
        if symbol:
            return await scraper.search_stock_news(symbol, limit)
        return await scraper.get_rss_news(limit=limit)
