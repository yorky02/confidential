import json
import re
import random
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, urlunsplit

import scrapy


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
        # DISABLE proxies - use YOUR home IP with proper fingerprint
        "USE_PROXIES": False,  # Set to True if you want to use proxies
        
        # Use YOUR real Firefox fingerprint (set in middleware)
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
        
        "DOWNLOADER_MIDDLEWARES": {
            # Headers middleware (uses your fingerprint)
            "catalog.scrapers.middlewares.StyleLevelingHeadersMiddleware": 410,
            # Proxy middleware (disabled by default)
            "catalog.scrapers.middlewares.ProxyMiddleware": 350,
        },
        
        # Very conservative settings for home IP
        "DOWNLOAD_DELAY": 5.0,  # 5 second delay between requests
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS": 1,  # Only 1 request at a time
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 5.0,
        "AUTOTHROTTLE_MAX_DELAY": 30,
        
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],  # Don't retry 403
        
        "DOWNLOAD_TIMEOUT": 60,
        "ROBOTSTXT_OBEY": False,  # Disable robots.txt to test
        "LOG_LEVEL": "INFO",
        "HTTPERROR_ALLOWED_CODES": [403],
        
        # Cookie handling
        "COOKIES_ENABLED": True,
        "COOKIES_DEBUG": False,
        
        # Real browser headers (these will be overridden by middleware)
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
        """Discover product pages and follow catalog pagination."""

        if response.status == 403:
            self.logger.error("%s blocked with HTTP 403", self.store_name)
            # Wait longer before retrying
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

        # Process each product with human-like delay
        for idx, product_url in enumerate(clean_links):
            # Add delay between products (like a human browsing)
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
            # Wait before going to next page
            time.sleep(random.uniform(2.0, 5.0))
            yield response.follow(
                next_url,
                callback=self.parse_sale_page,
                cb_kwargs={"audience": audience, "page_number": page_number + 1},
                errback=self.request_failed,
                dont_filter=True,
            )

    def parse_product(self, response, sale_audience):
        """Convert a retailer product page into the shared pipeline schema."""

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


# ====== SPIDER CLASSES ======

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
        "DOWNLOAD_DELAY": 8.0,  # Extra slow for PacSun
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "RETRY_TIMES": 2,
    }

    def is_product_url(self, url):
        path = urlsplit(url).path
        return path.endswith(".html") and "/sale/" not in path


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
        # Enable JavaScript rendering for H&M
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
    }

    def is_product_url(self, url):
        return "productpage." in urlsplit(url).path
    
    def parse_product(self, response, sale_audience):
        """H&M specific parser that looks for prices in multiple places."""
        
        # Try to find price in JSON-LD first
        product = self._json_ld_product(response)
        
        # Check if we have price from JSON-LD
        current_price = None
        original_price = None
        
        if product:
            offers = product.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            
            current_price = self._decimal(
                offers.get("price") or 
                offers.get("lowPrice") or
                self._extract_hm_price_from_js(response)
            )
            
            original_price = self._decimal(
                offers.get("highPrice") or
                self._extract_hm_original_price(response)
            )
        
        # If no price from JSON-LD, try other methods
        if current_price is None:
            current_price = self._extract_hm_price_from_js(response)
        
        if original_price is None:
            original_price = self._extract_hm_original_price(response)
        
        # Get product name
        name = product.get("name") if product else None
        if not name:
            name = self._first_text(
                response, 
                ['meta[property="og:title"]::attr(content)', "h1::text", '[class*="product-name"]::text']
            )
        
        # If no price, try to extract from page source
        if current_price is None:
            # Try to find price in any script tag
            for script in response.css('script::text').getall():
                # Look for price patterns in JavaScript
                price_match = re.search(r'"price"\s*:\s*"([\d.]+)"', script)
                if price_match:
                    current_price = self._decimal(price_match.group(1))
                    break
                
                # Look for other price patterns
                price_match = re.search(r'"regularPrice"\s*:\s*"([\d.]+)"', script)
                if price_match:
                    current_price = self._decimal(price_match.group(1))
                    break
        
        # Extract product ID
        product_id = self.external_id_from_url(response.url)
        
        # Extract images
        image_urls = []
        og_image = response.css('meta[property="og:image"]::attr(content)').get()
        if og_image:
            image_urls.append(self._clean_image_url(og_image))
        
        # Look for images in product JSON
        if product:
            images = product.get("image")
            if images:
                if isinstance(images, list):
                    for img in images:
                        if isinstance(img, dict):
                            img = img.get("url") or img.get("contentUrl")
                        if img:
                            image_urls.append(self._clean_image_url(img))
                elif isinstance(images, str):
                    image_urls.append(self._clean_image_url(images))
        
        # Try to get images from HTML
        if not image_urls:
            image_urls = response.css('img[class*="product"]::attr(src)').getall()
            image_urls = [self._clean_image_url(url) for url in image_urls if url]
        
        # If still no price, log and skip
        if current_price is None:
            self.logger.warning(f"No price found for H&M product: {response.url}")
            return
        
        # Build product data
        yield {
            "external_product_id": str(product_id)[:50],
            "product_name": " ".join(str(name or "H&M item").split()),
            "brand_name": "H&M",
            "category": self._breadcrumb(response) or "Clothing",
            "audience": sale_audience,
            "product_page_url": response.url,
            "current_price": current_price,
            "original_price": original_price or current_price,
            "image_urls": image_urls[:12],
        }
    
    def _extract_hm_price_from_js(self, response):
        """Extract price from H&M JavaScript data."""
        # Look for product data in script tags
        for script in response.css('script::text').getall():
            # Look for various price patterns
            patterns = [
                r'"price"\s*:\s*"([\d.]+)"',
                r'"price"\s*:\s*([\d.]+)',
                r'"currentPrice"\s*:\s*"([\d.]+)"',
                r'"price_value"\s*:\s*"([\d.]+)"',
                r'"Price"\s*:\s*([\d.]+)',
                r'"salePrice"\s*:\s*"([\d.]+)"',
                r'"listPrice"\s*:\s*"([\d.]+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, script)
                if match:
                    price_str = match.group(1).replace(',', '')
                    try:
                        price = Decimal(price_str)
                        if price > 0:
                            return price
                    except:
                        continue
        
        # Try to find price in HTML
        price_selectors = [
            '[class*="price"]::text',
            '[class*="Price"]::text',
            '.product-price::text',
            '[data-testid*="price"]::text',
            'span[itemprop="price"]::text',
            'meta[itemprop="price"]::attr(content)',
        ]
        
        for selector in price_selectors:
            price_text = response.css(selector).get()
            if price_text:
                price = self._decimal(price_text)
                if price:
                    return price
        
        return None
    
    def _extract_hm_original_price(self, response):
        """Extract original/regular price from H&M."""
        for script in response.css('script::text').getall():
            patterns = [
                r'"regularPrice"\s*:\s*"([\d.]+)"',
                r'"regularPrice"\s*:\s*([\d.]+)',
                r'"originalPrice"\s*:\s*"([\d.]+)"',
                r'"listPrice"\s*:\s*"([\d.]+)"',
                r'"compareAtPrice"\s*:\s*"([\d.]+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, script)
                if match:
                    price_str = match.group(1).replace(',', '')
                    try:
                        price = Decimal(price_str)
                        if price > 0:
                            return price
                    except:
                        continue
        
        # Look for struck-through prices in HTML
        original_selectors = [
            '[class*="original"]::text',
            '[class*="Original"]::text',
            '[class*="regular"]::text',
            '[class*="Regular"]::text',
            'del::text',
            's::text',
            '[class*="strike"]::text',
            '[class*="compare"]::text',
        ]
        
        for selector in original_selectors:
            price_text = response.css(selector).get()
            if price_text:
                price = self._decimal(price_text)
                if price:
                    return price
        
        return None


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


class UniqloSpider(RetailerSaleSpider):
    name = "uniqlo"
    store_name = "Uniqlo"
    store_url = "https://www.uniqlo.com/us/en/"
    allowed_domains = ["uniqlo.com", "www.uniqlo.com"]
    sale_pages = {
        "women": "https://www.uniqlo.com/us/en/feature/sale/women",
        "men": "https://www.uniqlo.com/us/en/feature/sale/men",
    }
    product_link_selectors = ('a.product-tile__link::attr(href)',)

    def is_product_url(self, url):
        return "/us/en/products/" in urlsplit(url).path

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


class Forever21Spider(RetailerSaleSpider):
    name = "forever21"
    store_name = "Forever 21"
    store_url = "https://www.forever21.com/"
    allowed_domains = ["forever21.com", "www.forever21.com"]
    sale_pages = {
        "men": "https://www.forever21.com/collections/mens-sale",
        "women": "https://www.forever21.com/collections/womens-sale",
    }
    product_link_selectors = ('a[href*="/products/"]::attr(href)',)

    def is_product_url(self, url):
        return "/products/" in urlsplit(url).path


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