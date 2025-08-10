"""
ProductCache - Redis-based caching for product data
High-speed caching with TTL management and similarity search
"""

import json
import logging
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

# Import models and config
from models.schemas import Product
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ProductCache:
    """Redis-based cache for product data with similarity search"""
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize Redis cache"""
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self.default_ttl = 3600  # 1 hour default TTL
        self.connection_pool = None
        self.redis_client = None
    
    async def initialize(self):
        """Initialize Redis connection pool"""
        try:
            connection_params = get_settings().get_redis_connection_params()
            self.connection_pool = ConnectionPool.from_url(
                connection_params["url"],
                max_connections=connection_params["max_connections"],
                decode_responses=connection_params["decode_responses"]
            )
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis cache initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis cache: {e}")
            raise
    
    def _get_cache_key(self, url: str, prefix: str = "product") -> str:
        """Generate cache key from URL"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return f"{prefix}:{url_hash}"
    
    def _get_metadata_key(self, url: str) -> str:
        """Generate metadata cache key"""
        return self._get_cache_key(url, "meta")
    
    def _get_similarity_key(self, product_type: str) -> str:
        """Generate similarity index key"""
        return f"similarity:{product_type.lower()}"
    
    async def get(self, url: str) -> Optional[Product]:
        """Get cached product by URL"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            cache_key = self._get_cache_key(url)
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data:
                product_data = json.loads(cached_data)
                logger.debug(f"Cache hit for URL: {url}")
                return Product(**product_data)
            
            logger.debug(f"Cache miss for URL: {url}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to get from cache: {e}")
            return None
    
    async def set(self, url: str, product: Product, ttl: Optional[int] = None) -> bool:
        """Cache product with TTL"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            cache_key = self._get_cache_key(url)
            metadata_key = self._get_metadata_key(url)
            ttl = ttl or self.default_ttl
            
            # Serialize product data
            product_data = product.model_dump()
            # Handle datetime serialization
            for field in ['created_at', 'updated_at', 'last_checked']:
                if field in product_data and product_data[field]:
                    if isinstance(product_data[field], datetime):
                        product_data[field] = product_data[field].isoformat()
            
            # Cache the product
            await self.redis_client.setex(
                cache_key,
                ttl,
                json.dumps(product_data)
            )
            
            # Cache metadata for search
            metadata = {
                "type": product.type,
                "confidence_score": product.confidence_score,
                "verified": product.verified,
                "cached_at": datetime.now().isoformat()
            }
            await self.redis_client.setex(
                metadata_key,
                ttl,
                json.dumps(metadata)
            )
            
            # Add to similarity index
            await self._add_to_similarity_index(product)
            
            logger.debug(f"Cached product for URL: {url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache product: {e}")
            return False
    
    async def invalidate(self, url: str) -> bool:
        """Remove product from cache"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            cache_key = self._get_cache_key(url)
            metadata_key = self._get_metadata_key(url)
            
            # Remove from cache
            deleted = await self.redis_client.delete(cache_key, metadata_key)
            
            if deleted > 0:
                logger.debug(f"Invalidated cache for URL: {url}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return False
    
    async def get_many(self, urls: List[str]) -> Dict[str, Optional[Product]]:
        """Get multiple products from cache"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            result = {}
            cache_keys = [self._get_cache_key(url) for url in urls]
            
            # Use pipeline for efficiency
            pipe = self.redis_client.pipeline()
            for key in cache_keys:
                pipe.get(key)
            
            cached_values = await pipe.execute()
            
            for url, cached_data in zip(urls, cached_values):
                if cached_data:
                    try:
                        product_data = json.loads(cached_data)
                        result[url] = Product(**product_data)
                    except Exception as e:
                        logger.warning(f"Failed to deserialize cached product for {url}: {e}")
                        result[url] = None
                else:
                    result[url] = None
            
            hits = sum(1 for v in result.values() if v is not None)
            logger.debug(f"Batch cache lookup: {hits}/{len(urls)} hits")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get multiple from cache: {e}")
            return {url: None for url in urls}
    
    async def set_many(self, products: Dict[str, Product], ttl: Optional[int] = None) -> bool:
        """Cache multiple products"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            ttl = ttl or self.default_ttl
            
            # Use pipeline for efficiency
            pipe = self.redis_client.pipeline()
            
            for url, product in products.items():
                cache_key = self._get_cache_key(url)
                product_data = product.model_dump()
                
                # Handle datetime serialization
                for field in ['created_at', 'updated_at', 'last_checked']:
                    if field in product_data and product_data[field]:
                        if isinstance(product_data[field], datetime):
                            product_data[field] = product_data[field].isoformat()
                
                pipe.setex(cache_key, ttl, json.dumps(product_data))
            
            await pipe.execute()
            logger.debug(f"Cached {len(products)} products")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache multiple products: {e}")
            return False
    
    async def _add_to_similarity_index(self, product: Product):
        """Add product to similarity search index"""
        try:
            similarity_key = self._get_similarity_key(product.type)
            
            # Create a simple similarity record
            similarity_data = {
                "url": str(product.url),
                "type": product.type,
                "description": product.description[:200],  # Truncate for efficiency
                "model_no": product.model_no or "",
                "confidence_score": product.confidence_score
            }
            
            # Add to sorted set with confidence score as score
            await self.redis_client.zadd(
                similarity_key,
                {json.dumps(similarity_data): product.confidence_score}
            )
            
            # Expire similarity index after 24 hours
            await self.redis_client.expire(similarity_key, 86400)
            
        except Exception as e:
            logger.warning(f"Failed to add to similarity index: {e}")
    
    async def get_similar(self, product: Product, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar products using type-based indexing"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            similarity_key = self._get_similarity_key(product.type)
            
            # Get products of same type sorted by confidence score
            similar_items = await self.redis_client.zrevrange(
                similarity_key,
                0,
                limit,
                withscores=True
            )
            
            results = []
            for item_data, score in similar_items:
                try:
                    item = json.loads(item_data)
                    # Skip the same product
                    if item["url"] != str(product.url):
                        item["similarity_score"] = float(score)
                        results.append(item)
                except Exception as e:
                    logger.warning(f"Failed to parse similarity item: {e}")
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Failed to find similar products: {e}")
            return []
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            info = await self.redis_client.info()
            
            # Count cached products
            cursor = 0
            product_count = 0
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match="product:*",
                    count=1000
                )
                product_count += len(keys)
                if cursor == 0:
                    break
            
            return {
                "total_keys": info.get("db0", {}).get("keys", 0),
                "cached_products": product_count,
                "memory_used": info.get("used_memory_human", "0B"),
                "connected_clients": info.get("connected_clients", 0),
                "cache_hits": info.get("keyspace_hits", 0),
                "cache_misses": info.get("keyspace_misses", 0)
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    async def clear_cache(self, pattern: str = "product:*") -> int:
        """Clear cache by pattern"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=1000
                )
                
                if keys:
                    deleted = await self.redis_client.delete(*keys)
                    deleted_count += deleted
                
                if cursor == 0:
                    break
            
            logger.info(f"Cleared {deleted_count} cache entries")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return 0
    
    async def close(self):
        """Close Redis connections"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            if self.connection_pool:
                await self.connection_pool.disconnect()
            logger.info("Redis cache connections closed")
        except Exception as e:
            logger.error(f"Error closing Redis connections: {e}")