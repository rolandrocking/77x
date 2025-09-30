"""
Authentication router for user registration and login endpoints.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import UserCreate, UserLogin, AuthResponse
from app.services.user_service import UserService
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# Router instance
router = APIRouter(tags=["authentication"])

# Security scheme
security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Get current user from JWT token.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User ID from the token
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    auth_service = AuthService()
    user_id = auth_service.verify_auth_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id


@router.post("/register", response_model=AuthResponse)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user account.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        Authentication response with access token
        
    Raises:
        HTTPException: If user already exists or registration fails
    """
    user_service = UserService(db)
    return await user_service.register_user(user_data)


@router.post("/login", response_model=AuthResponse)
async def login_user(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with existing user credentials.
    
    Args:
        login_data: User login credentials
        db: Database session
        
    Returns:
        Authentication response with access token
        
    Raises:
        HTTPException: If credentials are invalid or login fails
    """
    user_service = UserService(db)
    return await user_service.login_user(login_data)
