# catalog/scrapers/middlewares.py
import random
import base64
import time


class ProxyMiddleware:
    """Rotate proxies for each request to avoid IP-based blocking."""
    
    def __init__(self, crawler):
        self.crawler = crawler
        self.proxies = crawler.settings.get('PROXY_LIST', [])
        self.failed_proxies = set()
        self.proxy_stats = {}
        self.use_proxies = crawler.settings.get('USE_PROXIES', True)
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)
    
    def process_request(self, request, spider):
        if not self.use_proxies or not self.proxies:
            return None
        
        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
        
        if not available_proxies:
            spider.logger.warning("No available proxies, proceeding without proxy")
            return None
        
        if self.proxy_stats:
            sorted_proxies = sorted(
                available_proxies,
                key=lambda p: self.proxy_stats.get(p, {}).get('failures', 0)
            )
            proxy = sorted_proxies[0]
        else:
            proxy = random.choice(available_proxies)
        
        request.meta['proxy'] = proxy
        request.meta['proxy_used'] = proxy
        
        if '@' in proxy:
            parts = proxy.split('@')
            if len(parts) == 2:
                auth_part = parts[0].split('//')[-1] if '//' in parts[0] else parts[0]
                if ':' in auth_part:
                    auth = base64.b64encode(auth_part.encode()).decode()
                    request.headers['Proxy-Authorization'] = f'Basic {auth}'
        
        return None
    
    def process_response(self, request, response, spider):
        proxy = request.meta.get('proxy_used')
        if proxy:
            if proxy not in self.proxy_stats:
                self.proxy_stats[proxy] = {'failures': 0, 'successes': 0}
            
            if response.status in [403, 429, 500, 502, 503, 504]:
                self.proxy_stats[proxy]['failures'] += 1
                spider.logger.warning(f"Proxy {proxy} returned status {response.status}")
                
                if self.proxy_stats[proxy]['failures'] > 3:
                    self.failed_proxies.add(proxy)
                    spider.logger.warning(f"Marking proxy as failed: {proxy}")
            else:
                self.proxy_stats[proxy]['successes'] += 1
                if self.proxy_stats[proxy]['failures'] > 0:
                    self.proxy_stats[proxy]['failures'] = max(0, self.proxy_stats[proxy]['failures'] - 1)
        
        return response
    
    def process_exception(self, request, exception, spider):
        proxy = request.meta.get('proxy_used')
        if proxy:
            if proxy not in self.proxy_stats:
                self.proxy_stats[proxy] = {'failures': 0, 'successes': 0}
            self.proxy_stats[proxy]['failures'] += 1
            
            if self.proxy_stats[proxy]['failures'] > 3:
                self.failed_proxies.add(proxy)
                spider.logger.warning(f"Marking proxy as failed due to exception: {proxy}")
        
        return None


class StyleLevelingHeadersMiddleware:
    """Use YOUR real Firefox 154.0 browser fingerprint to avoid detection."""
    
    def __init__(self, crawler):
        self.crawler = crawler
        self.use_proxies = crawler.settings.get('USE_PROXIES', True)
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)
    
    def process_request(self, request, spider):
        """Use your EXACT Firefox 154.0 fingerprint from browser"""
        
        # === YOUR REAL BROWSER FINGERPRINT ===
        # Copied directly from your PacSun request
        
        # Firefox 154.0 on Windows
        request.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0'
        
        # Standard Firefox headers
        request.headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        request.headers['Accept-Language'] = 'en-US,en;q=0.9'
        request.headers['Accept-Encoding'] = 'gzip, deflate, br, zstd'
        request.headers['Connection'] = 'keep-alive'
        request.headers['Upgrade-Insecure-Requests'] = '1'
        
        # Firefox-specific headers
        request.headers['TE'] = 'trailers'
        request.headers['Priority'] = 'u=0, i'
        
        # Security headers that Firefox sends
        request.headers['Sec-Fetch-Dest'] = 'document'
        request.headers['Sec-Fetch-Mode'] = 'navigate'
        request.headers['Sec-Fetch-Site'] = 'none'
        request.headers['Sec-Fetch-User'] = '?1'
        
        # Cache control - use no-cache like your browser
        request.headers['Cache-Control'] = 'no-cache'
        request.headers['Pragma'] = 'no-cache'
        
        # Cookies are handled by Scrapy's cookie middleware
        # But we should set the same cookie flags if needed
        
        # If it's a PacSun request, add the referer like your browser
        if 'pacsun.com' in request.url:
            if 'sale' in request.url and request.headers.get('Referer') is None:
                request.headers['Referer'] = 'https://www.pacsun.com/'
        
        # If it's an H&M request, use their specific headers
        if 'hm.com' in request.url:
            request.headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
            request.headers['Sec-Fetch-Site'] = 'same-origin' if 'product' in request.url else 'none'
        
        # If using proxies, add slightly different fingerprint to avoid detection
        if self.use_proxies and self.crawler.settings.get('PROXY_LIST'):
            # Use same browser but with small variations
            pass
        
        # Add a human-like delay (1-3 seconds between requests)
        # This is more important than using proxies
        if not hasattr(spider, '_last_request_time'):
            spider._last_request_time = time.time()
        
        elapsed = time.time() - spider._last_request_time
        if elapsed < 3.0:
            # Wait to make it look like a human browsing
            wait_time = random.uniform(1.0, 3.0) - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
        
        spider._last_request_time = time.time()
        
        return None