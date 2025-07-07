"""
ProductFetcher - Enhanced web scraper with caching layer
Wraps existing stealth_scraper with async batch processing and rate limiting
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import time

# Add tools directory to path
sys.path.append(str(Path(__file__).parent.parent.parent / 'tools'))

# Import existing scraper
from stealth_scraper import StealthScraper, ScrapeResult, ScrapingMethod
from html_processor import HTMLProcessor

# Import new components
from tools.data_management.product_cache import ProductCache
from models.schemas import Product
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ProductFetcher:
    """Enhanced product fetcher with caching and batch processing"""
    
    def __init__(self, cache: Optional[ProductCache] = None):
        """Initialize product fetcher"""
        self.settings = get_settings()
        self.scraper = StealthScraper()
        self.html_processor = HTMLProcessor()
        self.cache = cache or ProductCache()
        
        # Rate limiting
        self.rate_limit = self.settings.scrape_rate_limit  # requests per minute
        self.last_request_times = []
        
        # Semaphore for concurrent requests
        self.semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests
    
    async def initialize(self):
        """Initialize cache and other components"""
        try:
            if self.settings.enable_caching:
                await self.cache.initialize()
            logger.info("ProductFetcher initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize cache: {e}")
    
    async def fetch(self, url: str, force_refresh: bool = False) -> ScrapeResult:
        """Fetch single product with caching"""
        try:
            # Check cache first (unless force refresh)
            if not force_refresh and self.settings.enable_caching:
                cached_product = await self.cache.get(url)
                if cached_product:
                    logger.debug(f"Cache hit for URL: {url}")
                    # Convert cached product back to ScrapeResult format
                    return self._product_to_scrape_result(cached_product, url)
            
            # Apply rate limiting
            await self._rate_limit()
            
            # Fetch from web
            async with self.semaphore:
                scrape_result = await self._fetch_from_web(url)
            
            # Cache the result if successful
            if scrape_result.success and self.settings.enable_caching:
                product = await self._scrape_result_to_product(scrape_result)
                if product:
                    await self.cache.set(url, product)
            
            return scrape_result
            
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return ScrapeResult(
                url=url,
                success=False,
                error=str(e),
                method_used=ScrapingMethod.AUTO
            )
    
    async def batch_fetch(self, urls: List[str], max_concurrent: int = 5, force_refresh: bool = False) -> List[ScrapeResult]:
        """Fetch multiple products with concurrency control"""
        try:
            # Update semaphore for batch operation
            self.semaphore = asyncio.Semaphore(max_concurrent)
            
            # Check cache for existing results
            cached_results = {}
            if not force_refresh and self.settings.enable_caching:
                cached_results = await self.cache.get_many(urls)
            
            # Separate cached and uncached URLs
            uncached_urls = []
            results = {}
            
            for url in urls:
                cached_product = cached_results.get(url)
                if cached_product:
                    results[url] = self._product_to_scrape_result(cached_product, url)
                    logger.debug(f"Using cached result for: {url}")
                else:
                    uncached_urls.append(url)
            
            logger.info(f"Batch fetch: {len(urls)} total, {len(uncached_urls)} need fetching, {len(results)} cached")
            
            # Fetch uncached URLs
            if uncached_urls:
                fetch_tasks = [self.fetch(url, force_refresh=True) for url in uncached_urls]
                
                # Process in batches to avoid overwhelming the server
                batch_size = max_concurrent
                for i in range(0, len(fetch_tasks), batch_size):
                    batch_tasks = fetch_tasks[i:i + batch_size]
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    for url, result in zip(uncached_urls[i:i + batch_size], batch_results):
                        if isinstance(result, Exception):
                            logger.error(f"Exception fetching {url}: {result}")
                            results[url] = ScrapeResult(
                                url=url,
                                success=False,
                                error=str(result),
                                method_used=ScrapingMethod.AUTO
                            )
                        else:
                            results[url] = result
                    
                    # Small delay between batches
                    if i + batch_size < len(fetch_tasks):
                        await asyncio.sleep(2)
            
            # Return results in original order
            return [results[url] for url in urls]
            
        except Exception as e:
            logger.error(f"Failed batch fetch: {e}")
            return [
                ScrapeResult(
                    url=url,
                    success=False,
                    error=str(e),
                    method_used=ScrapingMethod.AUTO
                )
                for url in urls
            ]
    
    def validate_url(self, url: str) -> bool:
        """Validate URL format and accessibility"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Additional validation
            if parsed.scheme not in ['http', 'https']:
                return False
            
            # Check for common invalid patterns
            invalid_patterns = ['localhost', '127.0.0.1', 'example.com']
            if any(pattern in parsed.netloc.lower() for pattern in invalid_patterns):
                return False
            
            return True
            
        except Exception:
            return False
    
    async def get_fetch_stats(self) -> Dict[str, Any]:
        """Get fetching statistics"""
        try:
            cache_stats = await self.cache.get_cache_stats() if self.cache else {}
            
            return {
                "rate_limit": self.rate_limit,
                "semaphore_capacity": self.semaphore._value,
                "recent_requests": len(self.last_request_times),
                "cache_stats": cache_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get fetch stats: {e}")
            return {}
    
    async def _fetch_from_web(self, url: str) -> ScrapeResult:
        """Fetch from web using existing scraper"""
        try:
            # Use the existing stealth scraper
            # Note: The existing scraper is synchronous, so we run it in executor
            loop = asyncio.get_event_loop()
            scrape_result = await loop.run_in_executor(
                None, 
                self.scraper.scrape_url, 
                url, 
                ScrapingMethod.AUTO
            )
            
            logger.debug(f"Fetched {url}: success={scrape_result.success}")
            return scrape_result
            
        except Exception as e:
            logger.error(f"Failed to fetch from web {url}: {e}")
            return ScrapeResult(
                url=url,
                success=False,
                error=str(e),
                method_used=ScrapingMethod.AUTO
            )
    
    async def _scrape_result_to_product(self, scrape_result: ScrapeResult) -> Optional[Product]:
        """Convert ScrapeResult to Product schema for caching"""
        try:
            if not scrape_result.success or not scrape_result.content:
                return None
            
            # Process HTML
            processed_html = self.html_processor.process_html(
                scrape_result.content,
                scrape_result.url
            )
            
            # Create basic product model for caching
            # Note: This doesn't include LLM extraction yet
            product = Product(
                project_id="",  # Will be set when adding to project
                url=scrape_result.url,
                type="Unknown",  # Will be extracted by LLM
                description=processed_html.title or "Product",
                confidence_score=0.5,  # Base score for successful scrape
                extraction_metadata={
                    "scrape_method": scrape_result.method_used,
                    "content_length": len(scrape_result.content),
                    "has_images": len(processed_html.image_urls) > 0,
                    "processed_html": processed_html.model_dump()
                }
            )
            
            return product
            
        except Exception as e:
            logger.error(f"Failed to convert scrape result to product: {e}")
            return None
    
    def _product_to_scrape_result(self, product: Product, url: str) -> ScrapeResult:
        """Convert cached Product back to ScrapeResult format"""
        try:
            # Extract original scrape data from metadata
            metadata = product.extraction_metadata
            processed_html_data = metadata.get("processed_html", {})
            
            # Reconstruct content from processed HTML
            content = f"<html><head><title>{product.description}</title></head><body>"
            content += f"<h1>{product.description}</h1>"
            if product.image_url:
                content += f"<img src='{product.image_url}' alt='Product Image'/>"
            content += "</body></html>"
            
            return ScrapeResult(
                url=url,
                success=True,
                content=content,
                content_length=len(content),
                method_used=metadata.get("scrape_method", ScrapingMethod.AUTO),
                response_time=0.1,  # Cached response time
                final_url=url
            )
            
        except Exception as e:
            logger.error(f"Failed to convert product to scrape result: {e}")
            return ScrapeResult(
                url=url,
                success=False,
                error=str(e),
                method_used=ScrapingMethod.AUTO
            )
    
    async def _rate_limit(self):
        """Apply rate limiting"""
        try:
            current_time = time.time()
            
            # Remove old request times (older than 1 minute)
            minute_ago = current_time - 60
            self.last_request_times = [
                t for t in self.last_request_times if t > minute_ago
            ]
            
            # Check if we're at the limit
            if len(self.last_request_times) >= self.rate_limit:
                # Calculate sleep time
                oldest_request = min(self.last_request_times)
                sleep_time = 60 - (current_time - oldest_request)
                if sleep_time > 0:
                    logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
                    await asyncio.sleep(sleep_time)
            
            # Record this request
            self.last_request_times.append(current_time)
            
        except Exception as e:
            logger.warning(f"Error in rate limiting: {e}")
    
    async def close(self):
        """Close connections"""
        try:
            if self.cache:
                await self.cache.close()
            logger.info("ProductFetcher closed")
        except Exception as e:
            logger.error(f"Error closing ProductFetcher: {e}")