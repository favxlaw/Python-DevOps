from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import start_http_server, Counter
import uvicorn


app = FastAPI(
    title="Custom Monitoring Dashboard",
    description="A FastAPI-based dashboard for tracking application metrics",
)

request_counter = Counter("http_requests_total", "Total number of HTTP requests", ["method", "endpoint", "status_code"])
start_http_server(8001)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def collect_metrics(request: Request, call_next):
    method = request.method
    endpoint = request.url.path
    response = await call_next(request)
    status_code = response.status_code
    request_counter.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
    return response


@app.get("/")
def read_root():
    return{"message": "Custom Monitoring Dashboard!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
