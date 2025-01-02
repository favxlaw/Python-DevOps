from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest
from fastapi.responses import Response
import uvicorn
import psutil  


app = FastAPI(
    title="Custom Monitoring Dashboard",
    description="A FastAPI-based dashboard for tracking application metrics",
)


origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Metrics
# Counter: Track the total number of HTTP requests by method, endpoint, and status code
http_request_counter = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

# Gauge: Track real-time system resource usage (e.g., active users)
active_users_gauge = Gauge(
    "active_users",
    "Number of active users on the platform"
)

# Gauge: Track CPU and memory usage
cpu_usage_gauge = Gauge("system_cpu_usage", "System CPU usage percentage")
memory_usage_gauge = Gauge("system_memory_usage", "System memory usage percentage")

# Histogram: Track request latency
request_latency_histogram = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"]
)

# Summary: Track response sizes
response_size_summary = Summary(
    "response_size_bytes",
    "Summary of HTTP response sizes in bytes",
    ["method", "endpoint"]
)

# Counter: Track total user logins by role
user_login_counter = Counter(
    "user_logins_total",
    "Total number of user logins",
    ["user_role"]
)

# Middleware to Collect Metrics
@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    method = request.method
    endpoint = request.url.path

    with request_latency_histogram.labels(method=method, endpoint=endpoint).time():
        try:
            response = await call_next(request)
        except Exception as e:
            # Increment error counter for exceptions
            status_code = 500
            http_request_counter.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
            raise e

        status_code = response.status_code
        http_request_counter.labels(method=method, endpoint=endpoint, status_code=status_code).inc()

        # Track response size
        response_size = len(response.body) if response.body else 0
        response_size_summary.labels(method=method, endpoint=endpoint).observe(response_size)

        return response

# Background Task for System Metrics
@app.on_event("startup")
async def collect_system_metrics():
    import asyncio

    async def track_system_metrics():
        while True:
            cpu_usage_gauge.set(psutil.cpu_percent())
            memory_usage_gauge.set(psutil.virtual_memory().percent)
            await asyncio.sleep(5)  # Update system metrics every 5 seconds

    asyncio.create_task(track_system_metrics())

# Simulated Endpoint for Business Metric
@app.post("/login")
def simulate_user_login(user_role: str):
    """
    Simulate a user login and increment the user login counter.
    """
    user_login_counter.labels(user_role=user_role).inc()
    return {"message": f"User with role '{user_role}' logged in successfully."}

# Health Check Endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Expose Metrics for Prometheus
@app.get("/metrics")
def metrics():
    content = generate_latest()
    return Response(content=content, media_type="text/plain")

# Root Endpoint
@app.get("/")
def read_root():
    return {"message": "Custom Monitoring Dashboard!"}



