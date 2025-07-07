"""
ExportAgent - Specbook generation and export management
Handles multi-format exports and Revit integration
"""

import logging
from typing import Dict, List, Any, Optional

# Import base agent framework
from agent.therma_pydantic import Agent, Tool, ToolParameter, AgentConfig

# Import export tools
from tools.export_tools.specbook_generator import SpecbookGenerator
from tools.export_tools.revit_connector import RevitConnector
from tools.data_management.project_store import ProjectStore

# Import schemas
from models.schemas import Product, SpecbookExport, ExportFormat, Intent, IntentAction

logger = logging.getLogger(__name__)


class ExportAgent(Agent):
    """Specialized agent for specbook generation and export"""
    
    def __init__(self, project_store: Optional[ProjectStore] = None):
        """Initialize export agent"""
        config = AgentConfig(
            system_prompt="""You are an export specialist for architectural specification books.
            You excel at:
            - Generating specification books in multiple formats (CSV, PDF, Excel, JSON)
            - Ensuring Revit compatibility and proper field mapping
            - Customizing exports based on project requirements
            - Validating export data quality and completeness
            
            Always:
            - Confirm export parameters before processing
            - Validate data completeness for exports
            - Provide clear instructions for using exported files
            - Ensure proper formatting for target applications""",
            max_iterations=8,
            enable_tool_calls=True
        )
        
        super().__init__(config=config)
        
        # Initialize components
        self.project_store = project_store or ProjectStore()
        self.specbook_generator = SpecbookGenerator()
        self.revit_connector = RevitConnector()
        
        # Setup tools
        self._setup_tools()
    
    @property
    def agent_id(self) -> str:
        return "export_agent"
    
    async def initialize(self):
        """Initialize agent components"""
        try:
            await self.project_store.initialize()
            logger.info("ExportAgent initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize some components: {e}")
    
    def _setup_tools(self):
        """Setup export tools"""
        
        def generate_specbook_export(project_id: str, export_format: str = "csv", 
                                   template: str = "revit", include_unverified: bool = False,
                                   filters: Dict[str, Any] = None) -> Dict[str, Any]:
            """Generate specbook export in specified format"""
            try:
                import asyncio
                
                # Get products
                products = asyncio.run(self.project_store.get_products(project_id, filters or {}))
                if not products:
                    return {
                        "success": False,
                        "error": "No products found in project",
                        "message": "Cannot export empty project"
                    }
                
                # Create export configuration
                try:
                    export_config = SpecbookExport(
                        project_id=project_id,
                        format=ExportFormat(export_format.lower()),
                        include_unverified=include_unverified,
                        filters=filters or {},
                        template=template
                    )
                except ValueError as e:
                    return {
                        "success": False,
                        "error": f"Invalid export configuration: {e}"
                    }
                
                # Generate export
                export_data = self.specbook_generator.generate_export(export_config, products)
                
                # Save to temporary file
                import tempfile
                import os
                from datetime import datetime
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_extension = export_format.lower()
                if file_extension == "excel":
                    file_extension = "xlsx"
                
                filename = f"specbook_{project_id}_{timestamp}.{file_extension}"
                temp_path = os.path.join(tempfile.gettempdir(), filename)
                
                with open(temp_path, 'wb') as f:
                    f.write(export_data)
                
                # Get export summary
                summary = self.specbook_generator.get_export_summary(products, export_config)
                
                return {
                    "success": True,
                    "export_path": temp_path,
                    "filename": filename,
                    "format": export_format,
                    "template": template,
                    "summary": summary,
                    "message": f"Specbook exported successfully as {filename}"
                }
                
            except Exception as e:
                logger.error(f"Failed to generate specbook export: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "message": "Export generation failed"
                }
        
        def validate_revit_compatibility(project_id: str) -> Dict[str, Any]:
            """Validate products for Revit compatibility"""
            try:
                import asyncio
                
                products = asyncio.run(self.project_store.get_products(project_id))
                if not products:
                    return {
                        "success": True,
                        "issues": [],
                        "message": "No products to validate"
                    }
                
                issues = self.revit_connector.validate_revit_compatibility(products)
                
                return {
                    "success": True,
                    "project_id": project_id,
                    "total_products": len(products),
                    "products_with_issues": len(issues),
                    "issues": issues,
                    "is_compatible": len(issues) == 0,
                    "message": f"Validated {len(products)} products, found {len(issues)} with compatibility issues"
                }
                
            except Exception as e:
                logger.error(f"Failed to validate Revit compatibility: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def generate_revit_import_file(project_id: str, file_format: str = "csv") -> Dict[str, Any]:
            """Generate Revit-compatible import file"""
            try:
                import asyncio
                
                products = asyncio.run(self.project_store.get_products(project_id))
                if not products:
                    return {
                        "success": False,
                        "error": "No products found in project"
                    }
                
                # Generate import file
                import_path = self.revit_connector.generate_import_file(products, file_format)
                
                return {
                    "success": True,
                    "import_path": import_path,
                    "project_id": project_id,
                    "product_count": len(products),
                    "format": file_format,
                    "message": f"Revit import file generated: {import_path}"
                }
                
            except Exception as e:
                logger.error(f"Failed to generate Revit import file: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def get_export_templates() -> Dict[str, Any]:
            """Get available export templates"""
            try:
                templates = self.specbook_generator.get_available_templates()
                
                return {
                    "success": True,
                    "templates": templates,
                    "count": len(templates)
                }
                
            except Exception as e:
                logger.error(f"Failed to get export templates: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "templates": {}
                }
        
        def get_revit_import_instructions() -> Dict[str, Any]:
            """Get instructions for importing into Revit"""
            try:
                instructions = self.revit_connector.get_revit_import_instructions()
                
                return {
                    "success": True,
                    "instructions": instructions
                }
                
            except Exception as e:
                logger.error(f"Failed to get Revit instructions: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def preview_export(project_id: str, export_format: str = "csv", 
                         template: str = "revit", filters: Dict[str, Any] = None) -> Dict[str, Any]:
            """Preview what would be exported without generating the file"""
            try:
                import asyncio
                
                products = asyncio.run(self.project_store.get_products(project_id, filters or {}))
                if not products:
                    return {
                        "success": False,
                        "error": "No products found for export preview"
                    }
                
                # Create export configuration
                try:
                    export_config = SpecbookExport(
                        project_id=project_id,
                        format=ExportFormat(export_format.lower()),
                        filters=filters or {},
                        template=template
                    )
                except ValueError as e:
                    return {
                        "success": False,
                        "error": f"Invalid export configuration: {e}"
                    }
                
                # Get summary without generating file
                summary = self.specbook_generator.get_export_summary(products, export_config)
                
                # Get sample products for preview
                sample_products = products[:5]  # First 5 products
                sample_data = []
                for product in sample_products:
                    sample_data.append({
                        "type": product.type,
                        "description": product.description[:100] + "..." if len(product.description) > 100 else product.description,
                        "model_no": product.model_no,
                        "verified": product.verified,
                        "confidence_score": product.confidence_score
                    })
                
                return {
                    "success": True,
                    "preview": {
                        "summary": summary,
                        "sample_products": sample_data,
                        "total_sample_count": len(sample_products)
                    },
                    "export_config": {
                        "format": export_format,
                        "template": template,
                        "filters": filters or {}
                    }
                }
                
            except Exception as e:
                logger.error(f"Failed to preview export: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def map_products_for_revit(project_id: str, limit: int = 10) -> Dict[str, Any]:
            """Show how products would be mapped for Revit"""
            try:
                import asyncio
                
                products = asyncio.run(self.project_store.get_products(project_id))
                if not products:
                    return {
                        "success": False,
                        "error": "No products found in project"
                    }
                
                # Map sample products
                sample_products = products[:limit]
                mapped_products = []
                
                for product in sample_products:
                    mapped = self.revit_connector.map_fields(product)
                    mapped_products.append({
                        "original_product": {
                            "id": product.id,
                            "type": product.type,
                            "description": product.description[:50] + "..." if len(product.description) > 50 else product.description,
                            "model_no": product.model_no
                        },
                        "revit_mapping": mapped
                    })
                
                return {
                    "success": True,
                    "project_id": project_id,
                    "mapped_products": mapped_products,
                    "sample_count": len(mapped_products),
                    "total_products": len(products)
                }
                
            except Exception as e:
                logger.error(f"Failed to map products for Revit: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Register tools
        tools = [
            Tool(
                name="generate_specbook_export",
                description="Generate specbook export in specified format",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True),
                    ToolParameter(name="export_format", type="str", description="Export format (csv, pdf, excel, json)", required=False),
                    ToolParameter(name="template", type="str", description="Export template (default, revit, minimal, detailed)", required=False),
                    ToolParameter(name="include_unverified", type="bool", description="Include unverified products", required=False),
                    ToolParameter(name="filters", type="dict", description="Export filters", required=False)
                ],
                function=generate_specbook_export
            ),
            Tool(
                name="validate_revit_compatibility",
                description="Validate products for Revit compatibility",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True)
                ],
                function=validate_revit_compatibility
            ),
            Tool(
                name="generate_revit_import_file",
                description="Generate Revit-compatible import file",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True),
                    ToolParameter(name="file_format", type="str", description="File format (csv)", required=False)
                ],
                function=generate_revit_import_file
            ),
            Tool(
                name="get_export_templates",
                description="Get available export templates",
                parameters=[],
                function=get_export_templates
            ),
            Tool(
                name="get_revit_import_instructions",
                description="Get instructions for importing into Revit",
                parameters=[],
                function=get_revit_import_instructions
            ),
            Tool(
                name="preview_export",
                description="Preview what would be exported without generating the file",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True),
                    ToolParameter(name="export_format", type="str", description="Export format", required=False),
                    ToolParameter(name="template", type="str", description="Export template", required=False),
                    ToolParameter(name="filters", type="dict", description="Export filters", required=False)
                ],
                function=preview_export
            ),
            Tool(
                name="map_products_for_revit",
                description="Show how products would be mapped for Revit",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True),
                    ToolParameter(name="limit", type="int", description="Number of products to sample", required=False)
                ],
                function=map_products_for_revit
            )
        ]
        
        for tool in tools:
            self.register_tool(tool)
    
    async def handle_intent(self, intent: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Handle export-related intents"""
        try:
            action = intent.get("action")
            entities = intent.get("entities", {})
            
            if action == IntentAction.GENERATE_SPECBOOK.value:
                project_id = entities.get("project_id")
                
                if not project_id:
                    return {
                        "success": False,
                        "error": "No project specified for specbook generation"
                    }
                
                # Determine format from entities or use default
                export_format = entities.get("format", "csv")
                deadline = entities.get("deadline")
                
                # Use appropriate template based on context
                template = "revit" if "revit" in entities.get("object_type", "").lower() else "default"
                
                return self.tools["generate_specbook_export"].call(
                    project_id=project_id,
                    export_format=export_format,
                    template=template,
                    include_unverified=False  # Default to verified products only
                )
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported action: {action}",
                    "message": "I don't know how to handle that export request"
                }
                
        except Exception as e:
            logger.error(f"Failed to handle export intent: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "An error occurred processing your export request"
            }
    
    async def close(self):
        """Close agent and cleanup resources"""
        try:
            await self.project_store.close()
            logger.info("ExportAgent closed")
        except Exception as e:
            logger.error(f"Error closing ExportAgent: {e}")