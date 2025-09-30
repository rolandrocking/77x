# Coupon Token Service

A FastAPI microservice that generates coupon tokens with a hard limit of 77 total issued tokens. The service includes user management with PostgreSQL, authentication, and uses Redis for atomic counter operations to ensure concurrency safety. It provides JWT-based tokens with single-use enforcement.

## Features

- **User Management**: User registration, login, and authentication with PostgreSQL
- **Hard Limit**: Exactly 77 tokens can be issued total
- **User Limits**: Each user can have maximum 5 tokens
- **Concurrency Safe**: Uses Redis atomic increment operations
- **JWT Tokens**: Secure, signed tokens with expiration
- **Single-Use Enforcement**: Tokens can only be used once
- **Production Ready**: Comprehensive error handling, logging, and health checks
- **Docker Support**: Easy local testing with Docker Compose

## Architecture

### Database Design

- **PostgreSQL**: Stores user data with ACID compliance
- **Redis**: Handles atomic counters and token usage tracking
- **Hybrid Approach**: Best of both worlds - reliable user data + fast counters

### Token Limit Enforcement

The service enforces two types of limits using Redis atomic operations:

1. **Global Limit**: Maximum 77 tokens across all users
2. **User Limit**: Maximum 5 tokens per user
3. **Atomic Counters**: Uses Redis `INCR` operation to atomically increment counters
4. **Limit Check**: After increment, checks both user and global limits
5. **Rollback**: If any limit exceeded, decrements counters and returns 429 error
6. **Concurrency Safety**: Redis atomic operations prevent race conditions

### Token Properties

- **Format**: JWT tokens with HS256 algorithm
- **Expiration**: 24 hours from generation
- **Content**: Token number, user ID, issue timestamp, expiration
- **Single-Use**: Tracked in Redis with expiration matching token expiry
- **User Association**: Each token is linked to a specific user

## API Endpoints

### POST /register

Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "name": "John Doe"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "user_id": "uuid-here",
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

### POST /login

Login with existing user credentials.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "user_id": "uuid-here",
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

### POST /generate-coupon

Generates a new coupon token if under the limits. Requires authentication.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "expires_at": "2024-01-02T12:00:00",
  "token_number": 1,
  "remaining_tokens": 76,
  "user_id": "uuid-here"
}
```

**Response (429 Too Many Requests):**
```json
{
  "detail": "User token limit reached. Maximum of 5 tokens per user allowed."
}
```

**Response (429 Too Many Requests - Global Limit):**
```json
{
  "detail": "Global token limit reached. Maximum of 77 tokens allowed. 0 tokens remaining."
}
```

### POST /validate-token

Validates a coupon token and checks if it's been used.

**Parameters:**
- `token` (query): The JWT token to validate

**Response:**
```json
{
  "valid": true,
  "message": "Token is valid and unused",
  "token_number": 1,
  "user_id": "uuid-here"
}
```

### POST /use-token

Marks a token as used (single-use enforcement).

**Parameters:**
- `token` (query): The JWT token to use

**Response (200 OK):**
```json
{
  "message": "Token successfully used",
  "token_number": 1,
  "user_id": "uuid-here",
  "used_at": "2024-01-01T12:00:00"
}
```

**Response (409 Conflict):**
```json
{
  "detail": "Token has already been used"
}
```

### GET /stats

Returns current statistics about token usage.

**Response:**
```json
{
  "tokens_issued": 5,
  "tokens_remaining": 72,
  "max_tokens": 77,
  "max_tokens_per_user": 5,
  "limit_reached": false,
  "timestamp": "2024-01-01T12:00:00"
}
```

### GET /user-stats

Returns current user's token statistics. Requires authentication.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "user_id": "uuid-here",
  "user_tokens_issued": 2,
  "user_tokens_remaining": 3,
  "max_tokens_per_user": 5,
  "user_limit_reached": false,
  "timestamp": "2024-01-01T12:00:00"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "redis_connected": true,
  "timestamp": "2024-01-01T12:00:00"
}
```

## Quick Start

### Using Docker Compose (Recommended)

1. **Start the services:**
   ```bash
   docker-compose up -d
   ```

2. **Check health:**
   ```bash
   curl http://localhost:8005/health
   ```

3. **Register a user:**
   ```bash
   curl -X POST http://localhost:8005/register \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "password123", "name": "Test User"}'
   ```

4. **Generate a token (replace TOKEN with the access_token from registration):**
   ```bash
   curl -X POST http://localhost:8005/generate-coupon \
     -H "Authorization: Bearer TOKEN"
   ```

5. **View stats:**
   ```bash
   curl http://localhost:8005/stats
   ```

6. **View user stats:**
   ```bash
   curl http://localhost:8005/user-stats \
     -H "Authorization: Bearer TOKEN"
   ```

### Manual Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL:**
   ```bash
   # Using Docker
   docker run --name postgres -e POSTGRES_PASSWORD=password -e POSTGRES_DB=coupon_service -p 5432:5432 -d postgres:15-alpine
   
   # Or using local PostgreSQL
   createdb coupon_service
   ```

3. **Start Redis:**
   ```bash
   redis-server
   ```

4. **Set environment variables:**
   ```bash
   export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/coupon_service"
   export REDIS_HOST="localhost"
   export REDIS_PORT="6379"
   export JWT_SECRET="your-secret-key-change-in-production"
   ```

5. **Start the service:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## Testing the Token Limits

### Method 1: Sequential Testing
```bash
# First register and get auth token
AUTH_TOKEN=$(curl -s -X POST http://localhost:8005/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123", "name": "Test User"}' \
  | jq -r '.access_token')

# Generate tokens one by one
for i in {1..10}; do
  echo "Token $i:"
  curl -X POST http://localhost:8005/generate-coupon \
    -H "Authorization: Bearer $AUTH_TOKEN"
  echo -e "\n"
done
```

### Method 2: Test User Limits
```bash
# Register multiple users and test per-user limits
for i in {1..3}; do
  AUTH_TOKEN=$(curl -s -X POST http://localhost:8005/register \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"user$i@example.com\", \"password\": \"password123\", \"name\": \"User $i\"}" \
    | jq -r '.access_token')
  
  echo "User $i generating 6 tokens (should fail after 5):"
  for j in {1..6}; do
    curl -X POST http://localhost:8005/generate-coupon \
      -H "Authorization: Bearer $AUTH_TOKEN"
    echo
  done
done
```

### Method 3: Using the Test Suite
```bash
# Run the comprehensive test suite
pytest test_coupon_service.py -v
```

## Configuration

Environment variables:

- `DATABASE_URL`: PostgreSQL connection string (default: postgresql+asyncpg://postgres:password@localhost:5432/coupon_service)
- `REDIS_HOST`: Redis host (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database (default: 0)
- `JWT_SECRET`: JWT signing secret (default: your-secret-key-change-in-production)

## Database Schema

### Users Table
```sql
CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
```

## Error Handling

The service handles various edge cases:

- **PostgreSQL Unavailable**: Returns 500 Internal Server Error
- **Redis Unavailable**: Returns 503 Service Unavailable
- **Token Limit Reached**: Returns 429 Too Many Requests
- **Invalid Tokens**: Returns 400 Bad Request
- **Already Used Tokens**: Returns 409 Conflict
- **Expired Tokens**: Returns validation failure
- **Authentication Required**: Returns 401 Unauthorized

## Concurrency Safety

The service ensures concurrency safety through:

1. **PostgreSQL ACID**: User data with full ACID compliance
2. **Redis Atomic Operations**: `INCR` and `DECR` are atomic
3. **Counter Rollback**: If limit exceeded, counter is decremented
4. **Single-Use Tracking**: Redis SETEX with expiration
5. **Connection Pooling**: Both PostgreSQL and Redis with retry logic

## Monitoring and Logging

- **Structured Logging**: All operations are logged with context
- **Health Checks**: PostgreSQL and Redis connectivity monitoring
- **Statistics**: Real-time token usage tracking
- **Error Tracking**: Comprehensive error logging

## Production Considerations

1. **Change JWT Secret**: Set a strong, unique JWT_SECRET
2. **Database Security**: Use strong passwords and SSL connections
3. **Redis Persistence**: Configure Redis with AOF/RDB persistence
4. **Load Balancing**: Use multiple service instances behind a load balancer
5. **Monitoring**: Set up monitoring for PostgreSQL, Redis and service health
6. **Backup**: Regular PostgreSQL and Redis backups
7. **Security**: Use HTTPS in production
8. **Rate Limiting**: Consider additional rate limiting at the API gateway level
9. **Database Migrations**: Use Alembic for schema migrations

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx aiosqlite

# Run tests
pytest test_coupon_service.py -v

# Run with coverage
pytest test_coupon_service.py --cov=main --cov-report=html
```

### Database Migrations
```bash
# Initialize Alembic (if not already done)
alembic init alembic

# Create a new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head
```

### Code Quality
```bash
# Format code
black main.py database.py test_coupon_service.py

# Lint code
flake8 main.py database.py test_coupon_service.py

# Type checking
mypy main.py database.py
```

## Why PostgreSQL + Redis?

### PostgreSQL for User Data
- **ACID Compliance**: Ensures data integrity for user accounts
- **Complex Queries**: Easy to add user analytics and reporting
- **Scalability**: Handles large numbers of users efficiently
- **Backup & Recovery**: Robust backup and point-in-time recovery
- **Security**: Row-level security, encryption at rest

### Redis for Counters
- **Atomic Operations**: Perfect for concurrent counter increments
- **Performance**: Sub-millisecond operations for high concurrency
- **Expiration**: Built-in TTL for token usage tracking
- **Memory Efficiency**: Optimized for counter-like operations

### Hybrid Benefits
- **Best of Both Worlds**: Reliable user data + fast counters
- **Separation of Concerns**: User management vs. token tracking
- **Independent Scaling**: Scale databases based on their specific needs
- **Fault Tolerance**: If Redis fails, user data is still safe

## License

MIT License - see LICENSE file for details.