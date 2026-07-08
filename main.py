from fastapi import FastAPI, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import time
import base64

app = FastAPI()

# ------------------------
# Enable CORS
# ------------------------


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# Storage
# ------------------------

orders = {}
idempotency_store = {}

next_order_id = 1

TOTAL_ORDERS = 50
RATE_LIMIT = 17
WINDOW = 10

client_requests = {}

# ------------------------
# POST /orders
# ------------------------

@app.post("/orders", status_code=201)
def create_order(idempotency_key: str = Header(..., alias="Idempotency-Key")):
    global next_order_id

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": next_order_id,
        "status": "created"
    }

    orders[next_order_id] = order
    idempotency_store[idempotency_key] = order

    next_order_id += 1

    return order

# ------------------------
# GET /orders
# ------------------------

@app.get("/orders")
def list_orders(limit: int = 10, cursor: Optional[str] = None):

    start = 1

    if cursor:
        start = int(base64.b64decode(cursor).decode())

    end = min(start + limit - 1, TOTAL_ORDERS)

    items = []

    for i in range(start, end + 1):
        items.append({
            "id": i,
            "status": "catalog"
        })

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
# Rate Limiting
# ------------------------

@app.middleware("http")
async def rate_limit(request, call_next):

    client = request.headers.get("X-Client-Id")
    

    if client:

        now = time.time()

        if client not in client_requests:
            client_requests[client] = []

        # Keep only requests from last 10 seconds
        client_requests[client] = [
            t for t in client_requests[client]
            if now - t < WINDOW
        ]

        

        if len(client_requests[client]) >= RATE_LIMIT:

            retry = WINDOW - (now - client_requests[client][0])

            

            return Response(
                content="Too Many Requests",
                status_code=429,
                headers={
                    "Retry-After": str(int(retry) + 1)
                }
            )

        client_requests[client].append(now)

        

    response = await call_next(request)

    return response

# ------------------------
# Home
# ------------------------

@app.get("/")
def home():
    return {"message": "Orders API Running"}