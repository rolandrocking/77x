"""
Test suite for the coupon service with async Redis.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import get_db, init_db, User, Base
from app.config import settings
from app.redis_manager import redis_manager


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


class TestCouponService:
    """Test cases for the coupon service with async Redis."""
    
    @pytest.fixture(autouse=True)
    async def setup_method(self):
        """Reset database and Redis state before each test."""
        # Create tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Initialize Redis manager for testing
        await redis_manager.initialize()
        
        # Clean up Redis
        try:
            await redis_manager.delete(settings.TOKEN_COUNTER_KEY)
            # Clean up any used token markers
            async for key in redis_manager.scan_iter(match="token_used:*"):
                await redis_manager.delete(key)
            async for key in redis_manager.scan_iter(match=f"{settings.USER_COUNTER_KEY_PREFIX}*"):
                await redis_manager.delete(key)
        except Exception:
            pass  # Redis might not be available in test environment
        
        yield
        
        # Clean up after test
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    def test_user_registration(self):
        """Test user registration."""
        client = TestClient(app)
        
        response = client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert "user_id" in data
        assert "created_at" in data
    
    def test_user_registration_duplicate_email(self):
        """Test user registration with duplicate email."""
        client = TestClient(app)
        
        # Register first user
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        # Try to register with same email
        response = client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password456",
                "name": "Another User"
            }
        )
        
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]
    
    def test_user_login(self):
        """Test user login."""
        client = TestClient(app)
        
        # Register user
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        # Login
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
    
    def test_user_login_invalid_credentials(self):
        """Test user login with invalid credentials."""
        client = TestClient(app)
        
        # Register user
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        # Try to login with wrong password
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_generate_coupon_success(self):
        """Test successful coupon generation."""
        client = TestClient(app)
        
        # Register and login user
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Generate coupon
        response = client.post("/coupons/generate", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "expires_at" in data
        assert data["token_number"] == 1
        assert data["remaining_tokens"] == 76
        assert data["user_id"] is not None
    
    def test_generate_coupon_limit_reached(self):
        """Test coupon generation when limit is reached."""
        client = TestClient(app)
        
        # Register and login user
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Generate all 77 tokens
        for i in range(77):
            response = client.post("/coupons/generate", headers=headers)
            assert response.status_code == 200
        
        # Try to generate one more
        response = client.post("/coupons/generate", headers=headers)
        assert response.status_code == 429
        assert "Global token limit reached" in response.json()["detail"]
    
    def test_generate_coupon_unauthorized(self):
        """Test coupon generation without authentication."""
        client = TestClient(app)
        
        response = client.post("/coupons/generate")
        assert response.status_code == 401
    
    def test_validate_token_valid(self):
        """Test token validation with valid token."""
        client = TestClient(app)
        
        # Register, login, and generate token
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        coupon_response = client.post("/coupons/generate", headers=headers)
        coupon_token = coupon_response.json()["token"]
        
        # Validate token
        response = client.post(
            "/coupons/validate",
            json={"token": coupon_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "Token is valid and unused" in data["message"]
    
    def test_use_token_success(self):
        """Test successful token usage."""
        client = TestClient(app)
        
        # Register, login, and generate token
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        coupon_response = client.post("/coupons/generate", headers=headers)
        coupon_token = coupon_response.json()["token"]
        
        # Use token
        response = client.post(
            "/coupons/use",
            json={"token": coupon_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "Token successfully used" in data["message"]
        assert "used_at" in data
    
    def test_use_token_already_used(self):
        """Test token usage when token is already used."""
        client = TestClient(app)
        
        # Register, login, and generate token
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        coupon_response = client.post("/coupons/generate", headers=headers)
        coupon_token = coupon_response.json()["token"]
        
        # Use token first time
        client.post("/coupons/use", json={"token": coupon_token})
        
        # Try to use token again
        response = client.post("/coupons/use", json={"token": coupon_token})
        assert response.status_code == 409
        assert "Token has already been used" in response.json()["detail"]
    
    def test_get_stats(self):
        """Test getting global statistics."""
        client = TestClient(app)
        
        # Register, login, and generate some tokens
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Generate 3 tokens
        for _ in range(3):
            client.post("/coupons/generate", headers=headers)
        
        # Get stats
        response = client.get("/coupons/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tokens_issued"] == 3
        assert data["tokens_remaining"] == 74
        assert data["max_tokens"] == 77
        assert data["limit_reached"] is False
    
    def test_get_user_stats(self):
        """Test getting user-specific statistics."""
        client = TestClient(app)
        
        # Register and login user
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Generate 2 tokens
        for _ in range(2):
            client.post("/coupons/generate", headers=headers)
        
        # Get user stats
        response = client.get("/coupons/user-stats", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_tokens_issued"] == 2
        assert data["user_tokens_remaining"] == 3
        assert data["max_tokens_per_user"] == 5
        assert data["user_limit_reached"] is False
    
    def test_concurrent_token_generation(self):
        """Test concurrent token generation to ensure atomicity."""
        client = TestClient(app)
        
        # Register and login user
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Generate tokens concurrently
        import threading
        import time
        
        results = []
        errors = []
        
        def generate_token():
            try:
                response = client.post("/coupons/generate", headers=headers)
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=generate_token)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        
        # Should have some successful and some rate limited
        success_count = results.count(200)
        rate_limited_count = results.count(429)
        
        assert success_count + rate_limited_count == 10
        assert success_count <= 5  # User limit
        assert rate_limited_count >= 5  # Should hit user limit
    
    def test_concurrent_token_usage(self):
        """Test concurrent token usage to ensure single-use enforcement."""
        client = TestClient(app)
        
        # Register, login, and generate token
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        coupon_response = client.post("/coupons/generate", headers=headers)
        coupon_token = coupon_response.json()["token"]
        
        # Try to use token concurrently
        import threading
        
        results = []
        errors = []
        
        def use_token():
            try:
                response = client.post("/coupons/use", json={"token": coupon_token})
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=use_token)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5
        
        # Should have exactly one success and rest conflicts
        success_count = results.count(200)
        conflict_count = results.count(409)
        
        assert success_count == 1
        assert conflict_count == 4
    
    def test_token_expiry(self):
        """Test token expiry functionality."""
        client = TestClient(app)
        
        # Register, login, and generate token
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        coupon_response = client.post("/coupons/generate", headers=headers)
        coupon_token = coupon_response.json()["token"]
        
        # Validate token
        response = client.post(
            "/coupons/validate",
            json={"token": coupon_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        
        # Note: In a real test, you would mock time to test expiry
        # For now, we just verify the token is valid when created
    
    def test_idempotency_retry(self):
        """Test that retrying operations doesn't cause issues."""
        client = TestClient(app)
        
        # Register and login user
        client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "password": "password123",
                "name": "Test User"
            }
        )
        
        login_response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Generate token
        response1 = client.post("/coupons/generate", headers=headers)
        assert response1.status_code == 200
        
        # Retry the same request (should fail due to user limit)
        response2 = client.post("/coupons/generate", headers=headers)
        assert response2.status_code == 200  # User can have multiple tokens
        
        # Generate more tokens to hit user limit
        for _ in range(3):
            client.post("/coupons/generate", headers=headers)
        
        # Now retry should fail
        response3 = client.post("/coupons/generate", headers=headers)
        assert response3.status_code == 429

