"""
Test cases for QualityChecker
"""

import pytest
from tools.quality_tools.quality_checker import QualityChecker
from models.schemas import Product


class TestQualityChecker:
    """Test cases for product quality assessment"""
    
    @pytest.fixture
    def quality_checker(self):
        """Create quality checker instance"""
        return QualityChecker()
    
    @pytest.fixture
    def complete_product(self):
        """Create a complete product for testing"""
        return Product(
            project_id="test_project",
            url="https://example.com/product",
            image_url="https://example.com/image.jpg",
            type="Faucet",
            description="High-quality kitchen faucet with pull-down sprayer and lifetime warranty",
            model_no="KF-123",
            qty=1,
            key="FAU_001",
            confidence_score=0.9,
            verified=True
        )
    
    @pytest.fixture
    def incomplete_product(self):
        """Create an incomplete product for testing"""
        return Product(
            project_id="test_project",
            url="https://example.com/product",
            type="Unknown",
            description="Product",
            qty=1,
            confidence_score=0.3
        )
    
    def test_completeness_check_complete_product(self, quality_checker, complete_product):
        """Test completeness check with complete product"""
        quality_score = quality_checker.check_completeness(complete_product)
        
        assert quality_score.completeness_score > 0.8
        assert len(quality_score.missing_fields) == 0
        assert len(quality_score.issues) == 0
    
    def test_completeness_check_incomplete_product(self, quality_checker, incomplete_product):
        """Test completeness check with incomplete product"""
        quality_score = quality_checker.check_completeness(incomplete_product)
        
        assert quality_score.completeness_score < 0.8
        assert len(quality_score.missing_fields) > 0
        assert "image_url" in quality_score.missing_fields
        assert "model_no" in quality_score.missing_fields
    
    def test_accuracy_check_valid_product(self, quality_checker, complete_product):
        """Test accuracy check with valid product"""
        quality_score = quality_checker.check_accuracy(complete_product)
        
        assert quality_score.accuracy_score > 0.7
        assert len(quality_score.issues) == 0
    
    def test_accuracy_check_invalid_urls(self, quality_checker):
        """Test accuracy check with invalid URLs"""
        product = Product(
            project_id="test_project",
            url="invalid-url",
            image_url="also-invalid",
            type="Faucet",
            description="Test product",
            qty=1
        )
        
        quality_score = quality_checker.check_accuracy(product)
        
        assert quality_score.accuracy_score < 0.8
        assert len(quality_score.issues) > 0
        assert any("URL" in issue for issue in quality_score.issues)
    
    def test_comprehensive_check(self, quality_checker, complete_product):
        """Test comprehensive quality check"""
        quality_score = quality_checker.comprehensive_check(complete_product)
        
        assert quality_score.overall_score > 0.0
        assert quality_score.completeness_score > 0.0
        assert quality_score.accuracy_score > 0.0
        assert not quality_score.needs_review
    
    def test_batch_quality_check(self, quality_checker, complete_product, incomplete_product):
        """Test batch quality checking"""
        products = [complete_product, incomplete_product]
        quality_scores = quality_checker.batch_check(products)
        
        assert len(quality_scores) == 2
        assert quality_scores[0].overall_score > quality_scores[1].overall_score
    
    def test_quality_summary(self, quality_checker, complete_product, incomplete_product):
        """Test quality summary generation"""
        products = [complete_product, incomplete_product]
        quality_scores = quality_checker.batch_check(products)
        summary = quality_checker.get_quality_summary(quality_scores)
        
        assert "total_products" in summary
        assert "average_score" in summary
        assert "auto_approve_count" in summary
        assert summary["total_products"] == 2
    
    def test_improvement_suggestions(self, quality_checker, incomplete_product):
        """Test improvement suggestions for low-quality products"""
        quality_score = quality_checker.comprehensive_check(incomplete_product)
        suggestions = quality_checker.suggest_improvements(incomplete_product, quality_score)
        
        assert len(suggestions) > 0
        assert any("image" in suggestion.lower() for suggestion in suggestions)
        assert any("model" in suggestion.lower() for suggestion in suggestions)