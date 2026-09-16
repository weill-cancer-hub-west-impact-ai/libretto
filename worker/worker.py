import argparse
import logging
import multiprocessing as mp
import os
import queue
import signal
import traceback
from typing import Dict, Any

from libretto.database import LLMExtractDatabase
from libretto.source_database import SourceDatabase, DEFAULT_NOTE_METADATA_QUERY, DEFAULT_NOTE_TEXT_QUERY
from libretto.types import project_environment, Patient, Note, NoteExtraction
from libretto.api_helper import setup_llm_api
from libretto.json_sanitize import convert_to_native_types

from libretto.noteextract.run import run_noteextract
from libretto.text_matching import get_extraction_citation
from libretto.prompt_only.run import run_prompt_only

# Global variables for graceful shutdown
shutdown_event = mp.Event()


def run_noteextract_and_store(
    db: LLMExtractDatabase,
    patient_data: list[Patient],
    spec_id: str,
    project_id,
    config: Dict[str, Any],
    cancel_check,
    on_note_processed=None,
) -> int:
    """
    Run extraction on a pre-loaded notes DataFrame and store results.

    Args:
        db: Database for storing results
        patient_data: List of Patient dictionaries to process
        spec_id: Extraction spec ID
        project_id: Project ID (may be None)
        config: Prepared extraction config
        cancel_check: Zero-argument callable; returns True if processing should stop
        on_note_processed: Optional callable(processed_count, total) called after each note is stored

    Returns:
        Number of notes processed before cancellation or completion
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    processed_count = 0
    total_notes = len(patient_data)
    if on_note_processed is not None:
        on_note_processed(0, total_notes)

    for patient in patient_data:
        if cancel_check():
            logger.info("Canceled, terminating loop")
            break

        extractions = run_noteextract(patient, config)

        logger.info("Extractions post processing: %s", extractions)
        db.insert_extractions(
            patient_id=patient["id"],
            spec_id=spec_id,
            extractions=convert_to_native_types(extractions),
            overwrite=False,
            project_id=project_id
        )

        if cancel_check():
            logger.info("Canceled, terminating loop")
            break
        processed_count += 1
        if on_note_processed is not None:
            on_note_processed(processed_count, total_notes)

    return processed_count

def run_prompt_only_and_store(
    db: LLMExtractDatabase,
    patient_data: list[Patient],
    spec_id: str,
    project_id,
    config: Dict[str, Any],
    cancel_check,
    on_note_processed=None,
) -> int:
    """
    Run prompt-only extraction on patient notes and store results.

    Args:
        db: Database for storing results
        patient_data: List of Patient dicts to process
        spec_id: Extraction spec ID
        project_id: Project ID (may be None)
        config: Prepared extraction config with 'prompt' and 'model_args'
        cancel_check: Zero-argument callable; returns True if processing should stop
        on_note_processed: Optional callable(processed_count, total) called after each patient is stored

    Returns:
        Number of patients processed before cancellation or completion
    """
    logger = logging.getLogger(__name__)
    processed_count = 0
    total_count = len(patient_data)

    project = db.get_project_by_id(project_id)
    model_id = config.get("model_args", {}).get("model_id") or os.getenv("EXTRACTION_MODEL_ID")
    prompt = config.get("prompt", "").strip()
    combine_notes = config.get("combine_notes", False)
    max_chunk_size = config.get("max_chunk_size", 100000)
    api = setup_llm_api(project, model_name=model_id)

    for patient in patient_data:
        if cancel_check():
            logger.info("Canceled, terminating loop")
            break

        extractions = run_prompt_only(patient, prompt, api, model_id=model_id,
                                      combine_notes=combine_notes, max_chunk_size=max_chunk_size)

        logger.info("Extractions post processing: %s", extractions)
        db.insert_extractions(
            patient_id=patient["id"],
            spec_id=spec_id,
            extractions=convert_to_native_types(extractions),
            overwrite=False,
            project_id=project_id
        )

        if cancel_check():
            logger.info("Canceled, terminating loop")
            break
        processed_count += 1
        if on_note_processed is not None:
            on_note_processed(processed_count, total_count)

    return processed_count


def process_extraction(db: LLMExtractDatabase, task_data: Dict[str, Any], source_db_connection: str) -> Dict[str, Any]:
    """
    Main extraction function that processes notes through specified extractor.
    This runs in worker processes.

    Args:
        db: Database for storing extraction results and task status
        task_data: {
            'task_id': str,
            'spec_id': str,
            'patient_ids': List[str]|None,
            'overwrite': bool (default False),
            'project_id': int (optional)
        }
        source_db_connection: Connection string for source database

    Returns:
        Dict with task results and statistics
    """
    logger = logging.getLogger(__name__)

    task_id = task_data['task_id']
    spec_id = task_data['spec_id']
    patient_ids = task_data.get('patient_ids')
    overwrite = task_data.get('overwrite', True)
    project_id = task_data.get('project_id')

    logger.info(f"Worker processing extraction task {task_id} with spec {spec_id} for project {project_id}")

    try:
        db.update_task_status(task_id, 'running')

        if not source_db_connection:
            raise ValueError("The project does not specify a source database and a default database is not configured")

        spec = db.get_spec_by_id(spec_id)
        if not spec:
            raise ValueError(f"Spec with ID {spec_id} not found")

        content = spec.get('content') or {}
        project = db.get_project_by_id(project_id)

        if overwrite:
            db.clear_existing_results(extraction_source=spec, patient_ids=patient_ids, project_id=project_id)

        print("Loading notes to extract from:", source_db_connection)
        source_db = SourceDatabase(source_db_connection)
        patient_data = source_db.get_notes({
            "source_notes": {
                "metadata": {
                    "query_string": project.get("note_metadata_query") or os.getenv("NOTE_METADATA_QUERY", DEFAULT_NOTE_METADATA_QUERY)
                },
                "note_text": {
                    "query_string": project.get("note_text_query") or os.getenv("NOTE_TEXT_QUERY", DEFAULT_NOTE_TEXT_QUERY)
                }
            }
        }, patient_ids=patient_ids)

        if not patient_data:
            logger.info(f"No patients found for task {task_id}")
            raise ValueError("No patients found for task")

        canceled = False

        def _should_cancel():
            nonlocal canceled
            current_task = db.get_task_status(task_id)
            if current_task and current_task.get('status') == 'canceled':
                logger.info(f"Task {task_id} was canceled")
                canceled = True
                return True
            if shutdown_event.is_set():
                logger.info(f"Task {task_id} interrupted by shutdown")
                db.update_task_status(task_id, 'canceled', status_message='Task canceled')
                canceled = True
                return True
            return False

        def _on_note_processed(processed_count, total):
            db.update_task_status(task_id, 'running', progress_current=processed_count, progress_total=total)

        if spec['executor'] == 'noteextract': executor = run_noteextract_and_store
        elif spec['executor'] == 'prompt_only': executor = run_prompt_only_and_store
        else: raise ValueError(f"Unsupported executor '{spec['executor']}'")

        processed_count = executor(
            db=db,
            patient_data=patient_data,
            spec_id=spec_id,
            project_id=project_id,
            config=content,
            cancel_check=_should_cancel,
            on_note_processed=_on_note_processed,
        )

        if canceled:
            return {'task_id': task_id, 'status': 'canceled'}

        final_status = 'completed'
        status_message = f'Processed all notes successfully'

        db.update_task_status(task_id, final_status, progress_current=processed_count, status_message=status_message)

        logger.info(f"Completed task {task_id}: {status_message}")
        return {'task_id': task_id, 'status': final_status, 'processed_count': processed_count}

    except KeyboardInterrupt as e:
        # Check if this was a cancellation or a general interruption
        current_task = db.get_task_status(task_id)
        if current_task and current_task.get('status') == 'canceled':
            # This was a user cancellation - task status already set to 'canceled'
            logger.info(f"Task {task_id} was canceled by user")
            return {'task_id': task_id, 'status': 'canceled'}
        else:
            # This was a general interruption (e.g., Ctrl+C)
            error_msg = f"Task interrupted: {str(e)}"
            db.update_task_status(task_id, 'canceled', error_message=error_msg)
            raise

    except Exception as e:
        # Handle task failure
        error_msg = f"Task failed: {str(e)}\n{traceback.format_exc()}"
        logger.error(f"Task {task_id} failed: {error_msg}")
        db.update_task_status(task_id, 'failed', error_message=error_msg)
        raise

def worker_process(task_queue: mp.Queue, database_conn: str, worker_id: int, source_db_connection: str):
    """
    Worker process function that processes tasks from the queue.

    Args:
        task_queue: Multiprocessing queue containing task data
        database_conn: Connection string for the extraction results database
        worker_id: Unique identifier for this worker
        source_db_connection: Connection string for source database to retrieve patients and notes
    """
    logger = logging.getLogger()
    logger.info(f"Worker {worker_id} started")

    db = LLMExtractDatabase(database_conn, enable_wal=True)

    try:
        while not shutdown_event.is_set():
            try:
                # Get task from queue with timeout
                task_data = task_queue.get(timeout=1.0)

                if task_data is None:  # Poison pill to shutdown
                    logger.info(f"Worker {worker_id} received shutdown signal")
                    break

                logger.info(f"Worker {worker_id} processing task {task_data.get('task_id')}")

                # Process the task
                project = None
                if project_id := task_data.get("project_id"):
                    project = db.get_project_by_id(project_id)
                    if not project:
                        raise ValueError(f"Project with ID {project_id} not found")
                if project is not None:
                    with project_environment(project):
                        result = process_extraction(db, task_data, project.get("source_connection", source_db_connection))
                else:
                    result = process_extraction(db, task_data, source_db_connection)
                logger.info(f"Worker {worker_id} completed task {result['task_id']}")

            except queue.Empty:
                # No task available, continue loop
                continue
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {str(e)}\n{traceback.format_exc()}")

    except KeyboardInterrupt:
        logger.info(f"Worker {worker_id} interrupted")
    finally:
        db.close()
        logger.info(f"Worker {worker_id} shutting down")

