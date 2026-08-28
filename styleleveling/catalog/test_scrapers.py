from decimal import Decimal

from django.test import TestCase
from scrapy.http import HtmlResponse, Request

from .models import Listing, PriceHistory, Store
from .scrapers.cotton_on import CottonOnSpider
from .scrapers.middlewares import StyleLevelingHeadersMiddleware
from .scrapers.pipelines import DjangoCatalogPipeline
from .scrapers.retailers import AsosSpider, Forever21Spider, HMSpider, UniqloSpider


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


class RetailerSaleSpiderTests(TestCase):
    def response(self, html, url):
        request = Request(url=url)
        return HtmlResponse(url=url, request=request, body=html, encoding="utf-8")

    def test_json_ld_product_parser_normalizes_a_retailer_item(self):
        html = """
          <html><head>
            <link rel="canonical" href="https://www2.hm.com/en_us/productpage.1234567001.html">
            <meta property="og:image" content="https://image.hm.com/item-1.jpg?width=400">
            <script type="application/ld+json">{
              "@context":"https://schema.org", "@type":"Product",
              "name":"Relaxed Shirt", "sku":"1234567001", "category":"Shirts",
              "brand":{"@type":"Brand","name":"H&M"},
              "image":["https://image.hm.com/item-1.jpg", "https://image.hm.com/item-2.jpg"],
              "offers":{"@type":"AggregateOffer","lowPrice":"14.99","highPrice":"29.99"}
            }</script>
          </head><body></body></html>
        """
        spider = HMSpider()
        response = self.response(
            html, "https://www2.hm.com/en_us/productpage.1234567001.html"
        )
        items = list(spider.parse_product(response, "men"))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["external_product_id"], "1234567001")
        self.assertEqual(items[0]["current_price"], Decimal("14.99"))
        self.assertEqual(items[0]["original_price"], Decimal("29.99"))
        self.assertEqual(items[0]["audience"], "men")
        self.assertEqual(items[0]["category"], "Shirts")
        self.assertEqual(len(items[0]["image_urls"]), 2)

    def test_uniqlo_sale_page_only_follows_product_links(self):
        html = """
          <a class="product-tile__link" href="/us/en/products/E123456-000/00">Item</a>
          <a href="/us/en/feature/sale/women">Navigation</a>
        """
        spider = UniqloSpider(audience="women", max_pages=1)
        response = self.response(html, "https://www.uniqlo.com/us/en/feature/sale/women")
        requests = list(spider.parse_sale_page(response, "women", 1))

        self.assertEqual(len(requests), 1)
        self.assertIn("/products/E123456-000/00", requests[0].url)

    def test_forever21_sale_page_only_follows_product_links(self):
        html = """
          <a href="/collections/womens-sale/products/01348623">Item</a>
          <a href="/collections/womens-sale">Navigation</a>
        """
        spider = Forever21Spider(audience="women", max_pages=1)
        response = self.response(html, spider.sale_pages["women"])
        requests = list(spider.parse_sale_page(response, "women", 1))

        self.assertEqual(len(requests), 1)
        self.assertIn("/products/01348623", requests[0].url)

    def test_asos_sale_page_only_follows_product_links(self):
        html = """
          <a href="https://www.asos.com/us/asos-design/test-shirt/prd/209187439#colourWayId-1">Item</a>
          <a href="/us/men/sale/cat/?cid=8409">Navigation</a>
        """
        spider = AsosSpider(audience="men", max_pages=1)
        response = self.response(html, spider.sale_pages["men"])
        requests = list(spider.parse_sale_page(response, "men", 1))

        self.assertEqual(len(requests), 1)
        self.assertIn("/prd/209187439", requests[0].url)


class StyleLevelingHeadersMiddlewareTests(TestCase):
    def test_adds_standard_headers_without_replacing_request_override(self):
        request = Request(
            "https://example.com/sale",
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        middleware = StyleLevelingHeadersMiddleware()

        middleware.process_request(request, CottonOnSpider())

        self.assertIn(b"text/html", request.headers[b"Accept"])
        self.assertEqual(request.headers[b"Accept-Language"], b"en-US,en;q=0.9")
        self.assertEqual(request.headers[b"Cache-Control"], b"max-age=0")
