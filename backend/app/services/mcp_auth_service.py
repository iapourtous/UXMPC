from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
import secrets
import base64
import json
from app.core.database import get_database
from app.models.mcp_connection import MCPAuth
import logging

logger = logging.getLogger(__name__)


class MCPAuthService:
    def __init__(self):
        self.auth_collection_name = "mcp_auth"
        self.oauth_states_collection_name = "mcp_oauth_states"
    
    @staticmethod
    def _prepare_document(doc):
        """Prepare MongoDB document for Pydantic model"""
        if doc and "_id" in doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
        return doc
    
    async def start_oauth_flow(self, connection_id: str, auth_config: Dict[str, Any]) -> Dict[str, str]:
        """Start OAuth flow for MCP connection"""
        db = get_database()
        
        # Generate secure state parameter
        state = secrets.token_urlsafe(32)
        
        # Store OAuth state temporarily
        oauth_state = {
            "state": state,
            "connection_id": connection_id,
            "auth_config": auth_config,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=15)  # 15 minute expiry
        }
        
        await db[self.oauth_states_collection_name].insert_one(oauth_state)
        
        # Build authorization URL
        auth_url = self._build_auth_url(auth_config, state)
        
        return {
            "auth_url": auth_url,
            "state": state
        }
    
    def _build_auth_url(self, auth_config: Dict[str, Any], state: str) -> str:
        """Build OAuth authorization URL"""
        base_url = auth_config.get("auth_url", "")
        client_id = auth_config.get("client_id", "")
        redirect_uri = auth_config.get("redirect_uri", "")
        scope = auth_config.get("scope", "")
        
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items() if v])
        return f"{base_url}?{query_string}"
    
    async def handle_oauth_callback(self, code: str, state: str) -> Optional[MCPAuth]:
        """Handle OAuth callback and exchange code for tokens"""
        db = get_database()
        
        # Verify state parameter
        oauth_state = await db[self.oauth_states_collection_name].find_one({"state": state})
        if not oauth_state:
            logger.error(f"Invalid or expired OAuth state: {state}")
            return None
        
        # Check expiry
        if datetime.utcnow() > oauth_state["expires_at"]:
            logger.error(f"Expired OAuth state: {state}")
            await db[self.oauth_states_collection_name].delete_one({"state": state})
            return None
        
        connection_id = oauth_state["connection_id"]
        auth_config = oauth_state["auth_config"]
        
        try:
            # Exchange code for tokens
            token_data = await self._exchange_code_for_tokens(code, auth_config)
            
            if not token_data:
                return None
            
            # Create or update auth record
            auth = MCPAuth(
                connection_id=connection_id,
                access_token=token_data.get("access_token", ""),
                refresh_token=token_data.get("refresh_token"),
                expires_at=self._calculate_expiry(token_data.get("expires_in")),
                scopes=token_data.get("scope", "").split() if token_data.get("scope") else [],
                auth_data=token_data
            )
            
            # Save to database
            auth_dict = auth.model_dump()
            await db[self.auth_collection_name].replace_one(
                {"connection_id": connection_id},
                auth_dict,
                upsert=True
            )
            
            # Clean up OAuth state
            await db[self.oauth_states_collection_name].delete_one({"state": state})
            
            return auth
            
        except Exception as e:
            logger.error(f"OAuth callback error: {e}")
            return None
    
    async def _exchange_code_for_tokens(self, code: str, auth_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access tokens"""
        # This would make an HTTP request to the token endpoint
        # For now, return a placeholder implementation
        logger.info(f"Exchanging code for tokens (placeholder implementation)")
        
        # In a real implementation, you would:
        # 1. Make POST request to token_url with code, client_id, client_secret, etc.
        # 2. Parse the JSON response
        # 3. Return the token data
        
        return {
            "access_token": f"placeholder_token_{secrets.token_urlsafe(32)}",
            "refresh_token": f"placeholder_refresh_{secrets.token_urlsafe(32)}",
            "expires_in": 3600,
            "scope": auth_config.get("scope", ""),
            "token_type": "Bearer"
        }
    
    def _calculate_expiry(self, expires_in: Optional[int]) -> Optional[datetime]:
        """Calculate token expiry datetime"""
        if expires_in:
            return datetime.utcnow() + timedelta(seconds=expires_in)
        return None
    
    async def refresh_token(self, connection_id: str) -> Optional[MCPAuth]:
        """Refresh access token using refresh token"""
        db = get_database()
        
        # Get current auth
        auth_doc = await db[self.auth_collection_name].find_one({"connection_id": connection_id})
        if not auth_doc:
            return None
        
        auth = MCPAuth(**self._prepare_document(auth_doc))
        
        if not auth.refresh_token:
            logger.error(f"No refresh token available for connection {connection_id}")
            return None
        
        try:
            # Refresh the token
            token_data = await self._refresh_access_token(auth)
            
            if not token_data:
                return None
            
            # Update auth record
            auth.access_token = token_data.get("access_token", auth.access_token)
            auth.refresh_token = token_data.get("refresh_token", auth.refresh_token)
            auth.expires_at = self._calculate_expiry(token_data.get("expires_in"))
            auth.updated_at = datetime.utcnow()
            auth.auth_data.update(token_data)
            
            # Save to database
            await db[self.auth_collection_name].replace_one(
                {"connection_id": connection_id},
                auth.model_dump()
            )
            
            return auth
            
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
    
    async def _refresh_access_token(self, auth: MCPAuth) -> Optional[Dict[str, Any]]:
        """Refresh access token using refresh token"""
        # This would make an HTTP request to refresh the token
        # For now, return a placeholder implementation
        logger.info(f"Refreshing access token (placeholder implementation)")
        
        return {
            "access_token": f"refreshed_token_{secrets.token_urlsafe(32)}",
            "refresh_token": auth.refresh_token,  # May or may not be rotated
            "expires_in": 3600,
            "token_type": "Bearer"
        }
    
    async def get_auth(self, connection_id: str) -> Optional[MCPAuth]:
        """Get authentication data for a connection"""
        db = get_database()
        auth_doc = await db[self.auth_collection_name].find_one({"connection_id": connection_id})
        
        if auth_doc:
            return MCPAuth(**self._prepare_document(auth_doc))
        return None
    
    async def delete_auth(self, connection_id: str) -> bool:
        """Delete authentication data for a connection"""
        db = get_database()
        result = await db[self.auth_collection_name].delete_one({"connection_id": connection_id})
        return result.deleted_count > 0
    
    async def is_token_valid(self, connection_id: str) -> bool:
        """Check if the access token is still valid"""
        auth = await self.get_auth(connection_id)
        if not auth:
            return False
        
        if not auth.access_token:
            return False
        
        # Check expiry
        if auth.expires_at and datetime.utcnow() >= auth.expires_at:
            return False
        
        return True
    
    async def get_valid_token(self, connection_id: str) -> Optional[str]:
        """Get a valid access token, refreshing if necessary"""
        auth = await self.get_auth(connection_id)
        if not auth:
            return None
        
        # Check if token is still valid
        if auth.expires_at and datetime.utcnow() >= auth.expires_at:
            # Try to refresh
            refreshed_auth = await self.refresh_token(connection_id)
            if refreshed_auth:
                return refreshed_auth.access_token
            return None
        
        return auth.access_token
    
    async def store_api_key(self, connection_id: str, api_key: str, additional_data: Optional[Dict[str, Any]] = None) -> MCPAuth:
        """Store API key authentication"""
        db = get_database()
        
        auth = MCPAuth(
            connection_id=connection_id,
            access_token=api_key,
            auth_data=additional_data or {}
        )
        
        # Save to database
        await db[self.auth_collection_name].replace_one(
            {"connection_id": connection_id},
            auth.model_dump(),
            upsert=True
        )
        
        return auth
    
    async def cleanup_expired_states(self) -> int:
        """Clean up expired OAuth states"""
        db = get_database()
        result = await db[self.oauth_states_collection_name].delete_many({
            "expires_at": {"$lt": datetime.utcnow()}
        })
        return result.deleted_count


class MCPAuthServiceSingleton:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = MCPAuthService()
        return cls._instance


# Global instance
mcp_auth_service = MCPAuthServiceSingleton()