"""MoneyControl news scraper for Indian stock market news."""

import re
from dataclasses import dataclass
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.moneycontrol.com"
NEWS_URL = f"{BASE_URL}/news/business/stocks"
SEARCH_URL = f"{BASE_URL}/news/tags"


@dataclass
class NewsArticle:
    """A scraped news article."""

    title: str
    content: str
    url: str
    published_at: datetime | None
    source: str = "moneycontrol"
    symbol: str | None = None


class MoneyControlScraper:
    """Scraper for MoneyControl news articles."""

    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            },
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def get_latest_news(self, limit: int = 10) -> list[NewsArticle]:
        """Fetch latest stock market news articles.

        Args:
            limit: Maximum number of articles to fetch
        """
        try:
            response = await self._client.get(NEWS_URL)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        soup = BeautifulSoup(response.text, "lxml")
        articles = []

        # Find news article links
        news_items = soup.select("li.clearfix")[:limit]

        for item in news_items:
            link = item.select_one("h2 a") or item.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            url = link.get("href", "")

            if not url.startswith("http"):
                url = BASE_URL + url

            # Fetch full article content
            article = await self._fetch_article(url, title)
            if article:
                articles.append(article)

        return articles

    async def search_news(
        self, query: str, limit: int = 10
    ) -> list[NewsArticle]:
        """Search for news by keyword or stock symbol.

        Args:
            query: Search term (e.g., "reliance", "TCS")
            limit: Maximum number of articles
        """
        search_url = f"{SEARCH_URL}/{query.lower()}.html"

        try:
            response = await self._client.get(search_url)
            response.raise_for_status()
        except httpx.HTTPError:
            # Try alternate search format
            return await self._search_fallback(query, limit)

        soup = BeautifulSoup(response.text, "lxml")
        articles = []

        # Find article links
        links = soup.select("a.fleft")[:limit]

        for link in links:
            title = link.get_text(strip=True)
            url = link.get("href", "")

            if not url.startswith("http"):
                url = BASE_URL + url

            article = await self._fetch_article(url, title, symbol=query.upper())
            if article:
                articles.append(article)

        return articles

    async def _search_fallback(
        self, query: str, limit: int
    ) -> list[NewsArticle]:
        """Fallback search using Google site search pattern."""
        # Use news section filtering
        news_url = f"{NEWS_URL}?tag={query}"

        try:
            response = await self._client.get(news_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        soup = BeautifulSoup(response.text, "lxml")
        articles = []

        news_items = soup.select("li.clearfix")[:limit]

        for item in news_items:
            link = item.select_one("h2 a") or item.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            url = link.get("href", "")

            if query.lower() not in title.lower():
                continue

            if not url.startswith("http"):
                url = BASE_URL + url

            article = await self._fetch_article(url, title, symbol=query.upper())
            if article:
                articles.append(article)

        return articles

    async def _fetch_article(
        self,
        url: str,
        title: str,
        symbol: str | None = None,
    ) -> NewsArticle | None:
        """Fetch and parse a single article."""
        try:
            response = await self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        soup = BeautifulSoup(response.text, "lxml")

        # Extract article content
        content_div = soup.select_one("div.content_wrapper") or soup.select_one(
            "div.article_desc"
        )

        if not content_div:
            # Try alternate selectors
            content_div = soup.select_one("article") or soup.select_one("div.arti-flow")

        if not content_div:
            return None

        # Get text content, removing scripts and styles
        for tag in content_div.select("script, style, aside"):
            tag.decompose()

        content = content_div.get_text(separator="\n", strip=True)

        # Clean up content
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)

        # Extract publish date
        published_at = None
        date_elem = soup.select_one("div.article_schedule") or soup.select_one(
            "span.article_schedule"
        )

        if date_elem:
            date_text = date_elem.get_text(strip=True)
            published_at = self._parse_date(date_text)

        return NewsArticle(
            title=title,
            content=content[:5000],  # Limit content length
            url=url,
            published_at=published_at,
            symbol=symbol,
        )

    def _parse_date(self, date_text: str) -> datetime | None:
        """Parse date from various MoneyControl formats."""
        # Common formats: "January 20, 2025 10:30 AM IST", "Jan 20, 2025"
        patterns = [
            r"(\w+ \d{1,2}, \d{4})",
            r"(\d{1,2} \w+ \d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    return datetime.strptime(match.group(1), "%B %d, %Y")
                except ValueError:
                    try:
                        return datetime.strptime(match.group(1), "%b %d, %Y")
                    except ValueError:
                        try:
                            return datetime.strptime(match.group(1), "%d %B %Y")
                        except ValueError:
                            continue

        return None


async def fetch_moneycontrol_news(
    query: str | None = None, limit: int = 10
) -> list[NewsArticle]:
    """Convenience function to fetch news.

    Args:
        query: Optional search query (stock symbol or keyword)
        limit: Maximum articles to fetch
    """
    async with MoneyControlScraper() as scraper:
        if query:
            return await scraper.search_news(query, limit)
        return await scraper.get_latest_news(limit)
