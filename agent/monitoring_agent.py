"""
MonitoringAgent - Change detection and proactive monitoring
Handles product change detection and system monitoring tasks
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

# Import base agent framework
from agent.therma_pydantic import Agent, Tool, ToolParameter, AgentConfig

# Import monitoring tools
from tools.product_tools.change_detector import ChangeDetector
from tools.product_tools.product_fetcher import ProductFetcher
from tools.data_management.project_store import ProjectStore
from tools.data_management.product_cache import ProductCache

# Import schemas
from models.schemas import Product, Change

logger = logging.getLogger(__name__)


class MonitoringAgent(Agent):
    """Specialized agent for change detection and system monitoring"""
    
    def __init__(self, project_store: Optional[ProjectStore] = None,
                 product_cache: Optional[ProductCache] = None):
        """Initialize monitoring agent"""
        config = AgentConfig(
            system_prompt="""You are a monitoring specialist for architectural product specifications.
            You excel at:
            - Detecting changes in product specifications over time
            - Proactive monitoring of product availability and updates
            - Finding alternative products when items are discontinued
            - Maintaining data freshness and accuracy
            
            Always:
            - Alert users to critical changes that affect specifications
            - Suggest alternatives when products become unavailable
            - Provide clear change summaries and impact assessments
            - Maintain audit trails of all detected changes""",
            max_iterations=12,
            enable_tool_calls=True
        )
        
        super().__init__(config=config)
        
        # Initialize components
        self.project_store = project_store or ProjectStore()
        self.product_cache = product_cache or ProductCache()
        self.change_detector = ChangeDetector()
        self.product_fetcher = ProductFetcher(self.product_cache)
        
        # Setup tools
        self._setup_tools()
    
    @property
    def agent_id(self) -> str:
        return "monitoring_agent"
    
    async def initialize(self):
        """Initialize agent components"""
        try:
            await self.project_store.initialize()
            await self.product_cache.initialize()
            await self.product_fetcher.initialize()
            logger.info("MonitoringAgent initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize some components: {e}")
    
    def _setup_tools(self):
        """Setup monitoring tools"""
        
        def check_product_changes(product_id: str, force_refresh: bool = False) -> Dict[str, Any]:
            """Check for changes in a specific product"""
            try:
                import asyncio
                
                # Get current product
                current_product = asyncio.run(self.project_store.get_product(product_id))
                if not current_product:
                    return {
                        "success": False,
                        "error": f"Product {product_id} not found"
                    }
                
                # Fetch latest data
                latest_scrape = asyncio.run(
                    self.product_fetcher.fetch(str(current_product.url), force_refresh=force_refresh)
                )
                
                if not latest_scrape.success:
                    return {
                        "success": False,
                        "error": f"Failed to fetch latest data: {latest_scrape.error}",
                        "product_id": product_id
                    }
                
                # Extract latest product data
                from tools.html_processor import HTMLProcessor
                from tools.product_tools.product_extractor import ProductExtractor
                
                html_processor = HTMLProcessor()
                product_extractor = ProductExtractor()
                
                processed_html = html_processor.process_html(
                    latest_scrape.content, 
                    latest_scrape.url
                )
                
                latest_product = asyncio.run(
                    product_extractor.extract(processed_html, current_product.project_id)
                )
                
                # Set the same ID for comparison
                latest_product.id = current_product.id
                latest_product.created_at = current_product.created_at
                
                # Detect changes
                changes = self.change_detector.detect_changes(current_product, latest_product)
                
                # Check if product is discontinued
                is_discontinued = self.change_detector.is_discontinued(latest_product)
                
                # Get change summary
                change_summary = self.change_detector.get_change_summary(changes)
                
                return {
                    "success": True,
                    "product_id": product_id,
                    "has_changes": len(changes) > 0,
                    "changes": [
                        {
                            "field": change.field,
                            "old_value": change.old_value,
                            "new_value": change.new_value,
                            "change_type": change.change_type,
                            "detected_at": change.detected_at.isoformat()
                        }
                        for change in changes
                    ],
                    "change_summary": change_summary,
                    "is_discontinued": is_discontinued,
                    "current_confidence": current_product.confidence_score,
                    "new_confidence": latest_product.confidence_score,
                    "last_checked": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Failed to check product changes: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "product_id": product_id
                }
        
        def monitor_project_products(project_id: str, days_since_check: int = 7) -> Dict[str, Any]:
            """Monitor all products in a project for changes"""
            try:
                import asyncio
                
                # Get products that haven't been checked recently
                cutoff_date = datetime.now() - timedelta(days=days_since_check)
                products = asyncio.run(self.project_store.get_products(project_id))
                
                products_to_check = [
                    p for p in products 
                    if not p.last_checked or p.last_checked < cutoff_date
                ]
                
                if not products_to_check:
                    return {
                        "success": True,
                        "message": "All products are up to date",
                        "products_checked": 0,
                        "total_products": len(products)
                    }
                
                # Check each product
                results = []
                for product in products_to_check:
                    result = check_product_changes(product.id, force_refresh=True)
                    if result["success"]:
                        results.append({
                            "product_id": product.id,
                            "type": product.type,
                            "description": product.description[:50] + "..." if len(product.description) > 50 else product.description,
                            "has_changes": result["has_changes"],
                            "change_count": len(result["changes"]),
                            "is_discontinued": result["is_discontinued"],
                            "critical_changes": result["change_summary"].get("critical_changes", [])
                        })
                        
                        # Update last_checked timestamp
                        asyncio.run(self.project_store.update_product(
                            product.id, 
                            {"last_checked": datetime.now()}
                        ))
                
                # Summary statistics
                products_with_changes = sum(1 for r in results if r["has_changes"])
                discontinued_products = sum(1 for r in results if r["is_discontinued"])
                critical_changes = sum(len(r["critical_changes"]) for r in results)
                
                return {
                    "success": True,
                    "project_id": project_id,
                    "products_checked": len(products_to_check),
                    "total_products": len(products),
                    "products_with_changes": products_with_changes,
                    "discontinued_products": discontinued_products,
                    "critical_changes": critical_changes,
                    "results": results,
                    "message": f"Monitored {len(products_to_check)} products, found {products_with_changes} with changes"
                }
                
            except Exception as e:
                logger.error(f"Failed to monitor project products: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "project_id": project_id
                }
        
        def find_product_alternatives(product_id: str, limit: int = 5) -> Dict[str, Any]:
            """Find alternative products for a given product"""
            try:
                import asyncio
                
                # Get the product
                product = asyncio.run(self.project_store.get_product(product_id))
                if not product:
                    return {
                        "success": False,
                        "error": f"Product {product_id} not found"
                    }
                
                # Get all products in the same project for similarity comparison
                all_products = asyncio.run(self.project_store.get_products(product.project_id))
                
                # Find alternatives
                alternatives = asyncio.run(
                    self.change_detector.find_alternatives(product, all_products)
                )
                
                # Format alternatives
                formatted_alternatives = []
                for alt in alternatives[:limit]:
                    formatted_alternatives.append({
                        "product_id": alt.id,
                        "type": alt.type,
                        "description": alt.description,
                        "model_no": alt.model_no,
                        "confidence_score": alt.confidence_score,
                        "verified": alt.verified,
                        "url": str(alt.url)
                    })
                
                return {
                    "success": True,
                    "product_id": product_id,
                    "original_product": {
                        "type": product.type,
                        "description": product.description,
                        "model_no": product.model_no
                    },
                    "alternatives": formatted_alternatives,
                    "alternatives_count": len(formatted_alternatives),
                    "message": f"Found {len(formatted_alternatives)} alternative products"
                }
                
            except Exception as e:
                logger.error(f"Failed to find alternatives: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "product_id": product_id
                }
        
        def get_stale_products(project_id: str = None, days_threshold: int = 30) -> Dict[str, Any]:
            """Get products that haven't been checked in a while"""
            try:
                import asyncio
                
                cutoff_date = datetime.now() - timedelta(days=days_threshold)
                
                if project_id:
                    products = asyncio.run(self.project_store.get_products(project_id))
                else:
                    # Get all active projects
                    projects = asyncio.run(self.project_store.list_projects())
                    products = []
                    for project in projects:
                        if project.status.value == "active":
                            project_products = asyncio.run(self.project_store.get_products(project.id))
                            products.extend(project_products)
                
                # Filter stale products
                stale_products = []
                for product in products:
                    if not product.last_checked or product.last_checked < cutoff_date:
                        days_since_check = (datetime.now() - (product.last_checked or product.created_at)).days
                        stale_products.append({
                            "product_id": product.id,
                            "project_id": product.project_id,
                            "type": product.type,
                            "description": product.description[:50] + "..." if len(product.description) > 50 else product.description,
                            "last_checked": product.last_checked.isoformat() if product.last_checked else None,
                            "days_since_check": days_since_check,
                            "url": str(product.url)
                        })
                
                # Sort by days since check (oldest first)
                stale_products.sort(key=lambda x: x["days_since_check"], reverse=True)
                
                return {
                    "success": True,
                    "stale_products": stale_products,
                    "count": len(stale_products),
                    "threshold_days": days_threshold,
                    "project_id": project_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get stale products: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "stale_products": []
                }
        
        def get_monitoring_summary(project_id: str = None) -> Dict[str, Any]:
            """Get overall monitoring summary"""
            try:
                import asyncio
                
                if project_id:
                    projects = [asyncio.run(self.project_store.get_project(project_id))]
                    if not projects[0]:
                        return {
                            "success": False,
                            "error": f"Project {project_id} not found"
                        }
                else:
                    projects = asyncio.run(self.project_store.list_projects())
                    projects = [p for p in projects if p.status.value == "active"]
                
                summary = {
                    "total_projects": len(projects),
                    "total_products": 0,
                    "products_never_checked": 0,
                    "products_stale": 0,
                    "products_fresh": 0,
                    "projects_summary": []
                }
                
                cutoff_date = datetime.now() - timedelta(days=7)  # 7 days threshold
                
                for project in projects:
                    products = asyncio.run(self.project_store.get_products(project.id))
                    
                    never_checked = sum(1 for p in products if not p.last_checked)
                    stale = sum(1 for p in products if p.last_checked and p.last_checked < cutoff_date)
                    fresh = len(products) - never_checked - stale
                    
                    summary["total_products"] += len(products)
                    summary["products_never_checked"] += never_checked
                    summary["products_stale"] += stale
                    summary["products_fresh"] += fresh
                    
                    summary["projects_summary"].append({
                        "project_id": project.id,
                        "project_name": project.name,
                        "total_products": len(products),
                        "never_checked": never_checked,
                        "stale": stale,
                        "fresh": fresh,
                        "needs_monitoring": never_checked + stale > 0
                    })
                
                return {
                    "success": True,
                    "summary": summary,
                    "project_id": project_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get monitoring summary: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def schedule_monitoring_task(project_id: str, frequency_days: int = 7) -> Dict[str, Any]:
            """Schedule regular monitoring for a project"""
            try:
                # This is a placeholder for scheduling functionality
                # In a real implementation, this would integrate with a task scheduler
                
                return {
                    "success": True,
                    "project_id": project_id,
                    "frequency_days": frequency_days,
                    "next_check": (datetime.now() + timedelta(days=frequency_days)).isoformat(),
                    "message": f"Monitoring scheduled every {frequency_days} days for project {project_id}"
                }
                
            except Exception as e:
                logger.error(f"Failed to schedule monitoring: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Register tools
        tools = [
            Tool(
                name="check_product_changes",
                description="Check for changes in a specific product",
                parameters=[
                    ToolParameter(name="product_id", type="str", description="Product identifier", required=True),
                    ToolParameter(name="force_refresh", type="bool", description="Force refresh from source", required=False)
                ],
                function=check_product_changes
            ),
            Tool(
                name="monitor_project_products",
                description="Monitor all products in a project for changes",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True),
                    ToolParameter(name="days_since_check", type="int", description="Days since last check threshold", required=False)
                ],
                function=monitor_project_products
            ),
            Tool(
                name="find_product_alternatives",
                description="Find alternative products for a given product",
                parameters=[
                    ToolParameter(name="product_id", type="str", description="Product identifier", required=True),
                    ToolParameter(name="limit", type="int", description="Maximum number of alternatives", required=False)
                ],
                function=find_product_alternatives
            ),
            Tool(
                name="get_stale_products",
                description="Get products that haven't been checked in a while",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier (optional)", required=False),
                    ToolParameter(name="days_threshold", type="int", description="Days threshold for stale products", required=False)
                ],
                function=get_stale_products
            ),
            Tool(
                name="get_monitoring_summary",
                description="Get overall monitoring summary",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier (optional)", required=False)
                ],
                function=get_monitoring_summary
            ),
            Tool(
                name="schedule_monitoring_task",
                description="Schedule regular monitoring for a project",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True),
                    ToolParameter(name="frequency_days", type="int", description="Monitoring frequency in days", required=False)
                ],
                function=schedule_monitoring_task
            )
        ]
        
        for tool in tools:
            self.register_tool(tool)
    
    async def automated_monitoring_workflow(self, project_id: str) -> Dict[str, Any]:
        """Run automated monitoring workflow for a project"""
        try:
            # Check for stale products
            stale_result = self.tools["get_stale_products"].call(
                project_id=project_id,
                days_threshold=7
            )
            
            if not stale_result["success"]:
                return stale_result
            
            stale_count = stale_result["count"]
            
            # If there are stale products, monitor them
            if stale_count > 0:
                monitor_result = self.tools["monitor_project_products"].call(
                    project_id=project_id,
                    days_since_check=7
                )
                
                return {
                    "success": True,
                    "project_id": project_id,
                    "stale_products_found": stale_count,
                    "monitoring_result": monitor_result,
                    "message": f"Automated monitoring completed: checked {stale_count} stale products"
                }
            else:
                return {
                    "success": True,
                    "project_id": project_id,
                    "stale_products_found": 0,
                    "message": "No stale products found, monitoring up to date"
                }
                
        except Exception as e:
            logger.error(f"Failed automated monitoring workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Automated monitoring workflow failed"
            }
    
    async def close(self):
        """Close agent and cleanup resources"""
        try:
            await self.project_store.close()
            await self.product_cache.close()
            await self.product_fetcher.close()
            logger.info("MonitoringAgent closed")
        except Exception as e:
            logger.error(f"Error closing MonitoringAgent: {e}")