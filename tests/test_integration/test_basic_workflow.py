"""
Basic integration test for the agent workflow
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from agent.conversation_agent import ConversationAgent
from agent.product_agent import ProductAgent
from tools.nlp.context_tracker import ContextTracker
from tools.data_management.project_store import ProjectStore


class TestBasicWorkflow:
    """Test basic user workflow integration"""
    
    @pytest.fixture
    async def mock_components(self):
        """Create mocked components for testing"""
        # Mock project store
        mock_store = AsyncMock(spec=ProjectStore)
        mock_store.create_project.return_value = "test_project_123"
        mock_store.get_project.return_value = MagicMock(
            id="test_project_123",
            name="Test Project",
            status="active"
        )
        
        # Mock context tracker
        mock_context = AsyncMock(spec=ContextTracker)
        mock_context.get_context.return_value = MagicMock(
            session_id="test_session",
            active_project_id=None,
            active_project_name=None
        )
        
        return {
            "project_store": mock_store,
            "context_tracker": mock_context
        }
    
    @pytest.mark.asyncio
    async def test_create_project_workflow(self, mock_components):
        """Test creating a project through conversation"""
        # Initialize agents with mocks
        conversation_agent = ConversationAgent(mock_components["context_tracker"])
        product_agent = ProductAgent(mock_components["project_store"])
        
        # Mock initialization
        conversation_agent.intent_parser = MagicMock()
        conversation_agent.intent_parser.parse.return_value = MagicMock(
            action="create_project",
            confidence=0.9,
            entities={"project": "Test Project"},
            raw_text="Create a new project called Test Project"
        )
        
        # Test conversation handling
        session_id = "test_session_123"
        message = "Create a new project called Test Project"
        
        response = await conversation_agent.handle_message(message, session_id)
        
        # Verify response structure
        assert response["success"] is True
        assert "target_agent" in response
        assert response["target_agent"] == "product_agent"
        
        # Test product agent handling the intent
        intent = response["intent"]
        product_response = await product_agent.handle_intent(intent, session_id)
        
        # Verify project creation
        assert product_response["success"] is True
        assert "project_id" in product_response
    
    @pytest.mark.asyncio
    async def test_intent_routing(self, mock_components):
        """Test intent routing to appropriate agents"""
        conversation_agent = ConversationAgent(mock_components["context_tracker"])
        
        # Mock intent parser
        conversation_agent.intent_parser = MagicMock()
        
        test_cases = [
            ("create_project", "product_agent"),
            ("add_products", "product_agent"),
            ("generate_specbook", "export_agent"),
            ("verify_product", "quality_agent")
        ]
        
        for action, expected_agent in test_cases:
            # Mock intent
            conversation_agent.intent_parser.parse.return_value = MagicMock(
                action=action,
                confidence=0.8,
                entities={},
                raw_text=f"Test {action}"
            )
            
            response = await conversation_agent.handle_message(f"Test {action}", "session")
            
            assert response["success"] is True
            assert response["target_agent"] == expected_agent
    
    def test_configuration_loading(self):
        """Test that configuration loads properly"""
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Verify key settings exist
        assert hasattr(settings, 'database_url')
        assert hasattr(settings, 'redis_url')
        assert hasattr(settings, 'llm_model')
        assert hasattr(settings, 'quality_auto_approve_threshold')
    
    def test_schema_validation(self):
        """Test Pydantic schema validation"""
        from models.schemas import Product, Project
        
        # Test valid product creation
        product = Product(
            project_id="test_123",
            url="https://example.com/product",
            type="Faucet",
            description="Test faucet",
            qty=1
        )
        
        assert product.project_id == "test_123"
        assert product.qty == 1
        assert product.confidence_score == 0.0  # Default value
        
        # Test valid project creation
        project = Project(
            name="Test Project"
        )
        
        assert project.name == "Test Project"
        assert project.status.value == "draft"  # Default status
        
        # Test validation error
        with pytest.raises(ValueError):
            Product(
                project_id="",  # Empty project_id should fail
                url="invalid-url",  # Invalid URL should fail
                type="",  # Empty type should fail
                description="",  # Empty description should fail
                qty=0  # Zero quantity should fail
            )
    
    def test_export_template_availability(self):
        """Test that export templates are available"""
        from tools.export_tools.specbook_generator import SpecbookGenerator
        
        generator = SpecbookGenerator()
        templates = generator.get_available_templates()
        
        # Verify required templates exist
        assert "default" in templates
        assert "revit" in templates
        assert "minimal" in templates
        assert "detailed" in templates
        
        # Verify template structure
        for template_name, template_info in templates.items():
            assert "name" in template_info
            assert "description" in template_info
            assert "use_case" in template_info