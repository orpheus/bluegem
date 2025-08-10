"""
SQLAlchemy database models
Uses async patterns with proper session handling
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, JSON, Text,
    ForeignKey, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import relationship, selectinload
from sqlalchemy.sql import func

# Create base class for models
Base = declarative_base()


class ProjectDB(Base):
    """Project database model"""
    __tablename__ = "projects"
    
    # Primary key
    id = Column(String, primary_key=True)
    
    # Core fields
    name = Column(String(200), nullable=False)
    status = Column(String(20), default="draft", nullable=False)
    project_metadata = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    archived_at = Column(DateTime, nullable=True)
    
    # Relationships
    products = relationship("ProductDB", back_populates="project", cascade="all, delete-orphan")
    verification_requests = relationship("VerificationRequestDB", back_populates="project")
    
    # Indexes
    __table_args__ = (
        Index("idx_project_status", "status"),
        Index("idx_project_created", "created_at"),
        CheckConstraint("status IN ('draft', 'active', 'review', 'completed', 'archived')", name="check_project_status"),
    )


class ProductDB(Base):
    """Product database model"""
    __tablename__ = "products"
    
    # Primary key
    id = Column(String, primary_key=True)
    
    # Foreign key
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Core fields
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    model_no = Column(String(200), nullable=True)
    qty = Column(Integer, default=1, nullable=False)
    key = Column(String(100), nullable=True)  # Revit key
    
    # Quality and verification
    confidence_score = Column(Float, default=0.0, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    extraction_metadata = Column(JSON, default={})
    last_checked = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    project = relationship("ProjectDB", back_populates="products")
    verification_requests = relationship("VerificationRequestDB", back_populates="product")
    change_history = relationship("ChangeHistoryDB", back_populates="product", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_product_project", "project_id"),
        Index("idx_product_type", "type"),
        Index("idx_product_verified", "verified"),
        Index("idx_product_confidence", "confidence_score"),
        Index("idx_product_url", "url"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="check_confidence_range"),
        CheckConstraint("qty > 0", name="check_qty_positive"),
    )


class VerificationRequestDB(Base):
    """Verification request database model"""
    __tablename__ = "verification_requests"
    
    # Primary key
    id = Column(String, primary_key=True)
    
    # Foreign keys
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Request details
    reason = Column(Text, nullable=False)
    priority = Column(Integer, default=5, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    
    # Review details
    reviewed_at = Column(DateTime, nullable=True)
    reviewer = Column(String(100), nullable=True)
    corrections = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    product = relationship("ProductDB", back_populates="verification_requests")
    project = relationship("ProjectDB", back_populates="verification_requests")
    
    # Indexes
    __table_args__ = (
        Index("idx_verification_status", "status"),
        Index("idx_verification_priority", "priority"),
        Index("idx_verification_created", "created_at"),
        CheckConstraint("priority >= 1 AND priority <= 10", name="check_priority_range"),
        CheckConstraint("status IN ('pending', 'in_progress', 'completed', 'cancelled')", name="check_verification_status"),
    )


class ChangeHistoryDB(Base):
    """Change history tracking for products"""
    __tablename__ = "change_history"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    
    # Change details
    field = Column(String(100), nullable=False)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    change_type = Column(String(20), nullable=False)  # added, removed, modified
    
    # Timestamp
    detected_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    product = relationship("ProductDB", back_populates="change_history")
    
    # Indexes
    __table_args__ = (
        Index("idx_change_product", "product_id"),
        Index("idx_change_detected", "detected_at"),
        CheckConstraint("change_type IN ('added', 'removed', 'modified')", name="check_change_type"),
    )


class TaskQueueDB(Base):
    """Task queue for async processing"""
    __tablename__ = "task_queue"
    
    # Primary key
    id = Column(String, primary_key=True)
    
    # Task details
    task_type = Column(String(50), nullable=False)
    task_data = Column(JSON, nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    # Timing
    created_at = Column(DateTime, default=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_task_status", "status"),
        Index("idx_task_type", "task_type"),
        Index("idx_task_created", "created_at"),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed', 'cancelled')", name="check_task_status"),
    )


# Database session management
class DatabaseManager:
    """Manager for database connections and sessions"""
    
    def __init__(self, database_url: str):
        """Initialize database manager"""
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def create_tables(self):
        """Create all tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self):
        """Drop all tables (use with caution)"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    async def get_session(self) -> AsyncSession:
        """Get a new database session"""
        async with self.async_session() as session:
            yield session
    
    async def close(self):
        """Close database connections"""
        await self.engine.dispose()