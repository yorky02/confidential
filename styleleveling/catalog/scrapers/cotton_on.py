import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

import scrapy


class CottonOnSpider(scrapy.Spider):
    """Import public Cotton On US sale listings for men and women."""

    name = "cotton_on"
    store_name = "Cotton On"
    store_url = "https://cottonon.com/US/"
    allowed_domains = ["cottonon.com"]
    sale_pages = {
        "men": "https://cottonon.com/US/co/co-sale/sale-mens/",
        "women": "https://cottonon.com/US/co/co-sale/sale-womens/",
    }
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "USER_AGENT": "StyleLevelingBot/1.0 (+https://levelingstyle.org)",
        "DOWNLOAD_DELAY": 1.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1.5,
        "AUTOTHROTTLE_MAX_DELAY": 10,
        "RETRY_TIMES": 2,
        "DOWNLOAD_TIMEOUT": 30,
        "LOG_LEVEL": "INFO",
    }

    def __init__(self, audience="both", max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if audience not in {"men", "women", "both"}:
            raise ValueError("audience must be men, women, or both")
        self.audience = audience
        self.max_pages = int(max_pages) if max_pages else None

    async def start(self):
        audiences = self.sale_pages if self.audience == "both" else [self.audience]
        for audience in audiences:
            yield scrapy.Request(
                self.sale_pages[audience],
                callback=self.parse_sale_page,
                cb_kwargs={"audience": audience, "page_number": 1},
            )

    def parse_sale_page(self, response, audience, page_number):
        for tile in response.css("div.product-tile[data-itemid]"):
            product_url = tile.css("a.thumb-link::attr(href)").get()
            external_id = tile.attrib.get("data-itemid")
            if not product_url or not external_id:
                continue
            yield response.follow(
                product_url,
                callback=self.parse_product,
                cb_kwargs={
                    "sale_audience": audience,
                    "discovered_external_id": external_id,
                },
            )

        next_url = response.css('link[rel="next"]::attr(href)').get()
        if next_url and (self.max_pages is None or page_number < self.max_pages):
            yield response.follow(
                next_url,
                callback=self.parse_sale_page,
                cb_kwargs={"audience": audience, "page_number": page_number + 1},
            )

    def parse_product(self, response, sale_audience, discovered_external_id):
        tracking = self._tracking_data(response)
        name = tracking.get("item_name") or response.css("h1::text").get()
        current_price = self._decimal(tracking.get("price"))
        discount = self._decimal(tracking.get("discount"))
        if not name or current_price is None:
            self.logger.warning("Skipping product with incomplete data: %s", response.url)
            return

        original_price = current_price + discount if discount and discount > 0 else current_price
        external_id = tracking.get("item_variant") or discovered_external_id
        category = tracking.get("item_category5") or "Clothing"
        audience = str(tracking.get("item_category4") or sale_audience).lower()
        if audience not in {"men", "women"}:
            audience = sale_audience

        image_urls = []
        for image_url in response.css(".product-thumbnails a.thumbnail-link::attr(href)").getall():
            clean_url = self._clean_image_url(response.urljoin(image_url))
            if clean_url not in image_urls:
                image_urls.append(clean_url)

        if not image_urls:
            for image_url in response.css(".pdp-product-images img::attr(src)").getall():
                clean_url = self._clean_image_url(response.urljoin(image_url))
                if clean_url not in image_urls:
                    image_urls.append(clean_url)

        yield {
            "external_product_id": str(external_id),
            "product_name": " ".join(name.split()),
            "brand_name": tracking.get("item_brand") or "Cotton On",
            "category": str(category).strip() or "Clothing",
            "audience": audience,
            "product_page_url": response.css('link[rel="canonical"]::attr(href)').get() or response.url,
            "current_price": current_price,
            "original_price": original_price,
            "image_urls": image_urls,
        }

    @staticmethod
    def _tracking_data(response):
        raw = response.css("input.ga4-gtm-product-data::attr(data-gtag)").get()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _decimal(value):
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _clean_image_url(url):
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
