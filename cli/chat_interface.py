"""
ChatInterface - Main CLI entry point for natural language interaction
Typer-based chat interface with Rich terminal UI and agent orchestration
"""

import asyncio
import logging
import signal
import sys
from typing import Dict, Any, Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

# Import agents
from agent.conversation_agent import ConversationAgent
from agent.product_agent import ProductAgent
from agent.quality_agent import QualityAgent
from agent.export_agent import ExportAgent
from agent.monitoring_agent import MonitoringAgent

# Import supporting tools
from tools.nlp.context_tracker import ContextTracker
from tools.data_management.project_store import ProjectStore
from tools.data_management.product_cache import ProductCache

# Import config
from config.settings import get_settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Rich console
console = Console()
app = typer.Typer()


class AgentOrchestrator:
    """Orchestrates multiple specialized agents"""
    
    def __init__(self):
        """Initialize agent orchestrator"""
        self.settings = get_settings()
        
        # Initialize shared components
        self.project_store = ProjectStore()
        self.product_cache = ProductCache()
        self.context_tracker = ContextTracker()
        
        # Initialize agents
        self.conversation_agent = ConversationAgent(self.context_tracker)
        self.product_agent = ProductAgent(self.project_store, self.product_cache)
        self.quality_agent = QualityAgent(self.project_store)
        self.export_agent = ExportAgent(self.project_store)
        self.monitoring_agent = MonitoringAgent(self.project_store, self.product_cache)
        
        self.agents = {
            "conversation_agent": self.conversation_agent,
            "product_agent": self.product_agent,
            "quality_agent": self.quality_agent,
            "export_agent": self.export_agent,
            "monitoring_agent": self.monitoring_agent
        }
        
        self.initialized = False
    
    async def initialize(self):
        """Initialize all agents"""
        try:
            console.print("🔧 Initializing agent system...", style="blue")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                
                task = progress.add_task("Initializing components...", total=None)
                
                # Initialize shared components
                progress.update(task, description="Initializing database...")
                await self.project_store.initialize()
                
                progress.update(task, description="Initializing cache...")
                await self.product_cache.initialize()
                
                progress.update(task, description="Initializing context tracker...")
                await self.context_tracker.initialize()
                
                # Initialize agents
                progress.update(task, description="Initializing agents...")
                await self.conversation_agent.initialize()
                await self.product_agent.initialize()
                await self.quality_agent.initialize()
                await self.export_agent.initialize()
                await self.monitoring_agent.initialize()
                
                progress.update(task, description="Initialization complete!")
            
            self.initialized = True
            console.print("✅ Agent system initialized successfully", style="green")
            
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
            console.print(f"❌ Initialization failed: {e}", style="red")
            raise
    
    async def handle_message(self, message: str, session_id: str) -> Dict[str, Any]:
        """Handle user message through agent orchestration"""
        try:
            # First, let conversation agent parse and route
            response = await self.conversation_agent.handle_message(message, session_id)
            
            if not response.get("success"):
                return response
            
            # If routing is needed, call appropriate specialist agent
            target_agent = response.get("target_agent")
            if target_agent and target_agent in self.agents:
                intent = response.get("intent")
                specialist_response = await self.agents[target_agent].handle_intent(intent, session_id)
                
                # Combine responses
                return {
                    "success": True,
                    "conversation_response": response.get("response"),
                    "specialist_response": specialist_response,
                    "agent_used": target_agent,
                    "intent": intent
                }
            
            # Return conversation agent response
            return response
            
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": "I encountered an error processing your request. Please try again."
            }
    
    async def close(self):
        """Close all agents and cleanup"""
        try:
            console.print("🔄 Closing agent system...", style="yellow")
            
            for agent in self.agents.values():
                await agent.close()
            
            await self.context_tracker.close()
            await self.project_store.close()
            await self.product_cache.close()
            
            console.print("✅ Agent system closed", style="green")
            
        except Exception as e:
            logger.error(f"Error closing agents: {e}")
            console.print(f"⚠️  Error during cleanup: {e}", style="yellow")


class ChatSession:
    """Manages a chat session with the agent system"""
    
    def __init__(self, orchestrator: AgentOrchestrator):
        """Initialize chat session"""
        self.orchestrator = orchestrator
        self.session_id = None
        self.running = True
    
    async def start(self):
        """Start interactive chat session"""
        try:
            # Start conversation session
            self.session_id = await self.orchestrator.conversation_agent.start_session()
            
            # Show welcome
            self._show_welcome()
            
            # Main chat loop
            while self.running:
                try:
                    # Get user input
                    user_input = Prompt.ask("\n[bold blue]You[/bold blue]", console=console)
                    
                    # Handle special commands
                    if user_input.lower() in ['quit', 'exit', 'bye']:
                        break
                    elif user_input.lower() == 'help':
                        self._show_help()
                        continue
                    elif user_input.lower() == 'status':
                        await self._show_status()
                        continue
                    elif user_input.lower() == 'clear':
                        console.clear()
                        continue
                    
                    # Process message
                    await self._process_message(user_input)
                    
                except KeyboardInterrupt:
                    console.print("\n\n👋 Goodbye!", style="blue")
                    break
                except Exception as e:
                    logger.error(f"Error in chat loop: {e}")
                    console.print(f"❌ An error occurred: {e}", style="red")
            
            # End session
            if self.session_id:
                await self.orchestrator.conversation_agent.end_session(self.session_id)
            
        except Exception as e:
            logger.error(f"Chat session failed: {e}")
            console.print(f"❌ Chat session failed: {e}", style="red")
    
    def _show_welcome(self):
        """Show welcome message"""
        welcome_text = """
# Welcome to Specbook Agent! 🏗️

I'm your AI assistant for architectural product specification management.

## What I can help you with:
- **Create and manage projects** - "Create a new project called Desert Modern"
- **Add products** - "Process these 10 product URLs for my project"
- **Generate spec books** - "Generate a spec book for client review"
- **Quality verification** - "Check the quality of all products"
- **Monitor changes** - "Check if any products have been updated"

## Quick commands:
- `help` - Show this help message
- `status` - Show current session status
- `clear` - Clear the screen
- `quit` - Exit the application

**Try saying:** "Create a new project" or "What projects do I have?"
        """
        
        console.print(Panel(
            Markdown(welcome_text),
            title="🏗️ Specbook Agent",
            border_style="blue"
        ))
    
    def _show_help(self):
        """Show help information"""
        help_text = """
# Commands and Examples

## Project Management
- "Create a new project called [name]"
- "List my projects"
- "Show me the Desert Modern project"

## Product Management  
- "Add these product URLs: [urls...]"
- "Process 10 products for Scottsdale project"
- "Update the kitchen faucet specifications"
- "Search for lighting fixtures"

## Quality & Verification
- "Check product quality for this project"
- "Verify all bathroom fixtures"
- "Show me products that need review"

## Export & Spec Books
- "Generate a spec book for client review"
- "Export products as CSV for Revit"
- "Create a PDF spec sheet"

## Monitoring
- "Check for product updates"
- "Monitor all active projects"
- "Find alternatives for discontinued items"

## System Commands
- `help` - Show this help
- `status` - Session information
- `clear` - Clear screen
- `quit` - Exit application
        """
        
        console.print(Panel(
            Markdown(help_text),
            title="📖 Help & Examples",
            border_style="green"
        ))
    
    async def _show_status(self):
        """Show current session status"""
        try:
            if not self.session_id:
                console.print("❌ No active session", style="red")
                return
            
            # Get session context
            context = await self.orchestrator.conversation_agent.get_session_context(self.session_id)
            
            # Create status table
            table = Table(title="Session Status")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Session ID", self.session_id[:8] + "...")
            table.add_row("Active Project", context.get("active_project", {}).get("name", "None"))
            table.add_row("Message Count", str(context.get("message_count", 0)))
            table.add_row("Duration", f"{context.get('duration_minutes', 0):.1f} minutes")
            
            console.print(table)
            
        except Exception as e:
            console.print(f"❌ Failed to get status: {e}", style="red")
    
    async def _process_message(self, message: str):
        """Process user message and show response"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                
                task = progress.add_task("Processing your request...", total=None)
                
                # Handle message
                response = await self.orchestrator.handle_message(message, self.session_id)
                
                progress.update(task, description="Formatting response...")
            
            # Display response
            self._display_response(response)
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            console.print(f"❌ Failed to process your request: {e}", style="red")
    
    def _display_response(self, response: Dict[str, Any]):
        """Display agent response in formatted way"""
        try:
            if not response.get("success"):
                console.print(f"❌ {response.get('response', 'Request failed')}", style="red")
                return
            
            # Show conversation response
            conversation_response = response.get("conversation_response", response.get("response"))
            if conversation_response:
                console.print(f"\n[bold green]Assistant[/bold green]: {conversation_response}")
            
            # Show specialist response if available
            specialist_response = response.get("specialist_response")
            if specialist_response:
                agent_used = response.get("agent_used", "specialist")
                self._display_specialist_response(specialist_response, agent_used)
            
        except Exception as e:
            logger.error(f"Failed to display response: {e}")
            console.print(f"❌ Error displaying response: {e}", style="red")
    
    def _display_specialist_response(self, response: Dict[str, Any], agent_type: str):
        """Display specialist agent response with formatting"""
        try:
            if not response.get("success"):
                console.print(f"❌ {response.get('message', 'Operation failed')}", style="red")
                return
            
            # Product agent responses
            if agent_type == "product_agent":
                if "projects" in response:
                    self._display_projects_table(response["projects"])
                elif "products" in response:
                    self._display_products_table(response["products"])
                elif "processed" in response:
                    self._display_batch_results(response)
                else:
                    console.print(f"✅ {response.get('message', 'Operation completed')}", style="green")
            
            # Quality agent responses
            elif agent_type == "quality_agent":
                if "summary" in response:
                    self._display_quality_summary(response["summary"])
                else:
                    console.print(f"✅ {response.get('message', 'Quality check completed')}", style="green")
            
            # Export agent responses
            elif agent_type == "export_agent":
                if "export_path" in response:
                    self._display_export_result(response)
                else:
                    console.print(f"✅ {response.get('message', 'Export completed')}", style="green")
            
            # Default response
            else:
                console.print(f"✅ {response.get('message', 'Operation completed')}", style="green")
            
        except Exception as e:
            logger.error(f"Failed to display specialist response: {e}")
            console.print(f"⚠️  Response formatting error: {e}", style="yellow")
    
    def _display_projects_table(self, projects: list):
        """Display projects in a table"""
        table = Table(title="Projects")
        table.add_column("Name", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Created", style="dim")
        
        for project in projects[:10]:  # Limit to 10 for display
            table.add_row(
                project["name"],
                project["status"],
                project.get("created_at", "Unknown")[:10] if project.get("created_at") else "Unknown"
            )
        
        console.print(table)
        if len(projects) > 10:
            console.print(f"... and {len(projects) - 10} more projects", style="dim")
    
    def _display_products_table(self, products: list):
        """Display products in a table"""
        table = Table(title="Products")
        table.add_column("Type", style="cyan")
        table.add_column("Description", style="white", max_width=50)
        table.add_column("Model", style="yellow")
        table.add_column("Verified", style="green")
        
        for product in products[:10]:  # Limit to 10 for display
            table.add_row(
                product["type"],
                product["description"][:47] + "..." if len(product["description"]) > 50 else product["description"],
                product.get("model_no", "N/A"),
                "✅" if product["verified"] else "⏳"
            )
        
        console.print(table)
        if len(products) > 10:
            console.print(f"... and {len(products) - 10} more products", style="dim")
    
    def _display_batch_results(self, response: Dict[str, Any]):
        """Display batch processing results"""
        processed = response.get("processed", 0)
        successful = response.get("successful", 0)
        failed = response.get("failed", 0)
        
        console.print(f"\n📊 **Batch Processing Results:**", style="bold")
        console.print(f"  • Processed: {processed}")
        console.print(f"  • Successful: {successful} ✅")
        console.print(f"  • Failed: {failed} ❌")
        
        if failed > 0:
            console.print(f"\n⚠️  {failed} products failed to process. Check the logs for details.", style="yellow")
    
    def _display_quality_summary(self, summary: Dict[str, Any]):
        """Display quality assessment summary"""
        console.print(f"\n📋 **Quality Summary:**", style="bold")
        console.print(f"  • Total Products: {summary.get('total_products', 0)}")
        console.print(f"  • Average Score: {summary.get('average_score', 0):.2f}")
        console.print(f"  • Auto-Approved: {summary.get('auto_approve_count', 0)} ✅")
        console.print(f"  • Need Review: {summary.get('manual_review_count', 0)} ⏳")
    
    def _display_export_result(self, response: Dict[str, Any]):
        """Display export result"""
        filename = response.get("filename", "export")
        export_format = response.get("format", "unknown")
        summary = response.get("summary", {})
        
        console.print(f"\n📤 **Export Completed:**", style="bold green")
        console.print(f"  • File: {filename}")
        console.print(f"  • Format: {export_format.upper()}")
        console.print(f"  • Products: {summary.get('total_products', 0)}")
        console.print(f"  • Verified: {summary.get('verified_products', 0)}")


async def main_chat():
    """Main chat interface"""
    orchestrator = AgentOrchestrator()
    
    try:
        # Initialize system
        await orchestrator.initialize()
        
        # Start chat session
        session = ChatSession(orchestrator)
        await session.start()
        
    except KeyboardInterrupt:
        console.print("\n\n👋 Goodbye!", style="blue")
    except Exception as e:
        logger.error(f"Chat interface failed: {e}")
        console.print(f"❌ Application error: {e}", style="red")
    finally:
        # Cleanup
        await orchestrator.close()


@app.command()
def chat():
    """Start the interactive chat interface"""
    console.print("🚀 Starting Specbook Agent...", style="blue")
    
    try:
        asyncio.run(main_chat())
    except KeyboardInterrupt:
        console.print("\n👋 Goodbye!", style="blue")
    except Exception as e:
        console.print(f"❌ Failed to start: {e}", style="red")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information"""
    console.print("Specbook Agent v1.0.0", style="green")
    console.print("Natural Language Interface for Architectural Product Specifications", style="dim")


if __name__ == "__main__":
    app()