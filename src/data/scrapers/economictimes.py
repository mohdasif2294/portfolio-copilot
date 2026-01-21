"""Economic Times news scraper for Indian stock market news."""

import re
from dataclasses import dataclass
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://economictimes.indiatimes.com"
MARKETS_URL = f"{BASE_URL}/markets/stocks/news"
STOCK_URL = f"{BASE_URL}/topic"


@dataclass
class NewsArticle:
    """A scraped news article."""

    title: str
    content: str
    url: str
    published_at: datetime | None
    source: str = "economictimes"
    symbol: str | None = None


class EconomicTimesScraper:
    """Scraper for Economic Times news articles."""

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

    async def get_latest_news(self, limit: int = 10) -> list[NewsArticle]:
        """Fetch latest stock market news articles.

        Args:
            limit: Maximum number of articles to fetch
        """
        try:
            response = await self._client.get(MARKETS_URL)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        soup = BeautifulSoup(response.text, "lxml")
        articles = []

        # Find news article links
        news_items = soup.select("div.eachStory")[:limit]

        if not news_items:
            news_items = soup.select("div.story-box")[:limit]

        if not news_items:
            # Try generic article links
            news_items = soup.select("a[href*='/markets/stocks/news/']")[:limit]

        for item in news_items:
            link = item.select_one("a") if item.name != "a" else item
            if not link:
                continue

            title = link.get_text(strip=True)
            url = link.get("href", "")

            if not title or len(title) < 10:
                continue

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
            query: Search term (e.g., "reliance", "TCS", "gabriel")
            limit: Maximum number of articles
        """
        # Try topic page first
        search_url = f"{STOCK_URL}/{query.lower()}"

        try:
            response = await self._client.get(search_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return await self._search_fallback(query, limit)

        soup = BeautifulSoup(response.text, "lxml")
        articles = []

        # Find article links on topic page
        news_items = soup.select("div.eachStory a, div.story-box a")[:limit]

        if not news_items:
            news_items = soup.select("a[href*='/articleshow/']")[:limit]

        for item in news_items:
            link = item if item.name == "a" else item.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            url = link.get("href", "")

            if not title or len(title) < 10:
                continue

            if not url.startswith("http"):
                url = BASE_URL + url

            article = await self._fetch_article(url, title, symbol=query.upper())
            if article:
                articles.append(article)

        if not articles:
            return await self._search_fallback(query, limit)

        return articles

    async def _search_fallback(
        self, query: str, limit: int
    ) -> list[NewsArticle]:
        """Fallback search using site search."""
        search_url = f"{BASE_URL}/searchresult.cms?query={query}"

        try:
            response = await self._client.get(search_url)
            response.raise_for_status()
        except httpx.HTTPError:
            return []

        soup = BeautifulSoup(response.text, "lxml")
        articles = []

        # Find search results
        results = soup.select("div.search-result a, div.eachStory a")[:limit]

        for link in results:
            title = link.get_text(strip=True)
            url = link.get("href", "")

            if not title or len(title) < 10:
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

        # Extract article content - try multiple selectors
        content_selectors = [
            "div.artText",
            "div.article-body",
            "div.Normal",
            "article",
        ]

        content_div = None
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                break

        if not content_div:
            return None

        # Remove unwanted elements
        for tag in content_div.select("script, style, aside, div.also-read"):
            tag.decompose()

        content = content_div.get_text(separator="\n", strip=True)

        # Clean up content
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)

        if len(content) < 50:
            return None

        # Extract publish date
        published_at = None
        date_elem = soup.select_one("time") or soup.select_one("span.publish_on")

        if date_elem:
            date_text = date_elem.get("datetime") or date_elem.get_text(strip=True)
            published_at = self._parse_date(date_text)

        return NewsArticle(
            title=title,
            content=content[:5000],
            url=url,
            published_at=published_at,
            symbol=symbol,
        )

    def _parse_date(self, date_text: str) -> datetime | None:
        """Parse date from various ET formats."""
        if not date_text:
            return None

        # Try ISO format first
        try:
            return datetime.fromisoformat(date_text.replace("Z", "+00:00"))
        except ValueError:
            pass

        # Try common formats
        patterns = [
            ("%B %d, %Y", r"(\w+ \d{1,2}, \d{4})"),
            ("%b %d, %Y", r"(\w+ \d{1,2}, \d{4})"),
            ("%d %b %Y", r"(\d{1,2} \w+ \d{4})"),
        ]

        for fmt, pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    return datetime.strptime(match.group(1), fmt)
                except ValueError:
                    continue

        return None


async def fetch_et_news(
    query: str | None = None, limit: int = 10
) -> list[NewsArticle]:
    """Convenience function to fetch Economic Times news.

    Args:
        query: Optional search query (stock symbol or keyword)
        limit: Maximum articles to fetch
    """
    async with EconomicTimesScraper() as scraper:
        if query:
            return await scraper.search_news(query, limit)
        return await scraper.get_latest_news(limit)
