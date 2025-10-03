"""
Google OAuth service for handling authentication without external libraries.
"""
import logging
import secrets
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import httpx

from app.config import settings
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    """Service for handling Google OAuth flow manually."""
    
    # Google OAuth endpoints
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    def __init__(self):
        self.auth_service = AuthService()
        # Store state codes temporarily (in production, use Redis or database)
        self._state_codes = {}
    
    def generate_authorization_url(self) -> Dict[str, str]:
        """
        Generate Google OAuth authorization URL.
        
        Returns:
            Dictionary with authorization URL and state code
        """
        # Generate a random state code for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state temporarily (in production, store in Redis with TTL)
        self._state_codes[state] = {
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=10)
        }
        
        # Build authorization URL
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "response_type": "code",
            "scope": settings.GOOGLE_SCOPES,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        
        auth_url = f"{self.GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
        
        return {
            "authorization_url": auth_url,
            "state": state
        }
    
    async def exchange_code_for_token(self, code: str, state: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from Google
            state: State parameter for CSRF protection
            
        Returns:
            Dictionary containing access token and user info
            
        Raises:
            ValueError: If state is invalid or code exchange fails
        """
        # Validate state parameter
        if state not in self._state_codes:
            raise ValueError("Invalid state parameter")
        
        state_info = self._state_codes[state]
        if datetime.utcnow() > state_info["expires_at"]:
            del self._state_codes[state]
            raise ValueError("State parameter has expired")
        
        # Clean up state code
        del self._state_codes[state]
        
        # Exchange code for token
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_REDIRECT_URI
            }
            
            try:
                response = await client.post(
                    self.GOOGLE_TOKEN_URL,
                    data=token_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                
                token_response = response.json()
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to exchange code for token: {e}")
                raise ValueError(f"Failed to exchange code for token: {e}")
        
        access_token = token_response.get("access_token")
        if not access_token:
            raise ValueError("No access token received from Google")
        
        # Get user information
        user_info = await self.get_user_info(access_token)
        
        return {
            "access_token": access_token,
            "user_info": user_info,
            "token_type": token_response.get("token_type", "Bearer"),
            "expires_in": token_response.get("expires_in"),
            "refresh_token": token_response.get("refresh_token")
        }
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from Google using access token.
        
        Args:
            access_token: Google access token
            
        Returns:
            Dictionary containing user information
            
        Raises:
            ValueError: If user info request fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.GOOGLE_USER_INFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                
                user_info = response.json()
                
                return {
                    "google_id": user_info["id"],
                    "name": user_info.get("name", ""),
                    "email": user_info.get("email", ""),
                    "picture": user_info.get("picture", "")
                }
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to get user info from Google: {e}")
                raise ValueError(f"Failed to get user info from Google: {e}")
    
    def generate_google_user_jwt(self, google_user_id: str, google_email: str, google_name: str) -> str:
        """
        Generate JWT token for Google-authenticated user.
        
        Args:
            google_user_id: Google user ID
            google_email: Google user email
            google_name: Google user name
            
        Returns:
            JWT token for the user
        """
        # Create payload with Google-specific data
        payload = {
            "user_id": google_user_id,
            "email": google_email,
            "name": google_name,
            "type": "google_auth",
            "issued_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRY_HOURS)).isoformat()
        }
        
        return self.auth_service.generate_jwt_token(payload)
    
    def verify_google_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token from Google authentication.
        
        Args:
            token: JWT token to verify
            
       Returns:
            Token payload if valid, None otherwise
        """
        return self.auth_service.verify_jwt_token(token)
    
    def cleanup_expired_states(self):
        """Clean up expired state codes."""
        now = datetime.utcnow()
        expired_states = [
            state for state, info in self._state_codes.items() 
            if now > info["expires_at"]
        ]
        
        for state in expired_states:
            del self._state_codes[state]
        
        if expired_states:
            logger.info(f"Cleaned up {len(expired_states)} expired state codes")
