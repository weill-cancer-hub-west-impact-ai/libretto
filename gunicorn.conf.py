# gunicorn.conf.py
# Production Gunicorn configuration for Uvicorn workers
# Only used for non-Docker deployment

import multiprocessing
import os

# Server socket binding
bind = os.getenv("BIND", "0.0.0.0:8000")
backlog = 2048  # Maximum pending connections queue

# Worker processes
workers = int(os.getenv("WORKERS", 2))
worker_class = "uvicorn.workers.UvicornWorker"  # ASGI worker
worker_connections = 100  # Max simultaneous clients per worker
max_requests = 1000  # Restart worker after this many requests
max_requests_jitter = 1000  # Randomize max_requests to avoid thundering herd
preload = True

# Timeouts
timeout = 60  # Worker timeout for handling a request
graceful_timeout = 30  # Time to finish requests during shutdown
keepalive = 5  # Seconds to wait for requests on keep-alive connection

# Process naming
proc_name = "libretto-server"  # Process name in ps output

# Server mechanics
daemon = False  # Do not daemonize (let systemd handle this)
pidfile = None  # PID file path (optional)
user = None  # User to run workers as
group = None  # Group to run workers as
tmp_upload_dir = None  # Temp directory for uploads

# Logging configuration
accesslog = "logs/server.access.log"  # Log to stdout for container environments
errorlog = "logs/server.error.log"  # Log errors to stderr
loglevel = os.getenv("LOG_LEVEL", "info")
capture_output = True
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Security settings
limit_request_line = 4094  # Max HTTP request line size
limit_request_fields = 100  # Max number of headers
limit_request_field_size = 8190  # Max size of each header
