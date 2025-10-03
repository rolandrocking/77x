"""
High-performance test suite for the coupon service with focus on 77-token limit and RPS testing.
"""
import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import statistics

from app.main import app
from app.core.database import get_db, Base
from app.core.config import settings
from app.managers.redis_manager import redis_manager


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
    """High-performance test cases for the coupon service with focus on 77-token limit."""
    
    @pytest.fixture(autouse=True)
    async def setup_method(self):
        """Reset database and Redis state before each test."""
        # Create tables
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Initialize Redis manager for testing
        await redis_manager.initialize()
        
        # Clean up Redis - CRITICAL for 77-token limit tests
        try:
            await redis_manager.delete(settings.TOKEN_COUNTER_KEY)
            # Clean up any used token markers
            async for key in redis_manager.scan_iter(match="token_used:*"):
                await redis_manager.delete(key)
            # Clean up user token counters
            async for key in redis_manager.scan_iter(match=f"{settings.USER_COUNTER_KEY_PREFIX}*"):
                await redis_manager.delete(key)
        except Exception:
            pass  # Redis might not be available in test environment
        
        yield
        
        # Clean up after test
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    def create_test_user(self, client: TestClient, email: str = None) -> dict:
        """Helper to create a test user and return auth token."""
        if not email:
            email = f"test_{int(time.time())}@example.com"
        
        response = client.post(
            "/register",
            json={
                "email": email,
                "password": "password123",
                "name": "Test User"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        return {
            "access_token": data["access_token"],
            "user_id": data["user"]["user_id"],
            "email": email
        }

    def generate_coupon_with_token(self, client: TestClient, auth_token: str) -> dict:
        """Helper to generate a coupon and return the response data."""
        response = client.post(
            "/generate-coupon",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        return {
            "status_code": response.status_code,
            "data": response.json() if response.status_code in [200, 429] else response.text,
            "timestamp": time.time()
        }

    @pytest.mark.asyncio
    async def test_exactly_77_tokens_limit_sequential(self):
        """Test that exactly 77 tokens can be issued sequentially."""
        client = TestClient(app)
        
        # Create a single user
        user = self.create_test_user(client)
        
        successful_tokens = []
        failed_requests = []
        
        # Try to generate 100 tokens (should stop at 77)
        for i in range(100):
            result = self.generate_coupon_with_token(client, user["access_token"])
            
            if result["status_code"] == 200:
                successful_tokens.append(result["data"])
                print(f"Token {len(successful_tokens)}: {result['data']['token_number']}")
            elif result["status_code"] == 429:
                failed_requests.append(result["data"])
                print(f"Request {i+1} failed with 429: Token limit reached")
                break
            else:
                pytest.fail(f"Unexpected status code: {result['status_code']}")
        
        # Verify exactly 77 tokens were issued
        assert len(successful_tokens) == 77, f"Expected exactly 77 tokens, got {len(successful_tokens)}"
        
        # Verify token numbers are sequential
        token_numbers = [token["token_number"] for token in successful_tokens]
        assert token_numbers == list(range(1, 78)), "Token numbers should be sequential from 1 to 77"
        
        # Verify final stats
        stats_response = client.get("/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["tokens_issued"] == 77
        assert stats["tokens_remaining"] == 0
        assert stats["limit_reached"] is True
        assert len(failed_requests) >= 1, "Should have received at least one 429 response"

    @pytest.mark.asyncio
    async def test_exactly_77_tokens_concurrent_high_rps(self):
        """Test 77-token limit with high concurrent RPS."""
        client = TestClient(app)
        
        # Create multiple users for concurrent testing
        users = []
        for i in range(10):
            users.append(self.create_test_user(client))
        
        total_successful_tokens = []
        total_429_responses = []
        request_stats = []
        
        def make_requests(user_data):
            """Function to be run in parallel for each user."""
            user_successful = []
            user_429_responses = []
            user_request_stats = []
            
            # Each user tries to generate 10 tokens
            for attempt in range(10):
                result = self.generate_coupon_with_token(
                    client, user_data["access_token"]
                )
                
                if result["status_code"] == 200:
                    user_successful.append(result["data"])
                elif result["status_code"] == 429:
                    user_429_responses.append(result["data"])
                
                user_request_stats.append(result)
                
                # Small delay to avoid overwhelming the service
                time.sleep(0.01)
            
            return user_successful, user_429_responses, user_request_stats
        
        # Run concurrent requests
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_requests, user) for user in users]
            
            for future in as_completed(futures):
                user_successful, user_429_responses, user_stats = future.result()
                total_successful_tokens.extend(user_successful)
                total_429_responses.extend(user_429_responses)
                request_stats.extend(user_stats)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Calculate RPS metrics
        total_requests = len(request_stats)
        successful_requests = len(total_successful_tokens)
        failed_requests = len(total_429_responses)
        
        rps = total_requests / total_time if total_time > 0 else 0
        
        print(f"\nConcurrency Test Results:")
        print(f"Total requests: {total_requests}")
        print(f"Successful tokens: {successful_requests}")
        print(f"429 responses: {failed_requests}")
        print(f"Total time: {total_time:.2f}s")
        print(f"RPS: {rps:.2f}")
        print(f"Success rate: {(successful_requests/total_requests)*100:.1f}%")
        
        # CRITICAL: Verify exactly 77 tokens were issued
        assert len(total_successful_tokens) == 77, f"Expected exactly 77 tokens globally, got {len(total_successful_tokens)}"
        
        # Verify we received 429 responses (429 is a valid waitable response)
        assert len(total_429_responses) > 0, "Should receive 429 responses when limit reached"
        
        # Verify token numbers don't exceed 77
        token_numbers = [token["token_number"] for token in total_successful_tokens]
        assert all(num <= 77 for num in token_numbers), "All token numbers should be <= 77"
        
        # Verify final stats
        stats_response = client.get("/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["tokens_issued"] == 77
        assert stats["tokens_remaining"] == 0
        assert stats["limit_reached"] is True
        
        # Performance assertions
        assert rps > 10, f"Should handle at least 10 RPS, got {rps:.2f}"
        assert successful_requests / total_requests >= 0.77, "Success rate should be reasonable"

    @pytest.mark.asyncio
    async def test_user_limit_combined_with_global_limit(self):
        """Test user limits (1 token per user) combined with global limit (77 total)."""
        client = TestClient(app)
        
        # Since MAX_TOKENS_PER_USER = 1, we need 77 users to reach global limit
        users = []
        successful_tokens = []
        
        # Create 100 users (more than global limit)
        for i in range(100):
            users.append(self.create_test_user(client))
        
        # Each user tries to generate their 1 allowed token
        for user in users:
            result = self.generate_coupon_with_token(client, user["access_token"])
            
            if result["status_code"] == 200:
                successful_tokens.append(result["data"])
            elif result["status_code"] == 429:
                # 429 is acceptable when global limit is reached
                break
        
        # Verify at most 77 tokens were issued globally
        assert len(successful_tokens) == 77, f"Expected exactly 77 tokens, got {len(successful_tokens)}"
        
        # Verify each user has at most 1 token
        stats_response = client.get("/stats")
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["limit_reached"] is True

    @pytest.mark.asyncio
    async def test_429_responses_as_valid_waitable(self):
        """Test that 429 responses are valid and contain proper information."""
        client = TestClient(app)
        
        # Create a user and exhaust the global limit
        user = self.create_test_user(client)
        
        # Generate all 77 tokens
        for i in range(77):
            result = self.generate_coupon_with_token(client, user["access_token"])
            assert result["status_code"] == 200, f"Token {i+1} generation failed"
        
        # Next request should return 429 with proper message
        result = self.generate_coupon_with_token(client, user["access_token"])
        
        assert result["status_code"] == 429, "Should return 429 when limit is reached"
        
        # Verify 429 response content
        error_detail = result["data"]
        assert "limit reached" in error_detail.lower(), "429 should mention limit reached"
        assert "77" in error_detail or "maximum" in error_detail.lower(), "429 should mention limit"

    @pytest.mark.asyncio
    async def test_atomic_race_condition_prevention(self):
        """Test that concurrent requests can't exceed the 77-token limit."""
        client = TestClient(app)
        
        # Create users for concurrent testing
        users = [self.create_test_user(client) for _ in range(20)]
        
        # Track all successful tokens across all threads
        successful_tokens_lock = threading.Lock()
        successful_tokens = []
        
        def generate_tokens_concurrently(user_data):
            """Generate tokens for a single user concurrently."""
            user_tokens = []
            
            # Each user tries to generate multiple tokens rapidly
            for attempt in range(10):
                result = self.generate_coupon_with_token(
                    client, user_data["access_token"]
                )
                
                if result["status_code"] == 200:
                    user_tokens.append(result["data"])
                    
                    with successful_tokens_lock:
                        successful_tokens.append(result["data"])
                
                # Minimal delay to create race conditions
                time.sleep(0.001)
            
            return user_tokens
        
        # Run all users concurrently
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(generate_tokens_concurrently, user) for user in users]
            results = [future.result() for future in as_completed(futures)]
        
        # CRITICAL: Total tokens should never exceed 77
        assert len(successful_tokens) <= 77, f"Race condition detected! Got {len(successful_tokens)} tokens"
        
        # If we have 77 tokens, verify final state
        if len(successful_tokens) == 77:
            stats_response = client.get("/stats")
            assert stats_response.status_code == 200
            stats = stats_response.json()
            assert stats["tokens_issued"] == 77
            assert stats["limit_reached"] is True

    @pytest.mark.asyncio
    async def test_performance_benchmark_rps(self):
        """Benchmark the service for RPS performance."""
        client = TestClient(app)
        
        # Create users for benchmarking
        users = [self.create_test_user(client) for _ in range(50)]
        
        request_times = []
        successful_requests = 0
        failed_requests = 0
        
        def benchmark_request(user_data):
            """Single request benchmark function."""
            start_time = time.time()
            result = self.generate_coupon_with_token(
                client, user_data["access_token"]
            )
            end_time = time.time()
            
            request_time = end_time - start_time
            
            if result["status_code"] == 200:
                return True, request_time
            elif result["status_code"] == 429:
                return False, request_time
            else:
                return False, request_time
        
        # Run benchmark
        start_benchmark = time.time()
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(benchmark_request, user) for user in users]
            
            for future in as_completed(futures):
                success, request_time = future.result()
                request_times.append(request_time)
                
                if success:
                    successful_requests += 1
                else:
                    failed_requests += 1
        
        end_benchmark = time.time()
        
        # Calculate metrics
        total_time = end_benchmark - start_benchmark
        total_requests = successful_requests + failed_requests
        rps = total_requests / total_time if total_time > 0 else 0
        
        # Response time statistics
        if request_times:
            avg_response_mode = statistics.mean(request_times) * 1000  # ms
            p95_response_time = statistics.quantiles(request_times, n=20)[18] * 1000  # 95th percentile
            min_response_time = min(request_times) * 1000
            max_response_time = max(request_times) * 1000
        else:
            avg_response_time = p95_response_time = min_response_time = max_response_time = 0
        
        print(f"\nPerformance Benchmark:")
        print(f"Total requests: {total_requests}")
        print(f"Successful: {successful_requests}")
        print(f"Failed (429): {failed_requests}")
        print(f"Total time: {total_time:.2f}s")
        print(f"RPS: {rps:.2f}")
        print(f"Avg response time: {avg_response_time:.2f}ms")
        print(f"P95 response time: {p95_response_time:.2f}ms")
        print(f"Min response time: {min_response_time:.2f}ms")
        print(f"Max response time: {max_response_time:.2f}ms")
        
        # Performance assertions
        assert total_requests >= 77, "Should process at least 77 requests"
        assert successful_requests == 77, f"Expected exactly 77 successful tokens, got {successful_requests}"
        
        # RPS should be reasonable (adjust based on your infrastructure)
        assert rps > 5, f"RPS too low: {rps:.2f}, should be > 5 RPS"
        
        # Response times should be reasonable (adjust based on your requirements)
        assert avg_response_time < 1000, f"Average response time too high: {avg_response_time:.2f}ms"

    def test_redis_atomic_operations(self):
        """Test Redis atomic operations directly."""
        import asyncio
        
        async def test_redis_atomic():
            await redis_manager.initialize()
            
            # Test atomic increment with limit
            result = await redis_manager.atomic_increment_with_limit(
                "test_counter", 5
            )
            
            # Test multiple atomic increments
            results = []
            for i in range(10):
                result = await redis_manager.atomic_increment_with_limit(
                    "test_counter", 3
                )
                results.append(result)
            
            # Cleanup
            await redis_manager.delete("test_counter")
            
            return results
        
        # Run async test
        results = asyncio.run(test_redis_atomic())
        
        # Verify atomic behavior
        successful_increments = sum(1 for count, success in results if success)
        assert successful_increments <= 3, "Atomic limit should be respected"

    @pytest.mark.asyncio
    async def test_stress_test_with_mixed_scenarios(self):
        """Comprehensive stress test mixing different scenarios."""
        client = TestClient(app)
        
        # Create a large number of users
        users = [self.create_test_user(client) for _ in range(150)]
        
        successful_tokens = []
        thread_local_storage = threading.local()
        
        def stress_user(user_data):
            """Stress test for a single user."""
            user_tokens = []
            user_id = user_data["user_id"]
            
            # Each user tries multiple approaches
            # 1. Rapid-fire requests
            for _ in range(5):
                result = self.generate_coupon_with_token(client, user_data["access_token"])
                if result["status_code"] == 200:
                    user_tokens.append(result["data"])
                elif result["status_code"] == 429:
                    break  # Expected when limit reached
            
            # 2. Small delays between requests
            time.sleep(0.01)
            result = self.generate_coupon_with_token(client, user_data["access_token"])
            if result["status_code"] == 200:
                user_tokens.append(result["data"])
            
            # 3. One more attempt
            time.sleep(0.05)
            result = self.generate_coupon_with_token(client, user_data["access_token"])
            if result["status_code"] == 200:
                user_tokens.append(result["data"])
            
            return user_tokens
        
        # Run stress test
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(stress_user, user) for user in users]
            
            for future in as_completed(futures):
                user_tokens = future.result()
                successful_tokens.extend(user_tokens)
        
        end_time = time.time()
        
        print(f"\nStress Test Results:")
        print(f"Total successful tokens: {len(successful_tokens)}")
        print(f"Execution time: {end_time - start_time:.2f}s")
        
        # CRITICAL: Never exceed 77 tokens
        assert len(successful_tokens) <= 77, f"Stress test failed! Got {len(successful_tokens)} tokens"
        
        # If we reached the limit, verify final state
        if len(successful_tokens) == 77:
            stats_response = client.get("/stats")
            assert stats_response.status_code == 200
            stats = stats_response.json()
            assert stats["tokens_issued"] == 77
            assert stats["limit_reached"] is True