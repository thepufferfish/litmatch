from __future__ import annotations

from typing import TYPE_CHECKING

from rotating_proxies.middlewares import RotatingProxyMiddleware
from scrapy import signals
from scrapy.exceptions import NotConfigured

from bookmarks.proxies import fetch_proxy_list

if TYPE_CHECKING:
    from scrapy import Request, Spider
    from scrapy.crawler import Crawler


class BookmarksDownloaderMiddleware:
    """Rewrites bookmark URLs to their review-page equivalents."""

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> BookmarksDownloaderMiddleware:
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request: Request, spider: Spider) -> Request | None:
        url = request.url
        if "https://bookmarks.reviews/bookmark" in url:
            new_url = url.replace(
                "https://bookmarks.reviews/bookmark",
                "https://bookmarks.reviews/reviews",
            )
            spider.logger.debug("Redirecting from %s to %s", url, new_url)
            return request.replace(url=new_url)
        return None

    def spider_opened(self, spider: Spider) -> None:
        spider.logger.info("Spider opened: %s", spider.name)


class WebshareProxyMiddleware(RotatingProxyMiddleware):
    """RotatingProxyMiddleware that fetches proxies from Webshare at init time.

    Proxies are loaded in-memory from the Webshare API when the middleware
    initialises -- no proxy file is written to disk. If PROXY_TOKEN is unset
    or the API call fails, the middleware raises NotConfigured so Scrapy
    disables it and requests go direct.
    """

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> WebshareProxyMiddleware:
        proxies = fetch_proxy_list()
        if not proxies:
            raise NotConfigured("No proxies available; middleware disabled")
        # Clear any file path to ensure the in-memory list takes precedence
        crawler.settings.set("ROTATING_PROXY_LIST_PATH", None, priority="cmdline")
        crawler.settings.set("ROTATING_PROXY_LIST", proxies, priority="cmdline")
        return super().from_crawler(crawler)
