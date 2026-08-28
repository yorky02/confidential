# catalog/scrapers/middlewares.py
import random
import base64
import time


class ProxyMiddleware:
    """Rotate proxies for each request to avoid IP-based blocking."""
    
    def __init__(self, proxies):
        self.proxies = proxies
        self.failed_proxies = set()
        self.proxy_stats = {}
        
    @classmethod
    def from_crawler(cls, crawler):
        # Load proxies from settings
        proxy_list = crawler.settings.get('PROXY_LIST', [])
        return cls(proxy_list)
    
    def process_request(self, request, spider):
        if not self.proxies:
            return None
        
        # Filter out failed proxies
        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
        
        if not available_proxies:
            spider.logger.warning("No available proxies, proceeding without proxy")
            return None
        
        # Select proxy with least failures if stats available, otherwise random
        if self.proxy_stats:
            # Sort by failure count (lower is better)
            sorted_proxies = sorted(
                available_proxies,
                key=lambda p: self.proxy_stats.get(p, {}).get('failures', 0)
            )
            proxy = sorted_proxies[0]
        else:
            proxy = random.choice(available_proxies)
        
        request.meta['proxy'] = proxy
        request.meta['proxy_used'] = proxy  # Track which proxy was used
        
        # Handle proxy authentication if needed
        if '@' in proxy:
            # Format: http://user:pass@proxy.com:8080 or http://proxy.com:8080
            parts = proxy.split('@')
            if len(parts) == 2:
                auth_part = parts[0].split('//')[-1] if '//' in parts[0] else parts[0]
                if ':' in auth_part:
                    auth = base64.b64encode(auth_part.encode()).decode()
                    request.headers['Proxy-Authorization'] = f'Basic {auth}'
        
        spider.logger.debug(f"Using proxy: {proxy}")
        
        # Add a random delay to make requests look more human
        if hasattr(spider, 'custom_settings') and spider.custom_settings.get('RANDOMIZE_DOWNLOAD_DELAY'):
            time.sleep(random.uniform(0.1, 0.5))
        
        return None
    
    def process_response(self, request, response, spider):
        proxy = request.meta.get('proxy_used')
        if proxy:
            # Track proxy performance
            if proxy not in self.proxy_stats:
                self.proxy_stats[proxy] = {'failures': 0, 'successes': 0}
            
            if response.status in [403, 429, 500, 502, 503, 504]:
                self.proxy_stats[proxy]['failures'] += 1
                spider.logger.warning(f"Proxy {proxy} returned status {response.status}")
                
                # If proxy fails too often, mark it as failed
                if self.proxy_stats[proxy]['failures'] > 3:
                    self.failed_proxies.add(proxy)
                    spider.logger.warning(f"Marking proxy as failed: {proxy}")
            else:
                self.proxy_stats[proxy]['successes'] += 1
                
                # Reset failure count after success
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
    """Add realistic browser headers to requests."""
    
    def process_request(self, request, spider):
        # Random User-Agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        ]
        request.headers['User-Agent'] = random.choice(user_agents)
        
        # Add standard browser headers if not already present
        if 'Accept' not in request.headers:
            request.headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        if 'Accept-Language' not in request.headers:
            request.headers['Accept-Language'] = 'en-US,en;q=0.9'
        if 'Accept-Encoding' not in request.headers:
            request.headers['Accept-Encoding'] = 'gzip, deflate, br'
        if 'Connection' not in request.headers:
            request.headers['Connection'] = 'keep-alive'
        if 'Upgrade-Insecure-Requests' not in request.headers:
            request.headers['Upgrade-Insecure-Requests'] = '1'
        if 'Sec-Fetch-Dest' not in request.headers:
            request.headers['Sec-Fetch-Dest'] = 'document'
        if 'Sec-Fetch-Mode' not in request.headers:
            request.headers['Sec-Fetch-Mode'] = 'navigate'
        if 'Sec-Fetch-Site' not in request.headers:
            request.headers['Sec-Fetch-Site'] = 'none'
        if 'Sec-Fetch-User' not in request.headers:
            request.headers['Sec-Fetch-User'] = '?1'
        if 'Cache-Control' not in request.headers:
            request.headers['Cache-Control'] = 'max-age=0'