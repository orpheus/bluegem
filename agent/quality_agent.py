"""
QualityAgent - Quality assurance and verification management
Handles automated quality checks and manual verification workflows
"""

import logging
from typing import Dict, List, Any, Optional

# Import base agent framework
from agent.therma_pydantic import Agent, Tool, ToolParameter, AgentConfig

# Import quality tools
from tools.quality_tools.quality_checker import QualityChecker
from tools.quality_tools.verification_queue import VerificationQueue
from tools.data_management.project_store import ProjectStore

# Import schemas
from models.schemas import Product, QualityScore, Intent, IntentAction

logger = logging.getLogger(__name__)


class QualityAgent(Agent):
    """Specialized agent for quality assurance and verification"""
    
    def __init__(self, project_store: Optional[ProjectStore] = None,
                 verification_queue: Optional[VerificationQueue] = None):
        """Initialize quality agent"""
        config = AgentConfig(
            system_prompt="""You are a quality assurance specialist for architectural product specifications.
            You excel at:
            - Automated quality validation and scoring
            - Managing manual verification workflows
            - Identifying data quality issues and suggesting improvements
            - Maintaining high standards for specification accuracy
            
            Always:
            - Provide detailed quality assessments
            - Suggest specific improvements for low-quality data
            - Prioritize critical quality issues
            - Maintain verification audit trails""",
            max_iterations=10,
            enable_tool_calls=True
        )
        
        super().__init__(config=config)
        
        # Initialize components
        self.project_store = project_store or ProjectStore()
        self.verification_queue = verification_queue or VerificationQueue(self.project_store)
        self.quality_checker = QualityChecker()
        
        # Setup tools
        self._setup_tools()
    
    @property
    def agent_id(self) -> str:
        return "quality_agent"
    
    async def initialize(self):
        """Initialize agent components"""
        try:
            await self.project_store.initialize()
            logger.info("QualityAgent initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize some components: {e}")
    
    def _setup_tools(self):
        """Setup quality assurance tools"""
        
        def check_product_quality(product_id: str) -> Dict[str, Any]:
            """Check quality of a specific product"""
            try:
                import asyncio
                
                # Get product
                product = asyncio.run(self.project_store.get_product(product_id))
                if not product:
                    return {
                        "success": False,
                        "error": f"Product {product_id} not found"
                    }
                
                # Check quality
                quality_score = self.quality_checker.comprehensive_check(product)
                
                # Get improvement suggestions
                suggestions = self.quality_checker.suggest_improvements(product, quality_score)
                
                return {
                    "success": True,
                    "product_id": product_id,
                    "quality_score": {
                        "overall_score": quality_score.overall_score,
                        "completeness_score": quality_score.completeness_score,
                        "accuracy_score": quality_score.accuracy_score,
                        "missing_fields": quality_score.missing_fields,
                        "issues": quality_score.issues,
                        "recommendations": quality_score.recommendations,
                        "needs_review": quality_score.needs_review
                    },
                    "suggestions": suggestions,
                    "auto_approve": quality_score.overall_score >= 0.8
                }
                
            except Exception as e:
                logger.error(f"Failed to check product quality: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def batch_quality_check(project_id: str) -> Dict[str, Any]:
            """Check quality for all products in a project"""
            try:
                import asyncio
                
                # Get all products
                products = asyncio.run(self.project_store.get_products(project_id))
                if not products:
                    return {
                        "success": True,
                        "message": "No products found in project",
                        "summary": {}
                    }
                
                # Check quality for all products
                quality_scores = self.quality_checker.batch_check(products)
                
                # Get summary
                summary = self.quality_checker.get_quality_summary(quality_scores)
                
                # Auto-queue low quality products
                queued_count = asyncio.run(
                    self.verification_queue.auto_queue_low_quality(products, quality_scores)
                )
                
                # Create detailed results
                detailed_results = []
                for i, (product, quality) in enumerate(zip(products, quality_scores)):
                    detailed_results.append({
                        "product_id": product.id,
                        "type": product.type,
                        "description": product.description[:100] + "..." if len(product.description) > 100 else product.description,
                        "overall_score": quality.overall_score,
                        "needs_review": quality.needs_review,
                        "issues_count": len(quality.issues),
                        "missing_fields": quality.missing_fields
                    })
                
                return {
                    "success": True,
                    "project_id": project_id,
                    "summary": summary,
                    "detailed_results": detailed_results,
                    "auto_queued": queued_count,
                    "message": f"Quality checked {len(products)} products, queued {queued_count} for review"
                }
                
            except Exception as e:
                logger.error(f"Failed batch quality check: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def get_pending_reviews(project_id: str = None, limit: int = 50) -> Dict[str, Any]:
            """Get products pending manual review"""
            try:
                import asyncio
                
                pending_items = asyncio.run(
                    self.verification_queue.get_pending(project_id, limit)
                )
                
                return {
                    "success": True,
                    "pending_reviews": pending_items,
                    "count": len(pending_items),
                    "project_id": project_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get pending reviews: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "pending_reviews": []
                }
        
        def queue_for_review(product_id: str, reason: str, priority: str = "medium") -> Dict[str, Any]:
            """Manually queue a product for review"""
            try:
                import asyncio
                
                verification_id = asyncio.run(
                    self.verification_queue.add_for_review(product_id, reason, priority)
                )
                
                return {
                    "success": True,
                    "verification_id": verification_id,
                    "product_id": product_id,
                    "message": f"Product queued for {priority} priority review"
                }
                
            except Exception as e:
                logger.error(f"Failed to queue product for review: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def mark_product_reviewed(verification_id: str, reviewer: str, 
                                corrections: Dict[str, Any] = None) -> Dict[str, Any]:
            """Mark a product as reviewed with optional corrections"""
            try:
                import asyncio
                
                success = asyncio.run(
                    self.verification_queue.mark_reviewed(verification_id, reviewer, corrections or {})
                )
                
                return {
                    "success": success,
                    "verification_id": verification_id,
                    "message": "Product marked as reviewed" if success else "Failed to mark as reviewed"
                }
                
            except Exception as e:
                logger.error(f"Failed to mark product as reviewed: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def get_verification_stats(project_id: str = None) -> Dict[str, Any]:
            """Get verification queue statistics"""
            try:
                import asyncio
                
                stats = asyncio.run(self.verification_queue.get_verification_stats(project_id))
                
                return {
                    "success": True,
                    "stats": stats,
                    "project_id": project_id
                }
                
            except Exception as e:
                logger.error(f"Failed to get verification stats: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "stats": {}
                }
        
        def get_overdue_reviews(hours_threshold: int = 24) -> Dict[str, Any]:
            """Get reviews that are overdue"""
            try:
                import asyncio
                
                overdue_items = asyncio.run(
                    self.verification_queue.get_overdue_reviews(hours_threshold)
                )
                
                return {
                    "success": True,
                    "overdue_reviews": overdue_items,
                    "count": len(overdue_items),
                    "threshold_hours": hours_threshold
                }
                
            except Exception as e:
                logger.error(f"Failed to get overdue reviews: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "overdue_reviews": []
                }
        
        def bulk_approve_products(verification_ids: List[str], reviewer: str) -> Dict[str, Any]:
            """Bulk approve multiple verification requests"""
            try:
                import asyncio
                
                approved_count = asyncio.run(
                    self.verification_queue.bulk_approve(verification_ids, reviewer)
                )
                
                return {
                    "success": True,
                    "approved_count": approved_count,
                    "total_requested": len(verification_ids),
                    "message": f"Approved {approved_count} of {len(verification_ids)} products"
                }
                
            except Exception as e:
                logger.error(f"Failed bulk approval: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "approved_count": 0
                }
        
        def validate_product_completeness(product_id: str) -> Dict[str, Any]:
            """Validate product data completeness"""
            try:
                import asyncio
                
                product = asyncio.run(self.project_store.get_product(product_id))
                if not product:
                    return {
                        "success": False,
                        "error": f"Product {product_id} not found"
                    }
                
                completeness = self.quality_checker.check_completeness(product)
                
                return {
                    "success": True,
                    "product_id": product_id,
                    "completeness_score": completeness.completeness_score,
                    "missing_fields": completeness.missing_fields,
                    "issues": completeness.issues,
                    "recommendations": completeness.recommendations,
                    "is_complete": len(completeness.missing_fields) == 0
                }
                
            except Exception as e:
                logger.error(f"Failed to validate completeness: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def validate_product_accuracy(product_id: str) -> Dict[str, Any]:
            """Validate product data accuracy"""
            try:
                import asyncio
                
                product = asyncio.run(self.project_store.get_product(product_id))
                if not product:
                    return {
                        "success": False,
                        "error": f"Product {product_id} not found"
                    }
                
                accuracy = self.quality_checker.check_accuracy(product)
                
                return {
                    "success": True,
                    "product_id": product_id,
                    "accuracy_score": accuracy.accuracy_score,
                    "issues": accuracy.issues,
                    "recommendations": accuracy.recommendations,
                    "is_accurate": accuracy.accuracy_score >= 0.8
                }
                
            except Exception as e:
                logger.error(f"Failed to validate accuracy: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Register tools
        tools = [
            Tool(
                name="check_product_quality",
                description="Check quality of a specific product",
                parameters=[
                    ToolParameter(name="product_id", type="str", description="Product identifier", required=True)
                ],
                function=check_product_quality
            ),
            Tool(
                name="batch_quality_check",
                description="Check quality for all products in a project",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=True)
                ],
                function=batch_quality_check
            ),
            Tool(
                name="get_pending_reviews",
                description="Get products pending manual review",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=False),
                    ToolParameter(name="limit", type="int", description="Maximum number of items", required=False)
                ],
                function=get_pending_reviews
            ),
            Tool(
                name="queue_for_review",
                description="Manually queue a product for review",
                parameters=[
                    ToolParameter(name="product_id", type="str", description="Product identifier", required=True),
                    ToolParameter(name="reason", type="str", description="Reason for review", required=True),
                    ToolParameter(name="priority", type="str", description="Review priority (critical, high, medium, low)", required=False)
                ],
                function=queue_for_review
            ),
            Tool(
                name="mark_product_reviewed",
                description="Mark a product as reviewed with optional corrections",
                parameters=[
                    ToolParameter(name="verification_id", type="str", description="Verification request ID", required=True),
                    ToolParameter(name="reviewer", type="str", description="Reviewer name", required=True),
                    ToolParameter(name="corrections", type="dict", description="Optional corrections to apply", required=False)
                ],
                function=mark_product_reviewed
            ),
            Tool(
                name="get_verification_stats",
                description="Get verification queue statistics",
                parameters=[
                    ToolParameter(name="project_id", type="str", description="Project identifier", required=False)
                ],
                function=get_verification_stats
            ),
            Tool(
                name="get_overdue_reviews",
                description="Get reviews that are overdue",
                parameters=[
                    ToolParameter(name="hours_threshold", type="int", description="Hours threshold for overdue", required=False)
                ],
                function=get_overdue_reviews
            ),
            Tool(
                name="bulk_approve_products",
                description="Bulk approve multiple verification requests",
                parameters=[
                    ToolParameter(name="verification_ids", type="list", description="List of verification IDs", required=True),
                    ToolParameter(name="reviewer", type="str", description="Reviewer name", required=True)
                ],
                function=bulk_approve_products
            ),
            Tool(
                name="validate_product_completeness",
                description="Validate product data completeness",
                parameters=[
                    ToolParameter(name="product_id", type="str", description="Product identifier", required=True)
                ],
                function=validate_product_completeness
            ),
            Tool(
                name="validate_product_accuracy",
                description="Validate product data accuracy",
                parameters=[
                    ToolParameter(name="product_id", type="str", description="Product identifier", required=True)
                ],
                function=validate_product_accuracy
            )
        ]
        
        for tool in tools:
            self.register_tool(tool)
    
    async def handle_intent(self, intent: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Handle quality-related intents"""
        try:
            action = intent.get("action")
            entities = intent.get("entities", {})
            
            if action == IntentAction.VERIFY_PRODUCT.value:
                product_id = entities.get("product_id")
                project_id = entities.get("project_id")
                
                if product_id:
                    return self.tools["check_product_quality"].call(product_id=product_id)
                elif project_id:
                    return self.tools["batch_quality_check"].call(project_id=project_id)
                else:
                    return {
                        "success": False,
                        "error": "No product or project specified for verification"
                    }
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported action: {action}",
                    "message": "I don't know how to handle that quality request"
                }
                
        except Exception as e:
            logger.error(f"Failed to handle quality intent: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "An error occurred processing your quality request"
            }
    
    async def auto_quality_workflow(self, project_id: str) -> Dict[str, Any]:
        """Run automated quality workflow for a project"""
        try:
            # Run batch quality check
            quality_result = self.tools["batch_quality_check"].call(project_id=project_id)
            
            if not quality_result["success"]:
                return quality_result
            
            # Get verification stats
            stats_result = self.tools["get_verification_stats"].call(project_id=project_id)
            
            return {
                "success": True,
                "project_id": project_id,
                "quality_summary": quality_result.get("summary", {}),
                "auto_queued": quality_result.get("auto_queued", 0),
                "verification_stats": stats_result.get("stats", {}),
                "message": f"Automated quality workflow completed for project {project_id}"
            }
            
        except Exception as e:
            logger.error(f"Failed auto quality workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Automated quality workflow failed"
            }
    
    async def close(self):
        """Close agent and cleanup resources"""
        try:
            await self.project_store.close()
            logger.info("QualityAgent closed")
        except Exception as e:
            logger.error(f"Error closing QualityAgent: {e}")