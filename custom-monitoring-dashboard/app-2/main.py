from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest
from fastapi.responses import Response
import uvicorn
import aiohttp
import asyncio
import time
import ssl
import certifi
from datetime import datetime
from typing import Dict, List

app = FastAPI(
    title="Website Performance Monitor",
    description="Real-time website performance and availability monitoring",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONITORED_SITES = {
    "httpbin": {
        "url": "https://httpbin.org",
        "endpoints": ["/get", "/status/200", "/status/404"],
        "check_interval": 30  # seconds
    }
}

# Prometheus Metrics
website_availability = Gauge(
    "website_availability",
    "Website availability status (1=up, 0=down)",
    ["site", "endpoint"]
)

response_time = Histogram(
    "website_response_time_seconds",
    "Website response time in seconds",
    ["site", "endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

http_status_counter = Counter(
    "website_http_status_total",
    "Count of HTTP status codes",
    ["site", "endpoint", "status_code"]
)

ssl_expiry_gauge = Gauge(
    "ssl_certificate_expiry_days",
    "Days until SSL certificate expiry",
    ["site"]
)

endpoint_failures = Counter(
    "endpoint_failures_total",
    "Total number of endpoint failures",
    ["site", "endpoint", "reason"]
)

async def check_ssl_expiry(url: str, site_name: str):
    """Check SSL certificate expiry date"""
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        conn = ssl_context.wrap_socket(
            ssl.socket(),
            server_hostname=url.split("//")[1].split("/")[0]
        )
        conn.connect((url.split("//")[1].split("/")[0], 443))
        cert = conn.getpeercert()
        expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y GMT')
        days_until_expiry = (expiry_date - datetime.now()).days
        ssl_expiry_gauge.labels(site=site_name).set(days_until_expiry)
    except Exception as e:
        endpoint_failures.labels(
            site=site_name,
            endpoint="ssl_check",
            reason="ssl_error"
        ).inc()

async def monitor_endpoint(session: aiohttp.ClientSession, site_name: str, base_url: str, endpoint: str):
    """Monitor a specific endpoint"""
    url = f"{base_url}{endpoint}"
    try:
        start_time = time.time()
        async with session.get(url) as response:
            response_duration = time.time() - start_time
            
            # Record metrics
            website_availability.labels(
                site=site_name,
                endpoint=endpoint
            ).set(1 if response.status == 200 else 0)
            
            response_time.labels(
                site=site_name,
                endpoint=endpoint
            ).observe(response_duration)
            
            http_status_counter.labels(
                site=site_name,
                endpoint=endpoint,
                status_code=response.status
            ).inc()

    except Exception as e:
        website_availability.labels(
            site=site_name,
            endpoint=endpoint
        ).set(0)
        endpoint_failures.labels(
            site=site_name,
            endpoint=endpoint,
            reason=type(e).__name__
        ).inc()

async def monitor_websites():
    """Main monitoring loop"""
    async with aiohttp.ClientSession() as session:
        while True:
            tasks = []
            for site_name, config in MONITORED_SITES.items():
                # Monitor each endpoint
                for endpoint in config['endpoints']:
                    tasks.append(
                        monitor_endpoint(
                            session,
                            site_name,
                            config['url'],
                            endpoint
                        )
                    )
                # Check SSL expiry
                tasks.append(check_ssl_expiry(config['url'], site_name))
            
            await asyncio.gather(*tasks)
            await asyncio.sleep(min(site['check_interval'] for site in MONITORED_SITES.values()))

@app.on_event("startup")
async def start_monitoring():
    asyncio.create_task(monitor_websites())

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")

@app.get("/status")
async def status():
    """Return current monitoring status"""
    status_data = {}
    for site_name in MONITORED_SITES:
        status_data[site_name] = {
            "availability": website_availability.labels(site=site_name, endpoint="/").get(),
            "response_time": response_time.labels(site=site_name, endpoint="/")._sum.get(),
            "ssl_expiry_days": ssl_expiry_gauge.labels(site=site_name).get()
        }
    return status_data

