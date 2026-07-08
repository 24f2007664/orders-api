from fastapi import FastAPI, Header, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import time
import base64

app = FastAPI()

# ------------------------
# CORS
# ------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://exam.sanand.workers.dev",
        "https://sanand.workers.dev",
        "http://localhost",
        "http://127.0.0.1",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# ------------------------
# Constants
# ------------------------

TOTAL_ORDERS = 50
RATE_LIMIT = 17
WINDOW = 10

# ------------------------
# Storage
# ------------------------

orders = {}
idempotency_store = {}
next_order_id = 1

client_requests = {}

# ------------------------
# Rate Limiter Middleware
# ------------------------

@app.middleware("http")
async def rate_limit(request: Request, call_next):

    client = request.headers.get("X-Client-Id")

    if client:

        now = time.time()

        if client not in client_requests:
            client_requests[client] = []

        # Keep only timestamps within last 10 seconds
        client_requests[client] = [
            t for t in client_requests[client]
            if now - t < WINDOW
        ]

        if len(client_requests[client]) >= RATE_LIMIT:
            retry = max(1, int(WINDOW - (now - client_requests[client][0])) + 1)

            return Response(
                content="Too Many Requests",
                status_code=429,
                headers={"Retry-After": str(retry)}
            )

        client_requests[client].append(now)

    return await call_next(request)

# ------------------------
# POST /orders
# ------------------------

@app.post("/orders")
def create_order(
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    global next_order_id

    if idempotency_key in idempotency_store:
        response.status_code = 200
        return idempotency_store[idempotency_key]

    order = {
        "id": next_order_id,
        "status": "created"
    }

    orders[next_order_id] = order
    idempotency_store[idempotency_key] = order

    next_order_id += 1

    response.status_code = 201
    return order

# ------------------------
# GET /orders
# ------------------------

@app.get("/orders")
def list_orders(limit: int = 10, cursor: Optional[str] = None):

    start = 1

    if cursor:
        try:
            start = int(base64.b64decode(cursor).decode())
        except Exception:
            start = 1

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = [
        {"id": i, "status": "catalog"}
        for i in range(start, end + 1)
    ]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(
            str(end + 1).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }

# ------------------------
# Home
# ------------------------

@app.get("/")
def home():
    return {"message": "Orders API Running"}