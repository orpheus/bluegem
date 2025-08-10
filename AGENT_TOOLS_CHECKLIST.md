# Agent Tools Checklist for Natural Language CLI

## Core Architecture Requirements

The CLI is a **chat interface** where architects speak naturally, e.g.:
- "Process these 50 product URLs for the Johnson project"
- "Update the kitchen faucet specs for Desert Modern"
- "Generate the spec book for client review tomorrow"

---

## Required Tools Checklist

### **Web Scraping & Data Collection**
- [x] **Web Scraper** - Fetches product pages with anti-bot detection
  - *Function*: Multi-tier scraping (requests → Selenium → Firecrawl)
  - *Use Case*: All - fetching product data from URLs
  - *Exists*: `tools/stealth_scraper.py`

- [x] **HTML Processor** - Cleans and structures raw HTML
  - *Function*: Removes ads/scripts, extracts clean content
  - *Use Case*: All - preprocessing before LLM extraction
  - *Exists*: `tools/html_processor.py`

### **AI & Data Extraction**
- [x] **LLM Extractor** - Extracts structured product data
  - *Function*: Uses AI to parse product specs into JSON
  - *Use Case*: All - converting HTML to structured data
  - *Exists*: `tools/llm_invocator.py` (needs API update)

- [x] **Prompt Generator** - Creates extraction prompts
  - *Function*: Product-specific prompt templates
  - *Use Case*: All - optimizing LLM extraction accuracy
  - *Exists*: `tools/prompt_templator.py`

### **Quality & Verification**
- [x] **Quality Evaluator** - Scores extraction quality
  - *Function*: Validates JSON, URLs, field completeness
  - *Use Case*: All - ensuring data quality
  - *Exists*: `tools/eval_product_extraction.py`

- [x] **Verification Framework** - Automated verification agents
  - *Function*: Multi-agent quality assessment
  - *Use Case*: B & C - validating updates and final specs
  - *Exists*: `agent/verification_framework.py`

- [x] **Manual Verification UI** - Human review interface
  - *Function*: Side-by-side comparison for manual checks
  - *Use Case*: Low-confidence items in all cases
  - *Exists*: `verification_ui.py`

### **Data Management**
- [ ] **Project Database** - Stores products by project
  - *Function*: PostgreSQL with project isolation
  - *Use Case*: All - persistent storage and retrieval
  - *Needed*: Project-aware data models

- [ ] **Change Tracker** - Monitors product updates
  - *Function*: Detects spec changes over time
  - *Use Case*: B - identifying what changed in updates
  - *Needed*: Content hashing and diff system

- [ ] **CSV Generator** - Revit-compatible export
  - *Function*: Formats data for Revit import
  - *Use Case*: C - generating final spec books
  - *Needed*: Column mapping and validation

### **Agent Orchestration**
- [ ] **Natural Language Parser** - Understands architect requests
  - *Function*: Converts chat to executable intents
  - *Use Case*: All - interpreting natural language
  - *Needed*: NLP with intent classification

- [ ] **Task Orchestrator** - Manages workflow execution
  - *Function*: Coordinates tools based on request type
  - *Use Case*: All - routing to appropriate tools
  - *Needed*: State machine for workflows

- [ ] **Context Manager** - Maintains conversation state
  - *Function*: Remembers project context and history
  - *Use Case*: All - multi-turn conversations
  - *Needed*: Session and project memory

### **User Interface**
- [ ] **Chat Interface** - Terminal-based conversation
  - *Function*: Rich CLI for natural dialogue
  - *Use Case*: All - primary user interaction
  - *Needed*: Typer/Rich with streaming responses

- [ ] **Progress Monitor** - Real-time status updates
  - *Function*: Shows processing progress
  - *Use Case*: A & C - batch operations feedback
  - *Needed*: Async progress tracking

- [ ] **Error Handler** - Graceful failure management
  - *Function*: User-friendly error messages and recovery
  - *Use Case*: All - handling failures gracefully
  - *Needed*: Retry logic and fallback options

---

## Use Case Mappings

### **A. Batch Product Fetch**
*"Process these 50 URLs for the Scottsdale project"*
- Natural Language Parser → Task Orchestrator → Web Scraper (parallel) → HTML Processor → LLM Extractor → Quality Evaluator → Project Database

### **B. Update Single Product**
*"The kitchen faucet model changed, update it"*
- Natural Language Parser → Context Manager → Project Database (retrieve) → Web Scraper → Change Tracker → LLM Extractor → Verification Framework → Project Database (update)

### **C. Generate Spec Book**
*"Create the spec book for tomorrow's presentation"*
- Natural Language Parser → Project Database (query) → Quality Evaluator → Manual Verification UI (if needed) → CSV Generator → Progress Monitor

---

## Implementation Priority

1. **Natural Language Parser** - Core to chat interface
2. **Task Orchestrator** - Routes all requests
3. **Project Database** - Enables multi-project support
4. **Context Manager** - Enables conversational flow
5. **CSV Generator** - Delivers business value
6. **Change Tracker** - Prevents outdated specs

**Existing Tools**: 7/16 (44%)  
**New Tools Needed**: 9/16 (56%)