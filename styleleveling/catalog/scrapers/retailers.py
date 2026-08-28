import json
import re
import random
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

import scrapy

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class RetailerSaleSpider(scrapy.Spider):
    """Base spider for public sale pages with product detail links."""

    sale_pages = {}
    product_link_selectors = ()
    product_image_selectors = (
        '[data-testid*="product"] img::attr(src)',
        '.product-images img::attr(src)',
        '.product-image img::attr(src)',
        '[class*="ProductImage"] img::attr(src)',
    )
    custom_settings = {
        "USE_PROXIES": False,
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
        "DOWNLOADER_MIDDLEWARES": {
            "catalog.scrapers.middlewares.StyleLevelingHeadersMiddleware": 410,
            "catalog.scrapers.middlewares.ProxyMiddleware": 350,
        },
        "DOWNLOAD_DELAY": 5.0,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 1,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 5.0,
        "AUTOTHROTTLE_MAX_DELAY": 30,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],
        "DOWNLOAD_TIMEOUT": 60,
        "ROBOTSTXT_OBEY": False,
        "LOG_LEVEL": "INFO",
        "HTTPERROR_ALLOWED_CODES": [403],
        "COOKIES_ENABLED": True,
        "COOKIES_DEBUG": False,
        "DEFAULT_REQUEST_HEADERS": {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'TE': 'trailers',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        }
    }

    def __init__(self, audience="both", max_pages=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if audience not in {"men", "women", "both"}:
            raise ValueError("audience must be men, women, or both")
        self.audience = audience
        self.max_pages = int(max_pages) if max_pages else None
        self._last_request_time = 0

    async def start(self):
        audiences = self.sale_pages if self.audience == "both" else [self.audience]
        for audience in audiences:
            yield scrapy.Request(
                self.sale_pages[audience],
                callback=self.parse_sale_page,
                cb_kwargs={"audience": audience, "page_number": 1},
                errback=self.request_failed,
                dont_filter=True,
            )

    def parse_sale_page(self, response, audience, page_number):
        if response.status == 403:
            self.logger.error("%s blocked with HTTP 403", self.store_name)
            time.sleep(random.uniform(10, 30))
            return

        links = []
        for selector in self.product_link_selectors:
            links.extend(response.css(selector).getall())

        clean_links = []
        for link in links:
            absolute = response.urljoin(link)
            if self.is_product_url(absolute) and absolute not in clean_links:
                clean_links.append(absolute)

        if not clean_links:
            self.logger.error("No product links found on %s", response.url)
            alt_links = response.css('a[href*="product"], a[href*="/p/"], a[href*="/pd/"]::attr(href)').getall()
            for link in alt_links:
                absolute = response.urljoin(link)
                if self.is_product_url(absolute) and absolute not in clean_links:
                    clean_links.append(absolute)

        for idx, product_url in enumerate(clean_links):
            if idx > 0:
                time.sleep(random.uniform(1.0, 3.0))
            yield scrapy.Request(
                product_url,
                callback=self.parse_product,
                cb_kwargs={"sale_audience": audience},
                errback=self.request_failed,
                dont_filter=True,
            )

        next_url = self.next_page_url(response, page_number)
        if next_url and (self.max_pages is None or page_number < self.max_pages):
            time.sleep(random.uniform(2.0, 5.0))
            yield response.follow(
                next_url,
                callback=self.parse_sale_page,
                cb_kwargs={"audience": audience, "page_number": page_number + 1},
                errback=self.request_failed,
                dont_filter=True,
            )

    def parse_product(self, response, sale_audience):
        product = self._json_ld_product(response)
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}

        name = product.get("name") or self._first_text(
            response, ['meta[property="og:title"]::attr(content)', "h1::text"]
        )
        current_price = self._decimal(
            offers.get("lowPrice")
            or offers.get("price")
            or self._first_text(
                response,
                [
                    'meta[property="product:price:amount"]::attr(content)',
                    '[class*="sale-price"]::text',
                    '[class*="SalePrice"]::text',
                    '[data-testid*="sale-price"]::text',
                    '[class*="price"]::text',
                    '.price::text',
                ],
            )
        )
        original_price = self._decimal(
            offers.get("highPrice")
            or self._first_text(
                response,
                [
                    '[class*="original-price"]::text',
                    '[class*="OriginalPrice"]::text',
                    '[class*="strike"]::text',
                    "del::text",
                    "s::text",
                    '[class*="was-price"]::text',
                ],
            )
        )
        if not name or current_price is None:
            self.logger.warning("Skipping product with incomplete data: %s", response.url)
            return
        if original_price is None or original_price < current_price:
            original_price = current_price

        images = self._as_list(product.get("image"))
        for selector in self.product_image_selectors:
            images.extend(response.css(selector).getall())
        og_image = response.css('meta[property="og:image"]::attr(content)').get()
        if og_image:
            images.append(og_image)
        
        image_urls = []
        for image in images:
            if isinstance(image, dict):
                image = image.get("url") or image.get("contentUrl")
            if not image:
                continue
            image = self._clean_image_url(response.urljoin(str(image)))
            if image not in image_urls:
                image_urls.append(image)

        external_id = str(
            product.get("sku")
            or product.get("productID")
            or product.get("mpn")
            or self.external_id_from_url(response.url)
        )
        category = product.get("category") or self._breadcrumb(response) or "Clothing"
        canonical = response.css('link[rel="canonical"]::attr(href)').get() or response.url

        yield {
            "external_product_id": external_id[:50],
            "product_name": " ".join(str(name).split()),
            "brand_name": self._brand_name(product),
            "category": " ".join(str(category).split())[:255],
            "audience": sale_audience,
            "product_page_url": canonical,
            "current_price": current_price,
            "original_price": original_price,
            "image_urls": image_urls[:12],
        }

    def is_product_url(self, url):
        return True

    def next_page_url(self, response, page_number):
        next_selectors = [
            'link[rel="next"]::attr(href)',
            'a[rel="next"]::attr(href)',
            'a.pagination__next::attr(href)',
            '.pagination a:last-child::attr(href)',
            'a[aria-label="Next"]::attr(href)',
            'a.next::attr(href)',
        ]
        for selector in next_selectors:
            next_url = response.css(selector).get()
            if next_url:
                return next_url
        return None

    def request_failed(self, failure):
        self.logger.error("Request failed: %s - %s", failure.request.url, failure.value)

    @staticmethod
    def _json_ld_product(response):
        def find_product(value):
            if isinstance(value, dict):
                kind = value.get("@type")
                if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
                    return value
                for child in value.values():
                    found = find_product(child)
                    if found:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = find_product(child)
                    if found:
                        return found
            return None

        for raw in response.css('script[type="application/ld+json"]::text').getall():
            try:
                found = find_product(json.loads(raw))
                if found:
                    return found
            except (TypeError, json.JSONDecodeError):
                continue
        return {}

    @staticmethod
    def _first_text(response, selectors):
        for selector in selectors:
            value = response.css(selector).get()
            if value and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _decimal(value):
        if value is None:
            return None
        match = re.search(r"\d[\d,]*(?:\.\d{1,2})?", str(value))
        if not match:
            return None
        try:
            return Decimal(match.group(0).replace(",", "")).quantize(Decimal("0.01"))
        except InvalidOperation:
            return None

    @staticmethod
    def _as_list(value):
        if not value:
            return []
        return value if isinstance(value, list) else [value]

    @staticmethod
    def _clean_image_url(url):
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @staticmethod
    def external_id_from_url(url):
        path = urlsplit(url).path
        matches = re.findall(r"(?:E)?\d{6,}(?:-\d+)?", path)
        return matches[-1] if matches else path.rstrip("/").split("/")[-1][:50]

    @staticmethod
    def _breadcrumb(response):
        values = response.css(
            '[aria-label="breadcrumb"] a::text, .breadcrumb a::text, [class*="Breadcrumb"] a::text'
        ).getall()
        return values[-1].strip() if values else None

    def _brand_name(self, product):
        brand = product.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        return str(brand or self.store_name)


# ====== COTTON ON SPIDER ======

class CottonOnSpider(RetailerSaleSpider):
    name = "cotton_on"
    store_name = "Cotton On"
    store_url = "https://cottonon.com/US/"
    allowed_domains = ["cottonon.com", "www.cottonon.com"]
    sale_pages = {
        "women": "https://cottonon.com/US/sale/women/",
        "men": "https://cottonon.com/US/sale/men/",
    }
    product_link_selectors = (
        'a[href*="/p/"]::attr(href)',
        '.product-tile a::attr(href)',
        '[data-testid*="product"] a::attr(href)',
    )
    
    def is_product_url(self, url):
        path = urlsplit(url).path
        return "/p/" in path and "sale" not in path


# ====== PAC SUN SPIDER ======

class PacSunSpider(RetailerSaleSpider):
    name = "pacsun"
    store_name = "PacSun"
    store_url = "https://www.pacsun.com/"
    allowed_domains = ["pacsun.com", "www.pacsun.com"]
    sale_pages = {
        "women": "https://www.pacsun.com/womens/sale/",
        "men": "https://www.pacsun.com/mens/sale/",
    }
    product_link_selectors = (
        '.product-tile a[href*=".html"]::attr(href)',
        '[data-testid*="product"] a::attr(href)',
        '.product-item a::attr(href)',
    )
    
    custom_settings = {
        **RetailerSaleSpider.custom_settings,
        "DOWNLOAD_DELAY": 8.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "RETRY_TIMES": 2,
    }

    def is_product_url(self, url):
        path = urlsplit(url).path
        return path.endswith(".html") and "/sale/" not in path


# ====== GAP SPIDER ======

class GapSpider(RetailerSaleSpider):
    name = "gap"
    store_name = "Gap"
    store_url = "https://www.gap.com/"
    allowed_domains = ["gap.com", "www.gap.com"]
    sale_pages = {
        "men": "https://www.gap.com/browse/men/sale?cid=65289&department=75",
        "women": "https://www.gap.com/browse/women/sale?cid=65179&department=136",
    }
    product_link_selectors = (
        'a[href*="/browse/product.do"]::attr(href)',
        '[data-testid*="product-card"] a::attr(href)',
        '.product-card a::attr(href)',
    )

    def is_product_url(self, url):
        return "/browse/product.do" in urlsplit(url).path


# ====== ASOS SPIDER ======

class AsosSpider(RetailerSaleSpider):
    name = "asos"
    store_name = "ASOS"
    store_url = "https://www.asos.com/us/"
    allowed_domains = ["asos.com", "www.asos.com"]
    sale_pages = {
        "men": "https://www.asos.com/us/men/sale/cat/?cid=8409",
        "women": "https://www.asos.com/us/women/sale/cat/?cid=7046",
    }
    product_link_selectors = ('a[href*="/prd/"]::attr(href)',)

    def is_product_url(self, url):
        return "/prd/" in urlsplit(url).path


# ====== FOREVER 21 SPIDER ======

class Forever21Spider(RetailerSaleSpider):
    name = "forever21"
    store_name = "Forever 21"
    store_url = "https://www.forever21.com/"
    allowed_domains = ["forever21.com", "www.forever21.com"]
    sale_pages = {
        "men": "https://www.forever21.com/collections/mens-sale",
        "women": "https://www.forever21.com/collections/womens-sale",
    }
    product_link_selectors = (
        'a[href*="/products/"]::attr(href)',
        'a[href*="/product/"]::attr(href)',
    )

    def is_product_url(self, url):
        path = urlsplit(url).path
        return "/products/" in path or "/product/" in path


# ====== UNIQLO SPIDER ======

class UniqloSpider(RetailerSaleSpider):
    name = "uniqlo"
    store_name = "Uniqlo"
    store_url = "https://www.uniqlo.com/us/en/"
    allowed_domains = ["uniqlo.com", "www.uniqlo.com"]
    sale_pages = {
        "women": "https://www.uniqlo.com/us/en/feature/sale/women",
        "men": "https://www.uniqlo.com/us/en/feature/sale/men",
    }
    product_link_selectors = (
        'a.product-tile__link::attr(href)',
        'a[href*="/products/"]::attr(href)',
        '.product-tile a::attr(href)',
    )

    def is_product_url(self, url):
        return "/us/en/products/" in urlsplit(url).path or "/products/" in urlsplit(url).path

    def parse_sale_page(self, response, audience, page_number):
        if response.status == 403:
            self.logger.error("Uniqlo blocked with HTTP 403")
            time.sleep(random.uniform(10, 30))
            return

        links = []
        for selector in self.product_link_selectors:
            links.extend(response.css(selector).getall())

        clean_links = []
        for link in links:
            absolute = response.urljoin(link)
            if self.is_product_url(absolute) and absolute not in clean_links:
                clean_links.append(absolute)

        if not clean_links:
            self.logger.error("No product links found on %s", response.url)
            alt_links = response.css('a[href*="product"]::attr(href)').getall()
            for link in alt_links:
                absolute = response.urljoin(link)
                if self.is_product_url(absolute) and absolute not in clean_links:
                    clean_links.append(absolute)

        for idx, product_url in enumerate(clean_links):
            if idx > 0:
                time.sleep(random.uniform(1.0, 3.0))
            yield scrapy.Request(
                product_url,
                callback=self.parse_product,
                cb_kwargs={"sale_audience": audience},
                errback=self.request_failed,
                dont_filter=True,
            )

        next_url = self.next_page_url(response, page_number)
        if next_url and (self.max_pages is None or page_number < self.max_pages):
            time.sleep(random.uniform(2.0, 5.0))
            yield response.follow(
                next_url,
                callback=self.parse_sale_page,
                cb_kwargs={"audience": audience, "page_number": page_number + 1},
                errback=self.request_failed,
                dont_filter=True,
            )

    def parse_product(self, response, sale_audience):
        state = None
        for raw in response.css("script::text").getall():
            marker = "window.__PRELOADED_STATE__ ="
            if marker not in raw:
                continue
            payload = raw.split(marker, 1)[1].strip().rstrip(";").strip()
            try:
                state = json.loads(payload)
            except json.JSONDecodeError:
                pass
            break

        product_id = self.external_id_from_url(response.url)

        def find_product(value):
            if isinstance(value, dict):
                if str(value.get("productId", "")).endswith(product_id.replace("E", "")):
                    return value
                if value.get("productId") == product_id:
                    return value
                for child in value.values():
                    found = find_product(child)
                    if found:
                        return found
            elif isinstance(value, list):
                for child in value:
                    found = find_product(child)
                    if found:
                        return found
            return None

        product = find_product(state) if state else None
        if not product:
            yield from super().parse_product(response, sale_audience)
            return

        prices = product.get("prices") or {}
        base = self._decimal((prices.get("base") or {}).get("value"))
        promo = self._decimal((prices.get("promo") or {}).get("value"))
        current_price = promo or base
        original_price = base or current_price
        if current_price is None:
            self.logger.warning("Skipping Uniqlo product without a price: %s", response.url)
            return

        image_urls = []
        def collect_images(value):
            if isinstance(value, dict):
                for child in value.values():
                    collect_images(child)
            elif isinstance(value, list):
                for child in value:
                    collect_images(child)
            elif isinstance(value, str) and value.startswith("https://image.uniqlo.com/"):
                clean = self._clean_image_url(value)
                if clean not in image_urls:
                    image_urls.append(clean)

        collect_images(product.get("images") or product)
        canonical = response.css('link[rel="canonical"]::attr(href)').get() or response.url
        yield {
            "external_product_id": str(product.get("productId") or product_id)[:50],
            "product_name": " ".join(str(product.get("name") or "Uniqlo item").split()),
            "brand_name": "Uniqlo",
            "category": self._breadcrumb(response) or "Clothing",
            "audience": sale_audience,
            "product_page_url": canonical,
            "current_price": current_price,
            "original_price": original_price,
            "image_urls": image_urls[:12],
        }


# ====== H&M SPIDER (with Selenium) ======

class HMSpider(RetailerSaleSpider):
    name = "hm"
    store_name = "H&M"
    store_url = "https://www2.hm.com/en_us/"
    allowed_domains = ["hm.com", "www2.hm.com"]
    sale_pages = {
        "men": "https://www2.hm.com/en_us/men/sale/view-all.html",
        "women": "https://www2.hm.com/en_us/women/sale/view-all.html",
    }
    product_link_selectors = ('a[href*="productpage."]::attr(href)',)
    
    custom_settings = {
        **RetailerSaleSpider.custom_settings,
        "DOWNLOAD_DELAY": 10.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "RETRY_TIMES": 2,
    }

    def is_product_url(self, url):
        return "productpage." in urlsplit(url).path
    
    def parse_product(self, response, sale_audience):
        """Use Selenium for H&M to get JavaScript-rendered content."""
        driver = None
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.set_preference("general.useragent.override", 
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0")
            options.set_preference("dom.webdriver.enabled", False)
            options.set_preference("useAutomationExtension", False)
            options.set_preference("media.navigator.enabled", False)
            
            service = Service(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=options)
            driver.set_page_load_timeout(30)
            
            self.logger.info(f"Loading H&M product with Selenium: {response.url}")
            driver.get(response.url)
            time.sleep(3)
            
            page_source = driver.page_source
            price = None
            
            price_patterns = [
                r'"price"\s*:\s*"([\d.]+)"',
                r'"price"\s*:\s*([\d.]+)',
                r'"currentPrice"\s*:\s*"([\d.]+)"',
                r'"salePrice"\s*:\s*"([\d.]+)"',
                r'\$(\d+\.\d{2})',
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, page_source)
                if match:
                    try:
                        price = self._decimal(match.group(1))
                        if price and price > 0:
                            break
                    except:
                        continue
            
            if price is None:
                self.logger.warning(f"No price found for H&M product: {response.url}")
                return
            
            name = None
            name_selectors = ['h1', '[class*="product-name"]', '.product-title']
            for selector in name_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    name = element.text.strip()
                    if name:
                        break
                except:
                    continue
            
            if not name:
                name = "H&M item"
            
            original_price = None
            original_selectors = ['[class*="original"]', 'del', 's']
            for selector in original_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and '$' in text:
                            match = re.search(r'\$?(\d+\.\d{2})', text)
                            if match:
                                original_price = self._decimal(match.group(1))
                                if original_price:
                                    break
                    if original_price:
                        break
                except:
                    continue
            
            image_urls = []
            try:
                image_selectors = ['meta[property="og:image"]', 'img[class*="product"]']
                for selector in image_selectors:
                    if 'meta' in selector:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements:
                            img_url = element.get_attribute('content')
                            if img_url:
                                image_urls.append(img_url)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for element in elements[:5]:
                            img_url = element.get_attribute('src')
                            if img_url and 'data:image' not in img_url:
                                image_urls.append(img_url)
                image_urls = [self._clean_image_url(url) for url in image_urls if url]
                image_urls = list(dict.fromkeys(image_urls))[:12]
            except:
                pass
            
            yield {
                "external_product_id": self.external_id_from_url(response.url)[:50],
                "product_name": " ".join(str(name).split())[:255],
                "brand_name": "H&M",
                "category": "Clothing",
                "audience": sale_audience,
                "product_page_url": response.url,
                "current_price": price,
                "original_price": original_price or price,
                "image_urls": image_urls,
            }
            
        except Exception as e:
            self.logger.error(f"Selenium error for {response.url}: {e}")
            yield from super().parse_product(response, sale_audience)
        finally:
            if driver:
                driver.quit()


# ====== HOLLISTER SPIDER (Simplified - No Selenium) ======

class HollisterSpider(RetailerSaleSpider):
    name = "hollister"
    store_name = "Hollister"
    store_url = "https://www.hollisterco.com/shop/us/"
    allowed_domains = ["hollisterco.com", "www.hollisterco.com"]
    sale_pages = {
        "men": "https://www.hollisterco.com/shop/us/mens-clearance",
        "women": "https://www.hollisterco.com/shop/us/womens-clearance",
    }
    product_link_selectors = (
        'a[href*="/shop/us/p/"]::attr(href)',
        '[data-testid*="product"] a::attr(href)',
        '.product-tile a::attr(href)',
    )

    def is_product_url(self, url):
        return "/shop/us/p/" in urlsplit(url).path


# ====== URBAN OUTFITTERS SPIDER (Simplified - No Selenium) ======

class UrbanOutfittersSpider(RetailerSaleSpider):
    name = "urban_outfitters"
    store_name = "Urban Outfitters"
    store_url = "https://www.urbanoutfitters.com/"
    allowed_domains = ["urbanoutfitters.com", "www.urbanoutfitters.com"]
    sale_pages = {
        "men": "https://www.urbanoutfitters.com/mens-clothing-sale",
        "women": "https://www.urbanoutfitters.com/womens-clothing-sale",
    }
    product_link_selectors = (
        'a[href*="/shop/"]::attr(href)',
        '[data-testid*="product"] a::attr(href)',
        '.product-tile a::attr(href)',
    )

    def is_product_url(self, url):
        path = urlsplit(url).path
        return path.startswith("/shop/") and "sale" not in path