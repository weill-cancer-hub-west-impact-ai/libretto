#!/usr/bin/env python3
"""
Extraction service entry point.

Operates in two modes:

1. Redis worker mode (default): Listens for tasks via Redis pub/sub and processes
   them using multiprocessing workers. Requires REDIS_HOST/PORT/DB and QUEUE_NAME
   environment variables.

2. Single-job mode (when --project_id and --spec_id are both provided): Runs a
   one-shot extraction job using a thread pool, without Redis or multiprocessing.
   Patient selection is controlled by --patient_ids, --patient_tag, or defaults
   to all patients in the project.

Required environment variables:
- INTERACTION_DB_CONNECTION: Connection string for the extraction database
- SOURCE_DB_CONNECTION: Connection string for the source database (Redis mode only)

Optional environment variables (Redis mode):
- REDIS_HOST: Redis server host (default: localhost)
- REDIS_PORT: Redis server port (default: 6379)
- REDIS_DB: Redis database number (default: 0)
- QUEUE_NAME: Redis queue name to listen to (default: extraction_tasks)

Command-line arguments:
- --workers: Number of worker processes/threads (default: 1)
- --debug: Enable debug logging
- --project_id: Project ID for single-job mode
- --spec_id: Spec ID for single-job mode
- --patient_ids: Comma-separated patient IDs for single-job mode
- --patient_tag: Patient tag to select patients for single-job mode
- --overwrite: Rerun extraction for patients that already have results

"""
import argparse
import json
import logging
logging.basicConfig(level=logging.INFO)

import multiprocessing as mp
import os
import queue
import signal
import sys
import traceback
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
import redis

from .worker import worker_process, shutdown_event
from .worker_single_job import run_single_job
from libretto.database import LLMExtractDatabase

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def redis_listener(task_queue: mp.Queue, redis_host='localhost', redis_port=6379, redis_db=0, queue_name='extraction_tasks'):
    """
    Listen for Redis messages and put them into the multiprocessing queue.

    Args:
        task_queue: Multiprocessing queue to put tasks into
        redis_host: Redis server host
        redis_port: Redis server port
        redis_db: Redis database number
        queue_name: Redis queue name to listen to
    """
    logger = logging.getLogger(__name__)

    # Connect to Redis
    r = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(queue_name)

    logger.info(f"Listening for tasks on Redis with {redis_host}, {redis_port}, {redis_db}, queue: {queue_name}")

    try:
        while not shutdown_event.is_set():
            message = pubsub.get_message(timeout=1.0)
            if not message or message.get("type") != "message": continue
            try:
                task_data = json.loads(message.get("data"))
                logger.info(f"Received message: {task_data}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse task JSON: {e}")
            else:
                task_queue.put(task_data)
                logger.info(f"Queued task {task_data.get('task_id', 'unknown')}")
                
    except KeyboardInterrupt:
        logger.info("Redis listener interrupted")
    finally:
        logger.info("Redis listener shutting down")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_event.set()

if __name__ == '__main__':
    load_dotenv()

    parser = argparse.ArgumentParser(description='Extraction service')
    parser.add_argument('--workers', type=int, default=1,
                       help='Number of worker processes/threads (default: 1)')
    parser.add_argument('--debug', action='store_true', default=False,
                       help='Whether to print debug messages')
    parser.add_argument('--project_id', type=int, default=None,
                       help='Project ID for single-job mode (requires --spec_id)')
    parser.add_argument('--spec_id', type=str, default=None,
                       help='Spec ID for single-job mode (requires --project_id)')
    parser.add_argument('--patient_ids', type=str, default=None,
                       help='Comma-separated patient IDs to run on (single-job mode only)')
    parser.add_argument('--patient_tag', type=str, default=None,
                       help='Patient tag to select patients (single-job mode only)')
    parser.add_argument('--patient_sample_size', type=int, default=None,
                           help='Number of patients to randomly sample from the patients matching patient_ids or patient_tag (single-job mode only)')
    parser.add_argument('--overwrite', action='store_true', default=False,
                       help='Rerun extraction for patients that already have results')

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    if (args.project_id is None) != (args.spec_id is None):
        parser.error("--project_id and --spec_id must be specified together")

    if args.patient_ids is not None and args.patient_tag is not None:
        parser.error("--patient_ids and --patient_tag are mutually exclusive")

    db_conn = os.getenv('INTERACTION_DB_CONNECTION')
    if not db_conn:
        raise ValueError("INTERACTION_DB_CONNECTION environment variable is required")

    if args.project_id is not None:
        patient_ids = [p.strip() for p in args.patient_ids.split(',')] if args.patient_ids else None
        run_single_job(
            db_conn=db_conn,
            project_id=args.project_id,
            spec_id=args.spec_id,
            patient_ids=patient_ids,
            patient_tag=args.patient_tag,
            patient_sample_size=args.patient_sample_size,
            overwrite=args.overwrite,
            workers=args.workers,
        )
        sys.exit(0)

    source_db_connection = os.getenv('SOURCE_DB_CONNECTION')

    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    redis_db = int(os.getenv('REDIS_DB', '0'))
    queue_name = os.getenv('QUEUE_NAME', 'extraction_tasks')

    with LLMExtractDatabase(db_conn, enable_wal=True) as db:
        pass

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info(f"Starting extraction service with {args.workers} workers")
    logger.info(f"Redis connection: {redis_host}:{redis_port}/{redis_db}")
    logger.info(f"Listening on queue: {queue_name}")

    task_queue = mp.Queue(maxsize=args.workers * 2)

    workers = []
    for i in range(args.workers):
        worker = mp.Process(target=worker_process, args=(task_queue, db_conn, i, source_db_connection))
        worker.start()
        workers.append(worker)
        logger.info(f"Started worker {i} (PID: {worker.pid})")

    try:
        redis_listener(task_queue, redis_host, redis_port, redis_db, queue_name)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("Shutting down extraction service...")

        shutdown_event.set()

        for _ in workers:
            try:
                task_queue.put(None, timeout=1)
            except:
                pass

        for i, worker in enumerate(workers):
            logger.info(f"Waiting for worker {i} to finish...")
            worker.join(timeout=5)
            if worker.is_alive():
                logger.warning(f"Terminating worker {i}")
                worker.terminate()
                worker.join()

        logger.info("All workers shut down. Service stopped.")
