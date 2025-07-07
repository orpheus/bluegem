"""
QualityChecker - Automated quality validation
Wraps existing eval_product_extraction with enhanced confidence scoring
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import re
from urllib.parse import urlparse

# Add tools directory to path
sys.path.append(str(Path(__file__).parent.parent.parent / 'tools'))

# Import existing evaluation tool
from eval_product_extraction import ProductExtractionEvaluator, EvalResult

# Import new components
from models.schemas import Product, QualityScore
from config.settings import get_settings

logger = logging.getLogger(__name__)


class QualityChecker:
    """Enhanced quality checker with confidence scoring"""
    
    def __init__(self):
        """Initialize quality checker"""
        self.settings = get_settings()
        self.evaluator = ProductExtractionEvaluator()
        
        # Quality thresholds
        self.auto_approve_threshold = self.settings.quality_auto_approve_threshold
        self.manual_review_threshold = self.settings.quality_manual_review_threshold
        
        # Field weights for scoring
        self.field_weights = {
            'image_url': 0.2,
            'type': 0.2,
            'description': 0.3,
            'model_no': 0.15,
            'qty': 0.05,
            'key': 0.1
        }
    
    def check_completeness(self, product: Product) -> QualityScore:
        """Check completeness of product data"""
        try:
            missing_fields = []
            issues = []
            recommendations = []
            
            # Check required fields
            if not product.image_url:
                missing_fields.append('image_url')
                issues.append('No product image found')
                recommendations.append('Verify product page has images')
            
            if not product.type or product.type.lower() in ['unknown', 'product']:
                missing_fields.append('type')
                issues.append('Product type not identified')
                recommendations.append('Review product title and description for category information')
            
            if not product.description or len(product.description) < 10:
                missing_fields.append('description')
                issues.append('Description too short or missing')
                recommendations.append('Extract more detailed product information')
            
            if not product.model_no:
                missing_fields.append('model_no')
                issues.append('No model number found')
                recommendations.append('Look for part numbers or SKU in product details')
            
            if product.qty <= 0:
                issues.append('Invalid quantity')
                recommendations.append('Set quantity to at least 1')
            
            # Calculate completeness score
            total_fields = len(self.field_weights)
            complete_fields = total_fields - len(missing_fields)
            completeness_score = complete_fields / total_fields
            
            return QualityScore(
                overall_score=completeness_score,
                completeness_score=completeness_score,
                accuracy_score=1.0,  # Will be calculated separately
                missing_fields=missing_fields,
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Failed to check completeness: {e}")
            return QualityScore(
                overall_score=0.0,
                completeness_score=0.0,
                accuracy_score=0.0,
                issues=[f"Quality check failed: {str(e)}"],
                recommendations=["Manual review required"]
            )
    
    def check_accuracy(self, product: Product) -> QualityScore:
        """Check accuracy of extracted data"""
        try:
            issues = []
            recommendations = []
            accuracy_score = 1.0
            
            # URL validation
            if not self._validate_url(product.url):
                issues.append('Invalid product URL')
                accuracy_score -= 0.2
                recommendations.append('Verify URL format and accessibility')
            
            # Image URL validation
            if product.image_url and not self._validate_url(product.image_url):
                issues.append('Invalid image URL')
                accuracy_score -= 0.1
                recommendations.append('Check image URL format')
            
            # Description quality
            desc_quality = self._check_description_quality(product.description)
            if desc_quality < 0.7:
                issues.append('Low quality description')
                accuracy_score -= 0.15
                recommendations.append('Improve description extraction')
            
            # Type validation
            if not self._validate_product_type(product.type):
                issues.append('Unusual product type')
                accuracy_score -= 0.1
                recommendations.append('Verify product categorization')
            
            # Model number format
            if product.model_no and not self._validate_model_number(product.model_no):
                issues.append('Unusual model number format')
                accuracy_score -= 0.05
                recommendations.append('Verify model number extraction')
            
            # Quantity reasonableness
            if product.qty > 1000:
                issues.append('Unusually high quantity')
                accuracy_score -= 0.05
                recommendations.append('Verify quantity is reasonable')
            
            return QualityScore(
                overall_score=max(0.0, accuracy_score),
                completeness_score=1.0,  # Calculated separately
                accuracy_score=max(0.0, accuracy_score),
                missing_fields=[],
                issues=issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Failed to check accuracy: {e}")
            return QualityScore(
                overall_score=0.0,
                completeness_score=0.0,
                accuracy_score=0.0,
                issues=[f"Accuracy check failed: {str(e)}"],
                recommendations=["Manual review required"]
            )
    
    def comprehensive_check(self, product: Product) -> QualityScore:
        """Perform comprehensive quality assessment"""
        try:
            # Get individual scores
            completeness = self.check_completeness(product)
            accuracy = self.check_accuracy(product)
            
            # Combine scores with weights
            overall_score = (
                completeness.completeness_score * 0.6 +
                accuracy.accuracy_score * 0.4
            )
            
            # Factor in confidence score from extraction
            if hasattr(product, 'confidence_score') and product.confidence_score:
                overall_score = overall_score * 0.8 + product.confidence_score * 0.2
            
            # Combine issues and recommendations
            all_issues = completeness.issues + accuracy.issues
            all_recommendations = completeness.recommendations + accuracy.recommendations
            all_missing = completeness.missing_fields
            
            return QualityScore(
                overall_score=overall_score,
                completeness_score=completeness.completeness_score,
                accuracy_score=accuracy.accuracy_score,
                missing_fields=all_missing,
                issues=all_issues,
                recommendations=list(set(all_recommendations))  # Remove duplicates
            )
            
        except Exception as e:
            logger.error(f"Failed comprehensive quality check: {e}")
            return QualityScore(
                overall_score=0.0,
                completeness_score=0.0,
                accuracy_score=0.0,
                issues=[f"Quality assessment failed: {str(e)}"],
                recommendations=["Complete manual review required"]
            )
    
    def batch_check(self, products: List[Product]) -> List[QualityScore]:
        """Check quality for multiple products"""
        try:
            results = []
            for product in products:
                quality_score = self.comprehensive_check(product)
                results.append(quality_score)
            
            logger.info(f"Quality checked {len(products)} products")
            return results
            
        except Exception as e:
            logger.error(f"Failed batch quality check: {e}")
            return [
                QualityScore(
                    overall_score=0.0,
                    completeness_score=0.0,
                    accuracy_score=0.0,
                    issues=[f"Batch check failed: {str(e)}"],
                    recommendations=["Manual review required"]
                )
                for _ in products
            ]
    
    def get_quality_summary(self, quality_scores: List[QualityScore]) -> Dict[str, Any]:
        """Get summary statistics for quality scores"""
        try:
            if not quality_scores:
                return {"error": "No quality scores provided"}
            
            overall_scores = [q.overall_score for q in quality_scores]
            auto_approve_count = sum(1 for score in overall_scores if score >= self.auto_approve_threshold)
            manual_review_count = sum(1 for score in overall_scores if score < self.manual_review_threshold)
            
            # Count common issues
            all_issues = []
            for q in quality_scores:
                all_issues.extend(q.issues)
            
            issue_counts = {}
            for issue in all_issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            
            return {
                "total_products": len(quality_scores),
                "average_score": sum(overall_scores) / len(overall_scores),
                "auto_approve_count": auto_approve_count,
                "manual_review_count": manual_review_count,
                "auto_approve_rate": auto_approve_count / len(overall_scores),
                "manual_review_rate": manual_review_count / len(overall_scores),
                "score_distribution": {
                    "high": sum(1 for s in overall_scores if s >= 0.8),
                    "medium": sum(1 for s in overall_scores if 0.6 <= s < 0.8),
                    "low": sum(1 for s in overall_scores if s < 0.6)
                },
                "common_issues": dict(sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5])
            }
            
        except Exception as e:
            logger.error(f"Failed to create quality summary: {e}")
            return {"error": str(e)}
    
    def suggest_improvements(self, product: Product, quality_score: QualityScore) -> List[str]:
        """Suggest specific improvements for low-quality products"""
        suggestions = []
        
        try:
            if quality_score.overall_score >= self.auto_approve_threshold:
                return ["Product quality is acceptable"]
            
            # Specific suggestions based on issues
            if 'image_url' in quality_score.missing_fields:
                suggestions.append("Try alternative scraping methods to find product images")
                suggestions.append("Check for image galleries or additional product photos")
            
            if 'type' in quality_score.missing_fields:
                suggestions.append("Look for category breadcrumbs or product navigation")
                suggestions.append("Extract type from product title or descriptions")
            
            if 'description' in quality_score.missing_fields:
                suggestions.append("Combine multiple text elements for fuller description")
                suggestions.append("Look for product specifications or feature lists")
            
            if 'model_no' in quality_score.missing_fields:
                suggestions.append("Search for SKU, part number, or item codes")
                suggestions.append("Check product specifications table")
            
            # URL-specific suggestions
            if any('URL' in issue for issue in quality_score.issues):
                suggestions.append("Verify the source URL is accessible and correct")
                suggestions.append("Check for redirects or changed product URLs")
            
            # General quality improvements
            if quality_score.overall_score < 0.5:
                suggestions.append("Consider using alternative extraction prompts")
                suggestions.append("Manual verification strongly recommended")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Failed to suggest improvements: {e}")
            return ["Manual review and correction recommended"]
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            if not url:
                return False
            
            # Convert to string if it's not already
            url_str = str(url)
            
            # Parse URL
            parsed = urlparse(url_str)
            
            # Check basic structure
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Check scheme
            if parsed.scheme not in ['http', 'https']:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _check_description_quality(self, description: str) -> float:
        """Assess description quality"""
        try:
            if not description:
                return 0.0
            
            score = 0.5  # Base score
            
            # Length check
            if len(description) > 50:
                score += 0.2
            if len(description) > 100:
                score += 0.1
            
            # Word count
            words = description.split()
            if len(words) > 10:
                score += 0.1
            
            # Check for product-specific keywords
            product_keywords = ['inch', 'steel', 'finish', 'mount', 'style', 'color', 'material']
            found_keywords = sum(1 for keyword in product_keywords if keyword.lower() in description.lower())
            score += min(0.1, found_keywords * 0.02)
            
            return min(1.0, score)
            
        except Exception:
            return 0.0
    
    def _validate_product_type(self, product_type: str) -> bool:
        """Validate product type"""
        try:
            if not product_type:
                return False
            
            # Common valid product types
            valid_types = [
                'faucet', 'sink', 'cabinet', 'countertop', 'lighting', 'fixture',
                'appliance', 'hardware', 'door', 'window', 'flooring', 'tile',
                'furniture', 'mirror', 'shower', 'bathtub', 'toilet', 'vanity'
            ]
            
            type_lower = product_type.lower()
            
            # Check if it matches or contains valid types
            for valid_type in valid_types:
                if valid_type in type_lower or type_lower in valid_type:
                    return True
            
            # Check if it's reasonable length and format
            if 2 <= len(product_type) <= 50 and product_type.replace(' ', '').isalpha():
                return True
            
            return False
            
        except Exception:
            return False
    
    def _validate_model_number(self, model_no: str) -> bool:
        """Validate model number format"""
        try:
            if not model_no:
                return False
            
            # Remove whitespace
            model_clean = model_no.strip()
            
            # Check length
            if len(model_clean) < 2 or len(model_clean) > 50:
                return False
            
            # Check for reasonable format (alphanumeric with common separators)
            if re.match(r'^[A-Za-z0-9\-_\.\s]+$', model_clean):
                return True
            
            return False
            
        except Exception:
            return False