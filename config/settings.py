"""
Configuration settings for the Specbook Agent System
Uses Pydantic BaseSettings for validation and environment variable loading
"""

import os
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Database configuration
    database_url: str = Field(
        default="postgresql+asyncpg://user:pass@localhost/specbook",
        description="PostgreSQL connection URL"
    )
    database_pool_size: int = Field(default=10, ge=1, le=100)
    database_max_overflow: int = Field(default=20, ge=0, le=100)
    
    # Redis configuration
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL"
    )
    redis_max_connections: int = Field(default=50, ge=10, le=500)
    redis_decode_responses: bool = Field(default=True)
    
    # API Keys (loaded from environment)
    openai_api_key: str = Field(..., description="OpenAI API key")
    firecrawl_api_key: Optional[str] = Field(None, description="Firecrawl API key")
    
    # NLP Configuration
    spacy_model: str = Field(default="en_core_web_sm", description="spaCy model to use")
    intent_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Scraping configuration
    scrape_timeout: int = Field(default=30, ge=5, le=120, description="Scraping timeout in seconds")
    scrape_rate_limit: int = Field(default=10, description="Max requests per minute")
    scrape_max_retries: int = Field(default=3, ge=1, le=10)
    
    # LLM Configuration
    llm_model: str = Field(default="gpt-4-turbo-preview", description="OpenAI model to use")
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2000, ge=100, le=4000)
    
    # Quality thresholds
    quality_auto_approve_threshold: float = Field(
        default=0.8, 
        ge=0.0, 
        le=1.0,
        description="Confidence threshold for auto-approval"
    )
    quality_manual_review_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Below this threshold, always require manual review"
    )
    
    # Export configuration
    export_csv_encoding: str = Field(default="utf-8")
    export_pdf_font: str = Field(default="Helvetica")
    export_revit_template: str = Field(default="default")
    
    # Application paths
    log_dir: Path = Field(default=Path("logs"))
    data_dir: Path = Field(default=Path("data"))
    temp_dir: Path = Field(default=Path("temp"))
    
    # Feature flags
    enable_monitoring: bool = Field(default=True)
    enable_caching: bool = Field(default=True)
    enable_async_processing: bool = Field(default=True)
    debug_mode: bool = Field(default=False)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @validator("database_url")
    def validate_database_url(cls, v):
        """Ensure database URL is properly formatted"""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must be a PostgreSQL connection string")
        return v
    
    @validator("redis_url")
    def validate_redis_url(cls, v):
        """Ensure Redis URL is properly formatted"""
        if not v.startswith("redis://"):
            raise ValueError("Redis URL must start with redis://")
        return v
    
    @validator("log_dir", "data_dir", "temp_dir")
    def create_directories(cls, v):
        """Create directories if they don't exist"""
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    def get_database_url_sync(self) -> str:
        """Get synchronous database URL for migrations"""
        return self.database_url.replace("+asyncpg", "")
    
    def get_redis_connection_params(self) -> dict:
        """Get Redis connection parameters"""
        return {
            "url": self.redis_url,
            "max_connections": self.redis_max_connections,
            "decode_responses": self.redis_decode_responses,
        }


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get cached settings instance"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings