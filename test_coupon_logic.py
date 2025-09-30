import asyncio
import httpx
import uuid
import multiprocessing
import time
from statistics import mean, median
from collections import defaultdict

BASE_URL = "http://localhost:8005"
REGISTER_ENDPOINT = f"{BASE_URL}/register"
COUPON_ENDPOINT = f"{BASE_URL}/generate-coupon"

# More conservative settings
CONCURRENCY_LIMIT = 10  # Reduced from 50
TIMEOUT = httpx.Timeout(60.0, connect=15.0)  # Increased timeout
MAX_RETRIES = 2
RETRY_DELAY = 1.0


async def register_and_get_token(client, idx: int, retry_count=0):
    """Register a new user and return JWT access token with retry logic."""
    email = f"user{idx}_{uuid.uuid4().hex[:6]}@example.com"
    payload = {
        "email": email,
        "password": "password123",
        "name": f"TestUser{idx}"
    }
    
    try:
        r = await client.post(REGISTER_ENDPOINT, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["access_token"], data["user"]["user_id"], None
    except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY * (retry_count + 1))
            return await register_and_get_token(client, idx, retry_count + 1)
        return None, None, f"Timeout after {retry_count + 1} attempts: {str(e)}"
    except httpx.HTTPStatusError as e:
        return None, None, f"HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return None, None, f"Unexpected error: {str(e)}"


async def generate_coupon(client, token: str):
    """Try to generate a coupon with a given JWT token."""
    start = time.perf_counter()
    
    try:
        r = await client.post(
            COUPON_ENDPOINT,
            headers={"Authorization": f"Bearer {token}"}
        )
        latency = time.perf_counter() - start

        if r.status_code == 200:
            return True, r.json(), latency, None
        else:
            return False, {"status": r.status_code}, latency, f"HTTP {r.status_code}"
    except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
        latency = time.perf_counter() - start
        return False, {}, latency, f"Timeout: {str(e)}"
    except Exception as e:
        latency = time.perf_counter() - start
        return False, {}, latency, f"Error: {str(e)}"


async def user_flow(idx: int, sem: asyncio.Semaphore):
    """One full user flow: register + generate coupon."""
    async with sem:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Registration
            token, user_id, reg_error = await register_and_get_token(client, idx)
            
            if reg_error:
                return {
                    "success": False,
                    "user_id": None,
                    "result": {},
                    "latency": 0,
                    "error": f"Registration failed: {reg_error}",
                    "stage": "registration"
                }
            
            # Coupon generation
            success, result, latency, coupon_error = await generate_coupon(client, token)
            
            return {
                "success": success,
                "user_id": user_id,
                "result": result,
                "latency": latency,
                "error": coupon_error,
                "stage": "coupon" if not coupon_error else "coupon_failed"
            }


async def run_users(start_idx: int, num_users: int):
    """Run many users concurrently inside one process."""
    sem = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = [user_flow(start_idx + i, sem) for i in range(num_users)]
    
    # Use return_exceptions to prevent one failure from stopping everything
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to error results
    processed_results = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            processed_results.append({
                "success": False,
                "user_id": None,
                "result": {},
                "latency": 0,
                "error": f"Unhandled exception: {str(r)}",
                "stage": "exception"
            })
        else:
            processed_results.append(r)
    
    return processed_results


def worker(start_idx: int, num_users: int, result_queue):
    """Worker process that runs a batch of users."""
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    
    try:
        results = asyncio.run(run_users(start_idx, num_users))
    except Exception as e:
        result_queue.put({
            "success": 0,
            "failure": num_users,
            "latencies": [],
            "errors": {f"Process error": num_users},
            "sample": []
        })
        return

    success_count = sum(1 for r in results if r["success"])
    failure_count = num_users - success_count
    latencies = [r["latency"] for r in results if r["success"]]
    
    # Categorize errors
    error_counts = defaultdict(int)
    for r in results:
        if not r["success"] and r.get("error"):
            error_type = r["error"].split(":")[0]  # Get error prefix
            error_counts[error_type] += 1

    result_queue.put({
        "success": success_count,
        "failure": failure_count,
        "latencies": latencies,
        "errors": dict(error_counts),
        "sample": results[:3]  # Sample results
    })


def main(total_users: int = 100, processes: int = 2):
    """Main runner that spawns processes and aggregates results."""
    users_per_process = total_users // processes
    result_queue = multiprocessing.Queue()
    jobs = []

    print(f"Starting load test: {total_users} users across {processes} processes")
    print(f"Concurrency limit per process: {CONCURRENCY_LIMIT}")
    print(f"Timeout: {TIMEOUT.read}s\n")

    start_time = time.time()

    for i in range(processes):
        start_idx = i * users_per_process
        p = multiprocessing.Process(
            target=worker,
            args=(start_idx, users_per_process, result_queue)
        )
        jobs.append(p)
        p.start()

    for p in jobs:
        p.join()

    total_success, total_failure = 0, 0
    all_latencies = []
    all_errors = defaultdict(int)

    while not result_queue.empty():
        result = result_queue.get()
        total_success += result["success"]
        total_failure += result["failure"]
        all_latencies.extend(result["latencies"])
        
        for error_type, count in result["errors"].items():
            all_errors[error_type] += count

    elapsed = time.time() - start_time
    
    print("=" * 60)
    print(f"LOAD TEST RESULTS")
    print("=" * 60)
    print(f"Total users simulated: {total_users}")
    print(f"Successful coupons: {total_success} ({total_success/total_users*100:.1f}%)")
    print(f"Failures: {total_failure} ({total_failure/total_users*100:.1f}%)")
    print(f"Elapsed time: {elapsed:.2f}s")
    print(f"Throughput: {total_users/elapsed:.2f} requests/second")

    if all_errors:
        print(f"\nError breakdown:")
        for error_type, count in sorted(all_errors.items(), key=lambda x: -x[1]):
            print(f"  {error_type}: {count} ({count/total_users*100:.1f}%)")

    if all_latencies:
        print(f"\nLatency statistics (successful requests only):")
        print(f"  Avg: {mean(all_latencies):.3f}s")
        print(f"  Median (p50): {median(all_latencies):.3f}s")
        print(f"  Min: {min(all_latencies):.3f}s")
        print(f"  Max: {max(all_latencies):.3f}s")
        sorted_latencies = sorted(all_latencies)
        for perc in [0.9, 0.95, 0.99]:
            idx = min(int(len(sorted_latencies) * perc), len(sorted_latencies) - 1)
            print(f"  p{int(perc*100)}: {sorted_latencies[idx]:.3f}s")
    else:
        print("\nNo successful requests - cannot calculate latency statistics")
    
    print("=" * 60)


if __name__ == "__main__":
    # Start with smaller load and gradually increase
    main(total_users=100, processes=2)