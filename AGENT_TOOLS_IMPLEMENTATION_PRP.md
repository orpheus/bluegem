# PRP: Agent Tools Implementation for Natural Language Specbook Automation

## Goal
Implement a natural language chat interface that allows architects to manage product specifications through conversational commands, building upon the existing specbook automation pipeline. The system should handle three core use cases:
- **Batch product fetch**: "Process these 50 product URLs for the Johnson project"
- **Update single product**: "Update the kitchen faucet specs for Desert Modern"
- **Generate specbook**: "Generate the spec book for client review tomorrow"

## Why
- **Business Value**: Reduce 20+ hour manual process to <2 hours (90% time savings)
- **User Impact**: Architects can use natural language instead of technical commands
- **Integration**: Leverages existing scraping/extraction tools while adding conversational layer
- **Problems Solved**: Manual data entry, complex command syntax, project management overhead

## What
A CLI chat interface that understands architect requests in natural language and orchestrates existing tools to fulfill those requests through specialized agents.

### Success Criteria
- [ ] Natural language commands successfully parsed and executed
- [ ] Batch processing of 50+ products in <30 minutes
- [ ] Single product updates in <2 minutes
- [ ] Specbook generation with Revit-compatible CSV export
- [ ] 80%+ confidence auto-approval for quality extractions
- [ ] Project isolation and multi-project support

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- file: /Users/roark/code/github/orpheus/theranchmine/phase1-specbook/AGENT_TOOL_SPECIFICATION.md
  why: Complete specification of all tools and agents to implement

- file: /Users/roark/code/github/orpheus/theranchmine/phase1-specbook/agent/therma_pydantic.py
  why: Existing agent framework to extend - patterns for Agent, Tool, Message classes

- file: /Users/roark/code/github/orpheus/theranchmine/phase1-specbook/agent/verification_framework.py
  why: Working example of multi-agent coordination pattern

- file: /Users/roark/code/github/orpheus/theranchmine/phase1-specbook/tools/stealth_scraper.py
  why: Existing scraper to wrap with ProductFetcher

- file: /Users/roark/code/github/orpheus/theranchmine/phase1-specbook/tools/llm_invocator.py
  why: LLM extraction to wrap with ProductExtractor

- file: /Users/roark/code/github/orpheus/theranchmine/phase1-specbook/tools/eval_product_extraction.py
  why: Quality evaluation to wrap with QualityChecker

- file: /Users/roark/code/github/orpheus/theranchmine/phase1-specbook/verification_ui.py
  why: Flask patterns and verification queue interface

- url: https://docs.sqlalchemy.org/en/20/orm/quickstart.html
  why: ORM patterns for ProjectStore implementation

- url: https://redis.io/docs/connect/clients/python/
  why: Redis client for ProductCache implementation

- url: https://spacy.io/usage/linguistic-features#named-entities
  why: NLP for IntentParser implementation

- url: https://typer.tiangolo.com/
  why: CLI framework for chat interface

- url: https://rich.readthedocs.io/en/stable/
  why: Rich terminal UI for progress tracking

- file: /Users/roark/code/github/orpheus/theranchmine/phase1-specbook/CLAUDE.md
  why: Project-specific conventions and commands to follow
```

### Current Codebase Tree
```bash
phase1-specbook/
├── agent/
│   ├── therma_pydantic.py       # Base agent framework
│   └── verification_framework.py # Multi-agent example
├── tools/
│   ├── stealth_scraper.py       # Web scraper
│   ├── html_processor.py        # HTML cleaning
│   ├── llm_invocator.py         # LLM extraction
│   ├── prompt_templator.py      # Prompt generation
│   └── eval_product_extraction.py # Quality evaluation
├── templates/                    # Flask templates
├── verification_ui.py           # Manual verification UI
├── requirements.txt             # Dependencies
└── CLAUDE.md                    # Project conventions
```

### Desired Codebase Tree with Files to be Added
```bash
phase1-specbook/
├── agent/
│   ├── therma_pydantic.py       # Base agent framework
│   ├── verification_framework.py # Multi-agent example
│   ├── conversation_agent.py    # NEW: Natural language interface
│   ├── product_agent.py         # NEW: Product operations
│   ├── quality_agent.py         # NEW: Quality assurance
│   ├── export_agent.py          # NEW: Specbook generation
│   └── monitoring_agent.py      # NEW: Change detection
├── tools/
│   ├── data_management/
│   │   ├── __init__.py          # NEW
│   │   ├── project_store.py     # NEW: PostgreSQL storage
│   │   └── product_cache.py     # NEW: Redis cache
│   ├── nlp/
│   │   ├── __init__.py          # NEW
│   │   ├── intent_parser.py     # NEW: NLP parsing
│   │   └── context_tracker.py   # NEW: Conversation state
│   ├── product_tools/
│   │   ├── __init__.py          # NEW
│   │   ├── product_fetcher.py   # NEW: Enhanced scraper
│   │   ├── product_extractor.py # NEW: LLM wrapper
│   │   └── change_detector.py   # NEW: Update monitoring
│   ├── export_tools/
│   │   ├── __init__.py          # NEW
│   │   ├── specbook_generator.py # NEW: CSV/PDF export
│   │   └── revit_connector.py   # NEW: Revit mapping
│   ├── quality_tools/
│   │   ├── __init__.py          # NEW
│   │   ├── quality_checker.py   # NEW: Quality wrapper
│   │   └── verification_queue.py # NEW: Review queue
│   └── (existing tools)
├── cli/
│   ├── __init__.py              # NEW
│   └── chat_interface.py        # NEW: Main CLI entry point
├── models/
│   ├── __init__.py              # NEW
│   ├── database.py              # NEW: SQLAlchemy models
│   └── schemas.py               # NEW: Pydantic schemas
├── tests/
│   ├── __init__.py              # NEW
│   ├── test_agents/             # NEW: Agent tests
│   ├── test_tools/              # NEW: Tool tests
│   └── test_integration/        # NEW: E2E tests
├── config/
│   ├── __init__.py              # NEW
│   └── settings.py              # NEW: Configuration
└── (existing files)
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: OpenAI API in llm_invocator.py uses deprecated patterns
# Must update to use ChatCompletion instead of Completion

# CRITICAL: Pydantic v2 is used - use field validators not root validators
# Example: @field_validator('field_name') not @validator

# CRITICAL: Redis connection must be managed carefully
# Use connection pooling to avoid connection exhaustion

# CRITICAL: SQLAlchemy async requires special session handling
# Use async_sessionmaker and async context managers

# CRITICAL: spaCy models must be downloaded separately
# Run: python -m spacy download en_core_web_sm

# CRITICAL: Existing scraper has rate limits (10 req/60s)
# ProductFetcher must respect these limits in batch operations
```

## Implementation Blueprint

### Data Models and Structure

```python
# models/schemas.py - Pydantic models for API/validation
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"

class Project(BaseModel):
    id: Optional[str] = None
    name: str
    status: ProjectStatus = ProjectStatus.DRAFT
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

class Product(BaseModel):
    id: Optional[str] = None
    project_id: str
    url: str
    image_url: Optional[str]
    type: str
    description: str
    model_no: Optional[str]
    qty: int = 1
    key: Optional[str]  # Revit key
    confidence_score: float = 0.0
    verified: bool = False
    last_checked: Optional[datetime]
    
    @field_validator('url')
    def validate_url(cls, v):
        # Use existing URL validation from stealth_scraper
        pass

# models/database.py - SQLAlchemy ORM models
from sqlalchemy import Column, String, Float, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ProjectDB(Base):
    __tablename__ = "projects"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String, default="draft")
    metadata = Column(JSON)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class ProductDB(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True)
    project_id = Column(String, nullable=False)
    url = Column(String, nullable=False)
    # ... other fields matching Product schema
```

### List of Tasks to Complete (in order)

```yaml
Task 1: Core Infrastructure Setup
CREATE config/settings.py:
  - PATTERN: Use pydantic BaseSettings for validation
  - INCLUDE: Database URLs, Redis config, API keys
  - REFERENCE: Environment variable loading from CLAUDE.md

CREATE models/schemas.py:
  - MIRROR: Pydantic patterns from agent/therma_pydantic.py
  - EXTEND: Product model from existing extraction format
  - ADD: Project, Intent, Context models

CREATE models/database.py:
  - IMPLEMENT: SQLAlchemy models matching schemas
  - PATTERN: Follow declarative_base pattern
  - INCLUDE: Proper indexes for performance

Task 2: Data Management Tools
CREATE tools/data_management/project_store.py:
  - IMPLEMENT: CRUD operations using SQLAlchemy async
  - PATTERN: Use async context managers for sessions
  - ERROR HANDLING: Wrap in try/except with proper rollback

CREATE tools/data_management/product_cache.py:
  - IMPLEMENT: Redis client with connection pooling
  - PATTERN: JSON serialization for Product models
  - INCLUDE: TTL management and cache invalidation

Task 3: NLP Tools
CREATE tools/nlp/intent_parser.py:
  - IMPLEMENT: spaCy-based intent extraction
  - PATTERN: Return Intent objects with confidence scores
  - INCLUDE: Entity extraction for projects, URLs, actions

CREATE tools/nlp/context_tracker.py:
  - IMPLEMENT: In-memory session storage with Redis backup
  - PATTERN: Context objects with project state
  - INCLUDE: Conversation history management

Task 4: Product Processing Tools
CREATE tools/product_tools/product_fetcher.py:
  - WRAP: Existing stealth_scraper with caching layer
  - IMPLEMENT: Async batch processing with semaphore
  - RESPECT: Rate limits from original scraper

CREATE tools/product_tools/product_extractor.py:
  - WRAP: Existing llm_invocator with validation
  - FIX: Update to use ChatCompletion API
  - PATTERN: Return typed Product objects

CREATE tools/product_tools/change_detector.py:
  - IMPLEMENT: Content hashing for change detection
  - INCLUDE: Similarity search using embeddings
  - PATTERN: Return structured Change objects

Task 5: Quality Tools
CREATE tools/quality_tools/quality_checker.py:
  - WRAP: Existing eval_product_extraction
  - EXTEND: Add confidence scoring
  - PATTERN: Return QualityScore objects

CREATE tools/quality_tools/verification_queue.py:
  - IMPLEMENT: Priority queue with PostgreSQL
  - PATTERN: Integration with verification_ui.py
  - INCLUDE: Review tracking and corrections

Task 6: Export Tools
CREATE tools/export_tools/specbook_generator.py:
  - IMPLEMENT: pandas-based CSV generation
  - INCLUDE: Revit column mapping
  - PATTERN: Multiple format support (CSV, PDF)

CREATE tools/export_tools/revit_connector.py:
  - IMPLEMENT: Field mapping and validation
  - PATTERN: Ensure Revit compatibility
  - INCLUDE: Key validation and generation

Task 7: Agent Implementation
CREATE agent/conversation_agent.py:
  - EXTEND: Base Agent from therma_pydantic.py
  - INTEGRATE: IntentParser and ContextTracker
  - PATTERN: Handle multi-turn conversations

CREATE agent/product_agent.py:
  - EXTEND: Base Agent class
  - INTEGRATE: ProductFetcher, ProductExtractor, ProjectStore
  - PATTERN: Batch and single product operations

CREATE agent/quality_agent.py:
  - EXTEND: Base Agent class
  - INTEGRATE: QualityChecker, VerificationQueue
  - PATTERN: Automated quality workflows

CREATE agent/export_agent.py:
  - EXTEND: Base Agent class
  - INTEGRATE: SpecbookGenerator, RevitConnector
  - PATTERN: Multi-format export handling

CREATE agent/monitoring_agent.py:
  - EXTEND: Base Agent class
  - INTEGRATE: ChangeDetector, ProductCache
  - PATTERN: Scheduled monitoring tasks

Task 8: CLI Interface
CREATE cli/chat_interface.py:
  - IMPLEMENT: Typer-based chat loop
  - INTEGRATE: Rich for terminal UI
  - PATTERN: Stream responses from agents
  - INCLUDE: Progress bars for batch operations

Task 9: Testing
CREATE tests/test_tools/:
  - PATTERN: pytest with fixtures
  - MOCK: External services (OpenAI, web requests)
  - INCLUDE: Parametrized tests for edge cases

CREATE tests/test_agents/:
  - PATTERN: Test agent coordination
  - MOCK: Tool responses
  - VERIFY: Proper workflow execution

CREATE tests/test_integration/:
  - IMPLEMENT: E2E tests with real services
  - PATTERN: Docker compose for test databases
  - VERIFY: Full workflow from chat to export
```

### Integration Points
```yaml
DATABASE:
  - migration: "alembic init alembic"
  - migration: "alembic revision --autogenerate -m 'Initial schema'"
  - migration: "alembic upgrade head"
  
CONFIG:
  - add to: .env
  - pattern: |
      DATABASE_URL=postgresql+asyncpg://user:pass@localhost/specbook
      REDIS_URL=redis://localhost:6379
      OPENAI_API_KEY=existing_key
      FIRECRAWL_API_KEY=existing_key
  
DEPENDENCIES:
  - add to: requirements.txt
  - packages: |
      sqlalchemy[asyncio]
      asyncpg
      redis
      spacy
      typer
      rich
      alembic
      pandas
      reportlab
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Fix code style issues
ruff check . --fix

# Type checking
mypy agent/ tools/ cli/ models/

# Expected: No errors
```

### Level 2: Unit Tests
```python
# tests/test_tools/test_project_store.py
import pytest
from tools.data_management.project_store import ProjectStore

@pytest.mark.asyncio
async def test_create_project():
    store = ProjectStore()
    project_id = await store.create_project("Test Project", {"client": "ABC"})
    assert project_id is not None

@pytest.mark.asyncio
async def test_add_product():
    store = ProjectStore()
    project_id = await store.create_project("Test", {})
    product_id = await store.add_product(project_id, product_data)
    assert product_id is not None

# tests/test_agents/test_conversation_agent.py
def test_parse_batch_request():
    agent = ConversationAgent()
    intent = agent.parse("Process these 10 URLs for Scottsdale project")
    assert intent.action == "batch_add"
    assert intent.project == "Scottsdale"
    assert len(intent.urls) == 10
```

```bash
# Run tests iteratively
pytest tests/ -v

# Run specific test file
pytest tests/test_tools/test_project_store.py -v
```

### Level 3: Integration Test
```bash
# Start required services
docker-compose up -d postgres redis

# Initialize database
alembic upgrade head

# Start the CLI
python -m cli.chat_interface

# Test commands:
# > Create a new project called Desert Modern
# > Add this product URL: https://example.com/faucet
# > Generate a spec book for Desert Modern

# Expected: Successful execution of each command
```

## Final Validation Checklist
- [ ] All tests pass: `pytest tests/ -v`
- [ ] No linting errors: `ruff check .`
- [ ] No type errors: `mypy .`
- [ ] Database migrations work: `alembic upgrade head`
- [ ] CLI accepts natural language: "Add these products to my project"
- [ ] Batch processing works: 50 products in <30 minutes
- [ ] Export generates valid CSV: Opens correctly in Excel/Revit
- [ ] Error messages are user-friendly
- [ ] Progress tracking shows real-time updates
- [ ] Multi-project isolation verified

## Anti-Patterns to Avoid
- ❌ Don't bypass existing tool functionality - wrap and enhance
- ❌ Don't create new scraping logic - use stealth_scraper
- ❌ Don't ignore rate limits - respect existing constraints
- ❌ Don't use sync database calls in async context
- ❌ Don't store sensitive data in logs
- ❌ Don't create tight coupling between agents

---

## Implementation Timeline Estimate
- **Week 1-2**: Core infrastructure (Tasks 1-2)
- **Week 3-4**: NLP and product tools (Tasks 3-4)
- **Week 5-6**: Quality and export tools (Tasks 5-6)
- **Week 7-8**: Agent implementation (Task 7)
- **Week 9-10**: CLI and testing (Tasks 8-9)
- **Week 11-12**: Integration testing and refinement

## Confidence Score: 8/10
Strong foundation exists with working tools and agent framework. Main risks are database setup complexity and NLP accuracy for intent parsing. The modular approach allows incremental development and testing.