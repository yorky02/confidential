from decimal import Decimal

from django.test import TestCase
from scrapy.http import HtmlResponse, Request

from .models import Listing, PriceHistory, Store
from .scrapers.cotton_on import CottonOnSpider
from .scrapers.pipelines import DjangoCatalogPipeline


class CottonOnSpiderTests(TestCase):
    def response(self, html, url="https://cottonon.com/US/test/123-01.html"):
        request = Request(url=url)
        return HtmlResponse(url=url, request=request, body=html, encoding="utf-8")

    def test_product_parser_extracts_prices_audience_category_and_images(self):
        html = """
            <html><head><link rel="canonical" href="https://cottonon.com/US/test/123-01.html"></head>
            <body>
              <h1>Test Shirt</h1>
              <input class="ga4-gtm-product-data" data-gtag='{"item_name":"Test Shirt","item_brand":"Cotton On Men","item_category4":"Men","item_category5":"Tops","item_variant":"123-01","price":12.48,"discount":12.51}'>
              <div class="product-thumbnails">
                <a class="thumbnail-link" href="/images/one.jpg?size=small"></a>
                <a class="thumbnail-link" href="/images/two.jpg"></a>
              </div>
            </body></html>
        """
        spider = CottonOnSpider()
        items = list(spider.parse_product(self.response(html), "men", "123-01"))

        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["current_price"], Decimal("12.48"))
        self.assertEqual(item["original_price"], Decimal("24.99"))
        self.assertEqual(item["audience"], "men")
        self.assertEqual(item["category"], "Tops")
        self.assertEqual(len(item["image_urls"]), 2)
        self.assertNotIn("?", item["image_urls"][0])


class DjangoCatalogPipelineTests(TestCase):
    def setUp(self):
        self.pipeline = DjangoCatalogPipeline()
        self.pipeline.spider_opened(CottonOnSpider())
        self.item = {
            "external_product_id": "123-01",
            "product_name": "Test Shirt",
            "brand_name": "Cotton On Men",
            "category": "Tops",
            "audience": "men",
            "product_page_url": "https://cottonon.com/US/test/123-01.html",
            "current_price": Decimal("12.48"),
            "original_price": Decimal("24.99"),
            "image_urls": ["https://cottonon.com/images/one.jpg", "https://cottonon.com/images/two.jpg"],
        }

    def test_pipeline_creates_and_then_updates_one_listing(self):
        self.pipeline.process_item(self.item)
        self.item["current_price"] = Decimal("10.00")
        self.pipeline.process_item(self.item)

        self.assertEqual(Store.objects.filter(store_name="Cotton On").count(), 1)
        self.assertEqual(Listing.objects.count(), 1)
        listing = Listing.objects.get()
        self.assertEqual(listing.current_price, Decimal("10.00"))
        self.assertEqual(listing.product.audience, "men")
        self.assertEqual(listing.images.count(), 2)
        self.assertEqual(PriceHistory.objects.count(), 2)
