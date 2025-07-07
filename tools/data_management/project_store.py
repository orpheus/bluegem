"""
ProjectStore - PostgreSQL-based project and product storage
CRUD operations using SQLAlchemy async with proper session handling
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

# Import models and schemas
from models.database import ProjectDB, ProductDB, VerificationRequestDB, DatabaseManager
from models.schemas import Project, Product, VerificationRequest, ProjectStatus
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ProjectStore:
    """PostgreSQL-based storage for projects and products"""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize project store with database connection"""
        settings = get_settings()
        self.db_url = database_url or settings.database_url
        self.db_manager = DatabaseManager(self.db_url)
    
    async def initialize(self):
        """Initialize database tables"""
        try:
            await self.db_manager.create_tables()
            logger.info("Database tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    # Project CRUD operations
    async def create_project(self, name: str, metadata: Dict[str, Any] = None) -> str:
        """Create a new project"""
        try:
            project = Project(
                name=name,
                metadata=metadata or {},
                status=ProjectStatus.DRAFT
            )
            
            project_db = ProjectDB(
                id=project.id,
                name=project.name,
                status=project.status.value,
                metadata=project.metadata,
                created_at=project.created_at,
                updated_at=project.updated_at
            )
            
            async with self.db_manager.async_session() as session:
                session.add(project_db)
                await session.commit()
                logger.info(f"Created project: {name} with ID: {project.id}")
                return project.id
                
        except Exception as e:
            logger.error(f"Failed to create project {name}: {e}")
            raise
    
    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID"""
        try:
            async with self.db_manager.async_session() as session:
                stmt = select(ProjectDB).where(ProjectDB.id == project_id)
                result = await session.execute(stmt)
                project_db = result.scalar_one_or_none()
                
                if not project_db:
                    return None
                
                return Project(
                    id=project_db.id,
                    name=project_db.name,
                    status=ProjectStatus(project_db.status),
                    metadata=project_db.metadata,
                    created_at=project_db.created_at,
                    updated_at=project_db.updated_at,
                    archived_at=project_db.archived_at
                )
                
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            raise
    
    async def list_projects(self, status: Optional[ProjectStatus] = None) -> List[Project]:
        """List projects, optionally filtered by status"""
        try:
            async with self.db_manager.async_session() as session:
                stmt = select(ProjectDB)
                if status:
                    stmt = stmt.where(ProjectDB.status == status.value)
                stmt = stmt.order_by(ProjectDB.updated_at.desc())
                
                result = await session.execute(stmt)
                projects_db = result.scalars().all()
                
                return [
                    Project(
                        id=p.id,
                        name=p.name,
                        status=ProjectStatus(p.status),
                        metadata=p.metadata,
                        created_at=p.created_at,
                        updated_at=p.updated_at,
                        archived_at=p.archived_at
                    )
                    for p in projects_db
                ]
                
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            raise
    
    async def update_project(self, project_id: str, updates: Dict[str, Any]) -> bool:
        """Update project fields"""
        try:
            async with self.db_manager.async_session() as session:
                stmt = (
                    update(ProjectDB)
                    .where(ProjectDB.id == project_id)
                    .values(**updates, updated_at=datetime.now())
                )
                result = await session.execute(stmt)
                await session.commit()
                
                success = result.rowcount > 0
                if success:
                    logger.info(f"Updated project {project_id}")
                return success
                
        except Exception as e:
            logger.error(f"Failed to update project {project_id}: {e}")
            raise
    
    async def delete_project(self, project_id: str) -> bool:
        """Delete project and all associated products"""
        try:
            async with self.db_manager.async_session() as session:
                stmt = delete(ProjectDB).where(ProjectDB.id == project_id)
                result = await session.execute(stmt)
                await session.commit()
                
                success = result.rowcount > 0
                if success:
                    logger.info(f"Deleted project {project_id}")
                return success
                
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            raise
    
    # Product CRUD operations
    async def add_product(self, project_id: str, product: Product) -> str:
        """Add product to project"""
        try:
            product.project_id = project_id
            
            product_db = ProductDB(
                id=product.id,
                project_id=product.project_id,
                url=str(product.url),
                image_url=str(product.image_url) if product.image_url else None,
                type=product.type,
                description=product.description,
                model_no=product.model_no,
                qty=product.qty,
                key=product.key,
                confidence_score=product.confidence_score,
                verified=product.verified,
                extraction_metadata=product.extraction_metadata,
                last_checked=product.last_checked,
                created_at=product.created_at,
                updated_at=product.updated_at
            )
            
            async with self.db_manager.async_session() as session:
                session.add(product_db)
                await session.commit()
                logger.info(f"Added product {product.id} to project {project_id}")
                return product.id
                
        except Exception as e:
            logger.error(f"Failed to add product to project {project_id}: {e}")
            raise
    
    async def get_product(self, product_id: str) -> Optional[Product]:
        """Get product by ID"""
        try:
            async with self.db_manager.async_session() as session:
                stmt = select(ProductDB).where(ProductDB.id == product_id)
                result = await session.execute(stmt)
                product_db = result.scalar_one_or_none()
                
                if not product_db:
                    return None
                
                return Product(
                    id=product_db.id,
                    project_id=product_db.project_id,
                    url=product_db.url,
                    image_url=product_db.image_url,
                    type=product_db.type,
                    description=product_db.description,
                    model_no=product_db.model_no,
                    qty=product_db.qty,
                    key=product_db.key,
                    confidence_score=product_db.confidence_score,
                    verified=product_db.verified,
                    extraction_metadata=product_db.extraction_metadata,
                    last_checked=product_db.last_checked,
                    created_at=product_db.created_at,
                    updated_at=product_db.updated_at
                )
                
        except Exception as e:
            logger.error(f"Failed to get product {product_id}: {e}")
            raise
    
    async def get_products(self, project_id: str, filters: Dict[str, Any] = None) -> List[Product]:
        """Get products for a project with optional filters"""
        try:
            async with self.db_manager.async_session() as session:
                stmt = select(ProductDB).where(ProductDB.project_id == project_id)
                
                # Apply filters
                if filters:
                    if 'type' in filters:
                        stmt = stmt.where(ProductDB.type == filters['type'])
                    if 'verified' in filters:
                        stmt = stmt.where(ProductDB.verified == filters['verified'])
                    if 'min_confidence' in filters:
                        stmt = stmt.where(ProductDB.confidence_score >= filters['min_confidence'])
                
                stmt = stmt.order_by(ProductDB.created_at.desc())
                result = await session.execute(stmt)
                products_db = result.scalars().all()
                
                return [
                    Product(
                        id=p.id,
                        project_id=p.project_id,
                        url=p.url,
                        image_url=p.image_url,
                        type=p.type,
                        description=p.description,
                        model_no=p.model_no,
                        qty=p.qty,
                        key=p.key,
                        confidence_score=p.confidence_score,
                        verified=p.verified,
                        extraction_metadata=p.extraction_metadata,
                        last_checked=p.last_checked,
                        created_at=p.created_at,
                        updated_at=p.updated_at
                    )
                    for p in products_db
                ]
                
        except Exception as e:
            logger.error(f"Failed to get products for project {project_id}: {e}")
            raise
    
    async def update_product(self, product_id: str, updates: Dict[str, Any]) -> bool:
        """Update product fields"""
        try:
            async with self.db_manager.async_session() as session:
                stmt = (
                    update(ProductDB)
                    .where(ProductDB.id == product_id)
                    .values(**updates, updated_at=datetime.now())
                )
                result = await session.execute(stmt)
                await session.commit()
                
                success = result.rowcount > 0
                if success:
                    logger.info(f"Updated product {product_id}")
                return success
                
        except Exception as e:
            logger.error(f"Failed to update product {product_id}: {e}")
            raise
    
    async def search_products(self, query: str, project_id: Optional[str] = None) -> List[Product]:
        """Search products by description, type, or model number"""
        try:
            async with self.db_manager.async_session() as session:
                search_term = f"%{query}%"
                stmt = select(ProductDB).where(
                    or_(
                        ProductDB.description.ilike(search_term),
                        ProductDB.type.ilike(search_term),
                        ProductDB.model_no.ilike(search_term)
                    )
                )
                
                if project_id:
                    stmt = stmt.where(ProductDB.project_id == project_id)
                
                result = await session.execute(stmt)
                products_db = result.scalars().all()
                
                return [
                    Product(
                        id=p.id,
                        project_id=p.project_id,
                        url=p.url,
                        image_url=p.image_url,
                        type=p.type,
                        description=p.description,
                        model_no=p.model_no,
                        qty=p.qty,
                        key=p.key,
                        confidence_score=p.confidence_score,
                        verified=p.verified,
                        extraction_metadata=p.extraction_metadata,
                        last_checked=p.last_checked,
                        created_at=p.created_at,
                        updated_at=p.updated_at
                    )
                    for p in products_db
                ]
                
        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            raise
    
    async def get_project_stats(self, project_id: str) -> Dict[str, Any]:
        """Get project statistics"""
        try:
            async with self.db_manager.async_session() as session:
                # Count products by status
                stmt = select(ProductDB).where(ProductDB.project_id == project_id)
                result = await session.execute(stmt)
                products = result.scalars().all()
                
                total_products = len(products)
                verified_products = sum(1 for p in products if p.verified)
                high_confidence = sum(1 for p in products if p.confidence_score >= 0.8)
                low_confidence = sum(1 for p in products if p.confidence_score < 0.6)
                
                return {
                    "total_products": total_products,
                    "verified_products": verified_products,
                    "unverified_products": total_products - verified_products,
                    "high_confidence": high_confidence,
                    "low_confidence": low_confidence,
                    "verification_rate": verified_products / total_products if total_products > 0 else 0
                }
                
        except Exception as e:
            logger.error(f"Failed to get project stats {project_id}: {e}")
            raise
    
    async def close(self):
        """Close database connections"""
        await self.db_manager.close()