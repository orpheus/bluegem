# The Ranch Mine - Agentic Specbook Automation System

A natural language interface for architects to automate product specification workflows through conversational AI agents.

## Overview

This system transforms the manual 20+ hour specbook creation process into a streamlined 2-hour automated workflow. Architects can use natural language commands to manage projects, process products, and generate specification documents.

### Core Capabilities

- **Natural Language Interface**: Chat with AI agents using plain English
- **Intelligent Product Processing**: Automated web scraping and data extraction
- **Quality Assurance**: AI-powered validation with manual review workflows
- **Multi-Format Export**: Generate specbooks for Revit, CSV, and custom formats
- **Project Management**: Track multiple projects with conversation context

## Quick Start

### Prerequisites

```bash
# System requirements
- Python 3.8+
- Chrome/Chromium browser
- PostgreSQL database
- Redis cache

# Environment variables
export OPENAI_API_KEY="your-openai-key"
export FIRECRAWL_API_KEY="your-firecrawl-key"
export DATABASE_URL="postgresql://postgres:password@localhost:5432/bluegem"
export REDIS_URL="redis://localhost:6379"
```

### Installation

```bash
# Clone and setup
git clone <repository>
cd phase1-specbook

# Install dependencies
pip install -r requirements.txt

# Install spaCy model for NLP
python -m spacy download en_core_web_sm

# Setup database and services
docker-compose up -d postgres redis

# Wait for services to be healthy, then initialize database
docker-compose exec postgres psql -U postgres -d bluegem -f - < init_db.sql

# Verify setup
docker-compose exec postgres psql -U postgres -d bluegem -c "\dt"
```

### Basic Usage

```bash
# IMPORTANT: Stop local PostgreSQL if running to avoid port conflicts
brew services stop postgresql@14

# Set environment variables for async database
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/bluegem"

# Start the conversational interface
python -m cli.chat_interface chat

# Example conversations:
> "Create a new project called Desert Modern"
> "Process these product URLs: https://example.com/faucet, https://example.com/tile"
> "Generate a spec book for client review tomorrow"
> "Update the kitchen faucet specs for project Johnson House"

# When done, restart local PostgreSQL
brew services start postgresql@14
```

## System Architecture

### Agents

The system uses 5 specialized AI agents:

1. **Conversation Agent** - Natural language understanding and routing
2. **Product Agent** - Product data processing and project management  
3. **Quality Agent** - Data validation and verification workflows
4. **Export Agent** - Document generation and format conversion
5. **Scraper Agent** - Web scraping orchestration and monitoring

### Tools

Each agent has access to specialized tools:

- **NLP Tools**: Intent parsing, entity extraction, context tracking
- **Data Tools**: Product fetching, LLM extraction, quality assessment
- **Storage Tools**: Project management, product caching, change detection
- **Export Tools**: Multi-format generation, Revit integration

### Data Flow

```
User Input → Intent Parser → Agent Router → Specialist Agent → Tools → Response
     ↓
Context Tracker → Session Management → Project State → Quality Gate → Export
```

## Usage Examples

### Creating a New Project

```bash
> "Start a new project for the Scottsdale Residence kitchen renovation"

✓ Created project: Scottsdale Residence (ID: proj_abc123)
✓ Set as active project
Ready to add products or generate specifications.
```

### Batch Product Processing

```bash
> "Process these 15 product URLs for Desert Modern:
   https://kohler.com/faucet-123
   https://daltile.com/tile-456
   [... more URLs]"

✓ Queued 15 products for processing
✓ Estimated completion: 3 minutes
✓ Quality check: Auto-approve threshold 80%
Monitor progress with: status
```

### Quality Review Workflow

```bash
> "Show me products that need review"

Found 3 products requiring manual verification:
- Faucet KF-123: Missing model number (confidence: 65%)
- Tile DT-456: Unclear description (confidence: 72%)
- Light LX-789: Invalid image URL (confidence: 45%)

Use: verify product <key> to review individual items
```

### Export Generation

```bash
> "Generate a detailed spec book for Revit import"

✓ Generated specification document
✓ Format: Revit CSV with field mapping
✓ Products: 23 verified, 2 pending review
✓ Output: exports/desert-modern-specbook-20240315.csv
✓ Revit import ready
```

## Development

### Testing

```bash
# Run all tests
pytest tests/ -v

# Test specific components
pytest tests/test_tools/test_intent_parser.py -v
pytest tests/test_tools/test_quality_checker.py -v
pytest tests/test_integration/test_basic_workflow.py -v

# Code quality checks
ruff check . --fix
mypy agent/ tools/ cli/ models/
```

### Code Structure

```
├── agent/                  # AI agent implementations
│   ├── conversation_agent.py
│   ├── product_agent.py
│   └── ...
├── tools/                  # Specialized tool modules
│   ├── nlp/               # Natural language processing
│   ├── data_management/   # Storage and caching
│   ├── product_processing/ # Web scraping and extraction
│   ├── quality_tools/     # Validation and review
│   └── export_tools/      # Document generation
├── models/                # Data schemas and database
├── config/                # Settings and configuration
├── cli/                   # Command line interface
└── tests/                 # Test suites
```

### Configuration

Key settings in `config/settings.py`:

```python
# Quality thresholds
QUALITY_AUTO_APPROVE_THRESHOLD = 0.8
CONFIDENCE_MINIMUM = 0.6

# Processing limits
MAX_CONCURRENT_SCRAPES = 5
RATE_LIMIT_REQUESTS_PER_MINUTE = 10

# LLM settings
LLM_MODEL = "gpt-4"
LLM_TEMPERATURE = 0.1
```

## Integration with Existing Tools

This system builds upon the original pipeline:

- **Legacy Scraper**: `tools/stealth_scraper.py` (enhanced with async support)
- **LLM Integration**: `tools/llm_invocator.py` (updated to ChatCompletion API)
- **Verification UI**: `verification_ui.py` (integrated with agent workflow)
- **Data Models**: Enhanced Pydantic schemas with validation

### Migration from v1

```bash
# Convert existing specbook.csv data
python -m tools.data_management.migrate_legacy_data

# Import existing projects
python -m cli.import_project --csv 01_llmpipeline/specbook.csv --name "Legacy Import"
```

## Advanced Features

### Custom Agents

Extend the system with custom agents:

```python
from agent.base_agent import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        self.tools = {
            "custom_tool": CustomTool()
        }
    
    async def handle_intent(self, intent, session_id):
        # Custom logic here
        pass
```

### Custom Export Templates

Add new export formats:

```python
# In tools/export_tools/specbook_generator.py
def register_template(name, template_config):
    self.templates[name] = {
        "fields": template_config.fields,
        "formatter": template_config.formatter,
        "use_case": template_config.description
    }
```

### Monitoring and Analytics

```bash
# View system metrics
python -m cli.metrics --period 7d

# Export usage analytics
python -m cli.analytics --format csv --output analytics.csv
```

## Troubleshooting

### Common Issues

**"Agent not responding"**
- Check Redis connection: `redis-cli ping`
- Verify OpenAI API key is valid
- Review logs: `tail -f logs/agent.log`

**"Quality scores too low"**
- Adjust threshold: `QUALITY_AUTO_APPROVE_THRESHOLD = 0.6`
- Review prompt templates in `tools/prompt_templator.py`
- Check product URL accessibility

**"Export failed"**
- Verify output directory permissions
- Check template configuration
- Review product data completeness

### Performance Optimization

```bash
# Enable caching
export REDIS_CACHE_TTL=3600

# Increase concurrency (carefully)
export MAX_CONCURRENT_SCRAPES=10

# Use faster LLM model for testing
export LLM_MODEL="gpt-3.5-turbo"
```

## Support

- **Issues**: Report bugs and feature requests via GitHub issues
- **Documentation**: See `CLAUDE.md` for development guidelines
- **Examples**: Check `notebooks/` for usage examples

---

**Note**: This system is designed for defensive security purposes only. All web scraping respects robots.txt and rate limits. No malicious use cases are supported.