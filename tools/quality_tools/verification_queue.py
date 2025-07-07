"""
VerificationQueue - Manual verification workflow management
Priority queue with PostgreSQL and integration with verification_ui.py
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.orm import selectinload

# Import database components
from tools.data_management.project_store import ProjectStore
from models.database import VerificationRequestDB, ProductDB, ProjectDB
from models.schemas import VerificationRequest, Product, QualityScore
from config.settings import get_settings

logger = logging.getLogger(__name__)


class VerificationQueue:
    """Manage manual verification workflow with priority queuing"""
    
    def __init__(self, project_store: Optional[ProjectStore] = None):
        """Initialize verification queue"""
        self.settings = get_settings()
        self.project_store = project_store or ProjectStore()
        
        # Priority mappings
        self.priority_mapping = {
            "critical": 10,
            "high": 7,
            "medium": 5,
            "low": 3,
            "deferred": 1
        }
    
    async def add_for_review(self, product_id: str, reason: str, priority: str = "medium") -> str:
        """Add product to verification queue"""
        try:
            # Get product to extract project_id
            product = await self.project_store.get_product(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            # Create verification request
            verification_request = VerificationRequest(
                product_id=product_id,
                project_id=product.project_id,
                reason=reason,
                priority=self.priority_mapping.get(priority, 5)
            )
            
            # Save to database
            verification_db = VerificationRequestDB(
                id=verification_request.id,
                product_id=verification_request.product_id,
                project_id=verification_request.project_id,
                reason=verification_request.reason,
                priority=verification_request.priority,
                status="pending",
                created_at=verification_request.created_at
            )
            
            async with self.project_store.db_manager.async_session() as session:
                session.add(verification_db)
                await session.commit()
            
            logger.info(f"Added product {product_id} to verification queue with priority {priority}")
            return verification_request.id
            
        except Exception as e:
            logger.error(f"Failed to add product to verification queue: {e}")
            raise
    
    async def get_pending(self, project_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending verification requests with product details"""
        try:
            async with self.project_store.db_manager.async_session() as session:
                # Build query
                stmt = (
                    select(VerificationRequestDB, ProductDB, ProjectDB)
                    .join(ProductDB, VerificationRequestDB.product_id == ProductDB.id)
                    .join(ProjectDB, VerificationRequestDB.project_id == ProjectDB.id)
                    .where(VerificationRequestDB.status == "pending")
                )
                
                if project_id:
                    stmt = stmt.where(VerificationRequestDB.project_id == project_id)
                
                # Order by priority (descending) then created_at (ascending)
                stmt = stmt.order_by(
                    VerificationRequestDB.priority.desc(),
                    VerificationRequestDB.created_at.asc()
                ).limit(limit)
                
                result = await session.execute(stmt)
                rows = result.all()
                
                # Format response
                pending_items = []
                for verification_db, product_db, project_db in rows:
                    pending_items.append({
                        "verification_id": verification_db.id,
                        "product_id": verification_db.product_id,
                        "project_id": verification_db.project_id,
                        "project_name": project_db.name,
                        "reason": verification_db.reason,
                        "priority": verification_db.priority,
                        "priority_name": self._get_priority_name(verification_db.priority),
                        "created_at": verification_db.created_at,
                        "product": {
                            "url": product_db.url,
                            "type": product_db.type,
                            "description": product_db.description,
                            "model_no": product_db.model_no,
                            "image_url": product_db.image_url,
                            "confidence_score": product_db.confidence_score,
                            "verified": product_db.verified
                        }
                    })
                
                logger.debug(f"Retrieved {len(pending_items)} pending verification requests")
                return pending_items
                
        except Exception as e:
            logger.error(f"Failed to get pending verification requests: {e}")
            return []
    
    async def mark_reviewed(self, verification_id: str, reviewer: str, corrections: Dict[str, Any] = None) -> bool:
        """Mark verification request as reviewed"""
        try:
            corrections = corrections or {}
            
            async with self.project_store.db_manager.async_session() as session:
                # Update verification request
                stmt = (
                    update(VerificationRequestDB)
                    .where(VerificationRequestDB.id == verification_id)
                    .values(
                        status="completed",
                        reviewed_at=datetime.now(),
                        reviewer=reviewer,
                        corrections=corrections
                    )
                )
                result = await session.execute(stmt)
                
                if result.rowcount == 0:
                    logger.warning(f"Verification request {verification_id} not found")
                    return False
                
                # If corrections were provided, apply them to the product
                if corrections:
                    # Get verification request to find product_id
                    verification_stmt = select(VerificationRequestDB).where(
                        VerificationRequestDB.id == verification_id
                    )
                    verification_result = await session.execute(verification_stmt)
                    verification_req = verification_result.scalar_one_or_none()
                    
                    if verification_req:
                        # Apply corrections to product
                        product_updates = {k: v for k, v in corrections.items() if k != 'verified'}
                        product_updates['verified'] = True
                        product_updates['updated_at'] = datetime.now()
                        
                        product_stmt = (
                            update(ProductDB)
                            .where(ProductDB.id == verification_req.product_id)
                            .values(**product_updates)
                        )
                        await session.execute(product_stmt)
                
                await session.commit()
                
                logger.info(f"Marked verification {verification_id} as reviewed by {reviewer}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to mark verification as reviewed: {e}")
            return False
    
    async def get_verification_stats(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get verification queue statistics"""
        try:
            async with self.project_store.db_manager.async_session() as session:
                base_query = select(VerificationRequestDB)
                if project_id:
                    base_query = base_query.where(VerificationRequestDB.project_id == project_id)
                
                # Count by status
                pending_count = await session.execute(
                    base_query.where(VerificationRequestDB.status == "pending")
                )
                pending_count = len(pending_count.scalars().all())
                
                completed_count = await session.execute(
                    base_query.where(VerificationRequestDB.status == "completed")
                )
                completed_count = len(completed_count.scalars().all())
                
                # Count by priority (pending only)
                priority_counts = {}
                for priority_name, priority_value in self.priority_mapping.items():
                    count_result = await session.execute(
                        base_query.where(
                            and_(
                                VerificationRequestDB.status == "pending",
                                VerificationRequestDB.priority == priority_value
                            )
                        )
                    )
                    priority_counts[priority_name] = len(count_result.scalars().all())
                
                # Average review time for completed items
                completed_items = await session.execute(
                    base_query.where(
                        and_(
                            VerificationRequestDB.status == "completed",
                            VerificationRequestDB.reviewed_at.isnot(None)
                        )
                    )
                )
                completed_items = completed_items.scalars().all()
                
                avg_review_time = None
                if completed_items:
                    review_times = []
                    for item in completed_items:
                        if item.reviewed_at and item.created_at:
                            review_time = (item.reviewed_at - item.created_at).total_seconds() / 3600  # hours
                            review_times.append(review_time)
                    
                    if review_times:
                        avg_review_time = sum(review_times) / len(review_times)
                
                return {
                    "pending_count": pending_count,
                    "completed_count": completed_count,
                    "total_count": pending_count + completed_count,
                    "completion_rate": completed_count / (pending_count + completed_count) if (pending_count + completed_count) > 0 else 0,
                    "priority_breakdown": priority_counts,
                    "average_review_time_hours": avg_review_time
                }
                
        except Exception as e:
            logger.error(f"Failed to get verification stats: {e}")
            return {"error": str(e)}
    
    async def auto_queue_low_quality(self, products: List[Product], quality_scores: List[QualityScore]) -> int:
        """Automatically queue products with low quality scores"""
        try:
            queued_count = 0
            
            for product, quality in zip(products, quality_scores):
                # Check if should be queued
                should_queue = False
                reason_parts = []
                priority = "medium"
                
                if quality.overall_score < self.settings.quality_manual_review_threshold:
                    should_queue = True
                    reason_parts.append(f"Low quality score: {quality.overall_score:.2f}")
                    priority = "high" if quality.overall_score < 0.4 else "medium"
                
                if quality.missing_fields:
                    should_queue = True
                    reason_parts.append(f"Missing fields: {', '.join(quality.missing_fields)}")
                
                if any("critical" in issue.lower() or "error" in issue.lower() for issue in quality.issues):
                    should_queue = True
                    priority = "critical"
                    reason_parts.append("Critical issues detected")
                
                # Queue for review if needed
                if should_queue:
                    reason = "; ".join(reason_parts)
                    await self.add_for_review(product.id, reason, priority)
                    queued_count += 1
            
            logger.info(f"Auto-queued {queued_count} products for manual review")
            return queued_count
            
        except Exception as e:
            logger.error(f"Failed to auto-queue low quality products: {e}")
            return 0
    
    async def get_next_for_review(self, reviewer: str, project_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get next highest priority item for review"""
        try:
            pending_items = await self.get_pending(project_id, limit=1)
            
            if not pending_items:
                return None
            
            # Mark as in progress
            item = pending_items[0]
            async with self.project_store.db_manager.async_session() as session:
                stmt = (
                    update(VerificationRequestDB)
                    .where(VerificationRequestDB.id == item["verification_id"])
                    .values(
                        status="in_progress",
                        reviewer=reviewer
                    )
                )
                await session.execute(stmt)
                await session.commit()
            
            item["status"] = "in_progress"
            item["reviewer"] = reviewer
            
            logger.info(f"Assigned verification {item['verification_id']} to {reviewer}")
            return item
            
        except Exception as e:
            logger.error(f"Failed to get next item for review: {e}")
            return None
    
    async def bulk_approve(self, verification_ids: List[str], reviewer: str) -> int:
        """Bulk approve multiple verification requests"""
        try:
            approved_count = 0
            
            for verification_id in verification_ids:
                success = await self.mark_reviewed(verification_id, reviewer, {"verified": True})
                if success:
                    approved_count += 1
            
            logger.info(f"Bulk approved {approved_count} verification requests")
            return approved_count
            
        except Exception as e:
            logger.error(f"Failed bulk approval: {e}")
            return 0
    
    async def get_overdue_reviews(self, hours_threshold: int = 24) -> List[Dict[str, Any]]:
        """Get verification requests that are overdue"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_threshold)
            
            async with self.project_store.db_manager.async_session() as session:
                stmt = (
                    select(VerificationRequestDB, ProductDB, ProjectDB)
                    .join(ProductDB, VerificationRequestDB.product_id == ProductDB.id)
                    .join(ProjectDB, VerificationRequestDB.project_id == ProjectDB.id)
                    .where(
                        and_(
                            or_(
                                VerificationRequestDB.status == "pending",
                                VerificationRequestDB.status == "in_progress"
                            ),
                            VerificationRequestDB.created_at < cutoff_time
                        )
                    )
                    .order_by(VerificationRequestDB.created_at.asc())
                )
                
                result = await session.execute(stmt)
                rows = result.all()
                
                overdue_items = []
                for verification_db, product_db, project_db in rows:
                    hours_overdue = (datetime.now() - verification_db.created_at).total_seconds() / 3600
                    
                    overdue_items.append({
                        "verification_id": verification_db.id,
                        "product_id": verification_db.product_id,
                        "project_name": project_db.name,
                        "reason": verification_db.reason,
                        "priority": verification_db.priority,
                        "hours_overdue": hours_overdue,
                        "status": verification_db.status,
                        "reviewer": verification_db.reviewer,
                        "product_type": product_db.type,
                        "product_description": product_db.description
                    })
                
                logger.debug(f"Found {len(overdue_items)} overdue verification requests")
                return overdue_items
                
        except Exception as e:
            logger.error(f"Failed to get overdue reviews: {e}")
            return []
    
    def _get_priority_name(self, priority_value: int) -> str:
        """Get priority name from value"""
        for name, value in self.priority_mapping.items():
            if value == priority_value:
                return name
        return "unknown"