import logging

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.users import User
from app.schemas.users import UserCreate, UserResponse, AuthResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.auth_service = AuthService()
    
    async def register_user(self, user_data: UserCreate) -> AuthResponse:
        try:
            # Check if user already exists
            result = await self.db.exec(select(User).where(User.email == user_data.email))
            existing_user = result.first()
            
            if existing_user:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists"
                )
            
            # Create new user
            hashed_password = self.auth_service.hash_password(user_data.password)
            new_user = User(
                email=user_data.email,
                name=user_data.name,
                password_hash=hashed_password
            )
            
            self.db.add(new_user)
            await self.db.commit()
            await self.db.refresh(new_user)
            
            # Generate auth token
            access_token = self.auth_service.generate_auth_token(str(new_user.user_id))
            
            logger.info(f"User registered: {user_data.email} (ID: {new_user.user_id})")
            
            return AuthResponse(
                access_token=access_token,
                token_type="bearer",
                user=UserResponse(
                    user_id=str(new_user.user_id),
                    email=new_user.email,
                    name=new_user.name,
                    created_at=new_user.created_at
                )
            )
            
        except Exception as e:
            logger.error(f"Database error during user registration: {e}")
            await self.db.rollback()
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during registration"
            )
    
    async def login_user(self, login_data) -> AuthResponse:
        try:
            # Find user by email
            result = await self.db.exec(select(User).where(User.email == login_data.email))
            user = result.first()
            
            if not user:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Verify password
            if not self.auth_service.verify_password(login_data.password, user.password_hash):
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            # Generate auth token
            access_token = self.auth_service.generate_auth_token(str(user.user_id))
            
            logger.info(f"User logged in: {login_data.email} (ID: {user.user_id})")
            
            return AuthResponse(
                access_token=access_token,
                token_type="bearer",
                user=UserResponse(
                    user_id=str(user.user_id),
                    email=user.email,
                    name=user.name,
                    created_at=user.created_at
                )
            )
            
        except Exception as e:
            logger.error(f"Database error during user login: {e}")
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during login"
            )
