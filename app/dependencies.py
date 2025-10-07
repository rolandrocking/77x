from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.database import AsyncDBSession
from sqlmodel import select

from app.models.users import User
from app.services.auth_service import AuthService

# Security scheme
security = HTTPBearer()


async def get_current_user(
    session: AsyncDBSession,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    auth_service = AuthService()
    user_id = auth_service.verify_auth_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    result = await session.exec(select(User).where(User.user_id == user_id))
    user = result.first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

