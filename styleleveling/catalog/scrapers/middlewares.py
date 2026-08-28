"""Downloader middleware shared by every StyleLeveling retailer spider.

Keeping request headers here prevents individual spiders from slowly drifting
into different configurations.  It also gives future maintainers one obvious
place to update the crawler's HTTP identity.
"""


class StyleLevelingHeadersMiddleware:
    """Add the project's standard headers without overwriting request-specific ones.

    ``setdefault`` is intentional: a retailer spider can still set a more
    specific header on one request when its documented public endpoint needs
    it, while normal catalog and product requests receive consistent defaults.
    """

    DEFAULT_HEADERS = {
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1",
    }

    @classmethod
    def from_crawler(cls, crawler):
        """Construct the middleware using Scrapy's standard component hook."""

        return cls()

    def process_request(self, request, spider):
        """Apply safe defaults immediately before Scrapy downloads a request."""

        for name, value in self.DEFAULT_HEADERS.items():
            request.headers.setdefault(name, value)

        # Returning None tells Scrapy to continue through the downloader stack.
        return None
