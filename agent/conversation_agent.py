"""
ConversationAgent - Natural language interface agent
Handles multi-turn conversations and orchestrates other agents
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import base agent framework
from agent.therma_pydantic import Agent, Tool, ToolParameter, Message, MessageRole, AgentConfig

# Import NLP tools
from tools.nlp.intent_parser import IntentParser
from tools.nlp.context_tracker import ContextTracker

# Import schemas
from models.schemas import Intent, Context, IntentAction

logger = logging.getLogger(__name__)


class ConversationAgent(Agent):
    """Primary conversational interface for architect interactions"""
    
    def __init__(self, context_tracker: Optional[ContextTracker] = None):
        """Initialize conversation agent"""
        config = AgentConfig(
            system_prompt="""You are a helpful assistant specializing in architectural product specification management. 
            You help architects manage product data, create spec books, and maintain project information.
            
            Always:
            - Be concise and professional
            - Ask for clarification when requests are ambiguous
            - Confirm important actions before executing
            - Provide status updates for long-running operations
            
            You can help with:
            - Creating and managing projects
            - Adding and updating product information
            - Generating specification books
            - Quality verification and validation
            - Searching and organizing products""",
            max_iterations=10,
            enable_tool_calls=True
        )
        
        super().__init__(config=config)
        
        # Initialize components
        self.intent_parser = IntentParser()
        self.context_tracker = context_tracker or ContextTracker()
        
        # Session state
        self.current_session = None
        
        # Setup tools
        self._setup_tools()
    
    @property
    def agent_id(self) -> str:
        return "conversation_agent"
    
    async def initialize(self):
        """Initialize agent components"""
        try:
            await self.context_tracker.initialize()
            logger.info("ConversationAgent initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize context tracker: {e}")
    
    def _setup_tools(self):
        """Setup conversational tools"""
        
        def parse_user_intent(message: str, session_id: str = None) -> Dict[str, Any]:
            """Parse user message to extract intent and entities"""
            try:
                # Get session context
                context = None
                if session_id:
                    import asyncio
                    context = asyncio.run(self.context_tracker.get_context(session_id))
                    context_dict = {
                        "active_project_id": context.active_project_id,
                        "active_project_name": context.active_project_name,
                        "session_id": context.session_id
                    }
                else:
                    context_dict = {}
                
                # Parse intent
                intent = self.intent_parser.parse(message, context_dict)
                
                return {
                    "success": True,
                    "intent": intent.model_dump(),
                    "confidence": intent.confidence,
                    "suggestions": self.intent_parser.suggest_clarifications(intent) if intent.confidence < 0.7 else []
                }
                
            except Exception as e:
                logger.error(f"Failed to parse intent: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "intent": None
                }
        
        def update_conversation_context(session_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
            """Update conversation context"""
            try:
                import asyncio
                asyncio.run(self.context_tracker.update_context(session_id, updates))
                
                return {
                    "success": True,
                    "message": "Context updated successfully"
                }
                
            except Exception as e:
                logger.error(f"Failed to update context: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def add_message_to_history(session_id: str, role: str, content: str) -> Dict[str, Any]:
            """Add message to conversation history"""
            try:
                import asyncio
                asyncio.run(self.context_tracker.add_message(session_id, role, content))
                
                return {
                    "success": True,
                    "message": "Message added to history"
                }
                
            except Exception as e:
                logger.error(f"Failed to add message: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def get_conversation_summary(session_id: str) -> Dict[str, Any]:
            """Get conversation summary and context"""
            try:
                import asyncio
                summary = asyncio.run(self.context_tracker.get_session_summary(session_id))
                
                return {
                    "success": True,
                    "summary": summary
                }
                
            except Exception as e:
                logger.error(f"Failed to get conversation summary: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        
        def route_to_specialist_agent(intent: Dict[str, Any], session_id: str) -> Dict[str, Any]:
            """Route request to appropriate specialist agent"""
            try:
                action = intent.get("action", "unknown")
                
                # Determine which agent to route to
                agent_routing = {
                    IntentAction.CREATE_PROJECT.value: "product_agent",
                    IntentAction.ADD_PRODUCTS.value: "product_agent", 
                    IntentAction.UPDATE_PRODUCT.value: "product_agent",
                    IntentAction.LIST_PROJECTS.value: "product_agent",
                    IntentAction.LIST_PRODUCTS.value: "product_agent",
                    IntentAction.SEARCH_PRODUCTS.value: "product_agent",
                    IntentAction.VERIFY_PRODUCT.value: "quality_agent",
                    IntentAction.GENERATE_SPECBOOK.value: "export_agent"
                }
                
                target_agent = agent_routing.get(action, "unknown")
                
                return {
                    "success": True,
                    "target_agent": target_agent,
                    "action": action,
                    "routing_needed": target_agent != "unknown"
                }
                
            except Exception as e:
                logger.error(f"Failed to route request: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "routing_needed": False
                }
        
        # Register tools
        parse_intent_tool = Tool(
            name="parse_user_intent",
            description="Parse user message to extract intent and entities",
            parameters=[
                ToolParameter(name="message", type="str", description="User message to parse", required=True),
                ToolParameter(name="session_id", type="str", description="Session identifier", required=False)
            ],
            function=parse_user_intent
        )
        
        update_context_tool = Tool(
            name="update_conversation_context", 
            description="Update conversation context with new information",
            parameters=[
                ToolParameter(name="session_id", type="str", description="Session identifier", required=True),
                ToolParameter(name="updates", type="dict", description="Context updates", required=True)
            ],
            function=update_conversation_context
        )
        
        add_message_tool = Tool(
            name="add_message_to_history",
            description="Add message to conversation history",
            parameters=[
                ToolParameter(name="session_id", type="str", description="Session identifier", required=True),
                ToolParameter(name="role", type="str", description="Message role (user/assistant)", required=True),
                ToolParameter(name="content", type="str", description="Message content", required=True)
            ],
            function=add_message_to_history
        )
        
        summary_tool = Tool(
            name="get_conversation_summary",
            description="Get conversation summary and current context",
            parameters=[
                ToolParameter(name="session_id", type="str", description="Session identifier", required=True)
            ],
            function=get_conversation_summary
        )
        
        routing_tool = Tool(
            name="route_to_specialist_agent",
            description="Determine which specialist agent should handle the request",
            parameters=[
                ToolParameter(name="intent", type="dict", description="Parsed intent object", required=True),
                ToolParameter(name="session_id", type="str", description="Session identifier", required=True)
            ],
            function=route_to_specialist_agent
        )
        
        self.register_tool(parse_intent_tool)
        self.register_tool(update_context_tool)
        self.register_tool(add_message_tool) 
        self.register_tool(summary_tool)
        self.register_tool(routing_tool)
    
    async def handle_message(self, message: str, session_id: str) -> Dict[str, Any]:
        """Handle incoming user message"""
        try:
            # Parse the user's intent
            intent_result = self.tools["parse_user_intent"].call(
                message=message,
                session_id=session_id
            )
            
            if not intent_result["success"]:
                return {
                    "response": "I'm sorry, I couldn't understand your request. Could you please rephrase?",
                    "success": False,
                    "error": intent_result.get("error")
                }
            
            intent = intent_result["intent"]
            
            # Add user message to history
            self.tools["add_message_to_history"].call(
                session_id=session_id,
                role="user", 
                content=message
            )
            
            # Check if we need clarification
            if intent_result.get("suggestions"):
                response = "I need some clarification:\n" + "\n".join([f"- {s}" for s in intent_result["suggestions"]])
                
                # Add assistant response to history
                self.tools["add_message_to_history"].call(
                    session_id=session_id,
                    role="assistant",
                    content=response
                )
                
                return {
                    "response": response,
                    "success": True,
                    "needs_clarification": True,
                    "intent": intent
                }
            
            # Route to appropriate specialist agent
            routing_result = self.tools["route_to_specialist_agent"].call(
                intent=intent,
                session_id=session_id
            )
            
            if not routing_result["routing_needed"]:
                response = "I understand you want help, but I'm not sure how to handle that request. Could you be more specific?"
                
                self.tools["add_message_to_history"].call(
                    session_id=session_id,
                    role="assistant",
                    content=response
                )
                
                return {
                    "response": response,
                    "success": True,
                    "intent": intent
                }
            
            # Prepare response indicating routing
            target_agent = routing_result["target_agent"]
            action = routing_result["action"]
            
            response = self._get_routing_response(action, intent)
            
            self.tools["add_message_to_history"].call(
                session_id=session_id,
                role="assistant", 
                content=response
            )
            
            return {
                "response": response,
                "success": True,
                "target_agent": target_agent,
                "intent": intent,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
            error_response = "I encountered an error processing your request. Please try again."
            
            try:
                self.tools["add_message_to_history"].call(
                    session_id=session_id,
                    role="assistant",
                    content=error_response
                )
            except:
                pass  # Don't fail on logging failure
            
            return {
                "response": error_response,
                "success": False,
                "error": str(e)
            }
    
    def _get_routing_response(self, action: str, intent: Dict[str, Any]) -> str:
        """Get appropriate response for routing to specialist agent"""
        entities = intent.get("entities", {})
        
        if action == IntentAction.CREATE_PROJECT.value:
            project_name = entities.get("project", "new project")
            return f"I'll help you create the project '{project_name}'. Let me set that up for you."
        
        elif action == IntentAction.ADD_PRODUCTS.value:
            url_count = len(entities.get("urls", []))
            project = entities.get("project", "current project")
            if url_count > 0:
                return f"I'll process {url_count} product URLs for {project}. Starting the extraction process..."
            else:
                return "I'll help you add products. Please provide the product URLs you'd like to process."
        
        elif action == IntentAction.UPDATE_PRODUCT.value:
            return "I'll help you update that product information. Let me check the current data..."
        
        elif action == IntentAction.GENERATE_SPECBOOK.value:
            project = entities.get("project", "the project")
            return f"I'll generate the specification book for {project}. Preparing the export..."
        
        elif action == IntentAction.LIST_PROJECTS.value:
            return "Let me show you the available projects..."
        
        elif action == IntentAction.LIST_PRODUCTS.value:
            return "I'll list the products for you..."
        
        else:
            return "I'll help you with that request. Processing..."
    
    async def start_session(self, session_id: str = None) -> str:
        """Start a new conversation session"""
        try:
            if not session_id:
                import uuid
                session_id = str(uuid.uuid4())
            
            # Initialize context
            context = await self.context_tracker.get_context(session_id)
            self.current_session = session_id
            
            # Add welcome message
            welcome_msg = """Hello! I'm your architectural specification assistant. I can help you:

• Create and manage projects
• Add and process product information  
• Generate specification books
• Verify product data quality
• Search and organize products

What would you like to work on today?"""
            
            await self.context_tracker.add_message(session_id, "assistant", welcome_msg)
            
            logger.info(f"Started conversation session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            raise
    
    async def end_session(self, session_id: str):
        """End conversation session"""
        try:
            # Add goodbye message
            goodbye_msg = "Session ended. Your conversation history has been saved."
            await self.context_tracker.add_message(session_id, "assistant", goodbye_msg)
            
            if self.current_session == session_id:
                self.current_session = None
            
            logger.info(f"Ended conversation session: {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to end session: {e}")
    
    async def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get current session context"""
        try:
            return await self.context_tracker.get_session_summary(session_id)
        except Exception as e:
            logger.error(f"Failed to get session context: {e}")
            return {"error": str(e)}
    
    async def close(self):
        """Close agent and cleanup resources"""
        try:
            await self.context_tracker.close()
            logger.info("ConversationAgent closed")
        except Exception as e:
            logger.error(f"Error closing ConversationAgent: {e}")