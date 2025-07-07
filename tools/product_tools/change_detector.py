"""
ChangeDetector - Monitor products for specification changes
Content hashing and similarity search for detecting product updates
"""

import hashlib
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from difflib import unified_diff
import re

# Import models
from models.schemas import Product, Change
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detect and analyze changes in product specifications"""
    
    def __init__(self):
        """Initialize change detector"""
        self.settings = get_settings()
        
        # Fields to monitor for changes
        self.monitored_fields = [
            'description', 'type', 'model_no', 'image_url', 'qty'
        ]
        
        # Significant change thresholds
        self.price_change_threshold = 0.1  # 10% price change
        self.description_similarity_threshold = 0.8
    
    def detect_changes(self, old_product: Product, new_product: Product) -> List[Change]:
        """Detect changes between old and new product versions"""
        changes = []
        
        try:
            for field in self.monitored_fields:
                old_value = getattr(old_product, field, None)
                new_value = getattr(new_product, field, None)
                
                if self._has_significant_change(field, old_value, new_value):
                    change = Change(
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                        change_type=self._determine_change_type(old_value, new_value)
                    )
                    changes.append(change)
                    
            # Check for content hash changes
            old_hash = self._calculate_content_hash(old_product)
            new_hash = self._calculate_content_hash(new_product)
            
            if old_hash != new_hash:
                logger.debug(f"Content hash changed for product {old_product.id}")
            
            return changes
            
        except Exception as e:
            logger.error(f"Failed to detect changes: {e}")
            return []
    
    def is_discontinued(self, product: Product) -> bool:
        """Check if product appears to be discontinued"""
        try:
            # Check common discontinuation indicators
            description = product.description.lower()
            
            discontinuation_keywords = [
                'discontinued', 'no longer available', 'out of stock',
                'unavailable', 'end of life', 'replaced by', 'superseded',
                'obsolete', 'retired', 'phased out'
            ]
            
            for keyword in discontinuation_keywords:
                if keyword in description:
                    return True
            
            # Check if confidence score is very low (might indicate page not found)
            if product.confidence_score < 0.2:
                return True
            
            # Check if image URL is broken or missing
            if not product.image_url or 'placeholder' in str(product.image_url).lower():
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check discontinuation status: {e}")
            return False
    
    async def find_alternatives(self, product: Product, all_products: List[Product] = None) -> List[Product]:
        """Find similar products as alternatives"""
        try:
            if not all_products:
                return []
            
            alternatives = []
            product_type = product.type.lower()
            
            # Find products of same type
            same_type_products = [
                p for p in all_products 
                if p.type.lower() == product_type and p.id != product.id
            ]
            
            # Calculate similarity scores
            scored_alternatives = []
            for candidate in same_type_products:
                similarity_score = self._calculate_similarity(product, candidate)
                if similarity_score > 0.3:  # Minimum similarity threshold
                    scored_alternatives.append((candidate, similarity_score))
            
            # Sort by similarity and return top alternatives
            scored_alternatives.sort(key=lambda x: x[1], reverse=True)
            alternatives = [alt[0] for alt in scored_alternatives[:5]]
            
            logger.debug(f"Found {len(alternatives)} alternatives for {product.type}")
            return alternatives
            
        except Exception as e:
            logger.error(f"Failed to find alternatives: {e}")
            return []
    
    def get_change_summary(self, changes: List[Change]) -> Dict[str, Any]:
        """Get summary of changes"""
        try:
            if not changes:
                return {"has_changes": False, "change_count": 0}
            
            summary = {
                "has_changes": True,
                "change_count": len(changes),
                "fields_changed": [c.field for c in changes],
                "change_types": {},
                "critical_changes": []
            }
            
            # Categorize changes
            for change in changes:
                change_type = change.change_type
                if change_type not in summary["change_types"]:
                    summary["change_types"][change_type] = 0
                summary["change_types"][change_type] += 1
                
                # Identify critical changes
                if self._is_critical_change(change):
                    summary["critical_changes"].append({
                        "field": change.field,
                        "old_value": change.old_value,
                        "new_value": change.new_value,
                        "reason": self._get_criticality_reason(change)
                    })
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to create change summary: {e}")
            return {"has_changes": False, "error": str(e)}
    
    def _has_significant_change(self, field: str, old_value: Any, new_value: Any) -> bool:
        """Check if change is significant enough to report"""
        try:
            # Handle None values
            if old_value is None and new_value is None:
                return False
            if old_value is None or new_value is None:
                return True
            
            # String fields
            if isinstance(old_value, str) and isinstance(new_value, str):
                # Normalize strings for comparison
                old_normalized = self._normalize_string(old_value)
                new_normalized = self._normalize_string(new_value)
                
                if old_normalized == new_normalized:
                    return False
                
                # Check similarity for description changes
                if field == 'description':
                    similarity = self._calculate_string_similarity(old_normalized, new_normalized)
                    return similarity < self.description_similarity_threshold
                
                return True
            
            # Numeric fields
            if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
                if old_value == 0:
                    return new_value != 0
                
                change_ratio = abs(new_value - old_value) / abs(old_value)
                return change_ratio > 0.05  # 5% change threshold
            
            # Default comparison
            return old_value != new_value
            
        except Exception as e:
            logger.error(f"Error checking significance of change: {e}")
            return True  # Err on side of reporting changes
    
    def _determine_change_type(self, old_value: Any, new_value: Any) -> str:
        """Determine the type of change"""
        if old_value is None:
            return "added"
        elif new_value is None:
            return "removed"
        else:
            return "modified"
    
    def _calculate_content_hash(self, product: Product) -> str:
        """Calculate hash of product content for change detection"""
        try:
            # Create hashable content from key fields
            content = {
                'description': product.description,
                'type': product.type,
                'model_no': product.model_no,
                'image_url': str(product.image_url) if product.image_url else None
            }
            
            content_str = json.dumps(content, sort_keys=True)
            return hashlib.md5(content_str.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Failed to calculate content hash: {e}")
            return ""
    
    def _calculate_similarity(self, product1: Product, product2: Product) -> float:
        """Calculate similarity score between two products"""
        try:
            score = 0.0
            weights = {
                'type': 0.3,
                'description': 0.4,
                'model_no': 0.2,
                'manufacturer': 0.1  # If available in description
            }
            
            # Type similarity
            if product1.type.lower() == product2.type.lower():
                score += weights['type']
            
            # Description similarity
            desc_similarity = self._calculate_string_similarity(
                product1.description, product2.description
            )
            score += weights['description'] * desc_similarity
            
            # Model number similarity
            if product1.model_no and product2.model_no:
                model_similarity = self._calculate_string_similarity(
                    product1.model_no, product2.model_no
                )
                score += weights['model_no'] * model_similarity
            
            return min(1.0, score)
            
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            return 0.0
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings"""
        try:
            if not str1 or not str2:
                return 0.0
            
            # Normalize strings
            norm1 = self._normalize_string(str1)
            norm2 = self._normalize_string(str2)
            
            if norm1 == norm2:
                return 1.0
            
            # Calculate word overlap
            words1 = set(norm1.split())
            words2 = set(norm2.split())
            
            if not words1 or not words2:
                return 0.0
            
            intersection = words1.intersection(words2)
            union = words1.union(words2)
            
            return len(intersection) / len(union)
            
        except Exception as e:
            logger.error(f"Failed to calculate string similarity: {e}")
            return 0.0
    
    def _normalize_string(self, text: str) -> str:
        """Normalize string for comparison"""
        try:
            # Convert to lowercase
            normalized = text.lower()
            
            # Remove extra whitespace
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            
            # Remove common variations
            normalized = re.sub(r'[^\w\s]', '', normalized)
            
            return normalized
            
        except Exception as e:
            logger.error(f"Failed to normalize string: {e}")
            return text
    
    def _is_critical_change(self, change: Change) -> bool:
        """Check if change is critical and needs immediate attention"""
        critical_fields = ['type', 'model_no']
        
        if change.field in critical_fields:
            return True
        
        # Check for price-related changes in description
        if change.field == 'description':
            old_desc = str(change.old_value).lower()
            new_desc = str(change.new_value).lower()
            
            # Look for price indicators
            price_keywords = ['$', 'price', 'cost', 'discontinued', 'unavailable']
            for keyword in price_keywords:
                if keyword in new_desc and keyword not in old_desc:
                    return True
        
        return False
    
    def _get_criticality_reason(self, change: Change) -> str:
        """Get reason why change is considered critical"""
        if change.field in ['type', 'model_no']:
            return f"Product {change.field} changed - may affect specifications"
        
        if change.field == 'description':
            new_desc = str(change.new_value).lower()
            if 'discontinued' in new_desc:
                return "Product may be discontinued"
            if 'price' in new_desc or '$' in new_desc:
                return "Price information changed"
        
        return "Significant product information change"