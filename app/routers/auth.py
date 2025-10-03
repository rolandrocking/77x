import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas import UserCreate, UserLogin, AuthResponse, GoogleAuthResponse
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.services.google_oauth_service import GoogleOAuthService

logger = logging.getLogger(__name__)

# Router instance
router = APIRouter(tags=["authentication"])

# Security scheme
security = HTTPBearer()

# Initialize services
google_oauth_service = GoogleOAuthService()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
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
    user_service = UserService(db)
    return await user_service.register_user(user_data)


@router.post("/login", response_model=AuthResponse)
async def login_user(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    user_service = UserService(db)
    return await user_service.login_user(login_data)


@router.get("/google/url")
async def get_google_auth_url():
    auth_data = google_oauth_service.generate_authorization_url()
    return auth_data


@router.post("/google/callback")
async def google_oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Exchange code for token and user info
        oauth_data = await google_oauth_service.exchange_code_for_token(code, state)
        user_info = oauth_data["user_info"]
        
        # Check if user exists in our database
        user_service = UserService(db)
        existing_user = await user_service.get_user_by_email(user_info["email"])
        
        if existing_user:
            # User exists, generate JWT token
            jwt_token = google_oauth_service.generate_google_user_jwt(
                existing_user.user_id,
                existing_user.email,
                existing_user.name
            )
        else:
            # Create new user from Google data
            user_data = UserCreate(
                email=user_info["email"],
                name=user_info["name"],
                password=""  # Empty password for Google users
            )
            new_user = await user_service.register_user(user_data)
            
            # Generate JWT token for new user
            jwt_token = google_oauth_service.generate_google_user_jwt(
                new_user["user"]["user_id"],
                user_info["email"],
                user_info["name"]
            )
        
        return GoogleAuthResponse(
            access_token=jwt_token,
            token_type="bearer",
            google_user_info=user_info,
            message=f"Welcome back! You have {5} coupon tokens available and {77} tokens remaining globally."
        )
        
    except ValueError as e:
        logger.error(f"Google OAuth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected Google OAuth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )
