"""
ProductAgent - Product operations and management
Handles batch processing, single product operations, and project management
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import base agent framework
from agent.therma_pydantic import Agent, Tool, ToolParameter, AgentConfig

# Import product tools
from tools.product_tools.product_fetcher import ProductFetcher
from tools.product_tools.product_extractor import ProductExtractor
from tools.data_management.project_store import ProjectStore
from tools.data_management.product_cache import ProductCache

# Import schemas
from models.schemas import Product, Project, Intent, IntentAction

logger = logging.getLogger(__name__)


class ProductAgent(Agent):
    """Specialized agent for product operations and project management"""
    
    def __init__(self, project_store: Optional[ProjectStore] = None, 
                 product_cache: Optional[ProductCache] = None):
        """Initialize product agent"""
        config = AgentConfig(
            system_prompt="""You are a product management specialist for architectural specifications.
            You excel at:
            - Processing product URLs and extracting specifications
            - Managing architectural projects and product collections
            - Batch processing multiple products efficiently
            - Organizing and searching product databases
            
            Always:
            - Provide progress updates for long operations
            - Validate data before processing
            - Handle errors gracefully with helpful messages
            - Maintain data integrity across projects""",
            max_iterations=15,
            enable_tool_calls=True
        )
        
        super().__init__(config=config)
        
        # Initialize components
        self.project_store = project_store or ProjectStore()
        self.product_cache = product_cache or ProductCache()
        self.product_fetcher = ProductFetcher(self.product_cache)
        self.product_extractor = ProductExtractor()
        
        # Setup tools
        self._setup_tools()
    
    @property
    def agent_id(self) -> str:
        return "product_agent"
    
    async def initialize(self):
        """Initialize agent components"""
        try:
            await self.project_store.initialize()
            await self.product_cache.initialize()
            await self.product_fetcher.initialize()
            logger.info("ProductAgent initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize some components: {e}")
    
    def _setup_tools(self):
        """Setup product management tools"""
        
        def create_project(name: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
            """Create a new architectural project"""
            try:
                import asyncio
                project_id = asyncio.run(self.project_store.create_project(name, metadata or {}))
                
                return {
                    "success": True,
                    "project_id": project_id,
                    "project_name": name,
                    "message": f"Successfully created project '{name}'"
                }
                
            except Exception as e:
                logger.error(f"Failed to create project: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "message": f"Failed to create project '{name}'"
                }
        
        def list_projects(status: str = None) -> Dict[str, Any]:
            """List available projects"""
            try:
                import asyncio
                from models.schemas import ProjectStatus
                
                project_status = None
                if status:
                    try:
                        project_status = ProjectStatus(status)
                    except ValueError:
                        pass
                
                projects = asyncio.run(self.project_store.list_projects(project_status))
                
                project_list = []
                for project in projects:
                    project_list.append({
                        "id": project.id,
                        "name": project.name,
                        "status": project.status.value,
                        "created_at": project.created_at.isoformat() if project.created_at else None,
                        "updated_at": project.updated_at.isoformat() if project.updated_at else None
                    })
                
                return {
                    "success": True,
                    "projects": project_list,
                    "count": len(project_list)
                }
                
            except Exception as e:
                logger.error(f"Failed to list projects: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "projects": []
                }
        
        def batch_add_products(project_id: str, urls: List[str], max_concurrent: int = 5) -> Dict[str, Any]:
            """Add multiple products to a project via batch processing"""
            try:
                import asyncio
                
                # Validate project exists
                project = asyncio.run(self.project_store.get_project(project_id))
                if not project:
                    return {
                        "success": False,
                        "error": f"Project {project_id} not found",
                        "processed": 0
                    }
                
                # Fetch products
                scrape_results = asyncio.run(
                    self.product_fetcher.batch_fetch(urls, max_concurrent, force_refresh=False)
                )
                
                # Process HTML and extract data
                processed_products = []
                for i, scrape_result in enumerate(scrape_results):
                    if scrape_result.success:
                        try:
                            # Process HTML
                            from tools.html_processor import HTMLProcessor
                            html_processor = HTMLProcessor()
                            processed_html = html_processor.process_html(
                                scrape_result.content, 
                                scrape_result.url
                            )
                            
                            # Extract product data
                            product = asyncio.run(
                                self.product_extractor.extract(processed_html, project_id)
                            )
                            
                            # Save to database
                            product_id = asyncio.run(
                                self.project_store.add_product(project_id, product)
                            )
                            
                            processed_products.append({
                                "url": urls[i],
                                "product_id": product_id,
                                "success": True,
                                "type": product.type,
                                "description": product.description[:100] + "..." if len(product.description) > 100 else product.description,
                                "confidence": product.confidence_score
                            })
                            
                        except Exception as e:
                            logger.error(f"Failed to process product {urls[i]}: {e}")
                            processed_products.append({
                                "url": urls[i],
                                "success": False,
                                "error": str(e)
                            })
                    else:
                        processed_products.append({
                            "url": urls[i],
                            "success": False,
                            "error": scrape_result.error or "Scraping failed"
                        })
                
                success_count = sum(1 for p in processed_products if p.get("success"))
                
                return {
                    "success": True,
                    "processed": len(processed_products),
                    "successful": success_count,
                    "failed": len(processed_products) - success_count,
                    "products": processed_products,
                    "message": f"Processed {len(urls)} URLs: {success_count} successful, {len(processed_products) - success_count} failed"
                }
                
            except Exception as e:
                logger.error(f"Failed batch product addition: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "processed": 0,
                    "message": "Batch processing failed"
                }
        
        def get_project_products(project_id: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
            """Get products for a specific project"""
            try:
                import asyncio
                
                products = asyncio.run(self.project_store.get_products(project_id, filters or {}))
                
                product_list = []
                for product in products:
                    product_list.append({
                        "id": product.id,
                        "type": product.type,
                        "description": product.description,
                        "model_no": product.model_no,
                        "qty": product.qty,
                        "verified": product.verified,
                        "confidence_score": product.confidence_score,
                        "url": str(product.url),
                        "image_url": str(product.image_url) if product.image_url else None,
                        "created_at": product.created_at.isoformat() if product.created_at else None
                    })
                
                return {
                    "success": True,
                    "products": product_list,
                    "count": len(product_list),
                    "project_id": project_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get project products: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "products": []
                }
        
        def update_product(product_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
            """Update a specific product"""
            try:
                import asyncio
                
                # Validate product exists
                product = asyncio.run(self.project_store.get_product(product_id))
                if not product:
                    return {
                        "success": False,
                        "error": f"Product {product_id} not found"
                    }
                
                # Update product
                success = asyncio.run(self.project_store.update_product(product_id, updates))
                
                if success:
                    return {
                        "success": True,
                        "product_id": product_id,
                        "message": "Product updated successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": "Failed to update product"
                    }
                    
            except Exception as e:
                logger.error(f"Failed to update product: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def search_products(query: str, project_id: str = None) -> Dict[str, Any]:
            """Search products by description, type, or model number"""
            try:
                import asyncio
                
                products = asyncio.run(self.project_store.search_products(query, project_id))
                
                results = []
                for product in products:
                    results.append({
                        "id": product.id,
                        "project_id": product.project_id,
                        "type": product.type,
                        "description": product.description,
                        "model_no": product.model_no,
                        "verified": product.verified,
                        "confidence_score": product.confidence_score,
                        "url": str(product.url)
                    })
                
                return {
                    "success": True,
                    "results": results,
                    "count": len(results),
                    "query": query
                }
                
            except Exception as e:
                logger.error(f"Failed to search products: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "results": []
                }
        
        def get_project_stats(project_id: str) -> Dict[str, Any]:
            """Get statistics for a project"""
            try:
                import asyncio
                
                stats = asyncio.run(self.project_store.get_project_stats(project_id))
                
                return {
                    "success": True,
                    "stats": stats,
                    "project_id": project_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get project stats: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "stats": {}
                }
        
        def refresh_product_data(product_id: str) -> Dict[str, Any]:
            """Re-fetch and update product data"""
            try:
                import asyncio
                
                # Get current product
                product = asyncio.run(self.project_store.get_product(product_id))
                if not product:
                    return {
                        "success": False,
                        "error": f"Product {product_id} not found"
                    }
                
                # Re-fetch data
                scrape_result = asyncio.run(
                    self.product_fetcher.fetch(str(product.url), force_refresh=True)
                )
                
                if not scrape_result.success:
                    return {
                        "success": False,
                        "error": f"Failed to re-fetch product data: {scrape_result.error}"
                    }
                
                # Process and extract
                from tools.html_processor import HTMLProcessor
                html_processor = HTMLProcessor()
                processed_html = html_processor.process_html(
                    scrape_result.content, 
                    scrape_result.url
                )
                
                new_product = asyncio.run(
                    self.product_extractor.extract(processed_html, product.project_id)
                )
                
                # Update with new data
                updates = {
                    "description": new_product.description,
                    "type": new_product.type,
                    "model_no": new_product.model_no,
                    "image_url": str(new_product.image_url) if new_product.image_url else None,
                    "confidence_score": new_product.confidence_score,
                    "last_checked": datetime.now(),
                    "verified": False  # Reset verification status
                }
                
                success = asyncio.run(self.project_store.update_product(product_id, updates))
                
                return {
                    "success": success,
                    "product_id": product_id,
                    "message": "Product data refreshed successfully" if success else "Failed to update product",
                    "new_confidence": new_product.confidence_score
                }
                
            except Exception as e:
                logger.error(f"Failed to refresh product data: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Register tools
        tools = [
            Tool(
                name="create_project",
                description="Create a new architectural project",
                parameters=[
                    ToolParameter(name="name", type="str", description="Project name", required=True),
                    ToolParameter(name="metadata", type="dict", description="Additional project metadata", required=False)
                ],
                function=create_project
            ),
            Tool(
                name="list_projects", 
                description="List available projects",
                parameters=[
                    ToolParameter(name="status", type="str", description="Filter by status (active, archived, etc.)", required=False)
                ],
                function=list_projects
            ),
            Tool(
                name="batch_add_products",
                description="Add multiple products to a project via batch processing",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True),
                    ToolParameter(name="urls", type="list", description="List of product URLs", required=True),
                    ToolParameter(name="max_concurrent", type="int", description="Maximum concurrent requests", required=False)
                ],
                function=batch_add_products
            ),
            Tool(
                name="get_project_products",
                description="Get products for a specific project",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True),
                    ToolParameter(name="filters", type="dict", description="Optional filters", required=False)
                ],
                function=get_project_products
            ),
            Tool(
                name="update_product",
                description="Update a specific product",
                parameters=[
                    ToolParameter(name="product_id", type="str", description="Product identifier", required=True),
                    ToolParameter(name="updates", type="dict", description="Fields to update", required=True)
                ],
                function=update_product
            ),
            Tool(
                name="search_products",
                description="Search products by description, type, or model number",
                parameters=[
                    ToolParameter(name="query", type="str", description="Search query", required=True),
                    ToolParameter(name="project_id", type="str", description="Limit search to specific project", required=False)
                ],
                function=search_products
            ),
            Tool(
                name="get_project_stats",
                description="Get statistics for a project",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True)
                ],
                function=get_project_stats
            ),
            Tool(
                name="refresh_product_data",
                description="Re-fetch and update product data from source",
                parameters=[
                    ToolParameter(name="product_id", type="str", description="Product identifier", required=True)
                ],
                function=refresh_product_data
            )
        ]
        
        for tool in tools:
            self.register_tool(tool)
    
    async def handle_intent(self, intent: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Handle product-related intents"""
        try:
            action = intent.get("action")
            entities = intent.get("entities", {})
            
            if action == IntentAction.CREATE_PROJECT.value:
                project_name = entities.get("project", "New Project")
                return self.tools["create_project"].call(name=project_name)
            
            elif action == IntentAction.ADD_PRODUCTS.value:
                urls = entities.get("urls", [])
                project_id = entities.get("project_id")
                
                if not urls:
                    return {
                        "success": False,
                        "error": "No URLs provided",
                        "message": "Please provide product URLs to process"
                    }
                
                if not project_id:
                    # Try to get from session context
                    return {
                        "success": False,
                        "error": "No project specified",
                        "message": "Please specify which project to add products to"
                    }
                
                return self.tools["batch_add_products"].call(
                    project_id=project_id,
                    urls=urls,
                    max_concurrent=min(len(urls), 5)
                )
            
            elif action == IntentAction.LIST_PROJECTS.value:
                return self.tools["list_projects"].call()
            
            elif action == IntentAction.LIST_PRODUCTS.value:
                project_id = entities.get("project_id")
                if project_id:
                    return self.tools["get_project_products"].call(project_id=project_id)
                else:
                    return self.tools["list_projects"].call()
            
            elif action == IntentAction.UPDATE_PRODUCT.value:
                product_id = entities.get("product_id")
                if not product_id:
                    return {
                        "success": False,
                        "error": "No product specified",
                        "message": "Please specify which product to update"
                    }
                
                return self.tools["refresh_product_data"].call(product_id=product_id)
            
            elif action == IntentAction.SEARCH_PRODUCTS.value:
                query = entities.get("query", "")
                project_id = entities.get("project_id")
                
                if not query:
                    return {
                        "success": False,
                        "error": "No search query provided",
                        "message": "Please provide a search term"
                    }
                
                return self.tools["search_products"].call(query=query, project_id=project_id)
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported action: {action}",
                    "message": "I don't know how to handle that request"
                }
                
        except Exception as e:
            logger.error(f"Failed to handle intent: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "An error occurred processing your request"
            }
    
    async def close(self):
        """Close agent and cleanup resources"""
        try:
            await self.project_store.close()
            await self.product_cache.close()
            await self.product_fetcher.close()
            logger.info("ProductAgent closed")
        except Exception as e:
            logger.error(f"Error closing ProductAgent: {e}")