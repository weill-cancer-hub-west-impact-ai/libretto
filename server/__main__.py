#!/usr/bin/env python3
"""
Entry point for the LLM Extract server service.

Starts the FastAPI server with uvicorn.
"""
import uvicorn
from uvicorn.config import LOGGING_CONFIG
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the LLM Extract server.")
    parser.add_argument("--reload", action="store_true", default=False, help="If set, auto-reload the server.")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    args = parser.parse_args()
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    uvicorn.run(
        "server.app:app",
        host="0.0.0.0",
        port=args.port,
        reload=args.reload,
        log_level="info"
    )