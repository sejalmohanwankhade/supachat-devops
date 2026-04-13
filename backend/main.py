"""
SupaChat Backend - FastAPI application for conversational analytics
"""
import os
import time
import json
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
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
REQUEST_COUNT = Counter("supachat_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("supachat_request_duration_seconds", "Request latency", ["endpoint"])
ACTIVE_CONNECTIONS = Gauge("supachat_active_connections", "Active connections")
QUERY_COUNT = Counter("supachat_queries_total", "Total NL queries processed", ["status"])
LLM_LATENCY = Histogram("supachat_llm_duration_seconds", "LLM processing latency")

# ─── Configuration ───────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# ─── Models ──────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []

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
        # Return demo data when Supabase is not configured
        return _demo_data(sql)

    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    # Use Supabase RPC for raw SQL execution
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/execute_query",
            headers=headers,
            json={"query_text": sql},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Supabase error: {resp.text}")
        return resp.json()


def _demo_data(sql: str) -> List[Dict[str, Any]]:
    """Return realistic demo data when Supabase is not configured."""
    sql_lower = sql.lower()

    if "topic" in sql_lower or "trending" in sql_lower:
        return [
            {"topic": "Artificial Intelligence", "views": 45230, "articles": 38, "avg_read_time": 7.2},
            {"topic": "Machine Learning", "views": 38120, "articles": 31, "avg_read_time": 8.1},
            {"topic": "Cloud Computing", "views": 29870, "articles": 24, "avg_read_time": 6.5},
            {"topic": "Cybersecurity", "views": 24560, "articles": 19, "avg_read_time": 9.3},
            {"topic": "DevOps", "views": 21340, "articles": 17, "avg_read_time": 7.8},
            {"topic": "Web3 & Blockchain", "views": 18920, "articles": 15, "avg_read_time": 5.9},
            {"topic": "Data Engineering", "views": 16430, "articles": 13, "avg_read_time": 8.7},
            {"topic": "Open Source", "views": 14210, "articles": 11, "avg_read_time": 6.1},
        ]
    elif "daily" in sql_lower or "trend" in sql_lower or "date" in sql_lower:
        import datetime
        rows = []
        base = datetime.date.today()
        for i in range(30, 0, -1):
            d = base - datetime.timedelta(days=i)
            rows.append({
                "date": d.isoformat(),
                "views": 1200 + int(800 * abs(__import__("math").sin(i * 0.4))) + i * 15,
                "unique_visitors": 800 + int(400 * abs(__import__("math").cos(i * 0.3))),
                "articles_published": max(0, 3 + (i % 5) - 2),
            })
        return rows
    elif "engag" in sql_lower or "compar" in sql_lower:
        return [
            {"topic": "AI", "avg_likes": 234, "avg_comments": 45, "avg_shares": 89, "engagement_rate": 12.4},
            {"topic": "ML", "avg_likes": 198, "avg_comments": 38, "avg_shares": 72, "engagement_rate": 10.8},
            {"topic": "DevOps", "avg_likes": 167, "avg_comments": 29, "avg_shares": 54, "engagement_rate": 9.2},
            {"topic": "Security", "avg_likes": 145, "avg_comments": 52, "avg_shares": 43, "engagement_rate": 11.1},
            {"topic": "Cloud", "avg_likes": 189, "avg_comments": 31, "avg_shares": 67, "engagement_rate": 9.8},
        ]
    elif "author" in sql_lower:
        return [
            {"author": "Sarah Chen", "articles": 24, "total_views": 89420, "avg_engagement": 11.2},
            {"author": "Marcus Rivera", "articles": 19, "total_views": 72310, "avg_engagement": 10.8},
            {"author": "Priya Patel", "articles": 22, "total_views": 68540, "avg_engagement": 12.1},
            {"author": "Alex Thompson", "articles": 15, "total_views": 54230, "avg_engagement": 9.7},
            {"author": "Jin-woo Park", "articles": 18, "total_views": 49870, "avg_engagement": 10.3},
        ]
    else:
        return [
            {"metric": "Total Articles", "value": 247, "change_pct": 12.3},
            {"metric": "Total Views (30d)", "value": 284930, "change_pct": 18.7},
            {"metric": "Avg Read Time", "value": "7.4 min", "change_pct": -2.1},
            {"metric": "Active Authors", "value": 34, "change_pct": 5.9},
            {"metric": "Topics Covered", "value": 18, "change_pct": 0.0},
        ]


# ─── NL → SQL Translation ─────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are SupaChat, an expert data analyst for a blog analytics database.

DATABASE SCHEMA:
- articles(id, title, topic, author_id, published_at, read_time_minutes, word_count)
- article_metrics(id, article_id, date, views, unique_visitors, avg_time_on_page)
- topics(id, name, slug, created_at)
- authors(id, name, email, bio, created_at)
- comments(id, article_id, author_name, created_at, sentiment)
- social_shares(id, article_id, platform, shared_at)
- likes(id, article_id, created_at)

Always respond with a JSON object containing:
{
  "sql": "SELECT ... FROM ...",
  "chart_type": "bar|line|pie|scatter|area|none",
  "chart_x": "column_name_for_x_axis",
  "chart_y": "column_name_for_y_axis",
  "chart_label": "human readable label",
  "narrative": "2-3 sentence explanation of what this query shows and any insights"
}

Rules:
- Write clean, efficient PostgreSQL SQL
- Always include ORDER BY for meaningful results
- LIMIT results to 20 rows max unless asked otherwise
- For time series: use date column on X axis
- For comparisons: use category column on X axis  
- Choose chart_type based on the data shape
- narrative should be insightful, not just describe the query
"""

async def nl_to_sql(message: str, history: List[Dict]) -> Dict[str, Any]:
    """Convert natural language to SQL using Claude."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None
    
    if not client:
        # Demo mode: return pre-built queries
        return _demo_query(message)

    with LLM_LATENCY.time():
        messages = []
        for h in history[-6:]:  # last 3 turns
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

    text = response.content[0].text
    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])

    return json.loads(text)


def _demo_query(message: str) -> Dict[str, Any]:
    """Return demo query configs when LLM is not configured."""
    msg = message.lower()
    if "trending" in msg or "topic" in msg:
        return {
            "sql": "SELECT topic, COUNT(*) as articles, SUM(m.views) as views FROM articles a JOIN article_metrics m ON a.id = m.article_id WHERE m.date >= NOW() - INTERVAL '30 days' GROUP BY topic ORDER BY views DESC LIMIT 10",
            "chart_type": "bar",
            "chart_x": "topic",
            "chart_y": "views",
            "chart_label": "Views by Topic",
            "narrative": "This shows the most-viewed topics over the last 30 days. AI and Machine Learning consistently dominate traffic, suggesting your audience has strong appetite for technical content in those areas.",
        }
    elif "daily" in msg or "trend" in msg:
        return {
            "sql": "SELECT date, SUM(views) as views, SUM(unique_visitors) as unique_visitors FROM article_metrics WHERE date >= NOW() - INTERVAL '30 days' GROUP BY date ORDER BY date",
            "chart_type": "area",
            "chart_x": "date",
            "chart_y": "views",
            "chart_label": "Daily Views Trend",
            "narrative": "Daily views show a clear upward trend with weekend dips. The spike around mid-month aligns with a viral AI article that was shared widely on social media.",
        }
    elif "engag" in msg:
        return {
            "sql": "SELECT t.name as topic, AVG(l.count) as avg_likes, AVG(c.count) as avg_comments, AVG(s.count) as avg_shares FROM topics t JOIN articles a ON t.id = a.topic_id LEFT JOIN ... GROUP BY t.name ORDER BY avg_likes DESC",
            "chart_type": "bar",
            "chart_x": "topic",
            "chart_y": "avg_likes",
            "chart_label": "Engagement by Topic",
            "narrative": "Security and AI articles generate the highest engagement rates. Security content drives more comments (community discussion), while AI drives more shares (broader appeal).",
        }
    elif "author" in msg:
        return {
            "sql": "SELECT au.name as author, COUNT(a.id) as articles, SUM(m.views) as total_views FROM authors au JOIN articles a ON au.id = a.author_id JOIN article_metrics m ON a.id = m.article_id GROUP BY au.name ORDER BY total_views DESC LIMIT 10",
            "chart_type": "bar",
            "chart_x": "author",
            "chart_y": "total_views",
            "chart_label": "Views by Author",
            "narrative": "Top authors show that quality trumps quantity. Sarah Chen's 24 articles generate more total views than several authors with more published pieces, suggesting strong topic selection and writing quality.",
        }
    else:
        return {
            "sql": "SELECT 'Total Articles' as metric, COUNT(*) as value FROM articles UNION ALL SELECT 'Total Views (30d)', SUM(views) FROM article_metrics WHERE date >= NOW() - INTERVAL '30 days'",
            "chart_type": "bar",
            "chart_x": "metric",
            "chart_y": "value",
            "chart_label": "Overview Metrics",
            "narrative": "Here's an overview of your blog's key performance metrics. The platform shows healthy growth with strong viewer retention and consistent publishing cadence.",
        }


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse)
async def health():
    supabase_ok = bool(SUPABASE_URL and SUPABASE_ANON_KEY)
    llm_ok = bool(ANTHROPIC_API_KEY)
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        supabase_connected=supabase_ok,
        llm_available=llm_ok,
        uptime_seconds=time.time() - START_TIME,
    )


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/chat")
async def chat(body: ChatMessage):
    import uuid
    query_id = str(uuid.uuid4())[:8]
    t0 = time.time()

    try:
        # Step 1: NL → SQL
        plan = await nl_to_sql(body.message, body.history or [])

        # Step 2: Execute SQL
        data = await supabase_query(plan["sql"])

        # Step 3: Build response
        columns = list(data[0].keys()) if data else []
        chart_config = None
        if plan.get("chart_type") and plan["chart_type"] != "none" and data:
            chart_config = {
                "type": plan["chart_type"],
                "x": plan.get("chart_x", columns[0] if columns else ""),
                "y": plan.get("chart_y", columns[1] if len(columns) > 1 else ""),
                "label": plan.get("chart_label", "Results"),
            }

        duration = (time.time() - t0) * 1000
        QUERY_COUNT.labels(status="success").inc()
        logger.info("query_processed", query_id=query_id, duration_ms=duration)

        return QueryResult(
            sql=plan["sql"],
            data=data,
            columns=columns,
            chart_config=chart_config,
            narrative=plan.get("narrative", "Query executed successfully."),
            query_id=query_id,
            duration_ms=round(duration, 1),
        )

    except Exception as e:
        QUERY_COUNT.labels(status="error").inc()
        logger.error("query_failed", query_id=query_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/suggestions")
async def suggestions():
    return {
        "suggestions": [
            "Show top trending topics in last 30 days",
            "Compare article engagement by topic",
            "Plot daily views trend for AI articles",
            "Who are the top 5 authors by total views?",
            "Show me articles with highest comment activity",
            "What's the average read time per topic?",
            "Show weekly publishing frequency by author",
            "Compare mobile vs desktop traffic this month",
        ]
    }


@app.get("/api/schema")
async def schema():
    return {
        "tables": [
            {"name": "articles", "columns": ["id", "title", "topic", "author_id", "published_at", "read_time_minutes", "word_count"]},
            {"name": "article_metrics", "columns": ["id", "article_id", "date", "views", "unique_visitors", "avg_time_on_page"]},
            {"name": "topics", "columns": ["id", "name", "slug", "created_at"]},
            {"name": "authors", "columns": ["id", "name", "email", "bio", "created_at"]},
            {"name": "comments", "columns": ["id", "article_id", "author_name", "created_at", "sentiment"]},
            {"name": "social_shares", "columns": ["id", "article_id", "platform", "shared_at"]},
            {"name": "likes", "columns": ["id", "article_id", "created_at"]},
        ]
    }