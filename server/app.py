"""FastAPI server to replace the SvelteKit API endpoints."""

from typing import Optional, List
import os
import redis
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from libretto.database import LLMExtractDatabase

# Import routers
from .routers import auth, projects, specs, patients, extractions

import logging
import json

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

# Global database connections
db: LLMExtractDatabase = None
redis_client: redis.Redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup database connections."""
    global db, redis_client

    # Initialize databases
    db_connection = os.getenv('INTERACTION_DB_CONNECTION', 'sqlite:///interactions.db')
    db = LLMExtractDatabase(db_connection, enable_wal=True)

    # Initialize Redis client using environment variables
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)

    # Set database connections in routers
    auth.set_database(db)
    projects.set_database(db)
    specs.set_database(db)
    patients.set_database(db)
    extractions.set_database(db)
    extractions.set_redis_client(redis_client)

    logger.info(f"Database connections:")
    logger.info(f"  - Interaction database: {db_connection}")
    yield

    # Cleanup
    if db:
        db.close()
    if redis_client:
        redis_client.close()


app = FastAPI(
    title="LLM Extract API",
    description="FastAPI server replacing SvelteKit API endpoints",
    lifespan=lifespan
)

# Include routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(specs.router)
app.include_router(patients.router)
app.include_router(extractions.router)

class ViewLogRequest(BaseModel):
    """Request model for logging page views."""
    page: str
    projectID: int
    patientID: Optional[str] = None
    noteID: Optional[str] = None
    specID: Optional[str] = None
    comparisonSpecs: Optional[List[str]] = None

# Logging endpoints
@app.post("/api/logs/pageview")
async def log_page_view(view_info: ViewLogRequest, current_user: auth.UserInfo = Depends(auth.get_current_user)):
    """Log page view information."""
    logger.info("PAGE VIEW: " + json.dumps({**view_info.model_dump(), "username": current_user.username, "timestamp": datetime.now(tz=timezone.utc).isoformat()}))
    return {"success": True}

# Mount static files - check for Docker path first, then local path
if os.path.exists("static"):
    # Docker deployment
    static_dir = "static"
elif os.path.exists("server/frontend/build"):
    # Local development from repository root
    static_dir = "server/frontend/build"
else:
    raise RuntimeError("Frontend build directory not found. Run 'npm run build' in server/frontend/")

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
