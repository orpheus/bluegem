"""
ContextTracker - Conversation state management
In-memory session storage with Redis backup for persistence
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import redis.asyncio as redis
from redis.asyncio.connection import ConnectionPool

# Import models
from models.schemas import Context
from config.settings import get_settings

logger = logging.getLogger(__name__)


class ContextTracker:
    """Manages conversation context and session state"""
    
    def __init__(self, redis_url: Optional[str] = None):
        """Initialize context tracker"""
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url
        self.connection_pool = None
        self.redis_client = None
        
        # In-memory cache for active sessions
        self._active_contexts: Dict[str, Context] = {}
        self._session_timeout = 3600  # 1 hour
        self._max_history_length = 50  # Maximum conversation history
    
    async def initialize(self):
        """Initialize Redis connection for persistence"""
        try:
            connection_params = get_settings().get_redis_connection_params()
            self.connection_pool = ConnectionPool.from_url(
                connection_params["url"],
                max_connections=connection_params["max_connections"],
                decode_responses=connection_params["decode_responses"]
            )
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Context tracker initialized successfully")
            
        except Exception as e:
            logger.warning(f"Redis not available for context persistence: {e}")
            # Continue without Redis - use memory only
            self.redis_client = None
    
    def _get_context_key(self, session_id: str) -> str:
        """Generate Redis key for context storage"""
        return f"context:{session_id}"
    
    async def get_context(self, session_id: str) -> Context:
        """Get or create context for session"""
        try:
            # Check in-memory cache first
            if session_id in self._active_contexts:
                context = self._active_contexts[session_id]
                # Check if context is still fresh
                if self._is_context_fresh(context):
                    return context
                else:
                    # Remove stale context
                    del self._active_contexts[session_id]
            
            # Try to load from Redis
            context = await self._load_from_redis(session_id)
            if context:
                self._active_contexts[session_id] = context
                return context
            
            # Create new context
            context = Context(session_id=session_id)
            self._active_contexts[session_id] = context
            await self._save_to_redis(context)
            
            logger.debug(f"Created new context for session: {session_id}")
            return context
            
        except Exception as e:
            logger.error(f"Failed to get context for session {session_id}: {e}")
            # Fallback to new context
            return Context(session_id=session_id)
    
    async def update_context(self, session_id: str, updates: Dict[str, Any]):
        """Update context with new information"""
        try:
            context = await self.get_context(session_id)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(context, key):
                    setattr(context, key, value)
            
            # Update last activity
            context.last_activity = datetime.now()
            
            # Update caches
            self._active_contexts[session_id] = context
            await self._save_to_redis(context)
            
            logger.debug(f"Updated context for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to update context for session {session_id}: {e}")
    
    async def add_message(self, session_id: str, role: str, content: str):
        """Add message to conversation history"""
        try:
            context = await self.get_context(session_id)
            context.add_message(role, content)
            
            # Trim history if too long
            if len(context.conversation_history) > self._max_history_length:
                context.conversation_history = context.conversation_history[-self._max_history_length:]
            
            # Update caches
            self._active_contexts[session_id] = context
            await self._save_to_redis(context)
            
        except Exception as e:
            logger.error(f"Failed to add message for session {session_id}: {e}")
    
    async def set_active_project(self, session_id: str, project_id: str, project_name: str):
        """Set the active project for a session"""
        await self.update_context(session_id, {
            "active_project_id": project_id,
            "active_project_name": project_name
        })
        
        # Add to conversation history
        await self.add_message(
            session_id, 
            "system", 
            f"Switched to project: {project_name}"
        )
    
    async def get_active_project(self, session_id: str) -> Optional[Dict[str, str]]:
        """Get active project for session"""
        try:
            context = await self.get_context(session_id)
            
            if context.active_project_id and context.active_project_name:
                return {
                    "project_id": context.active_project_id,
                    "project_name": context.active_project_name
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get active project for session {session_id}: {e}")
            return None
    
    async def get_recent_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        try:
            context = await self.get_context(session_id)
            return context.conversation_history[-limit:]
            
        except Exception as e:
            logger.error(f"Failed to get history for session {session_id}: {e}")
            return []
    
    async def clear_context(self, session_id: str):
        """Clear context for session"""
        try:
            # Remove from memory
            if session_id in self._active_contexts:
                del self._active_contexts[session_id]
            
            # Remove from Redis
            if self.redis_client:
                context_key = self._get_context_key(session_id)
                await self.redis_client.delete(context_key)
            
            logger.debug(f"Cleared context for session: {session_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear context for session {session_id}: {e}")
    
    async def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get summary of session state"""
        try:
            context = await self.get_context(session_id)
            
            return {
                "session_id": session_id,
                "active_project": {
                    "id": context.active_project_id,
                    "name": context.active_project_name
                } if context.active_project_id else None,
                "created_at": context.created_at.isoformat(),
                "last_activity": context.last_activity.isoformat(),
                "message_count": len(context.conversation_history),
                "duration_minutes": (
                    datetime.now() - context.created_at
                ).total_seconds() / 60
            }
            
        except Exception as e:
            logger.error(f"Failed to get session summary for {session_id}: {e}")
            return {"session_id": session_id, "error": str(e)}
    
    async def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions"""
        try:
            sessions = []
            
            # Get from memory first
            for session_id, context in self._active_contexts.items():
                if self._is_context_fresh(context):
                    sessions.append(await self.get_session_summary(session_id))
            
            # Also check Redis for persisted sessions
            if self.redis_client:
                cursor = 0
                while True:
                    cursor, keys = await self.redis_client.scan(
                        cursor=cursor,
                        match="context:*",
                        count=100
                    )
                    
                    for key in keys:
                        session_id = key.replace("context:", "")
                        if session_id not in self._active_contexts:
                            # Load and check freshness
                            context = await self._load_from_redis(session_id)
                            if context and self._is_context_fresh(context):
                                sessions.append(await self.get_session_summary(session_id))
                    
                    if cursor == 0:
                        break
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to list active sessions: {e}")
            return []
    
    async def cleanup_stale_sessions(self):
        """Remove stale sessions from memory and Redis"""
        try:
            removed_count = 0
            
            # Clean memory
            stale_sessions = []
            for session_id, context in self._active_contexts.items():
                if not self._is_context_fresh(context):
                    stale_sessions.append(session_id)
            
            for session_id in stale_sessions:
                del self._active_contexts[session_id]
                removed_count += 1
            
            # Clean Redis
            if self.redis_client:
                cursor = 0
                while True:
                    cursor, keys = await self.redis_client.scan(
                        cursor=cursor,
                        match="context:*",
                        count=100
                    )
                    
                    for key in keys:
                        session_id = key.replace("context:", "")
                        context = await self._load_from_redis(session_id)
                        if context and not self._is_context_fresh(context):
                            await self.redis_client.delete(key)
                            removed_count += 1
                    
                    if cursor == 0:
                        break
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} stale sessions")
            
        except Exception as e:
            logger.error(f"Failed to cleanup stale sessions: {e}")
    
    def _is_context_fresh(self, context: Context) -> bool:
        """Check if context is still within timeout window"""
        timeout_delta = timedelta(seconds=self._session_timeout)
        return (datetime.now() - context.last_activity) < timeout_delta
    
    async def _load_from_redis(self, session_id: str) -> Optional[Context]:
        """Load context from Redis"""
        try:
            if not self.redis_client:
                return None
            
            context_key = self._get_context_key(session_id)
            context_data = await self.redis_client.get(context_key)
            
            if context_data:
                data = json.loads(context_data)
                # Convert ISO datetime strings back to datetime objects
                if 'created_at' in data:
                    data['created_at'] = datetime.fromisoformat(data['created_at'])
                if 'last_activity' in data:
                    data['last_activity'] = datetime.fromisoformat(data['last_activity'])
                
                return Context(**data)
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to load context from Redis for {session_id}: {e}")
            return None
    
    async def _save_to_redis(self, context: Context):
        """Save context to Redis"""
        try:
            if not self.redis_client:
                return
            
            context_key = self._get_context_key(context.session_id)
            
            # Convert to dict and handle datetime serialization
            context_data = context.model_dump()
            if 'created_at' in context_data:
                context_data['created_at'] = context_data['created_at'].isoformat()
            if 'last_activity' in context_data:
                context_data['last_activity'] = context_data['last_activity'].isoformat()
            
            # Save with TTL
            await self.redis_client.setex(
                context_key,
                self._session_timeout,
                json.dumps(context_data)
            )
            
        except Exception as e:
            logger.warning(f"Failed to save context to Redis: {e}")
    
    async def close(self):
        """Close Redis connections"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            if self.connection_pool:
                await self.connection_pool.disconnect()
            logger.info("Context tracker connections closed")
        except Exception as e:
            logger.error(f"Error closing context tracker connections: {e}")