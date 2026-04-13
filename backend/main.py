"""
SupaChat Backend - FastAPI application for conversational analytics
"""
import os
import time
import json
import uuid
import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from starlette.responses import Response
import structlog

# ─── Logging ────────────────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

# ─── Prometheus Metrics ──────────────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "supachat_requests_total",
    "Total requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "supachat_request_duration_seconds",
    "Request latency",
    ["endpoint"],
)

ACTIVE_CONNECTIONS = Gauge(
    "supachat_active_connections",
    "Active connections",
)

QUERY_COUNT = Counter(
    "supachat_queries_total",
    "Total NL queries processed",
    ["status"],
)

LLM_LATENCY = Histogram(
    "supachat_llm_duration_seconds",
    "LLM processing latency",
)

# ─── Configuration ───────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")

# ─── Models ──────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None


class QueryResult(BaseModel):
    sql: str
    data: List[Dict[str, Any]]
    columns: List[str]
    chart_config: Optional[Dict[str, Any]] = None
    narrative: str
    query_id: str
    duration_ms: float


class HealthResponse(BaseModel):
    status: str
    version: str
    supabase_connected: bool
    llm_available: bool
    uptime_seconds: float


# ─── App Lifecycle ───────────────────────────────────────────────────────────
START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("supachat_starting", version="1.0.0")
    yield
    logger.info("supachat_stopping")


app = FastAPI(
    title="SupaChat API",
    description="Conversational analytics on Supabase PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Middleware ──────────────────────────────────────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ACTIVE_CONNECTIONS.inc()
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()

    REQUEST_LATENCY.labels(endpoint=request.url.path).observe(duration)
    ACTIVE_CONNECTIONS.dec()
    return response


# ─── Supabase MCP Client ─────────────────────────────────────────────────────
async def supabase_query(sql: str) -> List[Dict[str, Any]]:
    """Execute SQL against Supabase REST API (PostgREST)."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return _demo_data(sql)

    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/execute_query",
            headers=headers,
            json={"query_text": sql},
        )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Supabase error: {resp.text}",
            )
        return resp.json()


def _demo_data(sql: str) -> List[Dict[str, Any]]:
    sql_lower = sql.lower()

    if "topic" in sql_lower or "trending" in sql_lower:
        return [
            {"topic": "Artificial Intelligence", "views": 45230},
            {"topic": "Machine Learning", "views": 38120},
        ]
    elif "daily" in sql_lower or "trend" in sql_lower:
        rows = []
        base = datetime.date.today()
        for i in range(30, 0, -1):
            d = base - datetime.timedelta(days=i)
            rows.append(
                {
                    "date": d.isoformat(),
                    "views": 1200 + i * 10,
                }
            )
        return rows

    return [{"metric": "Total Articles", "value": 247}]


# ─── NL → SQL Translation ─────────────────────────────────────────────────────
async def nl_to_sql(message: str, history: List[Dict]) -> Dict[str, Any]:
    client = (
        anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        if ANTHROPIC_API_KEY
        else None
    )

    if not client:
        return {"sql": "SELECT 1", "narrative": "Demo query"}

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": message}],
    )

    text = response.content[0].text.strip()
    return json.loads(text)


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        supabase_connected=bool(SUPABASE_URL),
        llm_available=bool(ANTHROPIC_API_KEY),
        uptime_seconds=time.time() - START_TIME,
    )


@app.get("/metrics")
async def metrics():
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.post("/api/chat")
async def chat(body: ChatMessage):
    query_id = str(uuid.uuid4())[:8]
    t0 = time.time()

    plan = await nl_to_sql(body.message, body.history or [])
    data = await supabase_query(plan["sql"])

    duration = (time.time() - t0) * 1000

    return QueryResult(
        sql=plan["sql"],
        data=data,
        columns=list(data[0].keys()) if data else [],
        narrative=plan.get("narrative", ""),
        query_id=query_id,
        duration_ms=round(duration, 1),
    )


@app.get("/api/suggestions")
async def suggestions():
    return {
        "suggestions": [
            "Show top trending topics",
            "Compare engagement",
            "Daily trends",
        ]
    }


@app.get("/api/schema")
async def schema():
    return {
        "tables": [
            {"name": "articles"},
            {"name": "authors"},
        ]
    }