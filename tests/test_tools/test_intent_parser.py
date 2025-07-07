"""
Test cases for IntentParser
"""

import pytest
from tools.nlp.intent_parser import IntentParser
from models.schemas import IntentAction


class TestIntentParser:
    """Test cases for natural language intent parsing"""
    
    @pytest.fixture
    def parser(self):
        """Create intent parser instance"""
        return IntentParser()
    
    def test_create_project_intent(self, parser):
        """Test parsing project creation requests"""
        test_cases = [
            "Create a new project called Desert Modern",
            "Start a project named Scottsdale Residence",
            "New project for Johnson House",
            "Make a new project Kitchen Renovation"
        ]
        
        for message in test_cases:
            intent = parser.parse(message)
            assert intent.action == IntentAction.CREATE_PROJECT
            assert intent.confidence > 0.5
            assert intent.entities.get("project") is not None
    
    def test_add_products_intent(self, parser):
        """Test parsing product addition requests"""
        test_cases = [
            "Add these product URLs to my project",
            "Process these 10 products for Desert Modern",
            "Include these product links in the spec book",
            "Fetch data for these product pages"
        ]
        
        for message in test_cases:
            intent = parser.parse(message)
            assert intent.action == IntentAction.ADD_PRODUCTS
            assert intent.confidence > 0.5
    
    def test_generate_specbook_intent(self, parser):
        """Test parsing specbook generation requests"""
        test_cases = [
            "Generate a spec book for client review",
            "Create the specification sheet for tomorrow",
            "Export the spec book as CSV",
            "Make a specbook for Desert Modern"
        ]
        
        for message in test_cases:
            intent = parser.parse(message)
            assert intent.action == IntentAction.GENERATE_SPECBOOK
            assert intent.confidence > 0.5
    
    def test_url_extraction(self, parser):
        """Test URL extraction from messages"""
        message = "Process these URLs: https://example.com/product1 and https://example.com/product2"
        intent = parser.parse(message)
        
        urls = intent.entities.get("urls", [])
        assert len(urls) == 2
        assert "https://example.com/product1" in urls
        assert "https://example.com/product2" in urls
    
    def test_project_name_extraction(self, parser):
        """Test project name extraction"""
        test_cases = [
            ("Create a project called Desert Modern", "Desert Modern"),
            ("New project for 'Scottsdale Residence'", "Scottsdale Residence"),
            ("Start Kitchen Renovation project", "Kitchen Renovation")
        ]
        
        for message, expected_name in test_cases:
            intent = parser.parse(message)
            project_name = intent.entities.get("project")
            assert project_name is not None
            assert expected_name.lower() in project_name.lower()
    
    def test_low_confidence_suggestions(self, parser):
        """Test that low confidence intents provide suggestions"""
        ambiguous_message = "do something with stuff"
        intent = parser.parse(ambiguous_message)
        
        suggestions = parser.suggest_clarifications(intent)
        assert len(suggestions) > 0
        assert intent.confidence < 0.7
    
    def test_context_application(self, parser):
        """Test context application to enhance entities"""
        context = {
            "active_project_name": "Test Project",
            "active_project_id": "test_123"
        }
        
        message = "add these products"
        intent = parser.parse(message, context)
        
        # Should inherit project from context
        assert intent.entities.get("project") == "Test Project"
        assert intent.entities.get("project_id") == "test_123"